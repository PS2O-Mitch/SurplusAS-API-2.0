-- SurplusAS API v2.0 — Postgres schema.
-- Apply via shared/db_init.py (idempotent; safe to re-run).

CREATE TABLE IF NOT EXISTS partner_keys (
    api_key       TEXT PRIMARY KEY,
    partner_id    TEXT NOT NULL,
    partner_name  TEXT NOT NULL,
    context_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS partner_keys_partner_id_idx
    ON partner_keys (partner_id);


CREATE TABLE IF NOT EXISTS outcomes (
    id                BIGSERIAL PRIMARY KEY,
    partner_id        TEXT NOT NULL,
    listing_id        TEXT NOT NULL,
    event_type        TEXT NOT NULL CHECK (event_type IN (
        'sale_completed', 'pickup_confirmed', 'listing_expired', 'merchant_rejected'
    )),
    transaction_value NUMERIC(10, 2),
    billable          BOOLEAN NOT NULL DEFAULT FALSE,
    fee_amount        NUMERIC(10, 2),
    event_timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS outcomes_partner_event_idx
    ON outcomes (partner_id, event_type);
CREATE INDEX IF NOT EXISTS outcomes_listing_idx
    ON outcomes (listing_id);


-- Used by the Pricing Service for demand-signal grounding (Phase 4).
CREATE TABLE IF NOT EXISTS historical_sales (
    id            BIGSERIAL PRIMARY KEY,
    partner_id    TEXT NOT NULL,
    listing_id    TEXT NOT NULL,
    category      TEXT NOT NULL,
    items_json    JSONB,
    sold_price    NUMERIC(10, 2) NOT NULL,
    retail_value  NUMERIC(10, 2),
    day_of_week   SMALLINT CHECK (day_of_week BETWEEN 0 AND 6),
    hour_of_day   SMALLINT CHECK (hour_of_day BETWEEN 0 AND 23),
    sold_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS historical_sales_category_sold_at_idx
    ON historical_sales (category, sold_at DESC);
