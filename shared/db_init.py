"""Initialize the SurplusAS Postgres schema and seed the demo partner key.

Idempotent. Run from repo root:
    .venv\\Scripts\\python.exe -m shared.db_init
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from . import config  # noqa: F401  (loads .env, sets Vertex AI env defaults)
from .db import acquire, close_pool


SCHEMA_PATH = Path(__file__).resolve().parent / "db_schema.sql"


async def main() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    print(f"Applying schema from {SCHEMA_PATH.name} ...")
    async with acquire() as conn:
        await conn.execute(schema_sql)
    print("Schema applied.")

    # Seed the demo partner key from config.SURPLUSAS_API_KEY.
    demo_key = config.SURPLUSAS_API_KEY
    demo_ctx = config.DEFAULT_PARTNER_CONTEXT

    upsert_sql = """
        INSERT INTO partner_keys (api_key, partner_id, partner_name, context_json)
        VALUES ($1, $2, $3, $4::jsonb)
        ON CONFLICT (api_key) DO UPDATE
            SET partner_id = EXCLUDED.partner_id,
                partner_name = EXCLUDED.partner_name,
                context_json = EXCLUDED.context_json
    """
    async with acquire() as conn:
        await conn.execute(
            upsert_sql,
            demo_key,
            demo_ctx["partner_id"],
            demo_ctx["partner_name"],
            json.dumps(demo_ctx),
        )
    print(f"Demo partner key seeded: {demo_key} -> {demo_ctx['partner_name']!r}")

    async with acquire() as conn:
        rows = await conn.fetch(
            "SELECT api_key, partner_id, partner_name FROM partner_keys"
        )
    print(f"\npartner_keys ({len(rows)} rows):")
    for r in rows:
        print(f"  {r['api_key']}  ->  {r['partner_id']} / {r['partner_name']}")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
