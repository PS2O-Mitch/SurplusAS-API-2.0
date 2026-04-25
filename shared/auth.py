"""Bearer-token auth.

Phase 3a uses an in-memory partner_keys map seeded from config so the API is
runnable without Cloud SQL. Phase 3b will replace `_PARTNER_KEYS` with an
asyncpg-backed lookup against the Postgres `partner_keys` table; the
`verify_bearer` signature stays the same so the swap is local.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import DEFAULT_PARTNER_CONTEXT, SURPLUSAS_API_KEY


# TODO(phase-3b): replace with `await db.fetch_partner_by_key(token)` against
# Cloud SQL `partner_keys` table.
_PARTNER_KEYS: dict[str, dict] = {
    SURPLUSAS_API_KEY: {
        "partner_id": "demo_001",
        "partner_name": "SurplusAS Demo",
        "partner_context": DEFAULT_PARTNER_CONTEXT,
    },
}

_bearer = HTTPBearer(auto_error=False)


async def verify_bearer(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate Bearer token and return partner record."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    partner = _PARTNER_KEYS.get(creds.credentials)
    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return partner
