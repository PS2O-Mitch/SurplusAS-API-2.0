"""Seed `historical_sales` with synthetic rows so the Pricing Service has
something to ground on at first launch.

Run from repo root:
    .venv\\Scripts\\python.exe -m shared.seed_historical_sales

Idempotent: deletes prior demo rows (partner_id='demo_001') before insert.
Real partner sales rows are untouched.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from . import config  # noqa: F401  (loads .env)
from .db import acquire, close_pool


# Per-category retail price ranges and typical end-of-day discount (rough).
CATEGORIES = {
    "bakery":         (5.0, 25.0, (0.30, 0.50)),
    "prepared_meal":  (8.0, 18.0, (0.40, 0.60)),
    "produce":        (3.0, 20.0, (0.30, 0.50)),
    "dairy":          (4.0, 15.0, (0.30, 0.40)),
    "deli":           (6.0, 22.0, (0.30, 0.50)),
    "packaged_goods": (3.0, 15.0, (0.20, 0.35)),
    "frozen":         (5.0, 20.0, (0.20, 0.40)),
    "beverage":       (2.0, 10.0, (0.20, 0.40)),
    "mixed_bag":      (8.0, 25.0, (0.40, 0.55)),
}

# Hours when each category tends to clear surplus, weighted heavier.
PEAK_HOURS = {
    "bakery":         [16, 17, 18, 19, 11, 12],
    "prepared_meal":  [13, 14, 15, 19, 20, 21],
    "produce":        [16, 17, 18, 19, 20],
    "dairy":          [17, 18, 19, 20],
    "deli":           [13, 14, 15, 18, 19],
    "packaged_goods": [14, 15, 16, 17, 18],
    "frozen":         [15, 16, 17, 18, 19],
    "beverage":       [12, 13, 17, 18, 19],
    "mixed_bag":      [17, 18, 19, 20, 21],
}

ROWS_PER_CATEGORY = 12  # 9 categories * 12 rows ~= 108 rows total


async def main() -> None:
    rng = random.Random(1729)
    now = datetime.now(timezone.utc)

    rows: list[tuple] = []
    for cat, (low, high, (dmin, dmax)) in CATEGORIES.items():
        for _ in range(ROWS_PER_CATEGORY):
            retail = round(rng.uniform(low, high) * 4) / 4
            discount = rng.uniform(dmin, dmax)
            sold_price = round(retail * (1 - discount) * 4) / 4
            sold_at = now - timedelta(
                days=rng.randint(1, 90),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )
            hour = rng.choice(PEAK_HOURS[cat])
            sold_at = sold_at.replace(hour=hour)
            rows.append((
                "demo_001",                    # partner_id
                f"req_SEED{rng.randrange(0xFFFF):04X}",
                cat,                            # category
                None,                           # items_json (skip for synthetic)
                sold_price,
                retail,
                sold_at.weekday(),              # day_of_week (0-6)
                hour,                           # hour_of_day
                sold_at,                        # sold_at
            ))

    print(f"Seeding {len(rows)} synthetic historical_sales rows ...")

    async with acquire() as conn:
        await conn.execute(
            "DELETE FROM historical_sales WHERE partner_id = $1",
            "demo_001",
        )
        await conn.executemany(
            """
            INSERT INTO historical_sales
                (partner_id, listing_id, category, items_json, sold_price,
                 retail_value, day_of_week, hour_of_day, sold_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            rows,
        )

        result = await conn.fetch(
            """
            SELECT category, COUNT(*) AS n,
                   ROUND(AVG(sold_price)::numeric, 2) AS avg_sold,
                   ROUND(AVG(retail_value)::numeric, 2) AS avg_retail
            FROM historical_sales
            WHERE partner_id = 'demo_001'
            GROUP BY category
            ORDER BY category
            """
        )

    print("\nSeed summary:")
    print(f"  {'category':<16} {'n':>4} {'avg_sold':>10} {'avg_retail':>12}")
    for r in result:
        print(f"  {r['category']:<16} {r['n']:>4} {r['avg_sold']:>10} {r['avg_retail']:>12}")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
