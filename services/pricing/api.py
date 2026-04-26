"""Pricing Service — A2A endpoint over IAM-authenticated Cloud Run.

Mirror of the Compliance Service shape; private Cloud Run, accepts an
`AgentRequest` with `mode = pricing_optimize`. The Pricing agent grounds
on the `historical_sales` Cloud SQL table before the LLM call.
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, HTTPException

from shared.config import PRICING_APP_NAME
from shared.schemas import AgentRequest, AgentResponse
from shared.tracing import init_tracing, install_fastapi_middleware

from .agent import run_pricing_optimize

init_tracing(PRICING_APP_NAME)

logger = logging.getLogger("surplusas.pricing.api")

app = FastAPI(
    title="SurplusAS Pricing Service",
    version="2.0.0",
    description=(
        "Dynamic pricing service. Private Cloud Run; A2A peers authenticate "
        "via Google ID token (audience = service URL). Grounded on the "
        "`historical_sales` Cloud SQL table for demand-aware recommendations."
    ),
)


install_fastapi_middleware(app, PRICING_APP_NAME)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": PRICING_APP_NAME, "version": "2.0.0"}


@app.post("/v1/agent", response_model=AgentResponse)
async def agent_endpoint(request: AgentRequest) -> AgentResponse:
    if request.mode.value != "pricing_optimize":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Pricing Service only handles mode 'pricing_optimize' "
                f"(got {request.mode.value!r})."
            ),
        )

    partner_ctx = (
        request.partner_context.model_dump() if request.partner_context else None
    )

    try:
        data = await run_pricing_optimize(
            user_input=request.input,
            partner_context=partner_ctx,
            user_id=request.merchant_id or "pricing-caller",
        )
    except json.JSONDecodeError as e:
        logger.warning("Model returned non-JSON: %s", e)
        raise HTTPException(status_code=502, detail=f"Model returned non-JSON: {e}")
    except Exception as e:
        logger.exception("Pricing run failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    return AgentResponse(success=True, mode="pricing_optimize", data=data, warnings=[])
