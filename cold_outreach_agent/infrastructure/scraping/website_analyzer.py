"""
Production-grade website analyzer for contact extraction.
"""

import re
import asyncio
import logging
import aiohttp
from typing import Optional, List, Dict, Set, Tuple
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from dataclasses import dataclass

from ...core.models.lead import Lead, LeadUpdate
from ...core.models.common import OperationResult
from ...core.exceptions import WebsiteAnalysisError
from ..database.service import ProductionDatabaseService

@dataclass
class AnalysisResult:
    email: Optional[str] = None
    tag: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict = None

class ProductionWebsiteAnalyzerService:
    """
    Analyzes websites to extract contact information and value signals.
    Uses aiohttp for high-concurrency requests.
    """
    
    # Common email patterns
    EMAIL_PATTERNS = [
        r'[\w.-]+@[\w.-]+\.\w{2,}',  # Generic
        r'contact\s*\[at\]\s*[\w.-]+\.\w+', # Obfuscated [at]
        r'info\s*\[at\]\s*[\w.-]+\.\w+',
    ]
    
    # Paths to check for contact info
    CONTACT_PATHS = [
        '/contact', '/contact-us', '/contactus',
        '/about', '/about-us', '/aboutus',
        '/get-in-touch', '/support'
    ]
    
    def __init__(self, db_service: ProductionDatabaseService):
        self.db = db_service
        self.timeout = 15
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        self.semaphore = asyncio.Semaphore(5) # Limit concurrent requests

    async def analyze_leads(self, lead_ids: List[str]) -> Dict[str, bool]:
        """
        Analyze a list of leads by ID.
        Returns map of lead_id -> success
        """
        results = {}
        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = []
            for lead_id in lead_ids:
                task = asyncio.create_task(self._process_single_lead(lead_id, session))
                tasks.append(task)
            
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(completed):
                lead_id = lead_ids[i]
                if isinstance(result, Exception):
                    results[lead_id] = False
                else:
                    results[lead_id] = result
        
        return results

    async def _process_single_lead(self, lead_id: str, session: aiohttp.ClientSession) -> bool:
        """Process a single lead."""
        async with self.semaphore:
            try:
                # Get lead from DB
                from uuid import UUID
                lead = await self.db.get_lead_by_id(UUID(lead_id))
                if not lead or not lead.website_url:
                    return False

                result = await self.analyze_website(lead.website_url, session)
                
                # Update lead
                updates = {}
                if result.email:
                    updates['email'] = result.email
                
                if result.tag:
                    updates['tag'] = result.tag
                
                if result.metadata:
                    updates['discovery_metadata'] = lead.discovery_metadata or {}
                    updates['discovery_metadata'].update(result.metadata)
                
                if result.confidence > (lead.discovery_confidence or 0):
                    updates['discovery_confidence'] = result.confidence

                if updates:
                    await self.db.update_lead(lead.id, LeadUpdate(**updates))
                
                return True

            except Exception as e:
                # Log error
                return False

    async def analyze_website(self, url: str, session: aiohttp.ClientSession) -> AnalysisResult:
        """Analyze a single website URL."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        result = AnalysisResult(metadata={})
        
        try:
            # Fetch homepage
            home_html, final_url = await self._fetch_page(session, url)
            if not home_html:
                result.tag = 'website_unreachable'
                return result

            result.metadata['final_url'] = final_url
            
            # Analyze content tags
            result.tag = self._determine_tag(home_html, final_url)
            
            # Extract emails
            emails = self._extract_emails(home_html)
            
            # If no emails, check contact pages
            if not emails:
                for path in self.CONTACT_PATHS:
                    contact_url = urljoin(final_url, path)
                    contact_html, _ = await self._fetch_page(session, contact_url)
                    if contact_html:
                        contact_emails = self._extract_emails(contact_html)
                        emails.update(contact_emails)
                        if emails:
                            break
            
            # Select best email
            if emails:
                result.email = self._select_best_email(list(emails), final_url)
                result.confidence = 0.9
            else:
                result.confidence = 0.7 # Website exists but no email

            return result

        except Exception as e:
            result.metadata['error'] = str(e)
            return result

    async def _fetch_page(self, session: aiohttp.ClientSession, url: str) -> Tuple[Optional[str], str]:
        """Fetch page content properly handling redirects and SSL errors."""
        try:
            async with session.get(url, timeout=self.timeout, ssl=False) as response:
                if response.status == 200:
                    text = await response.text()
                    return text, str(response.url)
        except Exception:
            pass
        return None, url

    def _extract_emails(self, html: str) -> Set[str]:
        """Extract and clean emails from HTML."""
        emails = set()
        
        # De-obfuscate
        clean_html = html.replace('[at]', '@').replace('(at)', '@').replace(' [at] ', '@')
        
        # Regex
        for pattern in self.EMAIL_PATTERNS:
            for match in re.finditer(pattern, clean_html, re.IGNORECASE):
                email = match.group(0)
                if self._is_valid_email(email):
                    emails.add(email.lower())
        
        # Mailto
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0]
                if self._is_valid_email(email):
                    emails.add(email.lower())
                    
        return emails

    def _is_valid_email(self, email: str) -> bool:
        """Filter out invalid/garbage emails."""
        if not email or '@' not in email: return False
        
        email = email.lower()
        invalid_domains = ['example.com', 'domain.com', 'sentry.io', 'wixpress.com']
        invalid_exts = ['.png', '.jpg', '.js', '.css']
        
        if any(d in email for d in invalid_domains): return False
        if any(email.endswith(e) for e in invalid_exts): return False
        
        return True

    def _select_best_email(self, emails: List[str], url: str) -> Optional[str]:
        """Prioritize business emails over generic ones."""
        if not emails: return None
        
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        
        # Priority 1: Domain match + priority prefix
        priority_prefixes = ['contact', 'info', 'hello', 'sales', 'support', 'office', 'admin']
        
        for email in emails:
            if domain in email:
                for p in priority_prefixes:
                    if email.startswith(p + '@'):
                        return email
        
        # Priority 2: Domain match
        for email in emails:
            if domain in email:
                return email
                
        # Priority 3: Priority prefix (e.g. gmail)
        for email in emails:
             for p in priority_prefixes:
                    if email.startswith(p + '@'):
                        return email
                        
        return emails[0]

    def _determine_tag(self, html: str, url: str) -> str:
        """Determine a tag for the website."""
        lower_html = html.lower()
        if 'wordpress' in lower_html or 'wp-content' in lower_html:
            return 'wordpress_site'
        if 'shopify' in lower_html:
            return 'shopify_store'
        if 'wix.com' in lower_html:
            return 'wix_site'
        
        return 'active_website'
