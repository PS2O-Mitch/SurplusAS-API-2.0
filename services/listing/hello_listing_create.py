"""Phase 2 hello-world: validate ADK 2.0 + Vertex AI + Gemini end-to-end.

Runs the existing v2.1 system prompt through ADK 2.0 against Vertex AI Gemini
with a real bakery image and the listing_create mode prompt. Confirms:
  - ADC auth resolves
  - ADK Agent + Runner work on the 2.0 beta
  - Gemini accepts multimodal input via genai types
  - JSON output is parseable and contains the expected listing_create fields

Run from the repo root with the venv active:
    .\\.venv\\Scripts\\python.exe -m services.listing.hello_listing_create
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

# Force Vertex AI mode BEFORE importing google.adk / google.genai.
# These env vars are read at import time by the genai client.
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ps2o-surplusas-api")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from shared.prompts import SYSTEM_PROMPT, build_mode_prompt


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_IMAGE = REPO_ROOT / "static" / "demo" / "samples" / "bakery.webp"

APP_NAME = "surplusas_listing_hello"
USER_ID = "merchant_demo_001"
MODEL = "gemini-2.5-flash"


PARTNER_CONTEXT = {
    "partner_id": "demo_001",
    "partner_name": "SurplusAS Demo Bakery",
    "platform_type": "marketplace",
    "default_language": "en",
    "currency": "USD",
    "regulatory_region": "US",
    "discount_range": {"min": 30, "max": 70},
}

MERCHANT_INPUT = (
    "12 fresh croissants and 8 bagels left from morning bake. "
    "Closing at 7 PM tonight, need to clear inventory."
)


async def main() -> None:
    print(f"=== Phase 2 hello-world ===")
    print(f"Project:  {os.environ['GOOGLE_CLOUD_PROJECT']}")
    print(f"Location: {os.environ['GOOGLE_CLOUD_LOCATION']}")
    print(f"Model:    {MODEL}")
    print(f"Image:    {SAMPLE_IMAGE.name} ({SAMPLE_IMAGE.stat().st_size:,} bytes)")
    print()

    agent = Agent(
        name="surplusas_listing_hello",
        model=MODEL,
        instruction=SYSTEM_PROMPT,
    )
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )

    mode_prompt = build_mode_prompt("listing_create", PARTNER_CONTEXT)
    user_text = (
        f"{mode_prompt} {MERCHANT_INPUT}\n\n"
        "Respond with valid JSON only. No markdown, no explanation."
    )

    image_bytes = SAMPLE_IMAGE.read_bytes()
    content = types.Content(
        role="user",
        parts=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/webp"),
            types.Part.from_text(text=user_text),
        ],
    )

    final_text = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(p.text or "" for p in event.content.parts)

    if not final_text:
        print("!! No final response received from runner.")
        return

    print("=== Raw model output (first 2 KB) ===")
    print(final_text[:2000])
    print()

    raw = final_text.strip()
    # Strip markdown fences if the model included them despite the instruction
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"!! JSON parse failed: {e}")
        return

    print("=== Parsed JSON summary ===")
    print(f"  mode:            {parsed.get('mode')!r}")
    print(f"  listing_id:      {parsed.get('listing_id')!r}")
    print(f"  status:          {parsed.get('status')!r}")
    print(f"  confidence:      {parsed.get('confidence')!r}")
    print(f"  title:           {parsed.get('title')!r}")
    print(f"  category:        {parsed.get('category')!r}")
    print(f"  items_identified: {len(parsed.get('items_identified') or [])} items")
    pricing = parsed.get("pricing") or {}
    print(f"  pricing.suggested_surplus_price: {pricing.get('suggested_surplus_price')!r}")
    print(f"  pricing.discount_percentage:     {pricing.get('discount_percentage')!r}")
    image_analysis = parsed.get("image_analysis") or {}
    print(f"  image_analysis.photo_quality:    {image_analysis.get('photo_quality')!r}")
    print()

    expected_keys = {
        "mode", "listing_id", "status", "confidence", "title", "category",
        "items_identified", "dietary_attributes", "pricing", "pickup_window",
        "food_safety_notes", "image_analysis", "outcome_tracking",
    }
    actual_keys = set(parsed.keys())
    missing = expected_keys - actual_keys
    if missing:
        print(f"!! Missing expected keys: {sorted(missing)}")
    else:
        print("OK — all expected listing_create keys present.")


if __name__ == "__main__":
    asyncio.run(main())
