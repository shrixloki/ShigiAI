"""Production system integration tests."""

import asyncio
import pytest
from pathlib import Path
from uuid import uuid4

from ..config.production_settings import ProductionSettings
from ..infrastructure.database.service import ProductionDatabaseService
from ..infrastructure.logging.service import ProductionLoggingService
from ..infrastructure.email.service import ProductionEmailService
from ..infrastructure.email.providers import MockEmailProvider
from ..core.state_machines.lead_state_machine import LeadStateMachine
from ..core.state_machines.email_state_machine import EmailStateMachine
from ..core.models.lead import LeadCreate, LeadState, ReviewStatus, DiscoverySource
from ..core.models.email import EmailCampaignCreate, EmailState, CampaignType
from ..core.models.common import EntityType


@pytest.fixture
async def test_settings():
    """Create test settings."""
    settings = ProductionSettings()
    settings.database.path = Path(":memory:")  # In-memory database for tests
    settings.logging.log_dir = Path("test_logs")
    settings.logging.log_dir.mkdir(exist_ok=True)
    settings.email.primary_provider = "mock"
    return settings


@pytest.fixture
async def db_service(test_settings):
    """Create test database service."""
    db = ProductionDatabaseService(test_settings.database.path)
    await db.initialize()
    yield db


@pytest.fixture
async def logging_service(test_settings):
    """Create test logging service."""
    logger = ProductionLoggingService(
        log_dir=test_settings.logging.log_dir,
        log_level="DEBUG"
    )
    yield logger


@pytest.fixture
async def email_service(db_service, logging_service):
    """Create test email service with mock provider."""
    config = {
        'primary_provider': 'mock',
        'sender_name': 'Test Sender',
        'sender_email': 'test@example.com',
        'max_emails_per_day': 100,
        'max_emails_per_hour': 50
    }
    
    service = ProductionEmailService(
        db_service=db_service,
        audit_service=logging_service,
        config=config
    )
    
    # Add mock provider
    mock_provider = MockEmailProvider({})
    service.providers['mock'] = mock_provider
    service.primary_provider = 'mock'
    
    yield service


@pytest.fixture
async def lead_state_machine(db_service, logging_service):
    """Create test lead state machine."""
    return LeadStateMachine(db_service, logging_service)


@pytest.fixture
async def email_state_machine(db_service, logging_service):
    """Create test email state machine."""
    return EmailStateMachine(db_service, logging_service)


@pytest.fixture
def sample_lead_data():
    """Create sample lead data."""
    return LeadCreate(
        business_name="Test Restaurant",
        category="restaurant",
        location="Austin, TX",
        maps_url="https://maps.google.com/test",
        website_url="https://testrestaurant.com",
        email="contact@testrestaurant.com",
        phone="(555) 123-4567",
        discovery_source=DiscoverySource.GOOGLE_MAPS,
        discovery_confidence=0.9,
        tag="test_lead"
    )


class TestDatabaseService:
    """Test database service functionality."""
    
    async def test_database_initialization(self, db_service):
        """Test database initialization."""
        # Database should be initialized without errors
        assert db_service is not None
        
        # Test migration status
        status = await db_service.migration_manager.get_migration_status()
        assert status["current_version"] > 0
        assert status["pending_migrations"] == 0
    
    async def test_lead_crud_operations(self, db_service, sample_lead_data):
        """Test lead CRUD operations."""
        
        # Create lead
        lead = await db_service.create_lead(sample_lead_data)
        assert lead.id is not None
        assert lead.business_name == sample_lead_data.business_name
        assert lead.lifecycle_state == LeadState.DISCOVERED
        assert lead.review_status == ReviewStatus.PENDING
        
        # Read lead
        retrieved_lead = await db_service.get_lead_by_id(lead.id)
        assert retrieved_lead is not None
        assert retrieved_lead.id == lead.id
        assert retrieved_lead.business_name == lead.business_name
        
        # Update lead
        from ..core.models.lead import LeadUpdate
        update_data = LeadUpdate(business_name="Updated Restaurant")
        updated_lead = await db_service.update_lead(lead.id, update_data)
        assert updated_lead.business_name == "Updated Restaurant"
        assert updated_lead.version == lead.version + 1
        
        # List leads
        from ..core.models.common import PaginationParams
        result = await db_service.get_leads(pagination=PaginationParams())
        assert len(result.items) >= 1
        assert any(l.id == lead.id for l in result.items)
    
    async def test_duplicate_lead_prevention(self, db_service, sample_lead_data):
        """Test duplicate lead prevention."""
        
        # Create first lead
        lead1 = await db_service.create_lead(sample_lead_data)
        assert lead1 is not None
        
        # Try to create duplicate
        with pytest.raises(Exception):  # Should raise DatabaseError
            await db_service.create_lead(sample_lead_data)
    
    async def test_email_campaign_operations(self, db_service, sample_lead_data):
        """Test email campaign operations."""
        
        # Create lead first
        lead = await db_service.create_lead(sample_lead_data)
        
        # Create email campaign
        campaign_data = EmailCampaignCreate(
            lead_id=lead.id,
            campaign_type=CampaignType.INITIAL,
            subject="Test Subject",
            body_text="Test body",
            to_email=lead.email,
            to_name=lead.business_name,
            from_email="test@example.com",
            from_name="Test Sender"
        )
        
        campaign = await db_service.create_email_campaign(campaign_data)
        assert campaign.id is not None
        assert campaign.lead_id == lead.id
        assert campaign.email_state == EmailState.QUEUED
        
        # Retrieve campaign
        retrieved_campaign = await db_service.get_email_campaign_by_id(campaign.id)
        assert retrieved_campaign is not None
        assert retrieved_campaign.id == campaign.id


