"""Pricing grounding — query `historical_sales` and shape a small
context block the model can use to anchor its discount recommendation.

Kept simple on purpose: a few aggregations are far more useful for an
LLM than 500 raw rows. If we need more sophistication (Vertex AI Search
over per-store sales, RAG over partner-specific demand cohorts), the
seam is here.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from shared import db


_VALID_CATEGORIES = frozenset({
    "produce", "prepared_meal", "bakery", "dairy", "beverage",
    "packaged_goods", "deli", "frozen", "mixed_bag",
})

# Matches `category: bakery` or `"category": "bakery"` style lines.
_CATEGORY_LINE_RE = re.compile(r'"?category"?\s*[:=]\s*"?([a-z_]+)"?', re.IGNORECASE)


async def grounding_for(category: str | None) -> str:
    """Return a multi-line grounding context for the given category."""
    if not category:
        return "(no category provided — pricing without grounding)"

    rows = await db.historical_sales_for_category(category, limit=80)
    if not rows:
        return f"(no historical sales for category={category!r}; using model defaults)"

    prices = [float(r["sold_price"]) for r in rows if r.get("sold_price") is not None]
    retails = [float(r["retail_value"]) for r in rows if r.get("retail_value") is not None]
    if not prices:
        return f"(category={category!r}: {len(rows)} rows but no sold_price values)"

    avg_sold = sum(prices) / len(prices)
    avg_retail = sum(retails) / len(retails) if retails else 0.0
    discount_pct = (1 - avg_sold / avg_retail) * 100 if avg_retail > 0 else 0.0

    hour_counter = Counter(int(r["hour_of_day"]) for r in rows if r.get("hour_of_day") is not None)
    top_hours = ", ".join(f"{h:02d}:00 (n={n})" for h, n in hour_counter.most_common(3))

    dow_counter = Counter(int(r["day_of_week"]) for r in rows if r.get("day_of_week") is not None)
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    top_dows = ", ".join(f"{dow_names[d]} (n={n})" for d, n in dow_counter.most_common(3))

    return (
        f"=== HISTORICAL SALES GROUNDING (category={category}, samples={len(rows)}) ===\n"
        f"- Mean sold price: ${avg_sold:.2f}\n"
        f"- Mean retail value: ${avg_retail:.2f}\n"
        f"- Mean effective discount: {discount_pct:.0f}%\n"
        f"- Peak sale hours: {top_hours or 'n/a'}\n"
        f"- Peak sale days: {top_dows or 'n/a'}\n"
        f"=== END GROUNDING ==="
    )


def category_from_input(user_input: str) -> str | None:
    """Best-effort extract of `category` from a listing description.

    Tries three strategies in order:
      1. Parse as JSON and read the `category` field.
      2. Regex-match a `category: <value>` line in plain text (e.g.
         the listing-summary text the workflow pipeline sends).
      3. Scan the text for any whitelisted category keyword.
    """
    if not user_input:
        return None

    try:
        obj = json.loads(user_input)
        if isinstance(obj, dict):
            cat = obj.get("category")
            if isinstance(cat, str) and cat:
                normalized = cat.lower().strip()
                if normalized in _VALID_CATEGORIES:
                    return normalized
    except (json.JSONDecodeError, TypeError):
        pass

    match = _CATEGORY_LINE_RE.search(user_input)
    if match:
        normalized = match.group(1).lower().strip()
        if normalized in _VALID_CATEGORIES:
            return normalized

    lower = user_input.lower()
    for cat in _VALID_CATEGORIES:
        if cat in lower:
            return cat

    return None
