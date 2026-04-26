"""Listing Service — public REST surface.

Backward-compatible single front door for partners and the merchant demo.
`POST /v1/agent` accepts the same shape v1.0 partners send today; modes
owned by other services (`moderate`, `pricing_optimize`) return 503 until
Phase 4 wires up A2A to Compliance and Pricing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from shared.auth import verify_bearer
from shared.config import LISTING_APP_NAME, LISTING_SERVICE_MODES
from shared.schemas import AgentRequest, AgentResponse

from .agent import run_listing_mode
from .demo import router as demo_router

logger = logging.getLogger("surplusas.listing.api")

app = FastAPI(
    title="SurplusAS API v2.0 — Listing Service",
    version="2.0.0",
    description=(
        "Multi-agent SurplusAS API on Google Cloud + ADK 2.0. "
        "This is the Listing Service front door; it routes Compliance and "
        "Pricing modes to peer services via A2A (Phase 4)."
    ),
)

# Open CORS — the demo and partner integrations call this from arbitrary
# origins; auth is enforced at the Bearer-token layer, not the browser layer.
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
    return {"status": "ok", "service": LISTING_APP_NAME, "version": "2.0.0"}


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
    # Defend against path traversal even though FastAPI's path parameter
    # already excludes slashes; users can still try `..\foo`.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404)
    path = SAMPLES_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404)
    cache = "public, max-age=300" if filename == "manifest.json" else "public, max-age=3600"
    return FileResponse(path, headers={"Cache-Control": cache})


@app.post("/v1/agent", response_model=AgentResponse)
async def agent_endpoint(
    request: AgentRequest,
    partner: dict = Depends(verify_bearer),
) -> AgentResponse:
    mode = request.mode.value

    if mode not in LISTING_SERVICE_MODES:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Mode '{mode}' will be served by a peer service "
                "(Compliance or Pricing) via A2A in Phase 4. Not yet wired."
            ),
        )

    partner_ctx: dict = dict(partner.get("partner_context") or {})
    if request.partner_context is not None:
        partner_ctx.update(request.partner_context.model_dump(exclude_none=True))

    try:
        data = await run_listing_mode(
            mode=mode,
            user_input=request.input,
            image_b64=request.image,
            partner_context=partner_ctx,
            user_id=request.merchant_id or partner.get("partner_id", "anonymous"),
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


@app.exception_handler(ValueError)
async def value_error_handler(_, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})
