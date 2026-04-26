"""Compliance Service — A2A endpoint over IAM-authenticated Cloud Run.

Private Cloud Run service. Peer agents (currently the Listing Service,
later other enterprise tenants discoverable via A2A) authenticate with a
Google ID token whose audience matches this service's URL. The Bearer
in the Authorization header is the IAM token, not a partner key — there
is no per-tenant Bearer auth at this layer.

The single endpoint accepts an `AgentRequest` with `mode = moderate`,
mirroring the same wire shape the Listing Service receives, so anything
that already knows how to talk to a SurplusAS agent can call this one
without learning a new payload format.
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, HTTPException

from shared.config import COMPLIANCE_APP_NAME
from shared.schemas import AgentRequest, AgentResponse

from .agent import run_moderate

logger = logging.getLogger("surplusas.compliance.api")

app = FastAPI(
    title="SurplusAS Compliance Service",
    version="2.0.0",
    description=(
        "Listing-safety / moderation service. Private Cloud Run; A2A peers "
        "authenticate via Google ID token (audience = service URL). Single "
        "purpose: the `moderate` mode."
    ),
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": COMPLIANCE_APP_NAME, "version": "2.0.0"}


@app.post("/v1/agent", response_model=AgentResponse)
async def agent_endpoint(request: AgentRequest) -> AgentResponse:
    if request.mode.value != "moderate":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Compliance Service only handles mode 'moderate' "
                f"(got {request.mode.value!r})."
            ),
        )

    partner_ctx = (
        request.partner_context.model_dump() if request.partner_context else None
    )

    try:
        data = await run_moderate(
            user_input=request.input,
            partner_context=partner_ctx,
            user_id=request.merchant_id or "compliance-caller",
        )
    except json.JSONDecodeError as e:
        logger.warning("Model returned non-JSON: %s", e)
        raise HTTPException(status_code=502, detail=f"Model returned non-JSON: {e}")
    except Exception as e:
        logger.exception("Compliance run failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    return AgentResponse(success=True, mode="moderate", data=data, warnings=[])
