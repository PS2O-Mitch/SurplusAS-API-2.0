"""Anchor-price lookup against `reference_prices` (Cloud SQL Postgres).

Postgres-only adaptation of `surplusAS-pricing-intel/pricing_engine/
anchors.py` — the upstream version supports a SQLite dialect for dev;
this one drops it because the deployed Pricing Service only ever talks
to Cloud SQL via `shared.db.acquire`.

Selection rules (mirrored verbatim from upstream — keep them in sync):

1. Region fallback: `US-FL-Hillsborough` → `US-FL` → `US`.
2. Per-category source preference. Restaurants take Apify, grocery takes
   OFF, USDA wholesale only as last resort with category-specific markup.
3. Tier preference: caller may hint a restaurant tier; we prefer that
   exact match, otherwise we take the highest sample-count row.
"""

from __future__ import annotations

import logging

import asyncpg
from pydantic import BaseModel

logger = logging.getLogger("surplusas.pricing.engine.anchors")

SOURCE_PREFERENCE: dict[str, tuple[str, ...]] = {
    "produce": ("off", "usda"),
    "dairy": ("off", "usda"),
    "packaged_goods": ("off",),
    "frozen": ("off",),
    "mixed_bag": ("off",),
    "prepared_meal": ("apify",),
    "bakery": ("apify",),
    "beverage": ("apify",),
    "deli": ("apify",),
}

WHOLESALE_TO_RETAIL_MULTIPLIER: dict[str, float] = {
    "produce": 2.0,
    "dairy": 1.5,
}
_DEFAULT_WHOLESALE_MARKUP = 1.75


class Anchor(BaseModel):
    p25: float
    p50: float
    p75: float
    source: str
    region: str
    tier: str | None
    sample_count: int
    wholesale_markup_applied: float | None = None


def region_fallback_chain(region: str) -> list[str]:
    parts = region.split("-")
    return ["-".join(parts[:n]) for n in range(len(parts), 0, -1)]


def _markup_for(category: str) -> float:
    return WHOLESALE_TO_RETAIL_MULTIPLIER.get(category, _DEFAULT_WHOLESALE_MARKUP)


async def _fetch_rows(
    conn: asyncpg.Connection,
    *,
    category: str,
    region: str,
    sources: tuple[str, ...],
) -> list[dict]:
    if not sources:
        return []
    sql = (
        "SELECT category, region, tier, source, p25, p50, p75, sample_count "
        "FROM reference_prices "
        "WHERE category = $1 AND region = $2 AND source = ANY($3::text[])"
    )
    rows = await conn.fetch(sql, category, region, list(sources))
    return [dict(r) for r in rows]


def _pick_best(
    rows: list[dict],
    *,
    source_pref: tuple[str, ...],
    tier_hint: str | None,
) -> dict | None:
    if not rows:
        return None
    pref_index = {s: i for i, s in enumerate(source_pref)}

    def score(r: dict) -> tuple[int, int, int]:
        src_rank = pref_index.get(r["source"], len(source_pref))
        tier_rank = 0 if (tier_hint and r.get("tier") == tier_hint) else 1
        return (src_rank, tier_rank, -int(r.get("sample_count") or 0))

    return min(rows, key=score)


async def lookup_anchor(
    conn: asyncpg.Connection,
    *,
    category: str,
    region: str,
    tier: str | None = None,
) -> Anchor | None:
    sources = SOURCE_PREFERENCE.get(category, ())
    if not sources:
        logger.warning("anchors.no_source_preference category=%s", category)
        return None

    for candidate_region in region_fallback_chain(region):
        rows = await _fetch_rows(
            conn, category=category, region=candidate_region, sources=sources
        )
        best = _pick_best(rows, source_pref=sources, tier_hint=tier)
        if best is None:
            continue

        markup: float | None = None
        p25, p50, p75 = float(best["p25"]), float(best["p50"]), float(best["p75"])
        if best["source"] == "usda" and (best.get("tier") or "") == "wholesale":
            markup = _markup_for(category)
            p25, p50, p75 = p25 * markup, p50 * markup, p75 * markup

        logger.info(
            "anchors.resolved category=%s region=%s→%s source=%s tier=%s markup=%s",
            category, region, candidate_region, best["source"], best.get("tier"), markup,
        )
        return Anchor(
            p25=p25,
            p50=p50,
            p75=p75,
            source=best["source"],
            region=candidate_region,
            tier=best.get("tier"),
            sample_count=int(best["sample_count"]),
            wholesale_markup_applied=markup,
        )

    logger.warning(
        "anchors.no_row category=%s region=%s chain=%s",
        category, region, region_fallback_chain(region),
    )
    return None
