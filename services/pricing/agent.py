"""SurplusAS Pricing Service — deterministic formula on a real-data anchor.

Phase 2 rewire: the LLM-end-to-end pricing approach is replaced by the
deterministic `pricing_engine.formula.recommend()` (vendored under
`services/pricing/engine/`) running against the
`reference_prices` corpus and the latest `pricing_coefficients` row.

Flow:
  1. Parse the merchant input into a structured `PricingInput` (category,
     region, retail_value, expiry, units, now_hour). The freeform shape
     used by smoke tests and the listing pipeline is `key: value` lines,
     so a regex parser is enough — no LLM call needed at this edge.
  2. Look up the anchor row from `reference_prices` (region fallback +
     source-aware preference).
  3. Load the latest `pricing_coefficients` row for the cell.
  4. Run `recommend()`.
  5. Compose the `pricing_optimize` response shape, with the formula's
     `applied_pressures` audit trail attached.

Per guardrail #2 in the pricing-intel CLAUDE.md, every response must be
auditable from `applied_pressures` + `formula_version` + `anchor_p50`
alone — those three fields are surfaced as top-level keys.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from shared import db
from shared.config import AGENT_VERSION, PRICING_MODEL

from .engine.anchors import lookup_anchor
from .engine.coefficients import load_latest
from .engine.formula import recommend
from .engine.schemas import VALID_CATEGORIES, PricingInput

logger = logging.getLogger("surplusas.pricing.agent")

# Smoke-test inputs come in three flavours: `key: value` line text, JSON
# dicts (when the listing pipeline marshalls a structured listing), and
# free-form merchant prose. The line/JSON paths cover everything we ship
# today; prose falls back to keyword sniffing for category and a default
# expiry. Phase 2.5 can add an LLM parse step here if the prose case
# starts producing bad anchors.

_KV_LINE_RE = re.compile(r"^\s*([a-z_]+)\s*[:=]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_HOUR_OF_DAY_RE = re.compile(r"\b(\d{1,2})\s*(AM|PM|am|pm)\b")

# Very-fresh default if we can't figure out an expiry — bias toward
# small-discount territory rather than over-discounting blind.
_DEFAULT_HOURS_UNTIL_EXPIRY = 12.0


def _parse_kv_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _KV_LINE_RE.finditer(text):
        key, value = m.group(1).lower().strip(), m.group(2).strip()
        out[key] = value
    return out


def _parse_json_dict(text: str) -> dict | None:
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def _first_number(text: str) -> float | None:
    m = _NUMBER_RE.search(text)
    return float(m.group(0)) if m else None


def _hours_until_pickup_close(text: str, now_hour: int) -> float | None:
    """Estimate hours from now until a `closes 5 PM today`-style cutoff.

    Returns None if the text doesn't look like a wall-clock time. Same-day
    times in the past are treated as "tomorrow at that time".
    """
    m = _HOUR_OF_DAY_RE.search(text)
    if not m:
        return None
    h = int(m.group(1)) % 12
    if m.group(2).upper() == "PM":
        h += 12
    delta = h - now_hour
    if delta <= 0:
        delta += 24
    return float(delta)


def _category_from_text(text: str) -> str | None:
    lower = text.lower()
    for c in VALID_CATEGORIES:
        if c in lower:
            return c
    return None


def _build_pricing_input(
    user_input: str,
    partner_context: dict | None,
) -> tuple[PricingInput | None, dict[str, str]]:
    """Best-effort parse → (PricingInput | None, raw fields).

    Returns the parsed fields alongside the input so the response can
    include them in `reasoning` even when the formula can't run.
    """
    raw = _parse_json_dict(user_input) or {}
    if not raw:
        # Coerce kv-line values to strings so the rest of this function
        # can stay type-stable.
        raw = {k: v for k, v in _parse_kv_lines(user_input).items()}

    pctx = partner_context or {}
    region = (
        raw.get("region")
        or pctx.get("regulatory_region")
        or "US"
    )
    category = (raw.get("category") or "").lower().strip()
    if category not in VALID_CATEGORIES:
        category = _category_from_text(user_input) or ""

    retail_raw = raw.get("retail_value") or raw.get("estimated_retail_value")
    retail_value = (
        _first_number(str(retail_raw)) if retail_raw is not None
        else _first_number(user_input)
    )

    units_raw = raw.get("units") or raw.get("quantity") or "1"
    units = int(_first_number(str(units_raw)) or 1)

    now = datetime.now(timezone.utc)
    now_hour = now.hour

    pickup_text = str(raw.get("pickup_window") or raw.get("expiry") or user_input)
    hours = (
        _first_number(str(raw.get("hours_until_expiry"))) if raw.get("hours_until_expiry")
        else _hours_until_pickup_close(pickup_text, now_hour)
    )
    if hours is None:
        hours = _DEFAULT_HOURS_UNTIL_EXPIRY

    floor_pct = 0.10
    discount_range = pctx.get("discount_range") or {}
    if discount_range.get("min") is not None:
        # `discount_range.min` is the *minimum* discount the merchant
        # wants applied; the merchant floor is what's left of retail
        # after that minimum, expressed as a fraction.
        floor_pct = max(0.0, min(1.0, 1.0 - (float(discount_range["min"]) / 100.0)))
        # Clamp: a 70% min discount → 0.30 floor, not 0.0.
        floor_pct = max(floor_pct, 0.05)

    if not category or retail_value is None or retail_value <= 0:
        return None, raw

    try:
        return (
            PricingInput(
                category=category,
                region=region,
                units=max(1, units),
                retail_value=float(retail_value),
                hours_until_expiry=float(hours),
                now_hour=int(now_hour),
                merchant_floor_pct=floor_pct,
            ),
            raw,
        )
    except ValueError as exc:
        logger.warning("pricing.parse_failed error=%s raw=%s", exc, raw)
        return None, raw


def _urgency_from_hours(hours: float) -> str:
    if hours <= 1:
        return "critical"
    if hours <= 3:
        return "high"
    if hours <= 12:
        return "medium"
    return "low"


def _magnitude_from_delta(current_pct: int, recommended_pct: int) -> str:
    delta = abs(recommended_pct - current_pct)
    if delta <= 2:
        return "no_change"
    if delta <= 8:
        return "minor"
    if delta <= 20:
        return "moderate"
    return "significant"


def _reasoning_from_pressures(rec, anchor_p50: float, retail_value: float) -> str:
    """Deterministic rationale string built from the audit trail.

    Phase 2.5 may swap this for an LLM-rendered version; for now an
    explicit human-readable summary keeps the response auditable without
    a second model call.
    """
    p = rec.applied_pressures
    parts = [
        f"Anchor p50 ${anchor_p50:.2f} from {rec.anchor_source} ({rec.anchor_region}).",
        f"Pressures: base={p.base:+.2f}, expiry={p.expiry:+.2f}, "
        f"inventory={p.inventory:+.2f}, time_of_day={p.time_of_day:+.2f}, "
        f"floor={-p.merchant_floor:+.2f}.",
        f"Recommended ${rec.recommended_price:.2f} vs retail ${retail_value:.2f} "
        f"({rec.recommended_discount_pct * 100:.0f}% off).",
    ]
    if p.clamped_to_floor:
        parts.append("Clamped up to merchant floor.")
    if p.clamped_to_retail:
        parts.append("Clamped down to retail value.")
    return " ".join(parts)


def _server_overwrites() -> dict:
    return {
        "agent_version": AGENT_VERSION,
        "model_used": "pricing_engine/" + "v1",  # formula version
        "inference_timestamp": datetime.now(timezone.utc).isoformat(),
        "tokens_consumed": 0,
    }


def _fallback_recommendation(
    *,
    inp: PricingInput,
    reason: str,
) -> dict:
    """No anchor or coeffs in DB — last-resort flat-rate discount.

    Returns the same response shape as a real recommendation but flags
    `_grounding_used: false` and notes the fallback in `reasoning`. We'd
    rather respond conservatively than 502 the caller.
    """
    fallback_discount = 0.30  # conservative blend of seed base discounts
    price = round(inp.retail_value * (1.0 - fallback_discount) * 4) / 4
    return {
        "mode": "pricing_optimize",
        "current_discount_pct": 0,
        "recommended_discount_pct": int(round(fallback_discount * 100)),
        "recommended_price": price,
        "reasoning": (
            f"Fallback: {reason}. Applied flat {int(fallback_discount * 100)}% "
            f"discount on retail ${inp.retail_value:.2f}."
        ),
        "urgency_level": _urgency_from_hours(inp.hours_until_expiry),
        "price_change_magnitude": "moderate",
        "anchor_p50": None,
        "anchor_source": None,
        "anchor_region": None,
        "applied_pressures": None,
        "formula_version": "v1",
        "_grounding_used": False,
        "outcome_tracking": _server_overwrites(),
    }


async def run_pricing_optimize(
    user_input: str,
    partner_context: dict | None = None,
    user_id: str = "anonymous",
) -> dict:
    """Public entrypoint, called from `services/pricing/api.py`.

    `user_id` is accepted for signature compatibility with the previous
    LLM-based agent but unused — the formula is deterministic.
    """
    del user_id  # intentionally unused

    inp, raw_fields = _build_pricing_input(user_input, partner_context)
    if inp is None:
        # Couldn't even parse out a category + retail. Hand back a
        # zero-confidence response rather than fabricate one.
        return {
            "mode": "pricing_optimize",
            "current_discount_pct": 0,
            "recommended_discount_pct": 0,
            "recommended_price": 0.0,
            "reasoning": (
                "Insufficient input: could not extract category and retail_value "
                "from request. Provide structured fields or include them in the "
                "merchant text."
            ),
            "urgency_level": "low",
            "price_change_magnitude": "no_change",
            "anchor_p50": None,
            "anchor_source": None,
            "anchor_region": None,
            "applied_pressures": None,
            "formula_version": "v1",
            "_grounding_used": False,
            "outcome_tracking": _server_overwrites(),
        }

    current_discount_pct_raw = raw_fields.get("discount_pct") or raw_fields.get(
        "current_discount_pct"
    )
    current_discount_pct = (
        int(_first_number(str(current_discount_pct_raw)) or 0)
        if current_discount_pct_raw
        else 0
    )

    async with db.acquire() as conn:
        anchor = await lookup_anchor(
            conn, category=inp.category, region=inp.region
        )
        if anchor is None:
            return _fallback_recommendation(
                inp=inp,
                reason=f"no reference_prices anchor for ({inp.category}, {inp.region})",
            )

        coeffs = await load_latest(
            conn, category=inp.category, region=inp.region
        )
        if coeffs is None:
            return _fallback_recommendation(
                inp=inp,
                reason=f"no pricing_coefficients seed for ({inp.category}, {inp.region})",
            )

    rec = recommend(
        inp=inp,
        coeffs=coeffs,
        anchor_p50=anchor.p50,
        anchor_source=anchor.source,
        anchor_region=anchor.region,
    )

    recommended_pct_int = int(round(rec.recommended_discount_pct * 100))
    recommended_pct_int = max(0, min(100, recommended_pct_int))

    response = {
        "mode": "pricing_optimize",
        "current_discount_pct": current_discount_pct,
        "recommended_discount_pct": recommended_pct_int,
        "recommended_price": rec.recommended_price,
        "reasoning": _reasoning_from_pressures(rec, anchor.p50, inp.retail_value),
        "urgency_level": _urgency_from_hours(inp.hours_until_expiry),
        "price_change_magnitude": _magnitude_from_delta(
            current_discount_pct, recommended_pct_int
        ),
        # Audit-trail fields — required by guardrail #2.
        "anchor_p50": rec.anchor_p50,
        "anchor_source": rec.anchor_source,
        "anchor_region": rec.anchor_region,
        "applied_pressures": rec.applied_pressures.model_dump(),
        "formula_version": rec.formula_version,
        "_grounding_used": True,
        "outcome_tracking": _server_overwrites(),
    }
    # Keep the legacy server-overwrite field that previously carried the
    # Vertex model id so existing telemetry doesn't lose a column.
    response["outcome_tracking"]["model_used"] = (
        f"pricing_engine/{rec.formula_version} (was {PRICING_MODEL})"
    )
    return response
