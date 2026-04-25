"""Pydantic schemas — request and response shapes for the SurplusAS API.

Ported from v1.0 (app/schemas.py). Source of truth for all wire types.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class AgentMode(str, Enum):
    listing_create = "listing_create"
    listing_enhance = "listing_enhance"
    listing_batch = "listing_batch"
    search_interpret = "search_interpret"
    moderate = "moderate"
    translate = "translate"
    customer_assist = "customer_assist"
    pricing_optimize = "pricing_optimize"


class ListingStatus(str, Enum):
    ready_for_publish = "ready_for_publish"
    needs_review = "needs_review"
    blocked = "blocked"
    draft = "draft"


class PhotoQuality(str, Enum):
    good = "good"
    acceptable = "acceptable"
    poor = "poor"


class RiskLevel(str, Enum):
    pass_ = "pass"
    low_risk = "low_risk"
    medium_risk = "medium_risk"
    high_risk = "high_risk"
    block = "block"


class Severity(str, Enum):
    block = "block"
    warn = "warn"
    info = "info"


class UrgencyLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class PriceChangeMagnitude(str, Enum):
    no_change = "no_change"
    minor = "minor"
    moderate = "moderate"
    significant = "significant"


class SortPreference(str, Enum):
    relevance = "relevance"
    price_low = "price_low"
    price_high = "price_high"
    distance_near = "distance_near"
    expiring_soon = "expiring_soon"
    newest = "newest"


# ---------------------------------------------------------------------------
# Request shapes
# ---------------------------------------------------------------------------
class PartnerContext(BaseModel):
    partner_id: str = "demo_001"
    partner_name: str = "SurplusAS Demo"
    platform_type: str = "marketplace"
    supported_categories: list[str] | None = None
    default_language: str = "en"
    currency: str = "USD"
    regulatory_region: str = "US"
    discount_range: dict[str, int] = Field(default_factory=lambda: {"min": 30, "max": 70})
    pickup_model: str = "in_store"
    snap_ebt_enabled: bool = False
    moderation_strictness: str = "standard"


class AgentRequest(BaseModel):
    """Request body for POST /v1/agent."""
    mode: AgentMode
    input: str = Field(..., min_length=1, description="Merchant text, search query, or listing JSON")
    image: str | None = Field(None, description="Base64-encoded image (JPEG/PNG/WebP)")
    merchant_id: str | None = None
    partner_context: PartnerContext | None = None


# ---------------------------------------------------------------------------
# Response shapes — server overwrites + wrapper
# ---------------------------------------------------------------------------
class OutcomeTracking(BaseModel):
    agent_version: str = "2.1"
    model_used: str = ""
    inference_timestamp: str = ""
    tokens_consumed: int = 0


class IdentifiedItem(BaseModel):
    name: str
    quantity: int | str
    confidence: float = Field(ge=0.0, le=1.0)


class DietaryAttributes(BaseModel):
    is_vegan: bool = False
    is_vegetarian: bool = False
    is_gluten_free: bool = False
    is_halal: bool = False
    is_kosher: bool = False
    is_nut_free: bool = False
    is_dairy_free: bool = False
    allergen_warning: str | None = None


class Pricing(BaseModel):
    estimated_retail_value: float | None = None
    suggested_surplus_price: float | None = None
    discount_percentage: int | None = None
    currency: str = "USD"
    pricing_logic: str | None = None

    @field_validator("suggested_surplus_price")
    @classmethod
    def round_to_quarter(cls, v: float | None) -> float | None:
        if v is None:
            return None
        return round(v * 4) / 4


class ImageAnalysis(BaseModel):
    photo_quality: PhotoQuality = PhotoQuality.acceptable
    photo_suggestions: str | None = None
    merchant_feedback: str = ""


class ListingCreateResponse(BaseModel):
    mode: str = "listing_create"
    listing_id: str = ""
    status: ListingStatus = ListingStatus.needs_review
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    title: str = Field("", max_length=60)
    description: str = Field("", max_length=280)
    category: str = ""
    items_identified: list[IdentifiedItem] = Field(default_factory=list)
    dietary_attributes: DietaryAttributes = Field(default_factory=DietaryAttributes)
    pricing: Pricing = Field(default_factory=Pricing)
    pickup_window: str = ""
    food_safety_notes: str = ""
    image_analysis: ImageAnalysis = Field(default_factory=ImageAnalysis)
    clarification_needed: list[str] | str | None = None
    outcome_tracking: OutcomeTracking = Field(default_factory=OutcomeTracking)

    @field_validator("category")
    @classmethod
    def lowercase_category(cls, v: str) -> str:
        return v.lower().strip()


class DietaryRequirements(BaseModel):
    must_be_vegan: bool | None = None
    must_be_vegetarian: bool | None = None
    must_be_gluten_free: bool | None = None
    must_be_halal: bool | None = None
    must_be_kosher: bool | None = None
    must_be_nut_free: bool | None = None
    must_be_dairy_free: bool | None = None


class SearchFilters(BaseModel):
    category: str | None = None
    dietary_requirements: DietaryRequirements = Field(default_factory=DietaryRequirements)
    max_price: float | None = None
    max_distance_km: float | None = None
    pickup_before: str | None = None
    cuisine_type: str | None = None
    keywords: list[str] = Field(default_factory=list)


class SearchInterpretResponse(BaseModel):
    mode: str = "search_interpret"
    input_language: str = "en"
    interpreted_query: str = ""
    filters: SearchFilters = Field(default_factory=SearchFilters)
    sort_preference: SortPreference = SortPreference.relevance
    cross_language_keywords: list[str] = Field(default_factory=list)
    outcome_tracking: OutcomeTracking = Field(default_factory=OutcomeTracking)


class ModerationFlag(BaseModel):
    rule: str = ""
    severity: Severity = Severity.info
    explanation: str = ""
    suggested_fix: str | None = None


class ModerateResponse(BaseModel):
    mode: str = "moderate"
    approved: bool = False
    overall_risk: RiskLevel = RiskLevel.medium_risk
    flags: list[ModerationFlag] = Field(default_factory=list)
    outcome_tracking: OutcomeTracking = Field(default_factory=OutcomeTracking)


class PricingOptimizeResponse(BaseModel):
    mode: str = "pricing_optimize"
    current_discount_pct: int = 0
    recommended_discount_pct: int = 0
    recommended_price: float = 0.0
    reasoning: str = ""
    urgency_level: UrgencyLevel = UrgencyLevel.medium
    price_change_magnitude: PriceChangeMagnitude = PriceChangeMagnitude.no_change
    outcome_tracking: OutcomeTracking = Field(default_factory=OutcomeTracking)

    @field_validator("recommended_price")
    @classmethod
    def round_to_quarter(cls, v: float) -> float:
        return round(v * 4) / 4


# ---------------------------------------------------------------------------
# API wrapper
# ---------------------------------------------------------------------------
class AgentResponse(BaseModel):
    success: bool = True
    mode: str
    data: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
