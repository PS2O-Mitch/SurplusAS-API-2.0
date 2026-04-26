"""Configuration: env vars, valid enums, per-mode settings.

Ported from v1.0 (app/config.py) with v1.0-only cruft (vLLM/OpenAI client
config, GEMINI_API_KEY) removed and Vertex AI envs added.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Load .env from the repo root if present. No-op in deployed environments
# (Cloud Run gets env vars from the service config, not a file).
load_dotenv()

# --- Vertex AI / ADK ---
# `setdefault` so explicit env-var overrides (e.g., test fixtures) win.
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ps2o-surplusas-api")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

GOOGLE_CLOUD_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GOOGLE_CLOUD_LOCATION = os.environ["GOOGLE_CLOUD_LOCATION"]

# --- Per-service models ---
LISTING_MODEL = os.environ.get("LISTING_MODEL", "gemini-2.5-flash")
COMPLIANCE_MODEL = os.environ.get("COMPLIANCE_MODEL", "gemini-2.5-flash")
PRICING_MODEL = os.environ.get("PRICING_MODEL", "gemini-2.5-flash")

# --- ADK app names (must be valid Python identifiers per ADK validation) ---
LISTING_APP_NAME = "surplusas_listing"
COMPLIANCE_APP_NAME = "surplusas_compliance"
PRICING_APP_NAME = "surplusas_pricing"

# --- Agent version (stamped into every outcome_tracking) ---
AGENT_VERSION = "2.1"

# --- API server ---
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8080"))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# --- Demo / partner key seed ---
SURPLUSAS_API_KEY = os.environ.get("SURPLUSAS_API_KEY", "sk_demo_surplus_2026")

# --- Database (used in Phase 3b+ once Cloud SQL is provisioned) ---
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# --- Valid mode enums (for fast input validation) ---
VALID_MODES: frozenset[str] = frozenset({
    "listing_create",
    "listing_create_full",
    "listing_enhance",
    "listing_batch",
    "search_interpret",
    "moderate",
    "translate",
    "customer_assist",
    "pricing_optimize",
})

# Modes the Listing Service handles directly. The other two get fanned out to
# Compliance and Pricing via A2A in Phase 4. `listing_create_full` runs the
# Phase 4d ADK 2.0 graph workflow that internally fans out to peer services.
LISTING_SERVICE_MODES: frozenset[str] = frozenset({
    "listing_create",
    "listing_create_full",
    "listing_enhance",
    "listing_batch",
    "search_interpret",
    "customer_assist",
    "translate",  # also exposed as a function tool inside listing graph
})

# Per-mode model temperatures (carried over from v1.0).
MODE_TEMPERATURES: dict[str, float] = {
    "listing_create": 0.4,
    "listing_enhance": 0.4,
    "listing_batch": 0.3,
    "search_interpret": 0.3,
    "moderate": 0.2,
    "translate": 0.3,
    "customer_assist": 0.7,
    "pricing_optimize": 0.2,
}

# Default partner context if a request omits it / no partner_keys row applies.
DEFAULT_PARTNER_CONTEXT: dict = {
    "partner_id": "demo_001",
    "partner_name": "SurplusAS Demo",
    "platform_type": "marketplace",
    "default_language": "en",
    "currency": "USD",
    "regulatory_region": "US",
    "discount_range": {"min": 30, "max": 70},
    "pickup_model": "in_store",
    "snap_ebt_enabled": False,
    "moderation_strictness": "standard",
}
