# SurplusAS Agent API — Devpost write-up

**Track:** Track 3 — Refactor for Google Cloud Marketplace & Gemini Enterprise
**Submitter:** PS2O (Public Sustainability 2.0)
**Repo:** <https://github.com/PS2O-Mitch/SurplusAS-API-2.0>
**Live demo:** <https://listing-service-70904707890.us-central1.run.app/demo>
**API docs:** <https://listing-service-70904707890.us-central1.run.app/docs>

---

## Inspiration

Roughly a third of food produced globally is wasted. Grocers, bakeries, and prepared-meal sellers throw away tons of perfectly good inventory every night because the operational overhead of listing it for surplus sale — writing copy, picking categories, setting discounts, complying with allergen rules, translating for diverse customer bases — exceeds the marginal margin they'd recover.

SurplusAS is the autonomous agent layer that closes that gap. A merchant uploads a photo and a one-line note ("20 chocolate croissants, store closes 6 PM"); SurplusAS produces a complete, compliant, optimally-priced, multilingual listing and publishes it. The merchant never touches a form.

The v1.0 of SurplusAS shipped to Fly.io as a single FastAPI service that called Gemini through an OpenAI-compatible client and persisted to SQLite. It worked, but it was unsuitable for enterprise: no observability, no service isolation, no path to multi-tenant marketplace listing, no real grounding. Track 3's framing — "refactor for Google Cloud Marketplace & Gemini Enterprise" — is exactly the rebuild the product needed anyway. The contest became the forcing function.

## What it does

A single backward-compatible front door (`POST /v1/agent`) accepts a `mode` and merchant input; behind it, three Cloud Run services collaborate via Google's Agent-to-Agent (A2A) protocol:

- **Listing Service** (public) — coordinator. Owns merchant-facing modes: `listing_create`, `listing_enhance`, `listing_batch`, `search_interpret`, `customer_assist`, `translate`. Hosts an ADK 2.0 graph workflow.
- **Compliance Service** (private, IAM-only) — listing safety / moderation. Reachable only as an A2A peer.
- **Pricing Service** (private, IAM-only) — dynamic discount recommendations. Grounds on a `historical_sales` Cloud SQL table for time-of-day and category-aware demand patterns.

The flagship feature is `mode=listing_create_full`. One merchant request runs an autonomous four-node graph: **intake** (local listing agent) → **moderate** (A2A to Compliance) → **price** (A2A to Pricing, with Cloud SQL grounding) → **publish**. The merchant gets back a complete, moderated, priced, published listing with one HTTP call. ADK 2.0's `Workflow` orchestrates the chain; A2A handles inter-service auth via audience-scoped Google ID tokens.

A live `/demo` page lets anyone exercise the end-to-end flow without an API key — the demo proxy injects partner context server-side and shares the same dispatcher as production traffic, so what you see on the demo is exactly what a paying partner gets.

## How we built it

**Three Cloud Run services from one Docker image.** Each service is a FastAPI app sharing a `shared/` package; the same image is reused for all three deployments and `SERVICE_MODULE` env var picks the entry point. Build SA, runtime SAs, and IAM bindings are scripted via `gcloud`.

**ADK 2.0 graph workflow.** `services/listing/pipeline.py` builds a real `google.adk.workflow.Workflow` of four `FunctionNode`s wired by `Edge`s. Driven through `Runner.run_async(node=workflow, ...)` against a state-seeded session. We chose `SimpleSpanProcessor` over `BatchSpanProcessor` after watching spans get dropped on the floor — Cloud Run's idle-pause kills the batch processor's daemon thread.

**A2A with IAM auth.** `shared/a2a.py` mints Google ID tokens whose audience matches the target service URL, caches them per-audience for 50 minutes, and POSTs `AgentRequest` JSON. The peer service trusts Cloud Run's IAM check; there is no per-tenant Bearer at the A2A layer.

**Cloud SQL + grounding.** Postgres 15 (`db-f1-micro`), connected via the Cloud SQL Python Connector with the asyncpg driver. The Pricing Service runs three SQL aggregations per request (mean sold price, peak hours, peak days for the inferred category) and prepends a compact grounding block to the LLM prompt. Result: pricing reasoning explicitly cites the historical mean rather than guessing.

**Backward compatibility.** v1.0 partners (and the existing merchant-demo HTML) call `POST /v1/agent` with the same Bearer header and the same request shape. Modes that have moved to peer services (`moderate`, `pricing_optimize`) are fanned out by the Listing Service transparently.

**Observability across A2A.** `shared/tracing.py` registers a `CloudTraceSpanExporter` and a FastAPI middleware on each service. The middleware extracts the inbound W3C `traceparent`; the A2A client wraps each peer call in a CLIENT span and injects `traceparent` outbound. A single `listing_create_full` request shows up in Cloud Trace as one trace with ~26 spans across all three services, with ADK's auto-instrumented `invoke_workflow`/`invoke_node`/`invoke_agent`/`call_llm` nested correctly.

**Smoke tests.** `tests/smoke_test_modes.py` is ten pytest cases that hit the deployed Cloud Run URL with one fixture per mode plus the full pipeline. 10/10 pass in ~90 seconds. The tests catch Vertex AI prompt-format drift, ADK upgrades, and peer-service deploys — none of which a unit test would.

## Challenges we ran into

