"""Production-grade email service with transactional state management."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from ...core.models.email import EmailCampaign, EmailCampaignCreate, EmailState, CampaignType
from ...core.models.lead import Lead
from ...core.models.common import OperationResult
from ...core.exceptions import EmailDeliveryError, RateLimitExceededError, ConfigurationError
from ...core.state_machines.email_state_machine import EmailStateMachine
from .providers import SMTPProvider, GmailAPIProvider, EmailProvider
from .templates import EmailTemplateManager


class ProductionEmailService:
    """Production-grade email service with comprehensive error handling and state management."""
    
    def __init__(
        self,
        db_service,
        audit_service,
        config: Dict[str, Any]
    ):
        self.db = db_service
        self.audit = audit_service
        self.config = config
        self.state_machine = EmailStateMachine(db_service, audit_service)
        self.template_manager = EmailTemplateManager()
        
        # Initialize email providers
        self.providers: Dict[str, EmailProvider] = {}
        self._initialize_providers()
        
        # Rate limiting
        self.max_emails_per_day = config.get('max_emails_per_day', 20)
        self.max_emails_per_hour = config.get('max_emails_per_hour', 5)
        self.rate_limit_window = timedelta(hours=1)
        
        # Retry configuration
        self.max_retry_attempts = 3
        self.retry_delays = [300, 900, 3600]  # 5min, 15min, 1hour
    
    def _initialize_providers(self):
        """Initialize email providers based on configuration."""
        try:
            # SMTP Provider
            if self.config.get('smtp_enabled', True):
                smtp_config = {
                    'host': self.config.get('smtp_host', 'smtp.gmail.com'),
                    'port': self.config.get('smtp_port', 587),
                    'username': self.config.get('smtp_username'),
                    'password': self.config.get('smtp_password'),
                    'use_tls': self.config.get('smtp_use_tls', True)
                }
                
                if smtp_config['username'] and smtp_config['password']:
                    self.providers['smtp'] = SMTPProvider(smtp_config)
            
            # Gmail API Provider
            if self.config.get('gmail_api_enabled', False):
                gmail_config = {
                    'credentials_path': self.config.get('gmail_credentials_path'),
                    'token_path': self.config.get('gmail_token_path'),
                    'scopes': ['https://www.googleapis.com/auth/gmail.send']
                }
                
                if gmail_config['credentials_path']:
                    self.providers['gmail_api'] = GmailAPIProvider(gmail_config)
            
            if not self.providers:
                raise ConfigurationError("No email providers configured")
                
        except Exception as e:
            raise ConfigurationError(f"Email provider initialization failed: {str(e)}")
    
    async def send_email_campaign(
        self,
        campaign: EmailCampaign,
        provider_preference: Optional[str] = None
    ) -> OperationResult[EmailCampaign]:
        """
        Send email campaign with transactional state management.
        
        Args:
            campaign: Email campaign to send
            provider_preference: Preferred email provider ('smtp', 'gmail_api')
            
        Returns:
            OperationResult with updated campaign or error
        """
        try:
            # Check rate limits
            rate_limit_check = await self._check_rate_limits()
            if not rate_limit_check.success:
                return rate_limit_check
            
            # Transition to sending state
            sending_result = await self.state_machine.mark_sending(campaign.id)
            if not sending_result.success:
                return OperationResult.error_result(
                    error=f"Failed to transition to sending state: {sending_result.error}",
                    error_code="STATE_TRANSITION_FAILED"
                )
            
            # Select email provider
            provider = self._select_provider(provider_preference)
            if not provider:
                await self.state_machine.mark_failed(
                    campaign.id,
                    "No available email provider",
                    "system"
                )
                return OperationResult.error_result(
                    error="No available email provider",
                    error_code="NO_PROVIDER_AVAILABLE"
                )
            
            # Send email
            send_result = await self._send_with_provider(provider, campaign)
            
            if send_result.success:
                # Mark as sent
                await self.state_machine.mark_sent(
                    campaign.id,
                    send_result.data.get('message_id', ''),
                    send_result.data.get('provider_response', {}),
                    "system"
                )
                
                # Update rate limit tracking
                await self._record_sent_email()
                
                return OperationResult.success_result(
                    data=await self.db.get_email_campaign_by_id(campaign.id),
                    metadata={
                        "provider_used": provider.name,
                        "message_id": send_result.data.get('message_id')
                    }
                )
            else:
                # Mark as failed
                await self.state_machine.mark_failed(
                    campaign.id,
                    send_result.error,
                    "system"
                )
                
                return OperationResult.error_result(
                    error=send_result.error,
                    error_code=send_result.error_code
                )
                
        except Exception as e:
            # Mark as failed on unexpected error
            try:
                await self.state_machine.mark_failed(
                    campaign.id,
                    f"Unexpected error: {str(e)}",
                    "system"
                )
            except Exception:
                pass  # Don't fail if we can't update state
            
            return OperationResult.error_result(
                error=f"Email sending failed: {str(e)}",
                error_code="SEND_ERROR"
            )
    
    async def create_and_send_campaign(
        self,
        lead: Lead,
        campaign_type: CampaignType,
        template_id: Optional[str] = None,
        custom_subject: Optional[str] = None,
        custom_body: Optional[str] = None
    ) -> OperationResult[EmailCampaign]:
        """Create and send an email campaign for a lead."""
        try:
            # Validate lead is ready for outreach
            if not lead.is_ready_for_outreach():
                return OperationResult.error_result(
                    error="Lead is not ready for outreach",
                    error_code="LEAD_NOT_READY"
                )
            
            # Generate email content
            content_result = await self._generate_email_content(
                lead, campaign_type, template_id, custom_subject, custom_body
            )
            if not content_result.success:
                return content_result
            
            subject, body_text, body_html = content_result.data
            
            # Create campaign
            campaign_data = EmailCampaignCreate(
                lead_id=lead.id,
                campaign_type=campaign_type,
                template_id=template_id,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                to_email=lead.email,
                to_name=lead.business_name,
                from_email=self.config.get('sender_email'),
                from_name=self.config.get('sender_name')
            )
            
            campaign = await self.db.create_email_campaign(campaign_data)
            
            # Send campaign
            return await self.send_email_campaign(campaign)
            
        except Exception as e:
            return OperationResult.error_result(
                error=f"Failed to create and send campaign: {str(e)}",
                error_code="CAMPAIGN_CREATION_FAILED"
            )
    
    async def process_queued_campaigns(self) -> OperationResult[Dict[str, int]]:
        """Process all queued email campaigns."""
        try:
            queued_campaigns = await self.state_machine.get_queued_campaigns()
            
            results = {
                "processed": 0,
                "sent": 0,
                "failed": 0,
                "rate_limited": 0
            }
            
            for campaign in queued_campaigns:
                results["processed"] += 1
                
                # Check rate limits before each send
                rate_limit_check = await self._check_rate_limits()
                if not rate_limit_check.success:
                    results["rate_limited"] += 1
                    break  # Stop processing if rate limited
                
                send_result = await self.send_email_campaign(campaign)
                
                if send_result.success:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                
                # Add delay between sends
                await asyncio.sleep(2)
            
            return OperationResult.success_result(data=results)
            
        except Exception as e:
            return OperationResult.error_result(
                error=f"Failed to process queued campaigns: {str(e)}",
                error_code="QUEUE_PROCESSING_FAILED"
            )
    
    async def retry_failed_campaigns(self) -> OperationResult[Dict[str, int]]:
        """Retry failed email campaigns that are eligible for retry."""
        try:
            failed_campaigns = await self.state_machine.get_failed_campaigns_for_retry()
            
            results = {
                "processed": 0,
                "retried": 0,
                "failed": 0,
                "skipped": 0
            }
            
            for campaign in failed_campaigns:
                results["processed"] += 1
                
                # Check rate limits
                rate_limit_check = await self._check_rate_limits()
                if not rate_limit_check.success:
                    results["skipped"] += 1
                    continue
                
                # Retry the campaign
                retry_result = await self.state_machine.retry_failed_email(campaign.id)
                
                if retry_result.success:
                    # Send the retried campaign
                    send_result = await self.send_email_campaign(retry_result.data)
                    
                    if send_result.success:
                        results["retried"] += 1
                    else:
                        results["failed"] += 1
                else:
                    results["skipped"] += 1
                
                # Add delay between retries
                await asyncio.sleep(3)
            
            return OperationResult.success_result(data=results)
            
        except Exception as e:
            return OperationResult.error_result(
                error=f"Failed to retry campaigns: {str(e)}",
                error_code="RETRY_PROCESSING_FAILED"
            )
    
    async def _check_rate_limits(self) -> OperationResult[None]:
        """Check if we're within rate limits."""
        try:
            now = datetime.now()
            
            # Check daily limit
            daily_count = await self._get_emails_sent_in_period(
                now - timedelta(days=1), now
            )
            
            if daily_count >= self.max_emails_per_day:
                return OperationResult.error_result(
                    error=f"Daily rate limit exceeded ({daily_count}/{self.max_emails_per_day})",
                    error_code="DAILY_RATE_LIMIT_EXCEEDED"
                )
            
            # Check hourly limit
            hourly_count = await self._get_emails_sent_in_period(
                now - self.rate_limit_window, now
            )
            
            if hourly_count >= self.max_emails_per_hour:
                return OperationResult.error_result(
                    error=f"Hourly rate limit exceeded ({hourly_count}/{self.max_emails_per_hour})",
                    error_code="HOURLY_RATE_LIMIT_EXCEEDED"
                )
            
            return OperationResult.success_result()
            
        except Exception as e:
            return OperationResult.error_result(
                error=f"Rate limit check failed: {str(e)}",
                error_code="RATE_LIMIT_CHECK_FAILED"
            )
    
    async def _get_emails_sent_in_period(self, start_time: datetime, end_time: datetime) -> int:
        """Get count of emails sent in a time period."""
        try:
            # This would query the database for sent emails in the time period
            # Implementation depends on the database service
            campaigns = await self.db.get_email_campaigns_sent_in_period(start_time, end_time)
            return len(campaigns)
        except Exception:
            return 0
    
    async def _record_sent_email(self):
        """Record that an email was sent for rate limiting."""
        # This could update a separate rate limiting table or cache
        # For now, we rely on the email campaign records
        pass
    
    def _select_provider(self, preference: Optional[str] = None) -> Optional[EmailProvider]:
        """Select the best available email provider."""
        if preference and preference in self.providers:
            provider = self.providers[preference]
            if provider.is_available():
                return provider
        
        # Try providers in order of preference
        provider_order = ['gmail_api', 'smtp']
        
        for provider_name in provider_order:
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                if provider.is_available():
                    return provider
        
        return None
    
    async def _send_with_provider(
        self, 
        provider: EmailProvider, 
        campaign: EmailCampaign
    ) -> OperationResult[Dict[str, Any]]:
        """Send email using a specific provider."""
        try:
            return await provider.send_email(
                to_email=campaign.to_email,
                to_name=campaign.to_name,
                from_email=campaign.from_email,
                from_name=campaign.from_name,
                subject=campaign.subject,
                body_text=campaign.body_text,
                body_html=campaign.body_html
            )
        except Exception as e:
            return OperationResult.error_result(
                error=f"Provider {provider.name} failed: {str(e)}",
                error_code="PROVIDER_ERROR"
            )
    
    async def _generate_email_content(
        self,
        lead: Lead,
        campaign_type: CampaignType,
        template_id: Optional[str] = None,
        custom_subject: Optional[str] = None,
        custom_body: Optional[str] = None
    ) -> OperationResult[tuple]:
        """Generate email content from templates."""
        try:
            if custom_subject and custom_body:
                return OperationResult.success_result(
                    data=(custom_subject, custom_body, None)
                )
            
            # Use template manager to generate content
            template_result = await self.template_manager.generate_email(
                lead=lead,
                campaign_type=campaign_type,
                template_id=template_id
            )
            
            if not template_result.success:
                return template_result
            
            return OperationResult.success_result(data=template_result.data)
            
        except Exception as e:
            return OperationResult.error_result(
                error=f"Content generation failed: {str(e)}",
                error_code="CONTENT_GENERATION_FAILED"
            )
    
    async def get_campaign_statistics(self) -> Dict[str, Any]:
        """Get email campaign statistics."""
        try:
            stats = {}
            
            # Get counts by state
            for state in EmailState:
                campaigns = await self.state_machine.get_campaigns_by_state(state)
                stats[f"{state}_count"] = len(campaigns)
            
            # Get recent activity
            now = datetime.now()
            stats["sent_today"] = await self._get_emails_sent_in_period(
                now.replace(hour=0, minute=0, second=0, microsecond=0), now
            )
            
            stats["sent_this_hour"] = await self._get_emails_sent_in_period(
                now - timedelta(hours=1), now
            )
            
            # Rate limit status
            stats["daily_limit"] = self.max_emails_per_day
            stats["hourly_limit"] = self.max_emails_per_hour
            stats["daily_remaining"] = max(0, self.max_emails_per_day - stats["sent_today"])
            stats["hourly_remaining"] = max(0, self.max_emails_per_hour - stats["sent_this_hour"])
            
            return stats
            
        except Exception as e:
            return {"error": f"Failed to get statistics: {str(e)}"}
    
    async def cancel_campaign(self, campaign_id: UUID, reason: str) -> OperationResult[EmailCampaign]:
        """Cancel a queued email campaign."""
        return await self.state_machine.cancel_email(campaign_id, reason, "user")
    
    async def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all email providers."""
        status = {}
        
        for name, provider in self.providers.items():
            status[name] = {
                "available": provider.is_available(),
                "name": provider.name,
                "config": provider.get_config_summary()
            }
        
        return status