"""Demo proxy routes for the public merchant-demo page.

The HTML page is served from /demo and calls these key-free `/demo/v1/*`
endpoints. The proxy injects the demo partner context server-side and
forwards into the same `run_listing_mode` code path that authed partners
use, so demo behavior matches production behavior exactly.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from shared import db
from shared.config import LISTING_SERVICE_MODES, SURPLUSAS_API_KEY
from shared.schemas import AgentRequest, AgentResponse

from .agent import run_listing_mode

logger = logging.getLogger("surplusas.listing.demo")

router = APIRouter(prefix="/demo/v1", tags=["Demo"])


async def _demo_partner_ctx() -> dict:
    """Look up the demo partner row and return the merged context dict."""
    partner = await db.fetch_partner_by_key(SURPLUSAS_API_KEY)
    if partner is None:
        logger.error("Demo partner key %r not found in partner_keys", SURPLUSAS_API_KEY)
        raise HTTPException(status_code=503, detail="Demo backend is not configured.")
    return partner["partner_context"] or {}


@router.post("/agent", response_model=AgentResponse)
async def demo_agent(body: AgentRequest) -> AgentResponse:
    mode = body.mode.value
    if mode not in LISTING_SERVICE_MODES:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Mode '{mode}' is owned by a peer service "
                "(Compliance or Pricing); A2A wiring lands in Phase 4."
            ),
        )

    ctx = await _demo_partner_ctx()
    if body.partner_context is not None:
        ctx = {**ctx, **body.partner_context.model_dump(exclude_none=True)}

    try:
        data = await run_listing_mode(
            mode=mode,
            user_input=body.input,
            image_b64=body.image,
            partner_context=ctx,
            user_id=f"demo:{secrets.token_hex(4)}",
        )
    except Exception as exc:
        logger.exception("Demo agent run failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    return AgentResponse(success=True, mode=mode, data=data, warnings=[])


@router.post("/listings/publish")
async def demo_publish(payload: dict) -> dict:
    """Stub publish for the demo flow.

    Returns a server-generated `pub_*` id without persistence. Real
    publish lives behind the authed `/v1/listings/publish` endpoint
    (added in a later phase) and writes through the outcomes pipeline.
    """
    listing = payload.get("listing", {}) if isinstance(payload, dict) else {}
    return {
        "success": True,
        "published_listing_id": f"pub_{secrets.token_hex(4).upper()}",
        "listing_id": listing.get("listing_id", ""),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "partner_id": "demo_001",
        "store_id": None,
        "message": "Listing published (demo mode — not persisted).",
    }
