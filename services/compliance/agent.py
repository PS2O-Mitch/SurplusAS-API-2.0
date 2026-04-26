"""SurplusAS Compliance Service — ADK 2.0 agent for the `moderate` mode.

Owns listing safety / compliance review only. Other modes are rejected at
the api layer so the service stays single-purpose and independently
discoverable by enterprise A2A peers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from shared.config import AGENT_VERSION, COMPLIANCE_APP_NAME, COMPLIANCE_MODEL
from shared.prompts import SYSTEM_PROMPT, build_mode_prompt


_session_service = InMemorySessionService()
_runner: Runner | None = None


def _build_agent() -> Agent:
    return Agent(
        name=COMPLIANCE_APP_NAME,
        model=COMPLIANCE_MODEL,
        instruction=SYSTEM_PROMPT,
    )


def get_runner() -> Runner:
    global _runner
    if _runner is None:
        _runner = Runner(
            agent=_build_agent(),
            app_name=COMPLIANCE_APP_NAME,
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
    parsed["outcome_tracking"]["model_used"] = COMPLIANCE_MODEL
    parsed["outcome_tracking"]["inference_timestamp"] = (
        datetime.now(timezone.utc).isoformat()
    )
    return parsed


async def run_moderate(
    user_input: str,
    partner_context: dict | None = None,
    user_id: str = "anonymous",
) -> dict:
    """Run a moderation review and return the parsed JSON dict."""
    runner = get_runner()
    session = await _session_service.create_session(
        app_name=COMPLIANCE_APP_NAME,
        user_id=user_id,
    )

    mode_prompt = build_mode_prompt("moderate", partner_context or {})
    user_text = (
        f"{mode_prompt} {user_input}\n\n"
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
    return _apply_server_overwrites(parsed)
