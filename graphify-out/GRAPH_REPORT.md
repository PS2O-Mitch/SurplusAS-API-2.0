# Graph Report - .  (2026-04-26)

## Corpus Check
- 0 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 366 nodes · 557 edges · 28 communities detected
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 136 edges (avg confidence: 0.79)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]

## God Nodes (most connected - your core abstractions)
1. `Mixed Inventory Photo` - 16 edges
2. `Refrigerated Produce Display` - 12 edges
3. `_post_agent helper` - 11 edges
4. `Bakery Category` - 11 edges
5. `Glass Bakery Display Case` - 11 edges
6. `Bento Boxes (Plastic Containers)` - 11 edges
7. `run_listing_mode()` - 10 edges
8. `AgentResponse` - 10 edges
9. `_skip_if_disabled()` - 10 edges
10. `_post_agent()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Vertex AI Image Format Differs From OpenAI (risk)` --rationale_for--> `run_listing_mode dispatcher`  [INFERRED]
  TRACK3_MIGRATION_PLAN.md → services/listing/agent.py
- `test_pricing_optimize_via_a2a` --semantically_similar_to--> `a2a_client_span()`  [INFERRED] [semantically similar]
  tests/smoke_test_modes.py → shared\tracing.py
- `Three Cloud Run Services Architecture` --references--> `Listing Service FastAPI App`  [EXTRACTED]
  README.md → services/listing/api.py
- `Greenfield Persistence (no v1 outcomes migration)` --rationale_for--> `db_init schema + demo partner seed`  [INFERRED]
  TRACK3_MIGRATION_PLAN.md → shared/db_init.py
- `Phase 4d ADK 2.0 Graph Workflow` --references--> `LISTING_PIPELINE Workflow (intake->moderate->price->publish)`  [EXTRACTED]
  TRACK3_MIGRATION_PLAN.md → services/listing/pipeline.py

