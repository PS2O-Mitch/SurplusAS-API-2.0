# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SurplusAS Agent API v2.0 — three Cloud Run services (Listing, Compliance, Pricing) wired together by Google ADK 2.0 + the A2A protocol, backed by Cloud SQL Postgres and Vertex AI Gemini. Track 3 entry for the Google for Startups AI Agents Challenge. The full plan, decisions, and phase status live in `TRACK3_MIGRATION_PLAN.md`; the deployed-URL overview lives in `README.md`.

## Common commands

```bash
# Setup
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/pip install pytest          # not in requirements (not in the runtime image)
gcloud auth application-default login     # ADC for Vertex AI + Cloud SQL Connector

# Run a single service locally (swap module for compliance/pricing)
.venv/Scripts/uvicorn services.listing.api:app --port 8080 --reload

# Smoke tests (hit DEPLOYED Cloud Run URL by default, ~90s, real LLM calls)
.venv/Scripts/pytest tests/
.venv/Scripts/pytest tests/ -k pricing_optimize -v
SURPLUSAS_BASE_URL=https://other.run.app pytest tests/   # re-target
SURPLUSAS_SKIP=listing_batch,customer_assist pytest tests/  # skip slow modes

# Deploy (same image, three services — only SERVICE_MODULE differs)
gcloud run deploy listing-service    --source . --update-env-vars SERVICE_MODULE=services.listing.api    ...
gcloud run deploy compliance-service --source . --update-env-vars SERVICE_MODULE=services.compliance.api ...
gcloud run deploy pricing-service    --source . --update-env-vars SERVICE_MODULE=services.pricing.api    ...
```

## Architecture, the parts that aren't obvious from a single file

**One image, three services.** `Dockerfile` builds a single image whose `CMD` runs `uvicorn ${SERVICE_MODULE}:app`. Deploy-time `SERVICE_MODULE` env var picks which service this container becomes. Don't add per-service Dockerfiles unless the runtimes diverge.

**Mode routing.** `POST /v1/agent` is the only public surface (Listing Service). The handler in `services/listing/api.py` either runs the mode locally (anything in `LISTING_SERVICE_MODES` from `shared/config.py`) or fans it out via A2A — `moderate` → Compliance, `pricing_optimize` → Pricing — keyed off `COMPLIANCE_SERVICE_URL` / `PRICING_SERVICE_URL` env vars. Compliance and Pricing each expose the same `/v1/agent` shape but reject anything outside their owned mode.

**`listing_create_full` is the ADK 2.0 graph workflow**, not a regular mode. `services/listing/pipeline.py` builds a `Workflow` of `FunctionNode`s wired with `Edge`s (intake → moderate → price → publish). Intake runs the local listing agent; moderate and price fan out over A2A; publish stamps a `published_listing_id` if approved. Nodes share data via `ctx.state` keys (`listing`, `moderation`, `pricing`).

**A2A auth, locally.** `shared/a2a.py` mints a Google ID token whose audience is the target service URL and caches it 50 minutes. Plain user ADC **cannot** mint audience-scoped ID tokens — local A2A requires an attached service account or `gcloud auth application-default login --impersonate-service-account=<sa>`.

**Tracing across services.** `shared/tracing.py` configures one `TracerProvider` per service with a `CloudTraceSpanExporter`. Uses `SimpleSpanProcessor`, **not** `BatchSpanProcessor` — Cloud Run pauses idle instances and the batcher's daemon thread drops spans on the floor. FastAPI middleware extracts inbound W3C `traceparent`; `a2a_client_span` injects it into outbound httpx headers. A single `listing_create_full` request shows up as one ~26-span trace across all three services.

**Vertex AI env must be set before any `google.adk`/`google.genai` import.** `shared/config.py` does `os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")` etc. at module load. Service entry points (`services/*/api.py`) import `shared.config` *before* importing `.agent` for this reason — preserve that order.

**Cloud SQL access.** `shared/db.py` uses the Cloud SQL Python Connector (not a separate `cloud-sql-proxy` process), authenticated via ADC locally and the attached SA on Cloud Run. Singleton connector + asyncpg pool for the process lifetime.

**Server-side overwrites.** Each service's `_apply_server_overwrites` stamps `outcome_tracking.agent_version` / `model_used` / `inference_timestamp` on every parsed model response. The listing variant additionally regenerates placeholder `listing_id`s and rounds prices to the nearest $0.25. If you add a mode that returns money or IDs, route it through this helper.

**Auth.** Bearer tokens are validated against the `partner_keys` Cloud SQL table (`shared/auth.py`), with a process-local cache. `invalidate_cache()` exists for key rotation; call it if you mutate the table from another process.

## Deploy gotcha — read before touching `gcloud run deploy`

**Always `--update-env-vars` (additive), never `--set-env-vars` (full replacement).** The latter wipes `CLOUD_SQL_INSTANCE`, `COMPLIANCE_SERVICE_URL`, `PRICING_SERVICE_URL`, and friends, taking the service down silently until the next deploy. This is documented in README too — repeating because it's the easiest way to break production.

## Tests

`tests/` is smoke-only — pytest hits the deployed Cloud Run URL with a fixture per mode and asserts response shape. There are no unit tests; the migration's verification model is "real LLM call, real Vertex, real A2A hop, real DB" because contract drift from any of those is what the suite is paid to catch. `pytest.ini` registers the `smoke_test_*.py` discovery pattern. Default `SURPLUSAS_BASE_URL` and Bearer key in `tests/conftest.py` point at the canonical demo deployment.

## Repo layout

```
shared/                  schemas, auth, config, db (Cloud SQL Connector + asyncpg),
                         a2a (ID-token-authed peer client), tracing, prompts/
services/listing/        Public service. api.py (FastAPI), agent.py (run_listing_mode),
                         pipeline.py (ADK 2.0 graph), demo.py (key-free /demo proxy)
services/compliance/     Private. moderate-only ADK agent + /v1/agent
services/pricing/        Private. pricing_optimize ADK agent + grounding.py
                         (queries historical_sales for demand-aware discounts)
static/                  Merchant demo HTML + WebP samples, served from /demo
tests/                   Smoke pytest suite hitting the deployed URL
Dockerfile               One image, switched between services via SERVICE_MODULE
TRACK3_MIGRATION_PLAN.md Canonical plan / phase status / risks
```
