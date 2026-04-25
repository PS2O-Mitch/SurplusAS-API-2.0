# SurplusAS Agent API — v2.0

Multi-agent production API for **SurplusAS**, a B2B surplus-food marketplace platform. v2.0 is a ground-up rebuild on **Google Cloud** (Cloud Run, Vertex AI, Cloud SQL Postgres) using Google's **Agent Development Kit (ADK) 2.0** and the **Agent-to-Agent (A2A)** protocol.

This rebuild is the SurplusAS submission to **Track 3 of the Google for Startups AI Agents Challenge** ("Refactor for Google Cloud Marketplace & Gemini Enterprise").

## Architecture

Three Cloud Run services, A2A between them, ADK 2.0 graph workflow inside the Listing Service:

- **Listing Service** — coordinator + listing intake / enhance / batch, search, customer assist. `translate` as a shared tool.
- **Compliance Service** — listing moderation. Independent service, exposed via A2A.
- **Pricing Service** — dynamic pricing with grounding over a `historical_sales` Cloud SQL table. Exposed via A2A.

Backward-compatible `POST /v1/agent` front door so existing partners and the merchant demo don't need to change.

See [`TRACK3_MIGRATION_PLAN.md`](./TRACK3_MIGRATION_PLAN.md) for the full plan, architecture diagram, phases, risks, and verification steps.

## Status

🚧 Active rebuild. v1.0 (Fly.io / FastAPI / OpenAI-compatible client) lives at the predecessor repo, tagged `v1.0-fly` for archeological reference.

## License

[MIT](./LICENSE).
