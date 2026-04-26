# SurplusAS → Google Cloud + ADK 2.0 Migration (Track 3)

**Contest deadline:** 2026-06-05 17:00 PT  ·  **Judging window:** 2026-06-11 → 2026-06-18

> **Status as of 2026-04-26 — Migration complete.**
> v1.0 (Fly.io, `surplusas-api-dev.fly.dev`) was decommissioned ahead of the contest deadline.
> Final commit archived under git tag `v1.0-fly` in the legacy repo.
> All traffic — demo and (vestigial) partner — now resolves to v2.0 on Cloud Run.
> The marketing site (`PS2O Website3`) was repointed to the Cloud Run demo URL on the same day.

## Context

SurplusAS is competing in the **Google for Startups AI Agents Challenge — Track 3 ("Refactor for Google Cloud Marketplace & Gemini Enterprise")**. The track mandates: B2B focus, cloud-native runtime on Google Cloud, Vertex-powered intelligence, and A2A protocol interoperability.

The current SurplusAS Agent API runs on Fly.io as a monolithic FastAPI service that dispatches eight agent modes against a Google AI Gemini endpoint via an OpenAI-compatible client. SQLite stores partner keys and outcomes. None of this satisfies Track 3 as-is.

**Posture:** Real production migration with the contest as a forcing function — not throwaway prize theatre. After June 5, SurplusAS continues to run on the new stack. No shortcuts we'd have to undo. Boundaries are drawn where there's a real architectural seam, not where they look good in a diagram.

**Note on the rules:** The "New Projects Only" clause is in tension with Track 3's "refactor your existing agent" framing. Proceeding without emailing Devpost; the rebuild is substantively new code (new framework, new architecture, new runtime, new persistence) even where prompts and schemas carry over.

## Target architecture

```
                ┌─────────────────┐
                │ Partners + Demo │
                │  (REST clients) │
                └────────┬────────┘
                         │  POST /v1/agent  (Bearer auth, backward-compatible)
                         ▼
              ┌────────────────────────┐         A2A          ┌────────────────────┐
              │   Listing Service      │ ◄──────────────────► │ Compliance Service │
              │  (ADK 2.0 root agent)  │                      │  (moderate)        │
              │                        │ ◄──────────────────► ├────────────────────┤
              │  - listing_create      │         A2A          │  Pricing Service   │
              │  - listing_enhance     │                      │  (pricing_optimize │
              │  - listing_batch       │                      │   + grounding)     │
              │  - search_interpret    │                      └─────────┬──────────┘
              │  - customer_assist     │                                │
              │  - translate (tool)    │                                │
              │  - graph: intake →     │                                ▼
              │    moderate → price →  │                       ┌────────────────────┐
              │    translate → publish │                       │ historical_sales   │
              └───────────┬────────────┘                       │ (Cloud SQL table)  │
                          │                                    └────────────────────┘
                          ▼
                 ┌──────────────────┐
                 │ Cloud SQL Postgres│
                 │  - partner_keys   │
                 │  - outcomes       │
                 │  - historical_sales│
                 └──────────────────┘
```

**Decisions locked in:**

| Area | Choice |
|---|---|
| Track | Track 3 only |
| GitHub home | PS2O organization (production-owned namespace) |
| Framework | ADK 2.0 Beta (hybrid posture: isolate ADK-version-specific code so 1.x is a viable downgrade if 2.0 blocks us mid-build) |
| Runtime | Cloud Run (one service per agent) |
| LLM | Vertex AI Gemini (replaces direct Google AI usage; required for $500 credits) |
| Inter-agent | A2A protocol (ADK-native), IAM-authenticated service-to-service |
| Persistence | Cloud SQL Postgres (single `db-f1-micro` instance, both services connect via Cloud SQL Auth Proxy) |
| Public API | Backward-compatible. Listing Service keeps `POST /v1/agent` with `mode`. Compliance + Pricing also expose A2A endpoints for external enterprise discovery. |
| Persistence migration | Greenfield — only the demo `partner_keys` row needs to seed; outcomes start empty |

## Repo layout (new)

