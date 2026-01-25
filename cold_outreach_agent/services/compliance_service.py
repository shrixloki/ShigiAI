"""Compliance and risk control service."""

import asyncio
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from ..core.models.compliance import (
    UnsubscribeRecord, UnsubscribeSource, DoNotContactEntry, DoNotContactReason,
    SpamRiskAssessment, SpamRiskLevel, DomainWarmupStatus, DomainWarmupStage,
    CoolingOffPeriod, ComplianceCheck, AddToDoNotContactRequest,
    RemoveFromDoNotContactRequest, StartCoolingOffRequest
)
from ..core.exceptions import ColdOutreachAgentError
from ..modules.logger import action_logger


class ComplianceError(ColdOutreachAgentError):
    """Compliance operation failed."""
    pass


class ComplianceService:
    """
    Service for compliance and risk controls.
    
    Features:
    - Unsubscribe handling
    - Do-Not-Contact registry
    - Spam risk scoring
    - Domain warm-up tracking
    - Cooling-off automation
    """
    
    # Risk thresholds
    BOUNCE_RATE_CRITICAL = Decimal("0.10")  # 10%
    BOUNCE_RATE_HIGH = Decimal("0.05")
    SPAM_COMPLAINT_CRITICAL = Decimal("0.003")  # 0.3%
    SPAM_COMPLAINT_HIGH = Decimal("0.001")
    
    # Domain warmup configuration
    WARMUP_STAGES = {
        DomainWarmupStage.COLD: {"daily_limit": 10, "target_bounce": Decimal("0.02")},
        DomainWarmupStage.WARMING: {"daily_limit": 30, "target_bounce": Decimal("0.03")},
        DomainWarmupStage.WARM: {"daily_limit": 75, "target_bounce": Decimal("0.04")},
        DomainWarmupStage.HOT: {"daily_limit": 200, "target_bounce": Decimal("0.05")},
    }
    
    def __init__(self, db_service, email_rate_limiter=None):
        self.db = db_service
        self.rate_limiter = email_rate_limiter
        
        self._unsubscribes: Dict[str, UnsubscribeRecord] = {}  # email -> record
        self._dnc_entries: Dict[UUID, DoNotContactEntry] = {}
        self._domain_warmups: Dict[str, DomainWarmupStatus] = {}
        self._cooling_off: List[CoolingOffPeriod] = []
    
    async def process_unsubscribe(self, email: str, lead_id: Optional[UUID] = None,
                                   source: UnsubscribeSource = UnsubscribeSource.EMAIL_LINK,
                                   campaign_id: Optional[UUID] = None,
                                   ip_address: Optional[str] = None,
                                   user_agent: Optional[str] = None) -> UnsubscribeRecord:
        """
        Process an unsubscribe request.
        
        Args:
            email: Email to unsubscribe
            lead_id: Associated lead ID
            source: Source of unsubscribe request
            campaign_id: Campaign that triggered unsubscribe
            ip_address: Request IP
            user_agent: Request user agent
        
        Returns:
            UnsubscribeRecord
        """
        email_lower = email.lower()
        domain = email_lower.split('@')[-1] if '@' in email_lower else None
        
        # Check if already unsubscribed
        if email_lower in self._unsubscribes:
            return self._unsubscribes[email_lower]
        
        record = UnsubscribeRecord(
            email=email_lower,
            domain=domain,
            lead_id=lead_id,
            source=source,
            campaign_id=campaign_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self._unsubscribes[email_lower] = record
        
        # Also add to DNC list
        await self.add_to_dnc(AddToDoNotContactRequest(
            email=email_lower,
            reason=DoNotContactReason.UNSUBSCRIBED,
            reason_detail=f"Unsubscribed via {source.value if hasattr(source, 'value') else source}"
        ))
        
        action_logger.log_action(
            lead_id=str(lead_id) if lead_id else None,
            module_name="compliance",
            action="unsubscribe",
            result="success",
            details={"email": email_lower, "source": source.value if hasattr(source, 'value') else source}
        )
        
        return record
    
    async def is_unsubscribed(self, email: str) -> bool:
        """Check if email is unsubscribed."""
        return email.lower() in self._unsubscribes
    
    async def add_to_dnc(self, request: AddToDoNotContactRequest) -> DoNotContactEntry:
        """
        Add an entry to the Do-Not-Contact list.
        
        Args:
            request: DNC entry request
        
        Returns:
            Created DoNotContactEntry
        """
        entry = DoNotContactEntry(
            email=request.email.lower() if request.email else None,
            domain=request.domain.lower() if request.domain else None,
            reason=request.reason,
            reason_detail=request.reason_detail,
            is_permanent=request.is_permanent,
            expires_at=request.expires_at
        )
        
        self._dnc_entries[entry.id] = entry
        
        action_logger.log_action(
            lead_id=None,
            module_name="compliance",
            action="add_to_dnc",
            result="success",
            details={
                "email": request.email,
                "domain": request.domain,
                "reason": request.reason.value if hasattr(request.reason, 'value') else request.reason
            }
        )
        
        return entry
    
    async def remove_from_dnc(self, request: RemoveFromDoNotContactRequest) -> bool:
        """
        Remove an entry from the DNC list.
        
        Args:
            request: Removal request
        
        Returns:
            True if removed
        """
        entry = self._dnc_entries.get(request.entry_id)
        if not entry:
            return False
        
        entry.is_active = False
        entry.deactivated_at = datetime.now()
        entry.deactivation_reason = request.reason
        
        action_logger.log_action(
            lead_id=None,
            module_name="compliance",
            action="remove_from_dnc",
            result="success",
            details={"entry_id": str(request.entry_id), "reason": request.reason}
        )
        
        return True
    
    async def check_dnc(self, email: str) -> Optional[DoNotContactEntry]:
        """
        Check if email or domain is on DNC list.
        
        Args:
            email: Email to check
        
        Returns:
            Matching DNC entry or None
        """
        email_lower = email.lower()
        
        for entry in self._dnc_entries.values():
            if not entry.is_valid():
                continue
            if entry.matches_email(email_lower):
                return entry
        
        return None
    
    async def assess_spam_risk(self, sender_email: str,
                                metrics: Dict[str, Any] = None) -> SpamRiskAssessment:
        """
        Assess spam risk for sending.
        
        Args:
            sender_email: Email being sent from
            metrics: Current sending metrics
        
        Returns:
            SpamRiskAssessment
        """
        metrics = metrics or {}
        sender_domain = sender_email.split('@')[-1] if '@' in sender_email else ''
        
        # Get domain warmup status
        warmup = await self.get_domain_warmup(sender_domain)
        
        # Calculate risk scores
        bounce_rate = Decimal(str(metrics.get('bounce_rate', 0)))
        spam_rate = Decimal(str(metrics.get('spam_complaint_rate', 0)))
        volume_today = metrics.get('emails_sent_today', 0)
        open_rate = Decimal(str(metrics.get('open_rate', 0.2)))
        
        # Content risk (simplified)
        content_risk = Decimal("0.2")  # Default low
        
        # Volume risk
        if warmup:
            expected_limit = warmup.current_daily_limit
            if volume_today > expected_limit * 1.5:
                volume_risk = Decimal("0.8")
            elif volume_today > expected_limit:
                volume_risk = Decimal("0.5")
            else:
                volume_risk = Decimal("0.1")
        else:
            volume_risk = Decimal("0.3")
        
        # Reputation risk based on bounce and spam rates
        if bounce_rate >= self.BOUNCE_RATE_CRITICAL:
            reputation_risk = Decimal("0.9")
        elif bounce_rate >= self.BOUNCE_RATE_HIGH:
            reputation_risk = Decimal("0.6")
        else:
            reputation_risk = Decimal("0.2")
        
        if spam_rate >= self.SPAM_COMPLAINT_CRITICAL:
            reputation_risk = max(reputation_risk, Decimal("0.95"))
        elif spam_rate >= self.SPAM_COMPLAINT_HIGH:
            reputation_risk = max(reputation_risk, Decimal("0.7"))
        
        # Engagement risk (low opens = high risk)
        if open_rate < Decimal("0.05"):
            engagement_risk = Decimal("0.8")
        elif open_rate < Decimal("0.10"):
            engagement_risk = Decimal("0.5")
        else:
            engagement_risk = Decimal("0.2")
        
        # Determine overall risk level
        avg_risk = (content_risk + volume_risk + reputation_risk + engagement_risk) / 4
        
        if avg_risk >= Decimal("0.7"):
            overall_risk = SpamRiskLevel.CRITICAL
        elif avg_risk >= Decimal("0.5"):
            overall_risk = SpamRiskLevel.HIGH
        elif avg_risk >= Decimal("0.3"):
            overall_risk = SpamRiskLevel.MEDIUM
        else:
            overall_risk = SpamRiskLevel.LOW
        
        # Compile risk factors
        risk_factors = []
        if bounce_rate >= self.BOUNCE_RATE_HIGH:
            risk_factors.append(f"High bounce rate: {float(bounce_rate)*100:.1f}%")
        if spam_rate >= self.SPAM_COMPLAINT_HIGH:
            risk_factors.append(f"Spam complaints detected: {float(spam_rate)*100:.2f}%")
        if open_rate < Decimal("0.10"):
            risk_factors.append(f"Low open rate: {float(open_rate)*100:.1f}%")
        if warmup and volume_today > warmup.current_daily_limit:
            risk_factors.append(f"Volume exceeds warmup limit: {volume_today}/{warmup.current_daily_limit}")
        
        # Mitigation suggestions
        suggestions = []
        if bounce_rate >= self.BOUNCE_RATE_HIGH:
            suggestions.append("Verify email list quality before sending")
        if open_rate < Decimal("0.15"):
            suggestions.append("Improve subject lines and sender reputation")
        if overall_risk in [SpamRiskLevel.HIGH, SpamRiskLevel.CRITICAL]:
            suggestions.append("Reduce sending volume and wait for metrics to improve")
        
        assessment = SpamRiskAssessment(
            sender_email=sender_email,
            sender_domain=sender_domain,
            overall_risk=overall_risk,
            content_risk_score=content_risk,
            volume_risk_score=volume_risk,
            reputation_risk_score=reputation_risk,
            engagement_risk_score=engagement_risk,
            risk_factors=risk_factors,
            mitigation_suggestions=suggestions,
            metrics=metrics,
            valid_until=datetime.now() + timedelta(hours=1)
        )
        
        return assessment
    
    async def get_domain_warmup(self, domain: str) -> Optional[DomainWarmupStatus]:
        """Get warmup status for a domain."""
        return self._domain_warmups.get(domain.lower())
    
    async def init_domain_warmup(self, domain: str) -> DomainWarmupStatus:
        """
        Initialize domain warmup tracking.
        
        Args:
            domain: Email domain to warm up
        
        Returns:
            DomainWarmupStatus
        """
        domain_lower = domain.lower()
        
        if domain_lower in self._domain_warmups:
            return self._domain_warmups[domain_lower]
        
        stage_config = self.WARMUP_STAGES[DomainWarmupStage.COLD]
        
        warmup = DomainWarmupStatus(
            domain=domain_lower,
            stage=DomainWarmupStage.COLD,
            warmup_started_at=datetime.now(),
            stage_started_at=datetime.now(),
            current_daily_limit=stage_config["daily_limit"],
            target_daily_limit=self.WARMUP_STAGES[DomainWarmupStage.HOT]["daily_limit"]
        )
        
        self._domain_warmups[domain_lower] = warmup
        
        action_logger.log_action(
            lead_id=None,
            module_name="compliance",
            action="init_warmup",
            result="success",
            details={"domain": domain_lower}
        )
        
        return warmup
    
    async def update_domain_warmup(self, domain: str, 
                                    emails_sent: int = 0,
                                    bounces: int = 0,
                                    opens: int = 0) -> Optional[DomainWarmupStatus]:
        """
        Update domain warmup metrics and potentially advance stage.
        
        Args:
            domain: Domain to update
            emails_sent: Emails sent today
            bounces: Bounces today
            opens: Opens today
        
        Returns:
            Updated DomainWarmupStatus
        """
        warmup = await self.get_domain_warmup(domain)
        if not warmup:
            return None
        
        warmup.emails_sent_today = emails_sent
        warmup.total_emails_sent += emails_sent
        warmup.last_email_sent_at = datetime.now()
        
        # Calculate rates
        if warmup.total_emails_sent > 0:
            total_bounces = int(float(warmup.bounce_rate) * warmup.total_emails_sent) + bounces
            warmup.bounce_rate = Decimal(str(total_bounces / warmup.total_emails_sent))
            
            total_opens = int(float(warmup.open_rate) * warmup.total_emails_sent) + opens
            warmup.open_rate = Decimal(str(total_opens / warmup.total_emails_sent))
        
        # Check for stage advancement
        stage_config = self.WARMUP_STAGES[warmup.stage]
        days_in_stage = (datetime.now() - warmup.stage_started_at).days if warmup.stage_started_at else 0
        
        # Advance if: good metrics for 3+ days and at limit
        should_advance = (
            days_in_stage >= 3 and
            warmup.bounce_rate <= stage_config["target_bounce"] and
            warmup.emails_sent_today >= warmup.current_daily_limit * 0.8
        )
        
        if should_advance:
            # Get next stage
            stages = list(DomainWarmupStage)
            current_idx = stages.index(warmup.stage)
            if current_idx < len(stages) - 1:
                new_stage = stages[current_idx + 1]
                warmup.stage = new_stage
                warmup.stage_started_at = datetime.now()
                warmup.current_daily_limit = self.WARMUP_STAGES[new_stage]["daily_limit"]
                
                action_logger.log_action(
                    lead_id=None,
                    module_name="compliance",
                    action="advance_warmup",
                    result="success",
                    details={"domain": domain, "new_stage": new_stage.value}
                )
        
        # Check for health issues
        warmup.health_issues = []
        if warmup.bounce_rate >= self.BOUNCE_RATE_HIGH:
            warmup.is_healthy = False
            warmup.health_issues.append(f"High bounce rate: {float(warmup.bounce_rate)*100:.1f}%")
        
        warmup.last_health_check = datetime.now()
        warmup.updated_at = datetime.now()
        
        return warmup
    
    async def start_cooling_off(self, request: StartCoolingOffRequest) -> CoolingOffPeriod:
        """
        Start a cooling-off period for a lead or domain.
        
        Args:
            request: Cooling-off request
        
        Returns:
            CoolingOffPeriod
        """
        period = CoolingOffPeriod(
            lead_id=request.lead_id,
            domain=request.domain.lower() if request.domain else None,
            ends_at=datetime.now() + timedelta(hours=request.duration_hours),
            duration_hours=request.duration_hours,
            reason=request.reason
        )
        
        self._cooling_off.append(period)
        
        action_logger.log_action(
            lead_id=str(request.lead_id) if request.lead_id else None,
            module_name="compliance",
            action="start_cooling_off",
            result="success",
            details={
                "duration_hours": request.duration_hours,
                "reason": request.reason
            }
        )
        
        return period
    
    async def is_in_cooling_off(self, lead_id: Optional[UUID] = None,
                                 domain: Optional[str] = None) -> Optional[CoolingOffPeriod]:
        """Check if lead or domain is in cooling-off period."""
        for period in self._cooling_off:
            if not period.is_in_effect():
                continue
            
            if lead_id and period.lead_id == lead_id:
                return period
            if domain and period.domain and period.domain.lower() == domain.lower():
                return period
        
        return None
    
    async def run_compliance_check(self, lead_id: UUID, 
                                    email: str) -> ComplianceCheck:
        """
        Run a full compliance check before sending.
        
        Args:
            lead_id: Lead to check
            email: Email address to send to
        
        Returns:
            ComplianceCheck result
        """
        email_lower = email.lower()
        domain = email_lower.split('@')[-1] if '@' in email_lower else ''
        
        check = ComplianceCheck(
            lead_id=lead_id,
            email=email_lower,
            checks_performed=[]
        )
        
        # Check unsubscribe
        check.checks_performed.append("unsubscribe_check")
        check.is_unsubscribed = await self.is_unsubscribed(email_lower)
        if check.is_unsubscribed:
            check.is_compliant = False
            check.failed_checks.append("Email is unsubscribed")
        
        # Check DNC
        check.checks_performed.append("dnc_check")
        dnc_entry = await self.check_dnc(email_lower)
        if dnc_entry:
            check.is_do_not_contact = True
            check.is_compliant = False
            check.failed_checks.append(f"On DNC list: {dnc_entry.reason}")
        
        # Check cooling off
        check.checks_performed.append("cooling_off_check")
        cooling = await self.is_in_cooling_off(lead_id=lead_id, domain=domain)
        if cooling:
            check.is_in_cooling_off = True
            check.is_compliant = False
            check.failed_checks.append(f"In cooling-off: {cooling.get_remaining_hours()}h remaining")
        
        # Check domain warmup limits
        check.checks_performed.append("warmup_limit_check")
        # Get sender domain from settings (simplified)
        sender_domain = "example.com"  # In production, get from config
        warmup = await self.get_domain_warmup(sender_domain)
        if warmup and not warmup.can_send():
            check.daily_limit_reached = True
            check.is_compliant = False
            check.failed_checks.append("Daily sending limit reached")
        
        # Run spam risk assessment
        check.checks_performed.append("spam_risk_check")
        risk = await self.assess_spam_risk(sender_domain)
        check.spam_risk = risk.overall_risk
        if risk.should_pause_sending():
            check.warnings.append(f"High spam risk: {risk.overall_risk.value}")
        
        action_logger.log_action(
            lead_id=str(lead_id),
            module_name="compliance",
            action="compliance_check",
            result="pass" if check.is_compliant else "fail",
            details={
                "can_send": check.can_send(),
                "failed_checks": check.failed_checks
            }
        )
        
        return check
    
    async def get_unsubscribe_stats(self) -> Dict[str, Any]:
        """Get unsubscribe statistics."""
        total = len(self._unsubscribes)
        by_source = {}
        
        for record in self._unsubscribes.values():
            source = record.source.value if hasattr(record.source, 'value') else record.source
            by_source[source] = by_source.get(source, 0) + 1
        
        return {
            "total_unsubscribed": total,
            "by_source": by_source
        }
    
    async def get_dnc_stats(self) -> Dict[str, Any]:
        """Get DNC list statistics."""
        active = [e for e in self._dnc_entries.values() if e.is_valid()]
        
        by_reason = {}
        for entry in active:
            reason = entry.reason.value if hasattr(entry.reason, 'value') else entry.reason
            by_reason[reason] = by_reason.get(reason, 0) + 1
        
        return {
            "total_entries": len(active),
            "by_reason": by_reason
        }
    
    async def cleanup_expired(self):
        """Clean up expired cooling-off periods and DNC entries."""
        # Remove expired cooling-off periods
        self._cooling_off = [p for p in self._cooling_off if p.is_in_effect()]
        
        # Deactivate expired DNC entries
        for entry in self._dnc_entries.values():
            if entry.expires_at and entry.expires_at < datetime.now():
                entry.is_active = False
