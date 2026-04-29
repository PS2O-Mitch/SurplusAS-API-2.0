"""Pricing engine — vendored from `surplusAS-pricing-intel/pricing_engine`.

Source of truth lives in the pricing-intel repo; this is the Postgres-only
slice the production Pricing Service needs (no SQLite dialect branch). When
the upstream module changes shape, mirror the diff here — the two are
intentionally not packaged together (Cloud Build can't pull a private repo).
"""
