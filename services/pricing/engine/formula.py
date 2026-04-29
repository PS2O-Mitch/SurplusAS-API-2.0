"""Deterministic pricing formula — pure-Python, no LLM, no DB.

The math, verbatim from `surplusAS-Intelligence-Reference.md`:

    discount = base[category]
             + expiry_pressure(hours_until_expiry)
             + inventory_pressure(units)
             + time_of_day_pressure(now_hour)
             - merchant_floor_pct
    price = clamp( anchor × (1 − discount), merchant_floor, retail )

`merchant_floor_pct` subtracts so a partner with a higher floor naturally
gets a smaller total discount; the final clamp on price (not on
discount) is what actually enforces the dollar floor.

Every term lands in `Recommendation.applied_pressures`, which is the
audit trail required by guardrail #2 — a reviewer must be able to
reconstruct the price from the map alone.
"""

from __future__ import annotations

from .schemas import (
    FORMULA_VERSION,
    AppliedPressures,
    Coefficients,
    PricingInput,
    Recommendation,
)


def recommend(
    *,
    inp: PricingInput,
    coeffs: Coefficients,
    anchor_p50: float,
    anchor_source: str,
    anchor_region: str,
) -> Recommendation:
    """Return a deterministic price recommendation with full audit trail.

    Caller is expected to have already resolved the anchor row (with
    region fallback + source-aware preference handled in `anchors.py`)
    and the coefficient row (`coefficients.load_latest()`). This keeps
    the formula itself pure and trivially unit-testable.
    """
    base = coeffs.base_discount
    expiry = coeffs.expiry_curve.at(inp.hours_until_expiry)
    inventory = coeffs.inventory_curve.at(inp.units)
    time_of_day = coeffs.time_of_day_curve.at(inp.now_hour)
    floor = inp.merchant_floor_pct

    total_discount = base + expiry + inventory + time_of_day - floor
    raw_price = anchor_p50 * (1.0 - total_discount)

    floor_price = inp.retail_value * floor
    clamped_to_floor = raw_price < floor_price
    clamped_to_retail = raw_price > inp.retail_value

    if clamped_to_floor:
        price = floor_price
    elif clamped_to_retail:
        price = inp.retail_value
    else:
        price = raw_price

    # Quarter-dollar rounding mirrors the existing API-2.0 pricing service
    # (`_apply_server_overwrites` in services/pricing/agent.py). Keeping
    # the same convention so the rewire is a drop-in.
    price = round(price * 4) / 4

    effective_discount_pct = (1.0 - price / inp.retail_value) if inp.retail_value > 0 else 0.0

    return Recommendation(
        recommended_price=price,
        recommended_discount_pct=effective_discount_pct,
        anchor_p50=anchor_p50,
        anchor_source=anchor_source,
        anchor_region=anchor_region,
        applied_pressures=AppliedPressures(
            base=base,
            expiry=expiry,
            inventory=inventory,
            time_of_day=time_of_day,
            merchant_floor=floor,
            clamped_to_floor=clamped_to_floor,
            clamped_to_retail=clamped_to_retail,
        ),
        formula_version=FORMULA_VERSION,
    )
