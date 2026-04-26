"""Listing Service — public REST surface.

Backward-compatible single front door for partners and the merchant demo.
`POST /v1/agent` accepts the same shape v1.0 partners send today; modes
owned by peer services (`moderate`, `pricing_optimize`) are fanned out
over A2A to Compliance and Pricing respectively, keyed off the
`COMPLIANCE_SERVICE_URL` / `PRICING_SERVICE_URL` env vars.
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from pathlib import Path

from shared.a2a import call_peer_agent
from shared.auth import verify_bearer
from shared.config import LISTING_APP_NAME, LISTING_SERVICE_MODES
from shared.schemas import AgentRequest, AgentResponse

from .agent import run_listing_mode
from .demo import router as demo_router
from .pipeline import run_listing_pipeline

logger = logging.getLogger("surplusas.listing.api")

COMPLIANCE_SERVICE_URL = os.environ.get("COMPLIANCE_SERVICE_URL", "")
PRICING_SERVICE_URL = os.environ.get("PRICING_SERVICE_URL", "")


def _peer_url_for(mode: str) -> str | None:
    if mode == "moderate":
        return COMPLIANCE_SERVICE_URL or None
    if mode == "pricing_optimize":
        return PRICING_SERVICE_URL or None
    return None


app = FastAPI(
    title="SurplusAS API v2.0 — Listing Service",
    version="2.0.0",
    description=(
        "Multi-agent SurplusAS API on Google Cloud + ADK 2.0. "
        "Listing Service is the public front door; it fans `moderate` and "
        "`pricing_optimize` modes out to Compliance and Pricing peers via A2A."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(demo_router)


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "static"
SAMPLES_DIR = STATIC_DIR / "demo" / "samples"


@app.get("/health", tags=["System"])
async def health() -> dict:
    return {
        "status": "ok",
        "service": LISTING_APP_NAME,
        "version": "2.0.0",
        "peers": {
            "compliance": bool(COMPLIANCE_SERVICE_URL),
            "pricing": bool(PRICING_SERVICE_URL),
        },
    }


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "service": "surplusas_listing",
        "version": "2.0.0",
        "demo": "/demo",
        "docs": "/docs",
    }


@app.get("/demo", include_in_schema=False)
async def demo_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "surplusas-merchant-demo.html")


@app.get("/demo/samples/{filename}", include_in_schema=False)
async def demo_sample(filename: str) -> FileResponse:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404)
    path = SAMPLES_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404)
    cache = "public, max-age=300" if filename == "manifest.json" else "public, max-age=3600"
    return FileResponse(path, headers={"Cache-Control": cache})


async def _route_agent(
    request: AgentRequest,
    partner_ctx: dict,
    user_id: str,
) -> AgentResponse:
    """Either fan out to a peer service (A2A) or run the mode locally."""
    mode = request.mode.value

    peer = _peer_url_for(mode)
    if peer:
        try:
            response = await call_peer_agent(peer, request.model_dump(mode="json"))
        except httpx.HTTPStatusError as e:
            logger.warning("A2A peer %s returned %s", peer, e.response.status_code)
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Peer service returned {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            logger.exception("A2A call to %s failed", peer)
            raise HTTPException(status_code=502, detail=f"Peer service error: {e}")
        # Peer returns the same AgentResponse shape; pass through.
        return AgentResponse(**response)

    if mode not in LISTING_SERVICE_MODES:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Mode '{mode}' is owned by a peer service but no URL is "
                "configured (set COMPLIANCE_SERVICE_URL or PRICING_SERVICE_URL)."
            ),
        )

    try:
        if mode == "listing_create_full":
            data = await run_listing_pipeline(
                user_input=request.input,
                image_b64=request.image,
                partner_context=partner_ctx,
                user_id=user_id,
            )
        else:
            data = await run_listing_mode(
                mode=mode,
                user_input=request.input,
                image_b64=request.image,
                partner_context=partner_ctx,
                user_id=user_id,
            )
    except json.JSONDecodeError as e:
        logger.warning("Model returned non-JSON: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Model returned non-JSON response: {e}",
        )
    except Exception as e:
        logger.exception("Agent run failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {e}",
        )

    return AgentResponse(success=True, mode=mode, data=data, warnings=[])


@app.post("/v1/agent", response_model=AgentResponse)
async def agent_endpoint(
    request: AgentRequest,
    partner: dict = Depends(verify_bearer),
) -> AgentResponse:
    partner_ctx: dict = dict(partner.get("partner_context") or {})
    if request.partner_context is not None:
        partner_ctx.update(request.partner_context.model_dump(exclude_none=True))

    user_id = request.merchant_id or partner.get("partner_id", "anonymous")
    return await _route_agent(request, partner_ctx, user_id)


@app.exception_handler(ValueError)
async def value_error_handler(_, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})