## Hyperedges (group relationships)
- **ADK 2.0 Graph Workflow Pipeline** — listing_pipeline_intake_node, listing_pipeline_moderate_node, listing_pipeline_price_node, listing_pipeline_publish_node, listing_pipeline_workflow [EXTRACTED 1.00]
- **A2A IAM-Authenticated Peer Call Chain** — shared_a2a_call_peer_agent, shared_a2a_token_cache, compliance_api_app, pricing_api_app [EXTRACTED 1.00]
- **Cloud SQL Persistence Layer (3 tables)** — shared_db_pool, concept_partner_keys_table, concept_historical_sales_table, shared_db_init_main, shared_seed_historical_sales [EXTRACTED 1.00]
- **hyper_smoke_modes_share_post_agent** —  [EXTRACTED 1.00]
- **hyper_tracing_pipeline** —  [EXTRACTED 1.00]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (48): run_moderate (Compliance ADK agent), Compliance Service FastAPI App, historical_sales Cloud SQL table, listing_create_full End-to-End Flow, partner_keys Cloud SQL table, _apply_server_overwrites (price quarter rounding), run_listing_mode dispatcher, Singleton Runner + InMemorySessionService (+40 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (34): call_peer_agent(), _fetch_id_token(), Agent-to-Agent (A2A) client for IAM-authenticated Cloud Run peers.  Each call mi, POST `body` to a peer Cloud Run service and return the parsed JSON.      Raises, agent_endpoint(), health(), _peer_url_for(), Pricing Service — A2A endpoint over IAM-authenticated Cloud Run.  Mirror of the (+26 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (26): invalidate_cache(), _lookup(), Bearer-token auth backed by Cloud SQL `partner_keys`.  The lookup is cached for, Clear the auth cache (e.g., after rotating a partner key)., Validate Bearer token against partner_keys and return the partner record., verify_bearer(), acquire(), close_pool() (+18 more)

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (28): value_error_handler(), BaseModel, Enum, AgentMode, AgentRequest, DietaryAttributes, DietaryRequirements, IdentifiedItem (+20 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (23): _apply_server_overwrites(), _build_agent(), _decode_image(), get_runner(), SurplusAS Pricing Service — ADK 2.0 agent for `pricing_optimize`.  Pulls demand-, Run a listing-service mode against ADK 2.0 + Vertex AI Gemini.      Returns a pa, Return (bytes, mime_type) from a base64 string with optional data-URL prefix., Run a moderation review and return the parsed JSON dict. (+15 more)

### Community 5 - "Community 5"
Cohesion: 0.15
Nodes (23): Business Signal: Deli/Bakery Surplus, Business Signal: End-of-Day Markdown Candidate, Bakery Category, Prepared Food Category, End-of-Day Bakery Surplus Decision, Surplus Markdown Listing, Glass Bakery Display Case, Focaccia with Cherry Tomatoes and Basil (+15 more)

### Community 6 - "Community 6"
Cohesion: 0.15
Nodes (21): A2A protocol (peer-to-peer agent calls), ADK 2.0 graph workflow (intake->moderate->price->publish), POST /v1/agent (Listing Service), W3C traceparent propagation, _post_agent helper, _skip_if_disabled helper, test_customer_assist, test_listing_batch (+13 more)

### Community 7 - "Community 7"
Cohesion: 0.18
Nodes (18): Prepared Meals (Mixed Cuisine), Mixed Inventory Photo, Sesame Bagel, Couscous with Mushrooms, Indian Curry Platter (multi-compartment), Dessert Cake Slice, Falafel Bowl with Pickled Vegetables, Greek Salad with Feta and Olives (+10 more)

### Community 8 - "Community 8"
Cohesion: 0.25
Nodes (15): _post_agent(), End-to-end smoke tests against the deployed Listing Service.  One test per agent, `moderate` is owned by Compliance — Listing fans out via A2A., `pricing_optimize` is owned by Pricing — Listing fans out via A2A., Phase 4d: ADK 2.0 graph workflow chains intake → moderate → price → publish., _skip_if_disabled(), test_customer_assist(), test_listing_batch() (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (17): Bento Boxes (Plastic Containers), Business Signal: Markdown / Redistribution Candidate, Business Signal: Unsold Surplus Risk (End-of-Day), Cuisine: Japanese Bento, Category: Prepared Meal / Ready-to-Eat, Freshness: Same-Day / Short Shelf Life, Grilled Salmon with Lemon, Printed Ingredient Label (+9 more)

### Community 10 - "Community 10"
Cohesion: 0.17
Nodes (16): Bok Choy, Business Signal: Grocery / Supermarket Refrigerated Section, Business Signal: Perishable Inventory at Risk of Surplus, Category: Leafy Greens, Category: Fresh Vegetables, Cherry Tomatoes, Bagged Fresh Herbs, Freshness: High (visibly fresh) (+8 more)

### Community 11 - "Community 11"
Cohesion: 0.3
Nodes (12): Dairy-Free / Plant-Based, Perishable / Short-Shelf-Life Inventory, Unsweetened (attribute), Yokos (brand), Cultured Plant-Based Yogurt Alternatives, Dairy / Refrigerated Aisle Category, Dairy/Plant-Based Yogurt Product Photo, Yokos Banana Flavoured Cultured Coconut (Unsweetened, 500g) (+4 more)

### Community 12 - "Community 12"
Cohesion: 0.2
Nodes (12): Bush's Beans Cans, Canned Goods Collection, Del Monte Canned Vegetables, Food Pantry Donation Use Case, Goya Brand Cans, High Quantity Inventory, Long Shelf Life, Pantry Shelf with Canned Goods (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.24
Nodes (12): Cutover method: website-link repoint + suspending Fly app, v1.0 had only seeded demo_001 partner key in production, Final destroy of suspended Fly app pending explicit decision, Fly.io app surplusas-api-dev (surplusas-api-dev.fly.dev) — decommissioned, Fly app kept suspended (not destroyed) to preserve app name and allow fast rollback, Legacy repo archived under tag v1.0-fly, Migration complete status banner (as of 2026-04-26), Phase 6 cutover complete — partner traffic migrated 2026-04-26 ahead of contest window (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.24
Nodes (10): Grocery/Deli Hot Food Counter, Poultry, Prepared Foods, Hot, Freshly Cooked, Multiple Units (6+ chickens visible), Rotisserie Chicken, Commercial Rotisserie Oven, Rotisserie Chicken Display (+2 more)

### Community 15 - "Community 15"
Cohesion: 0.32
Nodes (7): partner_keys demo seed (sk_demo_surplus_2026), api_key(), base_url(), client(), Shared pytest configuration for the smoke tests.  Smoke tests hit a deployed Lis, A long-lived httpx client with auth + 240s timeout (LLM calls are slow)., test_health_endpoint

### Community 16 - "Community 16"
Cohesion: 0.67
Nodes (3): AgentMode enum (9 modes), AgentRequest pydantic model, PartnerContext pydantic model

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Configuration: env vars, valid enums, per-mode settings.  Ported from v1.0 (app/

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (2): One Image, SERVICE_MODULE Switch, Use --update-env-vars not --set-env-vars (rationale)

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (2): Top-level Python Dependencies, ADK 2.0/1.x Compatibility Hedge via shared/adk_compat.py (rationale)

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (0): 

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (0): 

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (0): 

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (0): 

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): asyncpg Pool via Cloud SQL Connector

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): insert_outcome

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): shared.tracing

## Knowledge Gaps
- **105 isolated node(s):** `Run a moderation review and return the parsed JSON dict.`, `Return (bytes, mime_type) from a base64 string with optional data-URL prefix.`, `Stamp server-controlled fields onto the parsed model output.`, `Run a listing-service mode against ADK 2.0 + Vertex AI Gemini.      Returns a pa`, `ADK 2.0 graph workflow: intake -> moderate -> price -> publish.  Phase 4d. A sin` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 17`** (2 nodes): `Configuration: env vars, valid enums, per-mode settings.  Ported from v1.0 (app/`, `config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (2 nodes): `One Image, SERVICE_MODULE Switch`, `Use --update-env-vars not --set-env-vars (rationale)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (2 nodes): `Top-level Python Dependencies`, `ADK 2.0/1.x Compatibility Hedge via shared/adk_compat.py (rationale)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `asyncpg Pool via Cloud SQL Connector`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `insert_outcome`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `shared.tracing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fetch_partner_by_key()` connect `Community 2` to `Community 1`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `_demo_partner_ctx()` connect `Community 1` to `Community 2`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `a2a_client_span()` connect `Community 6` to `Community 1`, `Community 3`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `Mixed Inventory Photo` (e.g. with `Korean-style Rice Bowl with Kimchi` and `Sliced Pork over Rice Bowl`) actually correct?**
  _`Mixed Inventory Photo` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Refrigerated Produce Display` (e.g. with `Bok Choy` and `Bagged Fresh Herbs`) actually correct?**
  _`Refrigerated Produce Display` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Bakery Category` (e.g. with `Focaccia with Cherry Tomatoes and Basil` and `Stuffed Bread Rolls / Sandwiches`) actually correct?**
  _`Bakery Category` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Run a moderation review and return the parsed JSON dict.`, `Return (bytes, mime_type) from a base64 string with optional data-URL prefix.`, `Stamp server-controlled fields onto the parsed model output.` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._