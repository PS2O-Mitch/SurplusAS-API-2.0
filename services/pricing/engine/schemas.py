"""Pydantic types for the deterministic pricing formula.

Three layers:

- `PricingInput`   — what the LLM-edge parser hands the formula.
- `Coefficients`   — what `coefficients.load_latest()` returns. Mirrors the
                     `pricing_coefficients` table; the curve fields are
                     piecewise-linear breakpoints serialised as JSON.
- `Recommendation` — what `formula.recommend()` returns. The
                     `applied_pressures` map is the audit trail required
                     by guardrail #2 in CLAUDE.md.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

VALID_CATEGORIES = (
    "produce",
    "prepared_meal",
    "bakery",
    "dairy",
    "beverage",
    "packaged_goods",
    "deli",
    "frozen",
    "mixed_bag",
)

# Bumped by hand whenever formula.recommend()'s math changes shape. Phase 3
# coefficient updates do NOT bump this — only formula edits do.
FORMULA_VERSION = "v1"


class PiecewiseCurve(BaseModel):
    """Sorted breakpoints `[(x, y), ...]`, linearly interpolated.

    `at(x)` returns y. Outside the breakpoint range the value clamps to
    the nearest endpoint — extrapolation would be a footgun for curves
    fit on observed ranges.
    """

    breakpoints: list[tuple[float, float]]

    @field_validator("breakpoints")
    @classmethod
    def _sorted_non_empty(cls, v: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if not v:
            raise ValueError("breakpoints must contain at least one (x, y) pair")
        xs = [x for x, _ in v]
        if xs != sorted(xs):
            raise ValueError("breakpoints must be sorted by x ascending")
        return v

    def at(self, x: float) -> float:
        bps = self.breakpoints
        if x <= bps[0][0]:
            return bps[0][1]
        if x >= bps[-1][0]:
            return bps[-1][1]
        for i in range(len(bps) - 1):
            x0, y0 = bps[i]
            x1, y1 = bps[i + 1]
            if x0 <= x <= x1:
                if x1 == x0:
                    return y1
                t = (x - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
        return bps[-1][1]  # unreachable; satisfies the type checker


class Coefficients(BaseModel):
    """One row from `pricing_coefficients`, deserialised.

    `expiry_curve` x-axis is hours-until-expiry (0 = now, large = fresh).
    `inventory_curve` x-axis is units (1 = single unit). `time_of_day_curve`
    x-axis is hour-of-day (0..23, local merchant time).
    """

    category: str
    region: str
    version: int
    base_discount: float
    expiry_curve: PiecewiseCurve
    inventory_curve: PiecewiseCurve
    time_of_day_curve: PiecewiseCurve
    source: str

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {VALID_CATEGORIES}, got {v!r}")
        return v


class PricingInput(BaseModel):
    category: str
    region: str
    units: int = Field(ge=1)
    retail_value: float = Field(gt=0)
    hours_until_expiry: float
    now_hour: int = Field(ge=0, le=23)
    merchant_floor_pct: float = Field(default=0.10, ge=0.0, le=1.0)

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {VALID_CATEGORIES}, got {v!r}")
        return v


class AppliedPressures(BaseModel):
    """Audit trail of every pressure the formula stacked.

    Sums (with sign) to `total_discount_pct`. A compliance reviewer must be
    able to reconstruct the recommended price from this map plus
    `anchor_p50` and `formula_version` (guardrail #2 in CLAUDE.md).
    """

    base: float
    expiry: float
    inventory: float
    time_of_day: float
    merchant_floor: float
    clamped_to_floor: bool = False
    clamped_to_retail: bool = False


class Recommendation(BaseModel):
    recommended_price: float
    recommended_discount_pct: float
    anchor_p50: float
    anchor_source: str
    anchor_region: str
    applied_pressures: AppliedPressures
    formula_version: str = FORMULA_VERSION