class TestLeadStateMachine:
    """Test lead state machine functionality."""
    
    async def test_lead_lifecycle(self, lead_state_machine, db_service, sample_lead_data):
        """Test complete lead lifecycle."""
        
        # Create lead
        lead = await db_service.create_lead(sample_lead_data)
        assert lead.lifecycle_state == LeadState.DISCOVERED
        
        # Transition to analyzing
        result = await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.ANALYZING,
            actor="test_system"
        )
        assert result.success
        assert result.data.lifecycle_state == LeadState.ANALYZING
        
        # Transition to analyzed
        result = await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.ANALYZED,
            actor="test_system"
        )
        assert result.success
        
        # Transition to pending review
        result = await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.PENDING_REVIEW,
            actor="test_system"
        )
        assert result.success
        
        # Approve lead
        result = await lead_state_machine.approve_lead(
            lead_id=lead.id,
            actor="test_user"
        )
        assert result.success
        assert result.data.lifecycle_state == LeadState.APPROVED
        assert result.data.review_status == ReviewStatus.APPROVED
    
    async def test_invalid_state_transitions(self, lead_state_machine, db_service, sample_lead_data):
        """Test invalid state transitions are rejected."""
        
        # Create lead
        lead = await db_service.create_lead(sample_lead_data)
        
        # Try invalid transition (discovered -> approved)
        result = await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.APPROVED,
            actor="test_system"
        )
        assert not result.success
        assert "Invalid transition" in result.error
    
    async def test_lead_approval_requirements(self, lead_state_machine, db_service, sample_lead_data):
        """Test lead approval requirements."""
        
        # Create lead without email
        lead_data = sample_lead_data.copy()
        lead_data.email = None
        lead = await db_service.create_lead(lead_data)
        
        # Move to pending review
        await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.ANALYZING,
            actor="test_system"
        )
        await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.ANALYZED,
            actor="test_system"
        )
        await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.PENDING_REVIEW,
            actor="test_system"
        )
        
        # Approve lead
        result = await lead_state_machine.approve_lead(
            lead_id=lead.id,
            actor="test_user"
        )
        assert result.success  # Approval should work
        
        # Try to mark ready for outreach (should fail without email)
        result = await lead_state_machine.mark_ready_for_outreach(
            lead_id=lead.id,
            actor="test_system"
        )
        assert not result.success
        assert "email" in result.error.lower()