```
services/
  listing/
    agent.py            # ADK root agent + graph workflow
    api.py              # Backward-compat REST surface (POST /v1/agent etc.)
    tools/
      translate.py      # translate as a function tool
      publish.py        # listing publish wrapper
    graph.py            # ADK 2.0 graph: intake → moderate → price → translate
  compliance/
    agent.py            # moderate
    a2a.py              # A2A server endpoint
  pricing/
    agent.py            # pricing_optimize with grounding
    a2a.py
    grounding.py        # historical sales lookup, demand signals
shared/
  schemas.py            # Pydantic — ported from app/schemas.py
  prompts/              # System v2.1 + 8 mode prompts — ported from app/prompt.py
  db.py                 # Postgres adapter — replaces app/database.py
  auth.py               # Bearer token auth — ported from app/auth.py
  config.py             # Env + valid enums — ported from app/config.py
  adk_compat.py         # Thin wrapper isolating ADK 2.0-specific calls (hybrid hedge)
infra/
  terraform/            # GCP provisioning (or gcloud scripts if simpler)
  cloudbuild/
    listing.yaml
    compliance.yaml
    pricing.yaml
static/                 # Reuse existing demo HTML + samples; swap base URL
.github/workflows/
  cloud-run-deploy.yml  # Replaces fly-deploy.yml
```

## Migration phases

### Phase 1 — Repository migration to PS2O GitHub

- Tag the final Fly.io-era commit (`v1.0-fly`) before further changes for archeological clarity.
- Transfer or recreate the SurplusAS repository under the `PS2O` GitHub organization so the production codebase lives in the company-owned namespace before the rebuild begins.
- Update local git remotes (`git remote set-url origin git@github.com:PS2O/<repo>.git`).
- Transfer GitHub Actions secrets, branch-protection rules, collaborators, and any deploy keys.
- Update `README.md`, `CLAUDE.md`, and any project-config references that pointed at the prior repo URL.

### Phase 2 — GCP foundation + ADK hello-world

- Create GCP project; enable APIs: Vertex AI, Cloud Run, Cloud SQL Admin, Artifact Registry, Cloud Build, IAM.
- Request $500 startup credits via the contest path.
- Provision Cloud SQL Postgres `db-f1-micro` (single instance); create database; port the two-table schema from `app/database.py:partner_keys` and `outcomes`; add a third table `historical_sales` (seeded with synthetic data for the Pricing Service demo).
- Create three service accounts (one per future Cloud Run service); grant minimum IAM (Vertex AI User, Cloud SQL Client, plus A2A-caller roles between peers).
- Local: `pip install google-adk --pre`. Stand up a "hello, listing_create" ADK agent that hits Vertex AI Gemini with one of the existing prompts and returns valid JSON. Validates the framework + model + auth path before investing in structure.

### Phase 3 — Listing Service core

