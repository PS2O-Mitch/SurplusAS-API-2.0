"""End-to-end smoke tests against the deployed Listing Service.

One test per agent mode plus the full ADK 2.0 graph workflow
(`listing_create_full`). Each test posts to `POST /v1/agent` over real
HTTPS, verifies a 200 response, and asserts the response carries the
right `mode` and the load-bearing fields the schema promises.

Why hit the deployed URL instead of mocking? The migration goal is
"production migration with the contest as a forcing function" — these
tests catch contract drift caused by Vertex AI prompt-format changes,
ADK upgrades, or peer-service deploys, none of which a unit test would
catch. They are slow (~15–30s each — LLM calls) and require network +
the demo Bearer key, which is the trade-off.

Skip individual tests by setting `SURPLUSAS_SKIP=mode1,mode2` (e.g.
`SURPLUSAS_SKIP=listing_batch,customer_assist`) for fast iteration.
"""

from __future__ import annotations

import os

import pytest


_SKIP = {m.strip() for m in os.environ.get("SURPLUSAS_SKIP", "").split(",") if m.strip()}


def _skip_if_disabled(mode: str) -> None:
    if mode in _SKIP:
        pytest.skip(f"Skipped via SURPLUSAS_SKIP={mode}")


def _post_agent(client, body: dict) -> dict:
    r = client.post("/v1/agent", json=body)
    assert r.status_code == 200, (
        f"{body['mode']} returned {r.status_code}: {r.text[:300]}"
    )
    return r.json()


def test_health_endpoint(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "surplusas_listing"
    # Phase 4 wired up peer URLs — these should both be true in production.
    peers = body.get("peers", {})
    assert peers.get("compliance") is True
    assert peers.get("pricing") is True


def test_listing_create(client) -> None:
    _skip_if_disabled("listing_create")
    body = _post_agent(
        client,
        {
            "mode": "listing_create",
            "input": "10 turkey sandwiches, made fresh today, available until 5 PM",
        },
    )
    assert body["success"] is True
    assert body["mode"] == "listing_create"
    data = body["data"]
    assert data["mode"] == "listing_create"
    assert data.get("listing_id", "").startswith("req_")
    assert data["title"]
    assert data["category"]
    assert "outcome_tracking" in data


def test_listing_enhance(client) -> None:
    _skip_if_disabled("listing_enhance")
    body = _post_agent(
        client,
        {
            "mode": "listing_enhance",
            "input": '{"title":"Bread","description":"some bread","category":"bakery"}',
        },
    )
    assert body["mode"] == "listing_enhance"
    assert body["data"]["mode"] == "listing_enhance"
    assert "enhanced" in body["data"]


def test_listing_batch(client) -> None:
    _skip_if_disabled("listing_batch")
    body = _post_agent(
        client,
        {
            "mode": "listing_batch",
            "input": "SKU-1: 5 baguettes; SKU-2: 8 ciabatta",
        },
    )
    assert body["mode"] == "listing_batch"
    data = body["data"]
    assert isinstance(data.get("listings"), list)
    assert len(data["listings"]) >= 1
    summary = data.get("batch_summary") or {}
    assert summary.get("total_items_processed", 0) >= 1


def test_search_interpret(client) -> None:
    _skip_if_disabled("search_interpret")
    body = _post_agent(
        client,
        {"mode": "search_interpret", "input": "cheap vegan dinner near me before 7pm"},
    )
    data = body["data"]
    assert data["mode"] == "search_interpret"
    assert "filters" in data
    assert data["filters"]["dietary_requirements"]["must_be_vegan"] is True


def test_customer_assist(client) -> None:
    _skip_if_disabled("customer_assist")
    body = _post_agent(
        client,
        {"mode": "customer_assist", "input": "When can I pick up my order?"},
    )
    data = body["data"]
    assert data["mode"] == "customer_assist"
    assert data.get("response")


def test_translate(client) -> None:
    _skip_if_disabled("translate")
    body = _post_agent(
        client,
        {
            "mode": "translate",
            "input": '{"title":"20 Chocolate Croissants",'
            '"description":"Freshly baked, pickup before 6 PM today",'
            '"target_language":"es"}',
        },
    )
    data = body["data"]
    assert data["mode"] == "translate"
    assert data.get("target_language") == "es"
    assert data.get("translations", {}).get("title")


def test_moderate_via_a2a(client) -> None:
    """`moderate` is owned by Compliance — Listing fans out via A2A."""
    _skip_if_disabled("moderate")
    body = _post_agent(
        client,
        {
            "mode": "moderate",
            "input": "Fresh sourdough bread, 5 loaves, baked this morning, $4.50 each",
        },
    )
    data = body["data"]
    assert data["mode"] == "moderate"
    assert "approved" in data
    assert data.get("overall_risk") in {
        "pass", "low_risk", "medium_risk", "high_risk", "block",
    }


def test_pricing_optimize_via_a2a(client) -> None:
    """`pricing_optimize` is owned by Pricing — Listing fans out via A2A."""
    _skip_if_disabled("pricing_optimize")
    body = _post_agent(
        client,
        {
            "mode": "pricing_optimize",
            "input": "category: bakery\nretail_value: 10.00\ndiscount_pct: 40\npickup_window: closes 5 PM today",
        },
    )
    data = body["data"]
    assert data["mode"] == "pricing_optimize"
    assert data["recommended_price"] > 0
    assert 0 <= data["recommended_discount_pct"] <= 100
    # Grounding should fire because category=bakery is in historical_sales.
    assert data.get("_grounding_used") is True


def test_listing_create_full_pipeline(client) -> None:
    """Phase 4d: ADK 2.0 graph workflow chains intake → moderate → price → publish."""
    _skip_if_disabled("listing_create_full")
    body = _post_agent(
        client,
        {
            "mode": "listing_create_full",
            "input": "20 chocolate croissants, baked this morning, store closes at 6 PM today, retail $4.50 each",
        },
    )
    data = body["data"]
    assert data["mode"] == "listing_create_full"
    assert data["status"] in {"published", "blocked_by_moderation"}

    # All four nodes must have run.
    assert data.get("listing", {}).get("listing_id", "").startswith("req_")
    assert "approved" in (data.get("moderation") or {})
    assert (data.get("pricing") or {}).get("recommended_price", 0) > 0

    # When moderation approves, the publish node stamps a published_listing_id.
    if data["status"] == "published":
        published = data.get("published") or {}
        assert published.get("published_listing_id", "").startswith("pub_")
