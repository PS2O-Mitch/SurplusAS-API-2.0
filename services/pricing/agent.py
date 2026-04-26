"""SurplusAS Pricing Service — ADK 2.0 agent for `pricing_optimize`.

Pulls demand-signal grounding from `historical_sales` (Cloud SQL) and
prepends it to the user message, so the model anchors its recommended
price on real partner data instead of generic priors.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from shared.config import AGENT_VERSION, PRICING_APP_NAME, PRICING_MODEL
from shared.prompts import SYSTEM_PROMPT, build_mode_prompt

from .grounding import category_from_input, grounding_for


_session_service = InMemorySessionService()
_runner: Runner | None = None


def _build_agent() -> Agent:
    return Agent(
        name=PRICING_APP_NAME,
        model=PRICING_MODEL,
        instruction=SYSTEM_PROMPT,
    )


def get_runner() -> Runner:
    global _runner
    if _runner is None:
        _runner = Runner(
            agent=_build_agent(),
            app_name=PRICING_APP_NAME,
            session_service=_session_service,
        )
    return _runner


def _strip_markdown_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _apply_server_overwrites(parsed: dict) -> dict:
    parsed.setdefault("outcome_tracking", {})
    parsed["outcome_tracking"]["agent_version"] = AGENT_VERSION
    parsed["outcome_tracking"]["model_used"] = PRICING_MODEL
    parsed["outcome_tracking"]["inference_timestamp"] = (
        datetime.now(timezone.utc).isoformat()
    )
    if parsed.get("recommended_price") is not None:
        parsed["recommended_price"] = round(parsed["recommended_price"] * 4) / 4
    return parsed


async def run_pricing_optimize(
    user_input: str,
    partner_context: dict | None = None,
    user_id: str = "anonymous",
) -> dict:
    """Run the pricing agent with grounding from historical_sales."""
    category = category_from_input(user_input)
    grounding = await grounding_for(category)

    runner = get_runner()
    session = await _session_service.create_session(
        app_name=PRICING_APP_NAME,
        user_id=user_id,
    )

    mode_prompt = build_mode_prompt("pricing_optimize", partner_context or {})
    user_text = (
        f"{mode_prompt}\n\n{grounding}\n\n"
        f"Listing and context: {user_input}\n\n"
        "Respond with valid JSON only. No markdown, no explanation."
    )

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_text)],
    )

    final_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(p.text or "" for p in event.content.parts)

    raw = _strip_markdown_fence(final_text)
    parsed = json.loads(raw)
    parsed["_grounding_used"] = bool(category)  # debug visibility
    return _apply_server_overwrites(parsed)
