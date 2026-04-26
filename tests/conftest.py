"""Shared pytest configuration for the smoke tests.

Smoke tests hit a deployed Listing Service URL by default. Override with:

    SURPLUSAS_BASE_URL=https://my-other-listing.run.app pytest tests/

The default points at the canonical deployed Listing Service for v2.0
(`listing-service-70904707890.us-central1.run.app`). The default Bearer
key is the demo key seeded in `partner_keys`. Override either with env
vars before running pytest.
"""

from __future__ import annotations

import os

import httpx
import pytest

DEFAULT_BASE_URL = "https://listing-service-70904707890.us-central1.run.app"
DEFAULT_API_KEY = "sk_demo_surplus_2026"


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("SURPLUSAS_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def api_key() -> str:
    return os.environ.get("SURPLUSAS_API_KEY", DEFAULT_API_KEY)


@pytest.fixture(scope="session")
def client(base_url: str, api_key: str):
    """A long-lived httpx client with auth + 240s timeout (LLM calls are slow)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(base_url=base_url, headers=headers, timeout=240.0) as c:
        yield c
