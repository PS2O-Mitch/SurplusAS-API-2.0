"""ADK 2.0 graph workflow: intake -> moderate -> price -> publish.

Phase 4d. A single merchant request to `mode=listing_create_full` runs
this graph end-to-end inside the Listing Service. The intake node calls
the local listing agent; moderate and price nodes fan out to the
Compliance and Pricing peer services over A2A; publish stamps a
published_listing_id and returns the combined payload.

The graph is a real `google.adk.workflow.Workflow` with `FunctionNode`s
wired by `Edge`s and executed through `Runner.run_async(node=workflow)`.
Nodes share data via session state (seeded at session creation; each
node writes its result key back to `ctx.state` for downstream nodes).
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any

import httpx
from google.adk.agents.context import Context
from google.adk.runners import Runner
from google.adk.workflow import Edge, FunctionNode, START, Workflow
from google.genai import types

from shared.a2a import call_peer_agent

from .agent import _session_service, run_listing_mode

logger = logging.getLogger("surplusas.listing.pipeline")

PIPELINE_APP_NAME = "surplusas_listing_pipeline"

COMPLIANCE_SERVICE_URL = os.environ.get("COMPLIANCE_SERVICE_URL", "")
PRICING_SERVICE_URL = os.environ.get("PRICING_SERVICE_URL", "")


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def intake(
    ctx: Context,
    user_input: str,
    partner_context: dict,
    image: str | None = None,
    user_id: str = "anonymous",
) -> dict:
    """Run the local `listing_create` agent and stash the listing in state."""
    listing = await run_listing_mode(
        mode="listing_create",
        user_input=user_input,
        image_b64=image,
        partner_context=partner_context,
        user_id=user_id,
    )
    ctx.state["listing"] = listing
    return {"listing": listing}


def _listing_summary(listing: dict) -> str:
    """Compact text the peer LLMs can read without seeing raw JSON noise."""
    parts = [
        f"title: {listing.get('title', '')}",
        f"description: {listing.get('description', '')}",
        f"category: {listing.get('category', '')}",
    ]
    pricing = listing.get("pricing") or {}
    if pricing.get("estimated_retail_value") is not None:
        parts.append(f"retail_value: {pricing['estimated_retail_value']}")
    if pricing.get("suggested_surplus_price") is not None:
        parts.append(f"suggested_price: {pricing['suggested_surplus_price']}")
    if pricing.get("discount_percentage") is not None:
        parts.append(f"discount_pct: {pricing['discount_percentage']}")
    if listing.get("pickup_window"):
        parts.append(f"pickup_window: {listing['pickup_window']}")
    return "\n".join(parts)


async def _call_peer(audience: str, body: dict) -> dict:
    """Wrap A2A call so we always return a dict even on peer errors."""
    if not audience:
        return {"_error": "Peer URL not configured."}
    try:
        return await call_peer_agent(audience, body)
    except httpx.HTTPStatusError as e:
        return {"_error": f"Peer {audience} returned {e.response.status_code}"}
    except Exception as e:
        logger.exception("Pipeline peer call failed")
        return {"_error": f"Peer {audience} error: {e}"}


async def moderate(ctx: Context, listing: dict) -> dict:
    """Fan out to Compliance via A2A. Result stashed under `moderation`."""
    body = {
        "mode": "moderate",
        "input": _listing_summary(listing),
    }
    response = await _call_peer(COMPLIANCE_SERVICE_URL, body)
    moderation = response.get("data", {}) if isinstance(response, dict) else {}
    if response.get("_error"):
        moderation = {"_error": response["_error"]}
    ctx.state["moderation"] = moderation
    return moderation


async def price(ctx: Context, listing: dict) -> dict:
    """Fan out to Pricing via A2A. Result stashed under `pricing`."""
    body = {
        "mode": "pricing_optimize",
        "input": _listing_summary(listing),
    }
    response = await _call_peer(PRICING_SERVICE_URL, body)
    pricing = response.get("data", {}) if isinstance(response, dict) else {}
    if response.get("_error"):
        pricing = {"_error": response["_error"]}
    ctx.state["pricing"] = pricing
    return pricing


async def publish(
    ctx: Context,
    listing: dict,
    moderation: dict,
    pricing: dict,
) -> dict:
    """Combine upstream outputs and stamp a published_listing_id."""
    approved = bool(moderation.get("approved")) and "_error" not in moderation

    published: dict[str, Any] | None = None
    if approved:
        published = {
            "published_listing_id": f"pub_{secrets.token_hex(4).upper()}",
            "listing_id": listing.get("listing_id", ""),
            "published_at": datetime.now(timezone.utc).isoformat(),
            "partner_id": (ctx.state.get("partner_context") or {}).get(
                "partner_id", ""
            ),
            "message": "Listing auto-published by graph workflow.",
        }

    final_status = (
        "published"
        if approved
        else ("blocked_by_moderation" if moderation else "incomplete")
    )

    return {
        "mode": "listing_create_full",
        "status": final_status,
        "listing": listing,
        "moderation": moderation,
        "pricing": pricing,
        "published": published,
    }


# ---------------------------------------------------------------------------
# Workflow graph
# ---------------------------------------------------------------------------

_intake_node = FunctionNode(func=intake, name="intake")
_moderate_node = FunctionNode(func=moderate, name="moderate")
_price_node = FunctionNode(func=price, name="price")
_publish_node = FunctionNode(func=publish, name="publish")

LISTING_PIPELINE = Workflow(
    name="listing_create_full",
    edges=[
        Edge(from_node=START, to_node=_intake_node),
        Edge(from_node=_intake_node, to_node=_moderate_node),
        Edge(from_node=_moderate_node, to_node=_price_node),
        Edge(from_node=_price_node, to_node=_publish_node),
    ],
)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_pipeline_runner: Runner | None = None


def _get_runner() -> Runner:
    global _pipeline_runner
    if _pipeline_runner is None:
        _pipeline_runner = Runner(
            node=LISTING_PIPELINE,
            app_name=PIPELINE_APP_NAME,
            session_service=_session_service,
        )
    return _pipeline_runner


async def run_listing_pipeline(
    user_input: str,
    image_b64: str | None,
    partner_context: dict,
    user_id: str = "anonymous",
) -> dict:
    """Run the full graph and return the publish node's combined dict."""
    runner = _get_runner()

    session = await _session_service.create_session(
        app_name=PIPELINE_APP_NAME,
        user_id=user_id,
        state={
            "user_input": user_input,
            "partner_context": partner_context,
            "image": image_b64,
            "user_id": user_id,
        },
    )

    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_input)],
    )

    final_output: dict | None = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=new_message,
    ):
        if getattr(event, "output", None) is not None and isinstance(
            event.output, dict
        ):
            if event.output.get("mode") == "listing_create_full":
                final_output = event.output

    if final_output is None:
        raise RuntimeError(
            "Pipeline finished without a publish-node output. "
            "Check Cloud Logging for node-level errors."
        )
    return final_output