class TestEmailStateMachine:
    """Test email state machine functionality."""
    
    async def test_email_lifecycle(self, email_state_machine, db_service, sample_lead_data):
        """Test complete email lifecycle."""
        
        # Create lead and campaign
        lead = await db_service.create_lead(sample_lead_data)
        
        campaign_data = EmailCampaignCreate(
            lead_id=lead.id,
            campaign_type=CampaignType.INITIAL,
            subject="Test Subject",
            body_text="Test body",
            to_email=lead.email,
            to_name=lead.business_name,
            from_email="test@example.com",
            from_name="Test Sender"
        )
        
        campaign = await db_service.create_email_campaign(campaign_data)
        assert campaign.email_state == EmailState.QUEUED
        
        # Mark as sending
        result = await email_state_machine.mark_sending(campaign.id)
        assert result.success
        assert result.data.email_state == EmailState.SENDING
        
        # Mark as sent
        result = await email_state_machine.mark_sent(
            campaign_id=campaign.id,
            message_id="test_message_123",
            provider_response={"status": "sent"}
        )
        assert result.success
        assert result.data.email_state == EmailState.SENT
        assert result.data.message_id == "test_message_123"
        
        # Mark as delivered
        result = await email_state_machine.mark_delivered(campaign.id)
        assert result.success
        assert result.data.email_state == EmailState.DELIVERED
    
    async def test_email_retry_logic(self, email_state_machine, db_service, sample_lead_data):
        """Test email retry logic."""
        
        # Create lead and campaign
        lead = await db_service.create_lead(sample_lead_data)
        
        campaign_data = EmailCampaignCreate(
            lead_id=lead.id,
            campaign_type=CampaignType.INITIAL,
            subject="Test Subject",
            body_text="Test body",
            to_email=lead.email,
            to_name=lead.business_name,
            from_email="test@example.com",
            from_name="Test Sender"
        )
        
        campaign = await db_service.create_email_campaign(campaign_data)
        
        # Mark as failed
        result = await email_state_machine.mark_failed(
            campaign_id=campaign.id,
            error_message="SMTP connection failed"
        )
        assert result.success
        assert result.data.email_state == EmailState.FAILED
        assert result.data.error_count == 1
        
        # Retry should be allowed
        result = await email_state_machine.retry_failed_email(campaign.id)
        assert result.success
        assert result.data.email_state == EmailState.QUEUED
        assert result.data.error_count == 1  # Error count preserved


class TestEmailService:
    """Test email service functionality."""
    
    async def test_email_sending(self, email_service, db_service, sample_lead_data):
        """Test email sending functionality."""
        
        # Create and approve lead
        lead = await db_service.create_lead(sample_lead_data)
        
        # Update lead to approved state
        from ..core.models.lead import LeadUpdate
        await db_service.update_lead(lead.id, {"lifecycle_state": LeadState.APPROVED, "review_status": ReviewStatus.APPROVED})
        lead = await db_service.get_lead_by_id(lead.id)
        
        # Create and send campaign
        result = await email_service.create_and_send_campaign(
            lead=lead,
            campaign_type=CampaignType.INITIAL
        )
        
        assert result.success
        assert result.data.email_state == EmailState.SENT
        
        # Check mock provider received the email
        mock_provider = email_service.providers['mock']
        sent_emails = mock_provider.get_sent_emails()
        assert len(sent_emails) == 1
        assert sent_emails[0]['to_email'] == lead.email
    
    async def test_rate_limiting(self, email_service, db_service, sample_lead_data):
        """Test email rate limiting."""
        
        # Create multiple leads
        leads = []
        for i in range(5):
            lead_data = sample_lead_data.copy()
            lead_data.business_name = f"Test Restaurant {i}"
            lead_data.email = f"test{i}@example.com"
            lead = await db_service.create_lead(lead_data)
            
            # Update to approved state
            await db_service.update_lead(lead.id, {"lifecycle_state": LeadState.APPROVED, "review_status": ReviewStatus.APPROVED})
            leads.append(await db_service.get_lead_by_id(lead.id))
        
        # Set low rate limit for testing
        email_service.max_emails_per_hour = 2
        
        # Send emails
        sent_count = 0
        rate_limited_count = 0
        
        for lead in leads:
            result = await email_service.create_and_send_campaign(
                lead=lead,
                campaign_type=CampaignType.INITIAL
            )
            
            if result.success:
                sent_count += 1
            elif "rate limit" in result.error.lower():
                rate_limited_count += 1
        
        # Should hit rate limit
        assert sent_count <= 2
        assert rate_limited_count > 0


