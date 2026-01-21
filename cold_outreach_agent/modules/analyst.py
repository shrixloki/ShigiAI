"""
Analyst Module - Lead classification with simple heuristics.

Classifies leads based on website presence and quality.
Does NOT send emails.
"""

import re
from typing import Optional
from urllib.parse import urlparse

from modules.logger import action_logger
from services.db_service import DatabaseService


# Valid tags
VALID_TAGS = ["no_website", "outdated_site", "no_cta", "unknown"]


class AnalystModule:
    """Classifies leads using rule-based heuristics. No AI creativity."""
    
    def __init__(self):
        self.db = DatabaseService()
    
    def classify_all(self) -> dict:
        """
        Classify all untagged leads.
        
        Returns:
            {classified: int, errors: int}
        """
        leads = self.db.get_leads_without_tag()
        classified = 0
        errors = 0
        
        for lead in leads:
            success = self.classify_lead(lead)
            if success:
                classified += 1
            else:
                errors += 1
        
        if classified > 0:
            action_logger.log_action(
                lead_id=None,
                module_name="analyst",
                action="classify_batch",
                result="success",
                details={"classified": classified, "errors": errors}
            )
        
        return {"classified": classified, "errors": errors}
    
    def classify_lead(self, lead: dict) -> bool:
        """
        Classify a single lead and update the database.
        Returns True on success.
        """
        lead_id = lead.get("lead_id")
        if not lead_id:
            return False
        
        website = lead.get("website_url", "").strip()
        
        # Determine tag based on heuristics
        tag = self._determine_tag(website)
        
        try:
            self.db.update_lead(lead_id, {"tag": tag})
            action_logger.log_action(
                lead_id=lead_id,
                module_name="analyst",
                action="classify",
                result="success",
                details={"tag": tag, "website": website}
            )
            return True
        except Exception as e:
            action_logger.log_action(
                lead_id=lead_id,
                module_name="analyst",
                action="classify",
                result="error",
                details={"error": str(e)}
            )
            return False
    
    def _determine_tag(self, website: str) -> str:
        """
        Determine the classification tag based on website.
        Uses simple heuristics - no external requests.
        """
        # No website provided
        if not website:
            return "no_website"
        
        # Normalize URL
        website = website.lower().strip()
        if not website.startswith(("http://", "https://")):
            website = "https://" + website
        
        try:
            parsed = urlparse(website)
            domain = parsed.netloc
        except Exception:
            return "unknown"
        
        # Check for signs of outdated site
        if self._looks_outdated(website, domain):
            return "outdated_site"
        
        # Check for missing CTA indicators
        if self._likely_no_cta(website, domain):
            return "no_cta"
        
        # Default
        return "unknown"
    
    def _looks_outdated(self, url: str, domain: str) -> bool:
        """
        Heuristic: Does the website URL suggest an outdated site?
        """
        outdated_indicators = [
            ".weebly.com",
            ".wix.com",
            ".wordpress.com",
            ".blogspot.com",
            ".tripod.com",
            ".angelfire.com",
            ".geocities.com",
            "~",  # Tilde URLs often indicate old personal pages
        ]
        
        for indicator in outdated_indicators:
            if indicator in url:
                return True
        
        # Very short domain names with numbers often indicate old sites
        if re.match(r"^[a-z]{2,4}\d+\.", domain):
            return True
        
        return False
    
    def _likely_no_cta(self, url: str, domain: str) -> bool:
        """
        Heuristic: Does the URL pattern suggest a site without clear CTAs?
        """
        # Social media profiles typically lack business CTAs
        social_domains = [
            "facebook.com",
            "instagram.com",
            "twitter.com",
            "linkedin.com",
            "yelp.com",
            "yellowpages.com"
        ]
        
        for social in social_domains:
            if social in domain:
                return True
        
        return False
    
    def get_observation_for_tag(self, tag: str) -> str:
        """
        Get a factual observation line for email personalization.
        These are templates, not AI-generated content.
        """
        observations = {
            "no_website": "I noticed your business doesn't have a website yet",
            "outdated_site": "I took a look at your current website and noticed it might benefit from a refresh",
            "no_cta": "I checked out your online presence and noticed there's an opportunity to make it easier for customers to take action",
            "unknown": "I came across your business and wanted to reach out"
        }
        return observations.get(tag, observations["unknown"])
