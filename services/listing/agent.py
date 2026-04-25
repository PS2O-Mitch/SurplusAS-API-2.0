"""SurplusAS Listing Service — ADK 2.0 root agent and dispatcher.

Importing `shared.config` first sets the Vertex AI env vars before any
google.adk / google.genai module reads them.
"""

from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timezone

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from shared.config import (
    AGENT_VERSION,
    LISTING_APP_NAME,
    LISTING_MODEL,
    LISTING_SERVICE_MODES,
)
from shared.prompts import SYSTEM_PROMPT, build_mode_prompt


# Singleton runner / session service for the lifetime of the process.
_session_service = InMemorySessionService()
_runner: Runner | None = None


def _build_agent() -> Agent:
    return Agent(
        name=LISTING_APP_NAME,
        model=LISTING_MODEL,
        instruction=SYSTEM_PROMPT,
    )


def get_runner() -> Runner:
    global _runner
    if _runner is None:
        _runner = Runner(
            agent=_build_agent(),
            app_name=LISTING_APP_NAME,
            session_service=_session_service,
        )
    return _runner


def _decode_image(image_b64: str) -> tuple[bytes, str]:
    """Return (bytes, mime_type) from a base64 string with optional data-URL prefix."""
    mime = "image/webp"
    if image_b64.startswith("data:"):
        sep = image_b64.find(";base64,")
        if sep > 5:
            mime = image_b64[5:sep]
        b64 = image_b64.split("base64,", 1)[1]
    else:
        b64 = image_b64
    return base64.b64decode(b64), mime


def _strip_markdown_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        # Drop the opening fence and an optional language tag, then any
        # trailing fence.
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _apply_server_overwrites(parsed: dict) -> dict:
    """Stamp server-controlled fields onto the parsed model output."""
    parsed.setdefault("outcome_tracking", {})
    parsed["outcome_tracking"]["agent_version"] = AGENT_VERSION
    parsed["outcome_tracking"]["model_used"] = LISTING_MODEL
    parsed["outcome_tracking"]["inference_timestamp"] = (
        datetime.now(timezone.utc).isoformat()
    )

    # listing_id: replace any placeholder with a real id.
    if "listing_id" in parsed:
        lid = parsed["listing_id"]
        if not lid or "X" in lid:
            parsed["listing_id"] = f"req_{secrets.token_hex(4).upper()}"

    if isinstance(parsed.get("category"), str):
        parsed["category"] = parsed["category"].lower().strip()

    pricing = parsed.get("pricing")
    if isinstance(pricing, dict) and pricing.get("suggested_surplus_price") is not None:
        pricing["suggested_surplus_price"] = round(pricing["suggested_surplus_price"] * 4) / 4
    if parsed.get("recommended_price") is not None:
        parsed["recommended_price"] = round(parsed["recommended_price"] * 4) / 4

    return parsed


async def run_listing_mode(
    mode: str,
    user_input: str,
    image_b64: str | None = None,
    partner_context: dict | None = None,
    user_id: str = "anonymous",
) -> dict:
    """Run a listing-service mode against ADK 2.0 + Vertex AI Gemini.

    Returns a parsed dict for JSON modes or `{"mode": ..., "response": text}`
    for `customer_assist`. Raises `ValueError` if the mode isn't owned by
    this service.
    """
    if mode not in LISTING_SERVICE_MODES:
        raise ValueError(f"Mode {mode!r} is not handled by the Listing Service")

    runner = get_runner()
    session = await _session_service.create_session(
        app_name=LISTING_APP_NAME,
        user_id=user_id,
    )

    mode_prompt = build_mode_prompt(mode, partner_context or {})
    user_text = f"{mode_prompt} {user_input}"
    if mode != "customer_assist":
        user_text += "\n\nRespond with valid JSON only. No markdown, no explanation."

    parts: list[types.Part] = []
    if image_b64:
        image_bytes, mime = _decode_image(image_b64)
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime))
    parts.append(types.Part.from_text(text=user_text))

    content = types.Content(role="user", parts=parts)

    final_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(p.text or "" for p in event.content.parts)

    if mode == "customer_assist":
        return {"mode": "customer_assist", "response": final_text}

    raw = _strip_markdown_fence(final_text)
    parsed = json.loads(raw)
    return _apply_server_overwrites(parsed)
