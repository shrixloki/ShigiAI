"""Public signal service for Looking for Developer system."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from ..core.models.public_signal import (
    BusinessProfile, ProfileStatus, RoleType, EngagementType, BudgetRange,
    DeveloperInquiry, ProfileApprovalRecord, ApprovalDecision,
    DirectorySearchFilters, DirectoryEntry, ProfileCreateRequest,
    ProfileUpdateRequest, SendInquiryRequest
)
from ..core.exceptions import ColdOutreachAgentError
from ..modules.logger import action_logger


class PublicSignalError(ColdOutreachAgentError):
    """Public signal operation failed."""
    pass


class PublicSignalService:
    """
    Service for the Looking for Developer public signal system.
    
    Features:
    - Business profile management
    - Public directory with search
    - Developer inquiry handling
    - Approval workflow
    - Inbound lead capture
    """
    
    def __init__(self, db_service, email_service=None):
        self.db = db_service
        self.email_service = email_service
        
        self._profiles: Dict[UUID, BusinessProfile] = {}
        self._inquiries: Dict[UUID, DeveloperInquiry] = {}
        self._approval_records: List[ProfileApprovalRecord] = []
    
    async def create_profile(self, request: ProfileCreateRequest) -> BusinessProfile:
        """
        Create a new business profile.
        
        Args:
            request: Profile creation request
        
        Returns:
            Created BusinessProfile
        """
        profile = BusinessProfile(
            business_name=request.business_name,
            industry=request.industry,
            website_url=request.website_url,
            location=request.location,
            contact_name=request.contact_name,
            contact_email=request.contact_email,
            contact_phone=request.contact_phone,
            role_types=request.role_types,
            budget_range=request.budget_range,
            engagement_type=request.engagement_type,
            project_description=request.project_description,
            required_skills=request.required_skills,
            status=ProfileStatus.DRAFT,
            is_looking_for_developer=True,
            looking_since=datetime.now()
        )
        
        self._profiles[profile.id] = profile
        
        action_logger.log_action(
            lead_id=None,
            module_name="public_signal",
            action="create_profile",
            result="success",
            details={
                "profile_id": str(profile.id),
                "business_name": profile.business_name
            }
        )
        
        return profile
    
    async def get_profile(self, profile_id: UUID) -> Optional[BusinessProfile]:
        """Get a profile by ID."""
        return self._profiles.get(profile_id)
    
    async def update_profile(self, profile_id: UUID,
                              update: ProfileUpdateRequest) -> Optional[BusinessProfile]:
        """Update an existing profile."""
        profile = self._profiles.get(profile_id)
        if not profile:
            return None
        
        if update.is_looking_for_developer is not None:
            profile.is_looking_for_developer = update.is_looking_for_developer
            if update.is_looking_for_developer:
                profile.looking_since = datetime.now()
        
        if update.role_types is not None:
            profile.role_types = update.role_types
        if update.budget_range is not None:
            profile.budget_range = update.budget_range
        if update.engagement_type is not None:
            profile.engagement_type = update.engagement_type
        if update.project_description is not None:
            profile.project_description = update.project_description
        if update.required_skills is not None:
            profile.required_skills = update.required_skills
        if update.urgency_level is not None:
            profile.urgency_level = update.urgency_level
        if update.is_searchable is not None:
            profile.is_searchable = update.is_searchable
        
        profile.updated_at = datetime.now()
        
        return profile
    
    async def submit_for_approval(self, profile_id: UUID) -> BusinessProfile:
        """Submit a profile for approval."""
        profile = self._profiles.get(profile_id)
        if not profile:
            raise PublicSignalError(f"Profile {profile_id} not found")
        
        if profile.status not in [ProfileStatus.DRAFT, ProfileStatus.REJECTED]:
            raise PublicSignalError(f"Profile cannot be submitted from status {profile.status}")
        
        profile.status = ProfileStatus.PENDING_APPROVAL
        profile.submitted_at = datetime.now()
        profile.updated_at = datetime.now()
        
        action_logger.log_action(
            lead_id=None,
            module_name="public_signal",
            action="submit_for_approval",
            result="success",
            details={"profile_id": str(profile_id)}
        )
        
        return profile
    
    async def review_profile(self, profile_id: UUID, decision: ApprovalDecision,
                              reviewer: str, reason: Optional[str] = None,
                              changes_requested: Optional[List[str]] = None) -> BusinessProfile:
        """
        Review and approve/reject a profile.
        
        Args:
            profile_id: Profile to review
            decision: Approval decision
            reviewer: Reviewer's user ID
            reason: Reason for decision
            changes_requested: List of changes needed (if requesting changes)
        
        Returns:
            Updated BusinessProfile
        """
        profile = self._profiles.get(profile_id)
        if not profile:
            raise PublicSignalError(f"Profile {profile_id} not found")
        
        if profile.status != ProfileStatus.PENDING_APPROVAL:
            raise PublicSignalError(f"Profile is not pending approval")
        
        previous_status = profile.status
        
        if decision == ApprovalDecision.APPROVE:
            profile.status = ProfileStatus.APPROVED
        elif decision == ApprovalDecision.REJECT:
            profile.status = ProfileStatus.REJECTED
            profile.rejection_reason = reason
        elif decision == ApprovalDecision.REQUEST_CHANGES:
            profile.status = ProfileStatus.DRAFT
            profile.rejection_reason = reason
        
        profile.reviewed_at = datetime.now()
        profile.reviewed_by = reviewer
        profile.updated_at = datetime.now()
        
        # Create approval record
        record = ProfileApprovalRecord(
            profile_id=profile_id,
            decision=decision,
            reason=reason,
            changes_requested=changes_requested,
            decided_by=reviewer,
            previous_status=previous_status,
            new_status=profile.status
        )
        self._approval_records.append(record)
        
        action_logger.log_action(
            lead_id=None,
            module_name="public_signal",
            action="review_profile",
            result="success",
            details={
                "profile_id": str(profile_id),
                "decision": decision.value if hasattr(decision, 'value') else decision,
                "reviewer": reviewer
            }
        )
        
        return profile
    
    async def search_directory(self, filters: DirectorySearchFilters) -> Dict[str, Any]:
        """
        Search the public directory.
        
        Args:
            filters: Search filters
        
        Returns:
            Dict with results and pagination info
        """
        # Get all active, searchable profiles
        all_profiles = [
            p for p in self._profiles.values()
            if p.is_active() and p.is_searchable
        ]
        
        # Apply filters
        filtered = all_profiles
        
        # Text search
        if filters.query:
            query_lower = filters.query.lower()
            filtered = [
                p for p in filtered
                if query_lower in p.business_name.lower()
                or query_lower in (p.project_description or '').lower()
                or any(query_lower in skill.lower() for skill in p.required_skills)
            ]
        
        # Role type filter
        if filters.role_types:
            filtered = [
                p for p in filtered
                if any(rt in p.role_types for rt in filters.role_types)
            ]
        
        # Budget range filter
        if filters.budget_ranges:
            filtered = [
                p for p in filtered
                if p.budget_range in filters.budget_ranges
            ]
        
        # Engagement type filter
        if filters.engagement_types:
            filtered = [
                p for p in filtered
                if p.engagement_type in filters.engagement_types
            ]
        
        # Industry filter
        if filters.industries:
            filtered = [
                p for p in filtered
                if p.industry and p.industry.lower() in [i.lower() for i in filters.industries]
            ]
        
        # Location filter
        if filters.locations:
            filtered = [
                p for p in filtered
                if p.location and any(loc.lower() in p.location.lower() for loc in filters.locations)
            ]
        
        # Skills filter
        if filters.skills:
            filtered = [
                p for p in filtered
                if any(
                    skill.lower() in [s.lower() for s in p.required_skills]
                    for skill in filters.skills
                )
            ]
        
        # Urgency filter
        if filters.min_urgency:
            filtered = [p for p in filtered if p.urgency_level >= filters.min_urgency]
        
        # Featured only
        if filters.featured_only:
            filtered = [p for p in filtered if p.is_featured]
        
        # Sort
        if filters.sort_by == 'created_at':
            filtered.sort(key=lambda p: p.created_at, reverse=(filters.sort_order == 'desc'))
        elif filters.sort_by == 'urgency_level':
            filtered.sort(key=lambda p: p.urgency_level, reverse=(filters.sort_order == 'desc'))
        elif filters.sort_by == 'business_name':
            filtered.sort(key=lambda p: p.business_name.lower(), reverse=(filters.sort_order == 'desc'))
        
        # Pagination
        total = len(filtered)
        start = (filters.page - 1) * filters.page_size
        end = start + filters.page_size
        page_results = filtered[start:end]
        
        # Convert to directory entries
        entries = [
            DirectoryEntry(
                id=p.id,
                business_name=p.business_name,
                industry=p.industry,
                location=p.location,
                role_types=[rt.value if hasattr(rt, 'value') else rt for rt in p.role_types],
                budget_range=p.budget_range.value if p.budget_range and hasattr(p.budget_range, 'value') else p.budget_range,
                engagement_type=p.engagement_type.value if p.engagement_type and hasattr(p.engagement_type, 'value') else p.engagement_type,
                required_skills=p.required_skills[:5],
                urgency_level=p.urgency_level,
                is_featured=p.is_featured,
                created_at=p.created_at
            )
            for p in page_results
        ]
        
        return {
            "results": entries,
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
            "total_pages": (total + filters.page_size - 1) // filters.page_size
        }
    
    async def get_public_profile(self, profile_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get public-facing profile data.
        
        Args:
            profile_id: Profile ID
        
        Returns:
            Public profile data or None
        """
        profile = self._profiles.get(profile_id)
        if not profile or not profile.is_active():
            return None
        
        # Increment view count
        profile.view_count += 1
        profile.last_viewed_at = datetime.now()
        
        return profile.get_public_summary()
    
    async def send_inquiry(self, request: SendInquiryRequest,
                           ip_address: Optional[str] = None,
                           referrer: Optional[str] = None) -> DeveloperInquiry:
        """
        Send an inquiry from a developer to a business.
        
        Args:
            request: Inquiry request
            ip_address: Request IP
            referrer: HTTP referrer
        
        Returns:
            Created DeveloperInquiry
        """
        profile = self._profiles.get(request.profile_id)
        if not profile or not profile.is_active():
            raise PublicSignalError("Profile not found or not active")
        
        inquiry = DeveloperInquiry(
            profile_id=request.profile_id,
            developer_name=request.developer_name,
            developer_email=request.developer_email,
            message=request.message,
            relevant_skills=request.relevant_skills,
            portfolio_links=request.portfolio_links,
            source_ip=ip_address,
            source_referrer=referrer
        )
        
        self._inquiries[inquiry.id] = inquiry
        
        # Update profile inquiry count
        profile.inquiry_count += 1
        
        # Send notification email to business (if email service available)
        if self.email_service:
            try:
                await self._send_inquiry_notification(profile, inquiry)
            except Exception as e:
                action_logger.warning(f"Failed to send inquiry notification: {e}")
        
        action_logger.log_action(
            lead_id=None,
            module_name="public_signal",
            action="send_inquiry",
            result="success",
            details={
                "profile_id": str(request.profile_id),
                "developer_email": request.developer_email
            }
        )
        
        return inquiry
    
    async def _send_inquiry_notification(self, profile: BusinessProfile,
                                          inquiry: DeveloperInquiry):
        """Send email notification to business about new inquiry."""
        subject = f"New Developer Inquiry: {inquiry.developer_name}"
        body = f"""
Hello {profile.contact_name},

You have received a new inquiry from a developer on your "Looking for Developer" listing.

Developer: {inquiry.developer_name}
Email: {inquiry.developer_email}

Message:
{inquiry.message}

Skills: {', '.join(inquiry.relevant_skills) if inquiry.relevant_skills else 'Not specified'}

You can reply directly to this email to contact the developer.

Best regards,
Lead Intelligence Platform
        """
        
        # In production, actually send email
        # await self.email_service.send_email(profile.contact_email, subject, body)
    
    async def get_profile_inquiries(self, profile_id: UUID) -> List[DeveloperInquiry]:
        """Get all inquiries for a profile."""
        return [
            i for i in self._inquiries.values()
            if i.profile_id == profile_id
        ]
    
    async def get_inquiry(self, inquiry_id: UUID) -> Optional[DeveloperInquiry]:
        """Get a specific inquiry."""
        return self._inquiries.get(inquiry_id)
    
    async def mark_inquiry_read(self, inquiry_id: UUID) -> Optional[DeveloperInquiry]:
        """Mark an inquiry as read."""
        inquiry = self._inquiries.get(inquiry_id)
        if inquiry:
            inquiry.is_read = True
            inquiry.read_at = datetime.now()
        return inquiry
    
    async def mark_inquiry_replied(self, inquiry_id: UUID) -> Optional[DeveloperInquiry]:
        """Mark an inquiry as replied."""
        inquiry = self._inquiries.get(inquiry_id)
        if inquiry:
            inquiry.is_replied = True
            inquiry.replied_at = datetime.now()
        return inquiry
    
    async def capture_as_lead(self, inquiry_id: UUID) -> Optional[UUID]:
        """
        Capture a developer inquiry as an inbound lead.
        
        Args:
            inquiry_id: Inquiry to capture
        
        Returns:
            Created lead ID or None
        """
        inquiry = self._inquiries.get(inquiry_id)
        if not inquiry:
            return None
        
        if inquiry.captured_as_lead:
            return inquiry.captured_lead_id
        
        # Create lead from inquiry
        try:
            lead_data = {
                'business_name': inquiry.developer_name,
                'email': inquiry.developer_email,
                'website_url': inquiry.developer_website,
                'category': 'developer',
                'discovery_source': 'inbound',
                'notes': inquiry.message
            }
            
            lead = await self.db.create_lead(lead_data)
            lead_id = lead.get('lead_id') or lead.get('id')
            
            inquiry.captured_as_lead = True
            inquiry.captured_lead_id = UUID(str(lead_id)) if lead_id else None
            
            action_logger.log_action(
                lead_id=str(lead_id),
                module_name="public_signal",
                action="capture_lead",
                result="success",
                details={"inquiry_id": str(inquiry_id)}
            )
            
            return inquiry.captured_lead_id
            
        except Exception as e:
            action_logger.error(f"Failed to capture lead: {e}")
            return None
    
    async def get_pending_approvals(self) -> List[BusinessProfile]:
        """Get all profiles pending approval."""
        return [
            p for p in self._profiles.values()
            if p.status == ProfileStatus.PENDING_APPROVAL
        ]
    
    async def get_featured_profiles(self, limit: int = 10) -> List[BusinessProfile]:
        """Get featured profiles for homepage/highlights."""
        featured = [
            p for p in self._profiles.values()
            if p.is_active() and p.is_featured
        ]
        featured.sort(key=lambda p: p.created_at, reverse=True)
        return featured[:limit]
    
    async def toggle_featured(self, profile_id: UUID, is_featured: bool) -> Optional[BusinessProfile]:
        """Toggle featured status of a profile."""
        profile = self._profiles.get(profile_id)
        if profile:
            profile.is_featured = is_featured
            profile.updated_at = datetime.now()
        return profile
    
    async def expire_old_profiles(self, days_old: int = 90):
        """Expire profiles older than specified days."""
        cutoff = datetime.now() - timedelta(days=days_old)
        
        for profile in self._profiles.values():
            if profile.status == ProfileStatus.APPROVED:
                if profile.looking_since and profile.looking_since < cutoff:
                    profile.status = ProfileStatus.EXPIRED
                    profile.updated_at = datetime.now()
                    
                    action_logger.log_action(
                        lead_id=None,
                        module_name="public_signal",
                        action="expire_profile",
                        result="success",
                        details={"profile_id": str(profile.id)}
                    )
    
    async def get_directory_stats(self) -> Dict[str, Any]:
        """Get statistics about the public directory."""
        profiles = list(self._profiles.values())
        active = [p for p in profiles if p.is_active()]
        
        # Role type distribution
        role_dist = {}
        for profile in active:
            for role in profile.role_types:
                role_val = role.value if hasattr(role, 'value') else role
                role_dist[role_val] = role_dist.get(role_val, 0) + 1
        
        # Budget distribution
        budget_dist = {}
        for profile in active:
            if profile.budget_range:
                budget_val = profile.budget_range.value if hasattr(profile.budget_range, 'value') else profile.budget_range
                budget_dist[budget_val] = budget_dist.get(budget_val, 0) + 1
        
        return {
            "total_profiles": len(profiles),
            "active_profiles": len(active),
            "pending_approval": sum(1 for p in profiles if p.status == ProfileStatus.PENDING_APPROVAL),
            "total_inquiries": len(self._inquiries),
            "unread_inquiries": sum(1 for i in self._inquiries.values() if not i.is_read),
            "role_distribution": role_dist,
            "budget_distribution": budget_dist,
            "avg_urgency": sum(p.urgency_level for p in active) / max(len(active), 1)
        }