class TestSystemIntegration:
    """Test full system integration."""
    
    async def test_complete_workflow(self, db_service, logging_service, email_service, 
                                   lead_state_machine, email_state_machine, sample_lead_data):
        """Test complete lead-to-email workflow."""
        
        # 1. Create lead (discovery simulation)
        lead = await db_service.create_lead(sample_lead_data)
        assert lead.lifecycle_state == LeadState.DISCOVERED
        
        # 2. Analyze lead (website analysis simulation)
        result = await lead_state_machine.mark_analysis_complete(
            lead_id=lead.id,
            analysis_results={"email_found": True, "website_quality": "good"}
        )
        assert result.success
        
        # 3. Move to pending review
        result = await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.PENDING_REVIEW,
            actor="system"
        )
        assert result.success
        
        # 4. Human approval
        result = await lead_state_machine.approve_lead(
            lead_id=lead.id,
            actor="human_reviewer"
        )
        assert result.success
        
        # 5. Mark ready for outreach
        result = await lead_state_machine.mark_ready_for_outreach(
            lead_id=lead.id
        )
        assert result.success
        
        # 6. Send email
        updated_lead = await db_service.get_lead_by_id(lead.id)
        result = await email_service.create_and_send_campaign(
            lead=updated_lead,
            campaign_type=CampaignType.INITIAL
        )
        assert result.success
        
        # 7. Verify audit trail
        # Check that all state transitions were logged
        # This would require implementing audit log retrieval
        
        # 8. Verify final states
        final_lead = await db_service.get_lead_by_id(lead.id)
        assert final_lead.lifecycle_state == LeadState.APPROVED
        assert final_lead.review_status == ReviewStatus.APPROVED
        
        campaign = result.data
        assert campaign.email_state == EmailState.SENT
    
    async def test_error_handling_and_recovery(self, db_service, lead_state_machine, sample_lead_data):
        """Test error handling and recovery mechanisms."""
        
        # Create lead
        lead = await db_service.create_lead(sample_lead_data)
        
        # Simulate analysis failure
        result = await lead_state_machine.mark_failed(
            lead_id=lead.id,
            error_reason="Website analysis timeout"
        )
        assert result.success
        assert result.data.lifecycle_state == LeadState.FAILED
        
        # Retry from failed state
        result = await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.DISCOVERED,
            actor="retry_system"
        )
        assert result.success
        
        # Should be able to continue normal workflow
        result = await lead_state_machine.transition_state(
            lead_id=lead.id,
            target_state=LeadState.ANALYZING,
            actor="system"
        )
        assert result.success


# Test configuration and settings
class TestConfiguration:
    """Test configuration management."""
    
    def test_settings_validation(self):
        """Test settings validation."""
        settings = ProductionSettings()
        validation_result = settings.validate()
        
        # Should have some validation errors with default settings
        # (missing email credentials, etc.)
        assert isinstance(validation_result, dict)
    
    def test_environment_override(self):
        """Test environment variable override."""
        import os
        
        # Set test environment variable
        os.environ["MAX_EMAILS_PER_DAY"] = "100"
        
        settings = ProductionSettings()
        assert settings.email.max_emails_per_day == 100
        
        # Clean up
        del os.environ["MAX_EMAILS_PER_DAY"]


# Performance and load tests
class TestPerformance:
    """Test system performance under load."""
    
    async def test_concurrent_lead_creation(self, db_service):
        """Test concurrent lead creation."""
        
        async def create_lead(i):
            lead_data = LeadCreate(
                business_name=f"Test Business {i}",
                category="test",
                location="Test City",
                discovery_source=DiscoverySource.GOOGLE_MAPS,
                discovery_confidence=0.8
            )
            return await db_service.create_lead(lead_data)
        
        # Create leads concurrently
        tasks = [create_lead(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful creations
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 10
    
    async def test_database_performance(self, db_service, sample_lead_data):
        """Test database performance with larger datasets."""
        
        # Create many leads
        leads = []
        for i in range(100):
            lead_data = sample_lead_data.copy()
            lead_data.business_name = f"Test Business {i}"
            lead_data.email = f"test{i}@example.com"
            lead = await db_service.create_lead(lead_data)
            leads.append(lead)
        
        # Test query performance
        import time
        
        start_time = time.time()
        from ..core.models.common import PaginationParams
        result = await db_service.get_leads(pagination=PaginationParams(page=1, page_size=50))
        query_time = time.time() - start_time
        
        assert len(result.items) == 50
        assert query_time < 1.0  # Should complete within 1 second
        
        # Test filtering performance
        start_time = time.time()
        from ..core.models.lead import LeadFilter
        filtered_result = await db_service.get_leads(
            filters=LeadFilter(lifecycle_state=LeadState.DISCOVERED),
            pagination=PaginationParams(page=1, page_size=50)
        )
        filter_time = time.time() - start_time
        
        assert filter_time < 1.0  # Should complete within 1 second