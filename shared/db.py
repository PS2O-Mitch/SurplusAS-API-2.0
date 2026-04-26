"""Cloud SQL Postgres access via the Cloud SQL Python Connector.

Uses ADC locally (mitch@ps2o.org) and the attached service account on Cloud
Run. Connections are pooled by asyncpg with the connector handling
authentication and TLS — no separate cloud-sql-proxy process required.

Env vars required:
    CLOUD_SQL_INSTANCE   ps2o-surplusas-api:us-central1:surplusas-db
    DB_NAME              surplusas
    DB_USER              surplusas_app
    DB_PASSWORD          (from Secret Manager / .env)
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import asyncpg
from google.cloud.sql.connector import Connector, IPTypes, create_async_connector

logger = logging.getLogger("surplusas.db")


# Singleton connector + pool for the lifetime of the process.
_connector: Connector | None = None
_pool: asyncpg.Pool | None = None


def _required(env: str) -> str:
    val = os.environ.get(env)
    if not val:
        raise RuntimeError(f"Required env var {env!r} is not set")
    return val


async def _open_pool() -> asyncpg.Pool:
    """Create the asyncpg pool, routing through the Cloud SQL connector."""
    global _connector
    if _connector is None:
        _connector = await create_async_connector()

    instance = _required("CLOUD_SQL_INSTANCE")
    db_name = _required("DB_NAME")
    db_user = _required("DB_USER")
    db_password = _required("DB_PASSWORD")
    ip_type = IPTypes.PRIVATE if os.environ.get("DB_PRIVATE_IP") == "true" else IPTypes.PUBLIC

    async def get_conn(*_args, **_kwargs) -> asyncpg.Connection:
        # asyncpg's pool may pass a `loop=` kwarg; the connector doesn't take
        # one, so ignore extras.
        return await _connector.connect_async(
            instance,
            "asyncpg",
            user=db_user,
            password=db_password,
            db=db_name,
            ip_type=ip_type,
        )

    pool = await asyncpg.create_pool(
        connect=get_conn,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )
    logger.info("Cloud SQL pool opened (instance=%s db=%s user=%s)", instance, db_name, db_user)
    return pool


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await _open_pool()
    return _pool


async def close_pool() -> None:
    """Close the pool and the connector. Call on app shutdown."""
    global _pool, _connector
    if _pool is not None:
        await _pool.close()
        _pool = None
    if _connector is not None:
        await _connector.close_async()
        _connector = None


@asynccontextmanager
async def acquire() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection from the pool. Used as `async with acquire() as conn:`."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Partner keys queries
# ---------------------------------------------------------------------------
async def fetch_partner_by_key(api_key: str) -> dict | None:
    """Look up a partner by their bearer token. Returns None if not found."""
    sql = """
        SELECT api_key, partner_id, partner_name, context_json, created_at
        FROM partner_keys
        WHERE api_key = $1
    """
    async with acquire() as conn:
        row = await conn.fetchrow(sql, api_key)
    if row is None:
        return None
    # asyncpg returns JSONB as a raw string unless a codec is registered.
    raw_ctx = row["context_json"]
    ctx = json.loads(raw_ctx) if isinstance(raw_ctx, str) else (raw_ctx or {})
    return {
        "api_key": row["api_key"],
        "partner_id": row["partner_id"],
        "partner_name": row["partner_name"],
        "partner_context": ctx,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


# ---------------------------------------------------------------------------
# Outcomes queries
# ---------------------------------------------------------------------------
async def insert_outcome(
    partner_id: str,
    listing_id: str,
    event_type: str,
    transaction_value: float | None,
    billable: bool,
    fee_amount: float | None,
) -> int:
    sql = """
        INSERT INTO outcomes (partner_id, listing_id, event_type,
                              transaction_value, billable, fee_amount)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
    """
    async with acquire() as conn:
        row = await conn.fetchrow(
            sql, partner_id, listing_id, event_type, transaction_value, billable, fee_amount
        )
    return row["id"]


async def summary_for_partner(partner_id: str) -> dict[str, Any]:
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE event_type = 'sale_completed')        AS sales_count,
            COALESCE(SUM(transaction_value)
                     FILTER (WHERE event_type = 'sale_completed'), 0)    AS revenue,
            COALESCE(SUM(fee_amount) FILTER (WHERE billable), 0)         AS fees,
            COUNT(*) FILTER (WHERE event_type = 'listing_expired')       AS expired_count,
            COUNT(*) FILTER (WHERE event_type = 'merchant_rejected')     AS rejected_count
        FROM outcomes
        WHERE partner_id = $1
    """
    async with acquire() as conn:
        row = await conn.fetchrow(sql, partner_id)
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# Historical sales (used by Pricing Service grounding in Phase 4)
# ---------------------------------------------------------------------------
async def historical_sales_for_category(category: str, limit: int = 50) -> list[dict]:
    sql = """
        SELECT category, sold_price, retail_value, day_of_week, hour_of_day, sold_at
        FROM historical_sales
        WHERE category = $1
        ORDER BY sold_at DESC
        LIMIT $2
    """
    async with acquire() as conn:
        rows = await conn.fetch(sql, category, limit)
    return [dict(r) for r in rows]
