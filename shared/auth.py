"""Bearer-token auth backed by Cloud SQL `partner_keys`.

The lookup is cached for the lifetime of the process (in-memory LRU) so
hot-path requests don't pay a round-trip to the DB. Cache size is small
because partner counts are low.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db


_bearer = HTTPBearer(auto_error=False)


# A trivial per-process cache so we don't hit the DB for every authed request.
# `lru_cache` on a sync wrapper that holds the most-recent dict result is fine
# for the call volume we're targeting; Phase 4 can move this to a real cache
# (e.g., Memorystore / Redis) if needed.
_cache: dict[str, dict] = {}
_cache_negatives: set[str] = set()


async def _lookup(api_key: str) -> dict | None:
    if api_key in _cache:
        return _cache[api_key]
    if api_key in _cache_negatives:
        return None
    partner = await db.fetch_partner_by_key(api_key)
    if partner is None:
        _cache_negatives.add(api_key)
    else:
        _cache[api_key] = partner
    return partner


def invalidate_cache() -> None:
    """Clear the auth cache (e.g., after rotating a partner key)."""
    _cache.clear()
    _cache_negatives.clear()


async def verify_bearer(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate Bearer token against partner_keys and return the partner record."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    partner = await _lookup(creds.credentials)
    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return partner