- Scaffold three-service repo layout (`services/listing`, `services/compliance`, `services/pricing`, `shared/`).
- Build `shared/` first: port `app/schemas.py` → `shared/schemas.py`, `app/prompt.py` → `shared/prompts/`, `app/auth.py` → `shared/auth.py`, `app/config.py` → `shared/config.py`. Replace `app/database.py` with `shared/db.py` using `asyncpg` + Cloud SQL Auth Proxy.
- Listing Service: ADK 2.0 root agent + `services/listing/api.py` exposing backward-compatible `POST /v1/agent`. Wire up `listing_create` end-to-end (image input handling is the riskiest piece — Vertex AI's image format differs from the OpenAI `image_url` shape used today).
- First Cloud Run deploy of Listing Service. Verify the merchant-demo HTML works against the deployed URL by changing one base URL.

### Phase 4 — Compliance + Pricing + A2A

- ✅ Compliance Service: `moderate` ported, ADK 2.0 agent, private Cloud Run with IAM-only A2A.
- ✅ Pricing Service: `pricing_optimize` ported with `services/pricing/grounding.py` reading `historical_sales` for demand signals. Private Cloud Run with IAM-only A2A.
- ✅ Listing Service fans `moderate` and `pricing_optimize` modes out via A2A (IAM-authed Google ID tokens, audience-scoped, cached 50 min).
- ✅ ADK 2.0 graph workflow inside Listing Service (`services/listing/pipeline.py`): `listing_create_full` mode runs a `Workflow` with four `FunctionNode`s — intake (local) → moderate (A2A) → price (A2A) → publish (local) — driven by `Runner.run_async(node=workflow)` against a state-seeded session. End-to-end verified: a single merchant request returns the chained intake + moderation + pricing + `published_listing_id`. `translate` deferred to Phase 5 since it's tool-shaped, not graph-shaped.

### Phase 5 — Remaining modes + grounding + observability

- ✅ All listing-owned modes ported and verified end-to-end on Cloud Run: `listing_enhance`, `listing_batch`, `search_interpret`, `customer_assist`, `translate`. The mode-agnostic `run_listing_mode` dispatcher + `build_mode_prompt` in `shared/prompts/system.py` cover all eight modes. `translate` ships as a mode for now; converting it to an in-graph function tool is a future polish item, not a contest blocker.
- ✅ Pricing Service grounding hardened: `category_from_input` now extracts the category from JSON, `key: value` lines, OR a bare keyword scan over the nine valid categories. `_grounding_used: True` confirmed for the workflow's plain-text listing summary.
- ✅ OpenTelemetry tracing across A2A: `shared/tracing.py` configures a `CloudTraceSpanExporter` with `SimpleSpanProcessor` (Cloud Run idle pauses kill BatchSpanProcessor's daemon thread). FastAPI middleware on each service extracts/creates W3C `traceparent`; `shared/a2a.py` injects it into the outbound httpx call. Verified: a single `listing_create_full` request produces a 26-span trace in Cloud Trace spanning `surplusas_listing` → `surplusas_compliance` → `surplusas_pricing`, with ADK-emitted `invoke_workflow` / `invoke_node` / `invoke_agent` / `call_llm` spans nested correctly.
- ✅ Public demo: `static/surplusas-merchant-demo.html` served from Cloud Run at `/demo` with a key-free `/demo/v1/*` proxy. End-to-end smoke test: `mode=listing_create` returns full ListingCreateResponse, sample images served from `/demo/samples/*.webp`.

### Phase 6 — Tests + production polish

- ✅ `tests/smoke_test_modes.py` — 10 pytest cases hit the deployed Cloud Run URL: `/health`, all eight agent modes (including A2A-fanned `moderate` and `pricing_optimize`), and the full `listing_create_full` ADK 2.0 graph workflow. Each asserts response shape (success, mode, key fields per schema). 10/10 passing in ~90s. Skip individual modes via `SURPLUSAS_SKIP=mode1,mode2`. Re-target a different deployment via `SURPLUSAS_BASE_URL=...`. `pytest.ini` registers the `smoke_test_*.py` pattern so pytest discovers the file.
- ✅ README.md refreshed with a Mermaid architecture diagram, deployed URLs, repo layout, local-run instructions, smoke-test invocation, and deploy commands. Suitable for the Devpost submission link.
- ✅ Production cutover for partner traffic completed 2026-04-26 — well ahead of the contest window. v1.0 (Fly.io) had only the seeded `demo_001` key in production, so cutover was a website-link repoint plus suspending the Fly app (`surplusas-api-dev`). The legacy repo is archived under tag `v1.0-fly`. Final destroy of the suspended Fly app is pending an explicit decision (kept suspended for now to preserve the app name and allow fast rollback if needed).

### Phase 7 — Submission

- ✅ Devpost write-up drafted in [`DEVPOST.md`](./DEVPOST.md) — Inspiration / What it does / How we built it / Challenges / Accomplishments / What we learned / What's next / Built with, plus a copy-paste curl and the live demo URL. Ready to paste into the Devpost submission form.
- ✅ 2-minute demo video shot list in [`DEMO_VIDEO_SCRIPT.md`](./DEMO_VIDEO_SCRIPT.md) — pre-record checklist, second-by-second narration timed to the demo flow, on-screen captions, editing notes, and final pre-upload checklist. (Recording the actual video is a one-shot human task.)
- ⏳ **Action required by user**:
  1. Record the 2-minute video per the script and upload to YouTube as Unlisted.
  2. Paste `DEVPOST.md` content into Devpost form, attach repo URL + video URL.
  3. Submit by **June 5, 17:00 PT** (hard contest deadline).

## Critical files to modify or create

**New:**
- `services/listing/agent.py`, `services/listing/api.py`, `services/listing/graph.py`, `services/listing/tools/translate.py`
- `services/compliance/agent.py`, `services/compliance/a2a.py`
- `services/pricing/agent.py`, `services/pricing/a2a.py`, `services/pricing/grounding.py`
- `shared/db.py` (Postgres replacement for `app/database.py`)
- `shared/adk_compat.py` (ADK 2.0 / 1.x abstraction layer — the 1.x downgrade hedge)
- `infra/terraform/` (project, services, IAM, Cloud SQL)
- `.github/workflows/cloud-run-deploy.yml`
- `tests/smoke_test_modes.py`

**Port from existing (with light edits):**
- `app/prompt.py` → `shared/prompts/` (system v2.1 + 8 mode prompts; the prompts themselves are reusable)
- `app/schemas.py` → `shared/schemas.py` (Pydantic models — most fields unchanged, drop OpenAI-specific shapes)
- `app/config.py` → `shared/config.py` (`VALID_MODES`, temperature map, default partner context)
- `app/auth.py` → `shared/auth.py` (Bearer pattern; same logic, new DB)
- `static/surplusas-merchant-demo.html` (keep entirely; only swap base URL constant)
- `static/demo/samples/*.webp`, `manifest.json` (reuse as-is)

**Retire after cutover:**
- `app/agent.py` (replaced by ADK agents)
- `app/database.py` (replaced by `shared/db.py`)
- `app/main.py`, `app/routes/*` (replaced by per-service `api.py`)
- `fly.toml`, `.github/workflows/fly-deploy.yml` (replaced by GCP equivalents)
- `Dockerfile` (replaced by per-service Dockerfiles)

## Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| ADK 2.0 Beta breaking change mid-build | Medium | All ADK-version-specific calls go through `shared/adk_compat.py`. Lock to a known-good `pip install google-adk==X.Y.Z --pre` once a working baseline exists. 1.x downgrade path documented. |
| A2A protocol rough edges in 2.0 | Medium | If A2A primitives are blocking, fall back to direct Cloud Run-to-Cloud Run HTTPS with IAM auth and a thin A2A-shaped envelope. The judging rubric cares about A2A intent and architecture; a clean implementation of the protocol's surface is what matters. |
| Vertex AI image input format differs from OpenAI | High | Validate image upload + processing in Phase 2's hello-world. This is the first thing to break in `listing_create`. |
| Cloud Run cold starts + Cloud SQL Auth Proxy latency | Low | Set `min-instances=1` on Listing Service in production. Compliance and Pricing can scale-to-zero. |
| Scope too large to ship before submission deadline | High | Each phase is independently demoable. If forced to cut, drop `listing_batch`, `customer_assist`, and `search_interpret` from the demo; the merchant write path (create → moderate → price → translate → publish) is the judging-critical flow. |
| GCP setup delays (credit approval up to 72 business hours) | Low | Request credits on Phase 2 Day 1; the project itself is creatable immediately and Vertex AI on a billing-enabled account works without credits in place. |

## Verification

**Local:**
- `adk web` (or equivalent) per service for interactive agent inspection.
- `pytest tests/smoke_test_modes.py` against `localhost:808x` for each service.

**Deployed:**
- `curl -X POST https://listing-XXX.a.run.app/v1/agent -H "Authorization: Bearer sk_demo_surplus_2026" -d '{"mode":"listing_create",...}'` returns valid JSON with `outcome_tracking` populated server-side.
- A2A trace: trigger `mode=moderate` via Listing front door, verify Cloud Logging shows the request hopping Listing → Compliance with a shared trace ID and IAM-authenticated call.
- Pricing grounding: `mode=pricing_optimize` returns a price that varies based on `historical_sales` rows, not a fixed-temperature hallucination.
- End-to-end: merchant-demo HTML at the new URL completes the full flow (image → listing → publish), visually identical to the current Fly.io demo.

**Submission readiness:**
- Public PS2O GitHub repo with the new repo layout pushed.
- Architecture diagram (this document's diagram, exported as PNG/SVG).
- 2-minute demo video showing the full graph workflow with A2A trace overlay.
- Devpost write-up: problem statement, architecture, ADK 2.0 features used (graph workflow, collaborative agents, A2A), Vertex AI grounding for Pricing, deployment story.
