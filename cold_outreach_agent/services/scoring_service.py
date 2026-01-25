"""Advanced multi-factor lead scoring engine."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from ..core.models.scoring import (
    LeadScore, ScoreComponent, ScoreCategory, ScoreLevel, ScoreExplanation,
    ScoringRule, ScoringRuleType, ScoreHistory, ScoreOverrideRequest
)
from ..core.models.enrichment import LeadEnrichment, BusinessMaturity
from ..core.exceptions import ColdOutreachAgentError
from ..modules.logger import action_logger


class ScoringError(ColdOutreachAgentError):
    """Scoring operation failed."""
    pass


class LeadScoringEngine:
    """
    Multi-factor lead scoring engine with configurable rules, 
    manual override support, and historical tracking.
    
    Score Categories:
    - Intent: How likely they need our services
    - Relevance: How well they fit our target profile
    - Recency: How fresh is the data
    - Industry Fit: How well their industry matches
    - Outreach Readiness: Are they ready for outreach
    """
    
    # Default weights for composite score
    DEFAULT_WEIGHTS: Dict[ScoreCategory, Decimal] = {
        ScoreCategory.INTENT: Decimal("0.25"),
        ScoreCategory.RELEVANCE: Decimal("0.25"),
        ScoreCategory.RECENCY: Decimal("0.15"),
        ScoreCategory.INDUSTRY_FIT: Decimal("0.15"),
        ScoreCategory.OUTREACH_READINESS: Decimal("0.20"),
    }
    
    # Target industries (configurable)
    DEFAULT_TARGET_INDUSTRIES = [
        'restaurant', 'cafe', 'bar', 'hotel', 'salon', 'spa', 'gym', 'fitness',
        'dental', 'medical', 'clinic', 'real estate', 'law', 'legal', 'accounting',
        'consulting', 'retail', 'store', 'shop', 'boutique', 'auto', 'repair',
        'plumber', 'electrician', 'contractor', 'cleaning', 'landscaping'
    ]
    
    def __init__(self, db_service, 
                 weights: Dict[ScoreCategory, Decimal] = None,
                 target_industries: List[str] = None):
        self.db = db_service
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.target_industries = target_industries or self.DEFAULT_TARGET_INDUSTRIES
        self.custom_rules: List[ScoringRule] = []
    
    def add_rule(self, rule: ScoringRule):
        """Add a custom scoring rule."""
        self.custom_rules.append(rule)
    
    def clear_rules(self):
        """Clear all custom rules."""
        self.custom_rules = []
    
    def update_weights(self, weights: Dict[ScoreCategory, Decimal]):
        """Update scoring weights."""
        # Validate weights sum to 1
        total = sum(weights.values())
        if abs(total - Decimal("1.0")) > Decimal("0.01"):
            raise ScoringError(f"Weights must sum to 1.0, got {total}")
        self.weights = weights
    
    async def score_lead(self, lead: Dict[str, Any], 
                          enrichment: Optional[LeadEnrichment] = None) -> LeadScore:
        """
        Calculate comprehensive lead score.
        
        Args:
            lead: Lead data dictionary
            enrichment: Optional enrichment data
        
        Returns:
            LeadScore with all components and composite score
        """
        lead_id_val = lead.get('lead_id') or lead.get('id')
        lead_id = UUID(str(lead_id_val)) if lead_id_val else uuid4()
        
        # Calculate each component score
        intent_score = self._calculate_intent_score(lead, enrichment)
        relevance_score = self._calculate_relevance_score(lead, enrichment)
        recency_score = self._calculate_recency_score(lead)
        industry_fit_score = self._calculate_industry_fit_score(lead)
        outreach_readiness_score = self._calculate_outreach_readiness_score(lead, enrichment)
        
        # Calculate composite score
        composite = (
            intent_score.score * self.weights[ScoreCategory.INTENT] +
            relevance_score.score * self.weights[ScoreCategory.RELEVANCE] +
            recency_score.score * self.weights[ScoreCategory.RECENCY] +
            industry_fit_score.score * self.weights[ScoreCategory.INDUSTRY_FIT] +
            outreach_readiness_score.score * self.weights[ScoreCategory.OUTREACH_READINESS]
        )
        
        # Apply custom rules
        composite = self._apply_custom_rules(composite, lead, enrichment)
        
        # Ensure within bounds
        composite = max(Decimal("0.0"), min(Decimal("1.0"), composite))
        
        # Create lead score
        lead_score = LeadScore(
            lead_id=lead_id,
            intent_score=intent_score,
            relevance_score=relevance_score,
            recency_score=recency_score,
            industry_fit_score=industry_fit_score,
            outreach_readiness_score=outreach_readiness_score,
            composite_score=composite,
            composite_level=ScoreComponent._score_to_level(composite),
            rules_applied=[r.name for r in self.custom_rules if r.is_active]
        )
        
        action_logger.log_action(
            lead_id=str(lead_id),
            module_name="scoring",
            action="score_lead",
            result="success",
            details=lead_score.get_score_summary()
        )
        
        return lead_score
    
    def _calculate_intent_score(self, lead: Dict[str, Any], 
                                 enrichment: Optional[LeadEnrichment]) -> ScoreComponent:
        """
        Calculate intent score based on signals indicating need for services.
        
        Factors:
        - No website or outdated website
        - Contact form/chat absence
        - Hiring signals (may need developer)
        - Tech stack gaps
        """
        factors = []
        base_score = Decimal("0.5")
        
        # Website status factor
        website_url = lead.get('website_url')
        tag = lead.get('tag', '')
        
        if not website_url or tag == 'no_website':
            factors.append(ScoreExplanation(
                factor_name="No Website",
                factor_weight=Decimal("0.3"),
                raw_value=Decimal("1.0"),
                weighted_value=Decimal("0.3"),
                explanation="Business has no website - high intent signal",
                data_points=["No website detected"]
            ))
            base_score += Decimal("0.3")
        elif tag == 'outdated_site':
            factors.append(ScoreExplanation(
                factor_name="Outdated Website",
                factor_weight=Decimal("0.2"),
                raw_value=Decimal("1.0"),
                weighted_value=Decimal("0.2"),
                explanation="Website appears outdated",
                data_points=["Website needs refresh"]
            ))
            base_score += Decimal("0.2")
        elif tag == 'no_cta':
            factors.append(ScoreExplanation(
                factor_name="Missing CTA",
                factor_weight=Decimal("0.15"),
                raw_value=Decimal("1.0"),
                weighted_value=Decimal("0.15"),
                explanation="Website lacks clear calls to action",
                data_points=["No contact forms or CTAs"]
            ))
            base_score += Decimal("0.15")
        
        # Enrichment-based factors
        if enrichment:
            # Hiring tech workers = potential budget for dev work
            if enrichment.is_hiring:
                factors.append(ScoreExplanation(
                    factor_name="Hiring",
                    factor_weight=Decimal("0.1"),
                    raw_value=Decimal("1.0"),
                    weighted_value=Decimal("0.1"),
                    explanation="Company is actively hiring, indicates growth",
                    data_points=[f"Found {len(enrichment.hiring_signals)} hiring signals"]
                ))
                base_score += Decimal("0.1")
            
            # No live chat = opportunity
            if not enrichment.has_live_chat:
                factors.append(ScoreExplanation(
                    factor_name="No Live Chat",
                    factor_weight=Decimal("0.05"),
                    raw_value=Decimal("1.0"),
                    weighted_value=Decimal("0.05"),
                    explanation="No live chat solution detected",
                    data_points=["Missing chat widget"]
                ))
                base_score += Decimal("0.05")
        
        # Ensure within bounds
        base_score = max(Decimal("0.0"), min(Decimal("1.0"), base_score))
        
        return ScoreComponent.from_score(
            category=ScoreCategory.INTENT,
            score=base_score,
            factors=factors,
            confidence=Decimal("0.7") if enrichment else Decimal("0.5")
        )
    
    def _calculate_relevance_score(self, lead: Dict[str, Any],
                                    enrichment: Optional[LeadEnrichment]) -> ScoreComponent:
        """
        Calculate relevance score based on fit with target profile.
        
        Factors:
        - Has email
        - Has website
        - Business maturity
        - Company size fit
        """
        factors = []
        base_score = Decimal("0.3")
        
        # Email availability
        email = lead.get('email')
        if email:
            factors.append(ScoreExplanation(
                factor_name="Has Email",
                factor_weight=Decimal("0.3"),
                raw_value=Decimal("1.0"),
                weighted_value=Decimal("0.3"),
                explanation="Valid email address available",
                data_points=[email[:20] + "..."]
            ))
            base_score += Decimal("0.3")
        
        # Website available
        website_url = lead.get('website_url')
        if website_url:
            factors.append(ScoreExplanation(
                factor_name="Has Website",
                factor_weight=Decimal("0.1"),
                raw_value=Decimal("1.0"),
                weighted_value=Decimal("0.1"),
                explanation="Website available for analysis",
                data_points=[]
            ))
            base_score += Decimal("0.1")
        
        # Enrichment-based relevance
        if enrichment:
            # Business maturity - prefer early stage to scaling
            maturity_scores = {
                BusinessMaturity.EARLY_STAGE: Decimal("0.2"),
                BusinessMaturity.SCALING: Decimal("0.15"),
                BusinessMaturity.MVP: Decimal("0.1"),
                BusinessMaturity.MATURE: Decimal("0.05"),
            }
            maturity_value = maturity_scores.get(enrichment.business_maturity, Decimal("0.0"))
            if maturity_value > 0:
                factors.append(ScoreExplanation(
                    factor_name="Business Maturity",
                    factor_weight=Decimal("0.2"),
                    raw_value=maturity_value,
                    weighted_value=maturity_value,
                    explanation=f"Business stage: {enrichment.business_maturity}",
                    data_points=[enrichment.business_maturity.value if hasattr(enrichment.business_maturity, 'value') else str(enrichment.business_maturity)]
                ))
                base_score += maturity_value
            
            # Social presence indicates legitimacy
            if enrichment.social_presences:
                social_bonus = min(len(enrichment.social_presences) * Decimal("0.03"), Decimal("0.1"))
                factors.append(ScoreExplanation(
                    factor_name="Social Presence",
                    factor_weight=Decimal("0.1"),
                    raw_value=social_bonus,
                    weighted_value=social_bonus,
                    explanation="Active on social platforms",
                    data_points=[p.platform for p in enrichment.social_presences[:3]]
                ))
                base_score += social_bonus
        
        base_score = max(Decimal("0.0"), min(Decimal("1.0"), base_score))
        
        return ScoreComponent.from_score(
            category=ScoreCategory.RELEVANCE,
            score=base_score,
            factors=factors,
            confidence=Decimal("0.75") if email else Decimal("0.4")
        )
    
    def _calculate_recency_score(self, lead: Dict[str, Any]) -> ScoreComponent:
        """
        Calculate recency score based on data freshness.
        
        Factors:
        - Discovery date
        - Last activity
        - Data age decay
        """
        factors = []
        
        # Parse discovery date
        discovered_at_str = lead.get('discovered_at') or lead.get('created_at')
        if discovered_at_str:
            if isinstance(discovered_at_str, str):
                try:
                    discovered_at = datetime.fromisoformat(discovered_at_str.replace('Z', '+00:00'))
                except:
                    discovered_at = datetime.now()
            else:
                discovered_at = discovered_at_str
            
            age_days = (datetime.now() - discovered_at.replace(tzinfo=None)).days
            
            # Decay function: 1.0 at 0 days, ~0.5 at 30 days, ~0.1 at 90 days
            if age_days <= 7:
                decay = Decimal("1.0")
            elif age_days <= 14:
                decay = Decimal("0.9")
            elif age_days <= 30:
                decay = Decimal("0.7")
            elif age_days <= 60:
                decay = Decimal("0.5")
            elif age_days <= 90:
                decay = Decimal("0.3")
            else:
                decay = Decimal("0.1")
            
            factors.append(ScoreExplanation(
                factor_name="Data Age",
                factor_weight=Decimal("1.0"),
                raw_value=decay,
                weighted_value=decay,
                explanation=f"Data is {age_days} days old",
                data_points=[f"Discovered: {discovered_at.strftime('%Y-%m-%d')}"]
            ))
            
            return ScoreComponent.from_score(
                category=ScoreCategory.RECENCY,
                score=decay,
                factors=factors,
                confidence=Decimal("0.95")
            )
        
        # No date info - assume moderate recency
        return ScoreComponent.from_score(
            category=ScoreCategory.RECENCY,
            score=Decimal("0.5"),
            factors=[],
            confidence=Decimal("0.3")
        )
    
    def _calculate_industry_fit_score(self, lead: Dict[str, Any]) -> ScoreComponent:
        """
        Calculate industry fit score.
        
        Factors:
        - Category match with target industries
        - Location fit (if configured)
        """
        factors = []
        base_score = Decimal("0.3")  # Default for unknown industry
        
        category = (lead.get('category') or '').lower()
        
        if category:
            # Check against target industries
            matched_industries = [ind for ind in self.target_industries 
                                  if ind.lower() in category]
            
            if matched_industries:
                factors.append(ScoreExplanation(
                    factor_name="Industry Match",
                    factor_weight=Decimal("0.7"),
                    raw_value=Decimal("1.0"),
                    weighted_value=Decimal("0.7"),
                    explanation=f"Industry matches target: {category}",
                    data_points=matched_industries[:3]
                ))
                base_score = Decimal("0.9")
            else:
                factors.append(ScoreExplanation(
                    factor_name="Industry Partial",
                    factor_weight=Decimal("0.3"),
                    raw_value=Decimal("0.5"),
                    weighted_value=Decimal("0.15"),
                    explanation=f"Industry not in primary targets: {category}",
                    data_points=[]
                ))
                base_score = Decimal("0.4")
        
        return ScoreComponent.from_score(
            category=ScoreCategory.INDUSTRY_FIT,
            score=base_score,
            factors=factors,
            confidence=Decimal("0.8") if category else Decimal("0.3")
        )
    
    def _calculate_outreach_readiness_score(self, lead: Dict[str, Any],
                                             enrichment: Optional[LeadEnrichment]) -> ScoreComponent:
        """
        Calculate outreach readiness score.
        
        Factors:
        - Email available
        - Review status
        - Previous outreach status
        - Decision maker found
        """
        factors = []
        base_score = Decimal("0.0")
        
        # Email is required
        email = lead.get('email')
        if email and '@' in email:
            factors.append(ScoreExplanation(
                factor_name="Email Ready",
                factor_weight=Decimal("0.4"),
                raw_value=Decimal("1.0"),
                weighted_value=Decimal("0.4"),
                explanation="Valid email address for outreach",
                data_points=[]
            ))
            base_score += Decimal("0.4")
        else:
            factors.append(ScoreExplanation(
                factor_name="No Email",
                factor_weight=Decimal("0.4"),
                raw_value=Decimal("0.0"),
                weighted_value=Decimal("0.0"),
                explanation="No email - cannot send outreach",
                data_points=[]
            ))
        
        # Review status
        review_status = lead.get('review_status', 'pending')
        if review_status == 'approved':
            factors.append(ScoreExplanation(
                factor_name="Approved",
                factor_weight=Decimal("0.3"),
                raw_value=Decimal("1.0"),
                weighted_value=Decimal("0.3"),
                explanation="Lead approved for outreach",
                data_points=[]
            ))
            base_score += Decimal("0.3")
        elif review_status == 'pending':
            factors.append(ScoreExplanation(
                factor_name="Pending Review",
                factor_weight=Decimal("0.3"),
                raw_value=Decimal("0.5"),
                weighted_value=Decimal("0.15"),
                explanation="Lead pending review",
                data_points=[]
            ))
            base_score += Decimal("0.15")
        
        # Outreach status
        outreach_status = lead.get('outreach_status', 'not_sent')
        if outreach_status == 'not_sent':
            factors.append(ScoreExplanation(
                factor_name="Fresh Lead",
                factor_weight=Decimal("0.2"),
                raw_value=Decimal("1.0"),
                weighted_value=Decimal("0.2"),
                explanation="Never contacted before",
                data_points=[]
            ))
            base_score += Decimal("0.2")
        
        # Decision maker available
        if enrichment and enrichment.primary_contact:
            factors.append(ScoreExplanation(
                factor_name="Decision Maker",
                factor_weight=Decimal("0.1"),
                raw_value=Decimal("1.0"),
                weighted_value=Decimal("0.1"),
                explanation=f"Decision maker identified: {enrichment.primary_contact.name}",
                data_points=[enrichment.primary_contact.title or "Unknown title"]
            ))
            base_score += Decimal("0.1")
        
        base_score = max(Decimal("0.0"), min(Decimal("1.0"), base_score))
        
        return ScoreComponent.from_score(
            category=ScoreCategory.OUTREACH_READINESS,
            score=base_score,
            factors=factors,
            confidence=Decimal("0.9") if email else Decimal("0.2")
        )
    
    def _apply_custom_rules(self, score: Decimal, lead: Dict[str, Any],
                            enrichment: Optional[LeadEnrichment]) -> Decimal:
        """Apply custom scoring rules."""
        for rule in self.custom_rules:
            if not rule.is_active:
                continue
            
            try:
                adjustment = self._evaluate_rule(rule, lead, enrichment)
                score += adjustment * rule.weight
            except Exception as e:
                action_logger.warning(f"Failed to apply rule {rule.name}: {e}")
        
        return score
    
    def _evaluate_rule(self, rule: ScoringRule, lead: Dict[str, Any],
                       enrichment: Optional[LeadEnrichment]) -> Decimal:
        """Evaluate a single scoring rule."""
        params = rule.parameters
        
        if rule.rule_type == ScoringRuleType.BOOLEAN:
            field = params.get('field')
            value = lead.get(field)
            target = params.get('target', True)
            return Decimal("0.1") if value == target else Decimal("0.0")
        
        elif rule.rule_type == ScoringRuleType.THRESHOLD:
            field = params.get('field')
            value = lead.get(field, 0)
            threshold = params.get('threshold', 0)
            return Decimal("0.1") if value >= threshold else Decimal("0.0")
        
        elif rule.rule_type == ScoringRuleType.MATCH:
            field = params.get('field')
            value = str(lead.get(field, '')).lower()
            matches = params.get('values', [])
            return Decimal("0.1") if any(m.lower() in value for m in matches) else Decimal("0.0")
        
        return Decimal("0.0")
    
    async def override_score(self, request: ScoreOverrideRequest) -> LeadScore:
        """
        Manually override a lead's score.
        
        Args:
            request: Override request with score and reason
        
        Returns:
            Updated LeadScore
        """
        # In production, this would fetch and update the existing score
        lead_score = LeadScore(
            lead_id=request.lead_id,
            is_manually_overridden=True,
            override_score=request.override_score,
            override_reason=request.reason,
            overridden_by=request.actor,
            overridden_at=datetime.now(),
            composite_score=request.override_score,
            composite_level=ScoreComponent._score_to_level(request.override_score)
        )
        
        action_logger.log_action(
            lead_id=str(request.lead_id),
            module_name="scoring",
            action="override_score",
            result="success",
            details={
                "new_score": float(request.override_score),
                "reason": request.reason,
                "actor": request.actor
            }
        )
        
        return lead_score
    
    async def score_batch(self, leads: List[Dict[str, Any]],
                          enrichments: Dict[UUID, LeadEnrichment] = None) -> List[LeadScore]:
        """
        Score multiple leads.
        
        Args:
            leads: List of lead dictionaries
            enrichments: Optional mapping of lead_id to enrichment
        
        Returns:
            List of LeadScores
        """
        enrichments = enrichments or {}
        scores = []
        
        for lead in leads:
            lead_id = UUID(lead.get('lead_id', lead.get('id', '')))
            enrichment = enrichments.get(lead_id)
            score = await self.score_lead(lead, enrichment)
            scores.append(score)
        
        return scores
