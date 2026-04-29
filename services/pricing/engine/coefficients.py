"""Coefficient loader against `pricing_coefficients` (Cloud SQL Postgres).

Postgres-only adaptation of `surplusAS-pricing-intel/pricing_engine/
coefficients.py`. Reads the latest version per (category, region) with a
10-minute in-process cache (matches the design doc; refresh cadence
matters here because Phase 3 will append new versioned rows nightly and
production needs to pick them up without a redeploy).

Region fallback mirrors `anchors`: county → state → country.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import asyncpg

from .anchors import region_fallback_chain
from .schemas import Coefficients, PiecewiseCurve

logger = logging.getLogger("surplusas.pricing.engine.coefficients")

CACHE_TTL_SECONDS = 600


@dataclass
class _CacheEntry:
    coeffs: Coefficients | None
    fetched_at: float


_cache: dict[tuple[str, str], _CacheEntry] = {}


def _parse_curve(raw: Any) -> PiecewiseCurve:
    """JSONB on Postgres comes back as a Python object via asyncpg unless a
    codec sets it to str. Handle both.
    """
    if isinstance(raw, str):
        raw = json.loads(raw)
    return PiecewiseCurve.model_validate(raw)


def _row_to_coefficients(row: dict[str, Any]) -> Coefficients:
    return Coefficients(
        category=row["category"],
        region=row["region"],
        version=int(row["version"]),
        base_discount=float(row["base_discount"]),
        expiry_curve=_parse_curve(row["expiry_curve"]),
        inventory_curve=_parse_curve(row["inventory_curve"]),
        time_of_day_curve=_parse_curve(row["time_of_day_curve"]),
        source=row["source"],
    )


async def _fetch_latest_for(
    conn: asyncpg.Connection,
    *,
    category: str,
    region: str,
) -> dict[str, Any] | None:
    sql = (
        "SELECT category, region, version, base_discount, expiry_curve, "
        "       inventory_curve, time_of_day_curve, source "
        "FROM pricing_coefficients "
        "WHERE category = $1 AND region = $2 "
        "ORDER BY effective_at DESC "
        "LIMIT 1"
    )
    row = await conn.fetchrow(sql, category, region)
    return dict(row) if row else None


async def load_latest(
    conn: asyncpg.Connection,
    *,
    category: str,
    region: str,
    use_cache: bool = True,
) -> Coefficients | None:
    key = (category, region)
    now = time.monotonic()
    if use_cache:
        entry = _cache.get(key)
        if entry is not None and (now - entry.fetched_at) < CACHE_TTL_SECONDS:
            return entry.coeffs

    for candidate_region in region_fallback_chain(region):
        row = await _fetch_latest_for(conn, category=category, region=candidate_region)
        if row is None:
            continue
        coeffs = _row_to_coefficients(row)
        _cache[key] = _CacheEntry(coeffs=coeffs, fetched_at=now)
        logger.info(
            "coefficients.resolved category=%s region=%s→%s version=%d source=%s",
            category, region, candidate_region, coeffs.version, coeffs.source,
        )
        return coeffs

    _cache[key] = _CacheEntry(coeffs=None, fetched_at=now)
    logger.warning(
        "coefficients.no_row category=%s region=%s chain=%s",
        category, region, region_fallback_chain(region),
    )
    return None


def clear_cache() -> None:
    _cache.clear()