- **ADK 2.0 Beta moved fast.** We pinned `google-adk==2.0.0b1` to lock against a known-good baseline. ADK-specific calls live in dedicated modules so the pin is reversible if 2.0 ships breakages. The `Workflow` API surface (`FunctionNode`, `Edge`, `START`, `Runner.run_async(node=...)`) was new to us; figuring out the right state-binding pattern (we use `parameter_binding='state'` with a session pre-seeded at `create_session(state=...)`) took a couple of iterations.
- **`gcloud run deploy --set-env-vars` is destructive.** The first Phase 4d deploy stripped `CLOUD_SQL_INSTANCE`, `DB_NAME`, and other essentials from the listing-service revision because `--set-env-vars` *replaces* the env. We learned (the hard way) to always use `--update-env-vars` and saved the lesson to a memory file we keep across sessions.
- **Cloud Run + `BatchSpanProcessor` = silent span loss.** Spans were created with valid trace IDs but never landed in Cloud Trace. The cause: `BatchSpanProcessor` flushes via a daemon thread that gets paused when Cloud Run idles the instance. Switching to `SimpleSpanProcessor` (synchronous flush per span) fixed it without measurable latency cost.
- **Pricing grounding silently no-op'd.** Our category extractor only parsed JSON, but the workflow's pipeline sends a plain-text listing summary (`title: ...\ncategory: bakery\n...`). `_grounding_used: False` was the only signal. We made the extractor try JSON, then a `category: <value>` regex, then a bare-keyword scan over the nine valid categories — all three patterns now exercise the historical-sales path.
- **Org-policy domain restrictions.** `constraints/iam.allowedPolicyMemberDomains` blocked granting `allUsers` invoker on Cloud Run, so the public demo couldn't reach the deployed service. Resolved by overriding the constraint at the project scope.
- **JSONB returned as string from asyncpg.** `partner_context` came out of Postgres as a JSON string, not a dict. The auth path failed on `dict.update` until we added a `json.loads` guard in the partner lookup.

## Accomplishments that we're proud of

- **Real production migration, not a contest-only artifact.** SurplusAS continues to run on this stack after the contest. No throwaway code, no shortcuts to undo.
- **One merchant request → one Cloud Trace, three services, 26 spans.** The multi-agent claim is verifiable, not narrative. We can show judges the trace tree.
- **`listing_create_full` autonomous flow.** A single API call produces a moderated, priced, published listing — the framing the contest asks for, executed cleanly with ADK 2.0's flagship `Workflow` primitive.
- **Backward compatibility kept.** v1.0 partners and the merchant-demo HTML didn't have to change. Same Bearer auth, same `POST /v1/agent`, same request schema.
- **Live, key-free demo.** `/demo` is reachable from any browser. No login. No setup. Click and watch the chain run.
- **Ten passing smoke tests against the deployed URL** in 90 seconds. Schema drift gets caught before it reaches partners.

## What we learned

- **A2A as IAM-authed Cloud Run is enough.** We don't need a separate A2A control plane to get the value: audience-scoped ID tokens + service URLs + an `AgentRequest`-shaped body is the entire protocol. Inter-agent discoverability comes for free from Cloud Run's service registry.
- **State-binding beats node-input chaining for graph workflows.** Threading a single dict through every `FunctionNode` made the graph harder to extend. Seeding session state once at workflow start and letting each node read its inputs by parameter name turned out to be cleaner — closer to how a human would write the same orchestration.
- **Grounding has to be measurable.** Without `_grounding_used: True` in the response, we couldn't tell whether the historical-sales aggregations were firing. Surface the signal.
- **Cloud Trace's auto-instrumentation of ADK 2.0 is excellent.** We added one middleware and one CLIENT span per A2A call; ADK gave us `invoke_workflow`, `invoke_node`, `invoke_agent`, `call_llm`, and `generate_content gemini-2.5-flash` for free.

## What's next for SurplusAS

- **Convert `translate` from a mode to an in-graph ADK function tool** so listings can be auto-translated for the merchant's target audiences as part of `listing_create_full`.
- **Vertex AI Search over `historical_sales`** for richer demand grounding — current SQL aggregations work but flatten signal across stores and seasons.
- **DNS cutover.** The merchant demo is already on Cloud Run; partner Bearer-token traffic stays on v1.0 (Fly.io) until after judging, then swaps via DNS.
- **Marketplace listing.** Track 3's framing implies eventual Google Cloud Marketplace publication — service-level pricing, terms-of-service, and a tenant-isolation review pass.
- **Compliance regional packs.** Today's Compliance Service is US-defaults; EU and CA regulatory packs are next.

## Built with

`python` `fastapi` `pydantic` `google-cloud-run` `google-cloud-sql` `vertex-ai` `gemini` `google-adk-2.0` `agent-to-agent-protocol-a2a` `cloud-trace` `opentelemetry` `cloud-build` `secret-manager` `artifact-registry` `iam` `pytest` `docker` `httpx` `asyncpg`

## Try it

```bash
curl -X POST https://listing-service-70904707890.us-central1.run.app/v1/agent \
  -H "Authorization: Bearer sk_demo_surplus_2026" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "listing_create_full",
    "input": "20 chocolate croissants, baked this morning, store closes 6 PM today, retail $4.50 each"
  }'
```

Or open <https://listing-service-70904707890.us-central1.run.app/demo> in a browser.
