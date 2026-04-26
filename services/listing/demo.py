"""Demo proxy routes for the public merchant-demo page.

The HTML page is served from /demo and calls these key-free `/demo/v1/*`
endpoints. The proxy injects the demo partner context server-side and
forwards into the same listing dispatcher (which itself fans peer-owned
modes out to Compliance / Pricing via A2A) so demo behavior matches
production behavior exactly.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException

from shared import db
from shared.a2a import call_peer_agent
from shared.config import LISTING_SERVICE_MODES, SURPLUSAS_API_KEY
from shared.schemas import AgentRequest, AgentResponse

from .agent import run_listing_mode

logger = logging.getLogger("surplusas.listing.demo")

router = APIRouter(prefix="/demo/v1", tags=["Demo"])


def _peer_url_for(mode: str) -> str | None:
    if mode == "moderate":
        return os.environ.get("COMPLIANCE_SERVICE_URL", "") or None
    if mode == "pricing_optimize":
        return os.environ.get("PRICING_SERVICE_URL", "") or None
    return None


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

    ctx = await _demo_partner_ctx()
    if body.partner_context is not None:
        ctx = {**ctx, **body.partner_context.model_dump(exclude_none=True)}

    peer = _peer_url_for(mode)
    if peer:
        try:
            response = await call_peer_agent(peer, body.model_dump(mode="json"))
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Peer service returned {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            logger.exception("Demo A2A call failed")
            raise HTTPException(status_code=502, detail=f"Peer service error: {e}")
        return AgentResponse(**response)

    if mode not in LISTING_SERVICE_MODES:
        raise HTTPException(
            status_code=503,
            detail=f"Mode '{mode}' is not handled by the Listing Service and no peer URL is configured.",
        )

    try:
        data = await run_listing_mode(
            mode=mode,
            user_input=body.input,
            image_b64=body.image,
            partner_context=ctx,
            user_id=f"demo:{secrets.token_hex(4)}",
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Model returned non-JSON: {e}")
    except Exception as exc:
        logger.exception("Demo agent run failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    return AgentResponse(success=True, mode=mode, data=data, warnings=[])


@router.post("/listings/publish")
async def demo_publish(payload: dict) -> dict:
    """Stub publish for the demo flow."""
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
