# SurplusAS Demo Video — 2:00 Shot List

**Total duration:** 2:00 (hard cap — Devpost truncates at 3:00 but judges skim past 2:00).
**Format:** screen-recorded, voice-over. No talking-head needed — the trace is the hero.
**Tools:** OBS or QuickTime for capture; iMovie / DaVinci Resolve for trimming. Caption everything.

## What to record before you start narrating

1. **Tab A — Merchant demo** open at <https://listing-service-70904707890.us-central1.run.app/demo>, with the bakery sample image (`/demo/samples/bakery.webp`) pre-selected.
2. **Tab B — Cloud Trace** open at <https://console.cloud.google.com/traces/list?project=ps2o-surplusas-api>. Filter to the last 5 minutes after running the demo so the new trace appears at the top.
3. **Tab C — README architecture diagram** rendered (GitHub renders the Mermaid block automatically). Have it pre-scrolled so the diagram fills the viewport.
4. **Tab D — `services/listing/pipeline.py`** in your editor or on GitHub, scrolled to the `LISTING_PIPELINE = Workflow(...)` block.

Run one trial pass through the demo to make sure the bakery image works and a trace shows up. Don't record yet.

## Script (timing is approximate)

| Time | What's on screen | Narration |
|---|---|---|
| 0:00–0:08 | Tab A, demo page hero | "SurplusAS turns a merchant photo and one line of text into a complete, moderated, priced, published surplus-food listing — autonomously." |
| 0:08–0:18 | Tab A, click the bakery sample, type "20 chocolate croissants, store closes 6 PM, retail $4.50 each", hit submit | "One merchant request. Behind it, three Cloud Run services on Google Cloud collaborate over the Agent-to-Agent protocol." |
| 0:18–0:30 | Tab A, wait while spinner runs (~10s), then the rendered listing appears with title, description, dietary, pricing, moderation, published_listing_id | "The Listing Service writes the copy, the Compliance Service moderates it via A2A, the Pricing Service recommends a discount grounded on real historical sales, and the published listing comes back in a single response." |
| 0:30–0:50 | Tab C, Cloud Trace — click into the most recent trace; full span tree visible | "This is what makes it real. One request, one Cloud Trace. Twenty-six spans. Three services correlated. The ADK 2.0 Workflow node, each graph step, each A2A call, each Vertex AI Gemini call — all visible end-to-end." |
| 0:50–1:05 | Tab C, hover over an `a2a.call_peer` CLIENT span and the matching `POST /v1/agent` SERVER span on the peer service; Cloud Trace shows them as parent/child | "The trace stitches across services because we propagate W3C `traceparent` over the A2A call. ADK 2.0 auto-instruments the rest." |
| 1:05–1:25 | Tab D, `pipeline.py` — highlight the four `FunctionNode`s and the `Edge` list defining `START → intake → moderate → price → publish` | "The orchestration is fifteen lines of declarative ADK 2.0. Edges from intake to moderate to price to publish. Two of those edges fan out to peer services via A2A. The Workflow runs through `Runner.run_async` with a state-seeded session." |
| 1:25–1:42 | Tab C → terminal split. Run `pytest tests/` and let the green dots roll past, or pre-record and play the result line | "Ten smoke tests against the deployed URL — every mode, plus the full graph pipeline. Ninety seconds, ten green. This is the only way we catch Vertex prompt drift before partners do." |
| 1:42–1:55 | Tab C, README architecture diagram (Mermaid) | "Three services on Cloud Run. Cloud SQL Postgres for partner keys, outcomes, and the historical-sales table that grounds pricing. Vertex AI Gemini for inference. Cloud Trace for observability. One Docker image, three deployments, IAM-only A2A between them." |
| 1:55–2:00 | Demo URL on screen | "Try it yourself. Surplusas dot demo. No key required." |

## Captions / on-screen text overlays (essentials)

- 0:00–0:08: **"SurplusAS — autonomous surplus-food listing agent"**
- 0:30–0:50: **"One trace · 26 spans · 3 services"** in the corner while showing Cloud Trace.
- 1:05–1:25: highlight `LISTING_PIPELINE = Workflow(name="listing_create_full", edges=[...])` in the editor — circle / arrow.
- 1:55–2:00: full-width banner with the demo URL.

## Editing notes

- **Speed up the spinner.** The demo response takes ~10s; cut to 4s in post.
- **Don't dwell.** Each tab cut should be ≤ 5s unless something specific is happening.
- **No music**, or very quiet ambient. Judges watch with audio off as often as on.
- **No talking head.** The screen is the demo.
- **Subtitle the whole thing.** Many judges scrub muted.

## Final checks before upload

- [ ] Total length ≤ 2:00.
- [ ] Demo URL visible at start AND end.
- [ ] Cloud Trace span tree visible for at least 8 seconds.
- [ ] At least one frame clearly shows `published_listing_id: pub_XXXXXXXX` on the response.
- [ ] At least one frame clearly shows the `Workflow` declaration in `pipeline.py`.
- [ ] At least one frame clearly shows the architecture diagram.
- [ ] Pytest 10/10 green frame visible (even if briefly).
- [ ] Upload to YouTube as **Unlisted** (Devpost requires a public URL).
- [ ] Paste the YouTube URL into the Devpost submission form.
