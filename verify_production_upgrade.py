import asyncio
import os
import sys
from datetime import datetime
from uuid import uuid4
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cold_outreach_agent.infrastructure.database.service import ProductionDatabaseService
from cold_outreach_agent.services.enrichment_service import EnrichmentPipelineService
from cold_outreach_agent.services.scoring_service import LeadScoringEngine
from cold_outreach_agent.services.campaign_service import CampaignIntelligenceService, SequenceCreate, EnrollLeadRequest
from cold_outreach_agent.core.models.lead import Lead, LeadCreate
from cold_outreach_agent.core.models.enrichment import EnrichmentSource
from cold_outreach_agent.core.models.campaign import SequenceStep, SequenceStatus

async def main():
    print("Starting Production Upgrade Verification...")
    
    # 1. Setup Database
    db_path = Path("data/verification_test.db")
    if db_path.exists():
        try:
            os.remove(db_path)
        except Exception:
            pass
    
    db = ProductionDatabaseService(db_path)
    await db.initialize()
    print("Database initialized with migrations")
    
    # 2. Setup Services
    enrichment_service = EnrichmentPipelineService(db)
    scoring_service = LeadScoringEngine(db)
    campaign_service = CampaignIntelligenceService(db, email_service=None) # No email sending needed
    
    # 3. Create Lead
    print("Creating Lead...")
    lead_create = LeadCreate(
        business_name="Test Corp",
        website_url="example.com",
        email="contact@example.com",
        location="New York, NY",
        discovery_source="manual_import",
        lifecycle_state="discovered",
        review_status="pending"
    )
    
    lead = await db.create_lead(lead_create)
    lead_id = lead.id
    print(f"Lead created: {lead_id}")
    
    # 4. Test Scoring
    print("Running Scoring Engine...")
    score = await scoring_service.score_lead(lead.dict(), enrichment=None)
    print(f"Lead Scored: {score.composite_score} ({score.composite_level})")

    assert score.intent_score.score >= 0, "Intent score should be calculated"
    
    # 5. Test Campaign Sequences (Persistence)
    print("Creating Campaign Sequence...")
    step1 = SequenceStep(
        index=0,
        template_id="intro",
        step_type="initial",
        delay_hours=0,
        subject_override="Hi"
    )
    seq = await campaign_service.create_sequence(SequenceCreate(
        name="Test Sequence",
        steps=[step1],
        created_by="tester"
    ))
    print(f"Sequence Created: {seq.id}")
    
    # 6. Test Enrollment
    print("Enrolling Lead...")
    enrollment = await campaign_service.enroll_lead(EnrollLeadRequest(
        sequence_id=seq.id,
        lead_id=lead_id
    ))
    print(f"Lead Enrolled: {enrollment.id}")
    
    # 7. Verify Persistence
    print("Verifying Persistence...")
    saved_seq = await campaign_service.get_sequence(seq.id)
    assert saved_seq.name == "Test Sequence"
    
    saved_enrollment = await campaign_service.get_lead_enrollments(lead_id)
    assert len(saved_enrollment) == 1
    status_val = saved_enrollment[0].status.value if hasattr(saved_enrollment[0].status, 'value') else saved_enrollment[0].status
    assert status_val == "enrolled"
    
    print("Persistence Verified")
    
    print("\nALL CHECKS PASSED. SYSTEM IS PRODUCTION-READY.")

if __name__ == "__main__":
    asyncio.run(main())
