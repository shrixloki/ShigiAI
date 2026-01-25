"""Advanced multi-factor lead scoring engine models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ScoreCategory(str, Enum):
    """Categories of lead scores."""
    INTENT = "intent"
    RELEVANCE = "relevance"
    RECENCY = "recency"
    INDUSTRY_FIT = "industry_fit"
    OUTREACH_READINESS = "outreach_readiness"
    COMPOSITE = "composite"


class ScoreLevel(str, Enum):
    """Human-readable score levels."""
    EXCELLENT = "excellent"  # 0.8 - 1.0
    GOOD = "good"            # 0.6 - 0.8
    FAIR = "fair"            # 0.4 - 0.6
    POOR = "poor"            # 0.2 - 0.4
    VERY_POOR = "very_poor"  # 0.0 - 0.2


class ScoreExplanation(BaseModel):
    """Explanation for a specific score factor."""
    factor_name: str = Field(..., max_length=100)
    factor_weight: Decimal = Field(..., ge=0, le=1)
    raw_value: Decimal = Field(..., ge=0, le=1)
    weighted_value: Decimal = Field(..., ge=0, le=1)
    explanation: str = Field(..., max_length=500)
    data_points: List[str] = Field(default_factory=list)


class ScoreComponent(BaseModel):
    """Individual scoring component with explanation."""
    category: ScoreCategory
    score: Decimal = Field(..., ge=0, le=1)
    level: ScoreLevel
    factors: List[ScoreExplanation] = Field(default_factory=list)
    calculated_at: datetime = Field(default_factory=datetime.now)
    confidence: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    
    @classmethod
    def from_score(cls, category: ScoreCategory, score: Decimal, 
                   factors: List[ScoreExplanation], confidence: Decimal = Decimal("0.5")):
        """Create component from a score value."""
        level = cls._score_to_level(score)
        return cls(
            category=category,
            score=score,
            level=level,
            factors=factors,
            confidence=confidence
        )
    
    @staticmethod
    def _score_to_level(score: Decimal) -> ScoreLevel:
        """Convert numeric score to level."""
        if score >= Decimal("0.8"):
            return ScoreLevel.EXCELLENT
        elif score >= Decimal("0.6"):
            return ScoreLevel.GOOD
        elif score >= Decimal("0.4"):
            return ScoreLevel.FAIR
        elif score >= Decimal("0.2"):
            return ScoreLevel.POOR
        return ScoreLevel.VERY_POOR


class ScoringRuleType(str, Enum):
    """Types of scoring rules."""
    BOOLEAN = "boolean"        # Has/doesn't have something
    THRESHOLD = "threshold"    # Value above/below threshold
    RANGE = "range"            # Value within range
    MATCH = "match"            # Matches list of values
    RECENCY = "recency"        # Time-based decay
    CUSTOM = "custom"          # Custom calculation


class ScoringRule(BaseModel):
    """Configurable scoring rule."""
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    category: ScoreCategory
    rule_type: ScoringRuleType
    
    # Weight and configuration
    weight: Decimal = Field(default=Decimal("1.0"), ge=0, le=10)
    is_active: bool = Field(default=True)
    
    # Rule parameters (depends on rule_type)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(default="system", max_length=100)
    
    class Config:
        use_enum_values = True


class LeadScore(BaseModel):
    """Complete lead scoring with all components."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    
    # Component scores
    intent_score: Optional[ScoreComponent] = None
    relevance_score: Optional[ScoreComponent] = None
    recency_score: Optional[ScoreComponent] = None
    industry_fit_score: Optional[ScoreComponent] = None
    outreach_readiness_score: Optional[ScoreComponent] = None
    
    # Composite score
    composite_score: Decimal = Field(default=Decimal("0.0"), ge=0, le=1)
    composite_level: ScoreLevel = Field(default=ScoreLevel.VERY_POOR)
    
    # Override handling
    is_manually_overridden: bool = Field(default=False)
    override_score: Optional[Decimal] = Field(None, ge=0, le=1)
    override_reason: Optional[str] = Field(None, max_length=500)
    overridden_by: Optional[str] = Field(None, max_length=100)
    overridden_at: Optional[datetime] = None
    
    # Scoring metadata
    scoring_config_version: str = Field(default="1.0", max_length=20)
    rules_applied: List[str] = Field(default_factory=list)
    
    # Timestamps
    calculated_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    version: int = Field(default=1)
    
    def get_effective_score(self) -> Decimal:
        """Get the effective score (considering overrides)."""
        if self.is_manually_overridden and self.override_score is not None:
            return self.override_score
        return self.composite_score
    
    def get_effective_level(self) -> ScoreLevel:
        """Get the effective level (considering overrides)."""
        score = self.get_effective_score()
        return ScoreComponent._score_to_level(score)
    
    def get_score_summary(self) -> Dict[str, Any]:
        """Get a summary of all scores for display."""
        return {
            "composite": float(self.get_effective_score()),
            "level": self.get_effective_level().value,
            "is_overridden": self.is_manually_overridden,
            "components": {
                "intent": float(self.intent_score.score) if self.intent_score else None,
                "relevance": float(self.relevance_score.score) if self.relevance_score else None,
                "recency": float(self.recency_score.score) if self.recency_score else None,
                "industry_fit": float(self.industry_fit_score.score) if self.industry_fit_score else None,
                "outreach_readiness": float(self.outreach_readiness_score.score) if self.outreach_readiness_score else None
            },
            "calculated_at": self.calculated_at.isoformat()
        }
    
    def get_full_explanation(self) -> Dict[str, Any]:
        """Get detailed explanation of all score factors."""
        explanation = {
            "composite_score": float(self.get_effective_score()),
            "composite_level": self.get_effective_level().value,
            "is_overridden": self.is_manually_overridden,
            "components": {}
        }
        
        for name, component in [
            ("intent", self.intent_score),
            ("relevance", self.relevance_score),
            ("recency", self.recency_score),
            ("industry_fit", self.industry_fit_score),
            ("outreach_readiness", self.outreach_readiness_score)
        ]:
            if component:
                explanation["components"][name] = {
                    "score": float(component.score),
                    "level": component.level.value,
                    "confidence": float(component.confidence),
                    "factors": [
                        {
                            "name": f.factor_name,
                            "weight": float(f.factor_weight),
                            "value": float(f.weighted_value),
                            "explanation": f.explanation,
                            "data_points": f.data_points
                        }
                        for f in component.factors
                    ]
                }
        
        if self.is_manually_overridden:
            explanation["override"] = {
                "score": float(self.override_score) if self.override_score else None,
                "reason": self.override_reason,
                "by": self.overridden_by,
                "at": self.overridden_at.isoformat() if self.overridden_at else None
            }
        
        return explanation
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class ScoreHistory(BaseModel):
    """Historical record of lead score changes."""
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    score_id: UUID = Field(...)
    
    # Score snapshot
    composite_score: Decimal = Field(..., ge=0, le=1)
    composite_level: ScoreLevel
    component_scores: Dict[str, Decimal] = Field(default_factory=dict)
    
    # Change tracking
    previous_score: Optional[Decimal] = Field(None, ge=0, le=1)
    score_delta: Optional[Decimal] = None
    change_reason: Optional[str] = Field(None, max_length=500)
    
    # Metadata
    recorded_at: datetime = Field(default_factory=datetime.now)
    triggered_by: str = Field(default="system", max_length=100)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class ScoreOverrideRequest(BaseModel):
    """Request to manually override a lead score."""
    lead_id: UUID = Field(...)
    override_score: Decimal = Field(..., ge=0, le=1)
    reason: str = Field(..., min_length=10, max_length=500)
    actor: str = Field(..., max_length=100)


class ScoringConfigUpdate(BaseModel):
    """Update request for scoring configuration."""
    rules: Optional[List[ScoringRule]] = None
    weights: Optional[Dict[ScoreCategory, Decimal]] = None
    thresholds: Optional[Dict[str, Decimal]] = None
    updated_by: str = Field(..., max_length=100)
