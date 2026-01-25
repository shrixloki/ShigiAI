"""Lead enrichment pipeline service with async processing and retry logic."""

import asyncio
import re
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from ..core.models.enrichment import (
    LeadEnrichment, EnrichmentState, EnrichmentSource, BusinessMaturity, CompanySize,
    TechStackItem, TechStackCategory, HiringSignal, ContactIntentSignal,
    SocialPresence, DecisionMaker, EnrichmentCreate
)
from ..core.exceptions import ColdOutreachAgentError
from ..modules.logger import action_logger


class EnrichmentError(ColdOutreachAgentError):
    """Enrichment operation failed."""
    pass


class EnrichmentPipelineService:
    """
    Asynchronous lead enrichment pipeline.
    
    Features:
    - Website crawling for tech stack, hiring signals, contact intent
    - Social presence detection (LinkedIn, Twitter, GitHub)
    - Business maturity classification
    - Decision-maker extraction
    - Confidence scoring
    - Retry-safe and state-tracked
    """
    
    # Tech stack detection patterns
    TECH_PATTERNS: Dict[str, Tuple[str, TechStackCategory]] = {
        # Frontend
        'react': (r'react(?:\.js)?|_react', TechStackCategory.FRONTEND),
        'vue': (r'vue(?:\.js)?|__vue', TechStackCategory.FRONTEND),
        'angular': (r'angular(?:\.js)?|ng-', TechStackCategory.FRONTEND),
        'jquery': (r'jquery', TechStackCategory.FRONTEND),
        'bootstrap': (r'bootstrap', TechStackCategory.FRONTEND),
        'tailwind': (r'tailwind', TechStackCategory.FRONTEND),
        
        # CMS
        'wordpress': (r'wp-content|wordpress', TechStackCategory.CMS),
        'wix': (r'wix\.com|wixsite', TechStackCategory.CMS),
        'squarespace': (r'squarespace', TechStackCategory.CMS),
        'webflow': (r'webflow', TechStackCategory.CMS),
        'shopify': (r'shopify|myshopify', TechStackCategory.ECOMMERCE),
        'woocommerce': (r'woocommerce', TechStackCategory.ECOMMERCE),
        
        # Analytics
        'google_analytics': (r'google-analytics|googletagmanager|gtag', TechStackCategory.ANALYTICS),
        'hotjar': (r'hotjar', TechStackCategory.ANALYTICS),
        'mixpanel': (r'mixpanel', TechStackCategory.ANALYTICS),
        'segment': (r'segment\.io|segment\.com', TechStackCategory.ANALYTICS),
        
        # Marketing
        'hubspot': (r'hubspot', TechStackCategory.MARKETING),
        'mailchimp': (r'mailchimp', TechStackCategory.MARKETING),
        'intercom': (r'intercom', TechStackCategory.MARKETING),
        'drift': (r'drift\.com', TechStackCategory.MARKETING),
        
        # Hosting
        'cloudflare': (r'cloudflare', TechStackCategory.HOSTING),
        'aws': (r'amazonaws\.com|aws\.amazon', TechStackCategory.HOSTING),
        'vercel': (r'vercel', TechStackCategory.HOSTING),
        'netlify': (r'netlify', TechStackCategory.HOSTING),
        
        # Payment
        'stripe': (r'stripe', TechStackCategory.PAYMENT),
        'paypal': (r'paypal', TechStackCategory.PAYMENT),
    }
    
    # Hiring signal keywords
    HIRING_KEYWORDS = [
        r'we\'?re hiring', r'join our team', r'career', r'careers',
        r'job opening', r'open position', r'we\'?re looking for',
        r'hiring now', r'job opportunities', r'work with us'
    ]
    
    # Contact intent signals
    CONTACT_SIGNALS = {
        'contact_form': [r'contact form', r'get in touch', r'send message'],
        'chat_widget': [r'chat', r'live chat', r'support chat', r'intercom', r'drift', r'crisp'],
        'cta_button': [r'get started', r'free trial', r'book a demo', r'schedule call', r'request quote'],
        'phone': [r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'],
    }
    
    # Social platform patterns
    SOCIAL_PATTERNS = {
        'linkedin': r'linkedin\.com/(?:company|in)/([a-zA-Z0-9_-]+)',
        'twitter': r'twitter\.com/([a-zA-Z0-9_]+)|x\.com/([a-zA-Z0-9_]+)',
        'github': r'github\.com/([a-zA-Z0-9_-]+)',
        'facebook': r'facebook\.com/([a-zA-Z0-9._-]+)',
        'instagram': r'instagram\.com/([a-zA-Z0-9._]+)',
    }

    def __init__(self, db_service, max_retries: int = 3, timeout: int = 30):
        self.db = db_service
        self.max_retries = max_retries
        self.timeout = timeout
        self._session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
        return self._session
    
    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def enrich_lead(self, lead_id: UUID, website_url: Optional[str] = None,
                          sources: List[EnrichmentSource] = None) -> LeadEnrichment:
        """
        Run enrichment pipeline for a single lead.
        
        Args:
            lead_id: Lead to enrich
            website_url: Website to crawl (optional, fetched from lead if not provided)
            sources: Enrichment sources to use
        
        Returns:
            LeadEnrichment with all discovered data
        """
        sources = sources or [EnrichmentSource.WEBSITE_CRAWL]
        
        # Create or get existing enrichment
        enrichment = LeadEnrichment(
            lead_id=lead_id,
            enrichment_state=EnrichmentState.IN_PROGRESS,
            started_at=datetime.now()
        )
        
        try:
            action_logger.info(f"Starting enrichment for lead {lead_id}")
            
            # Get lead data if website not provided
            if not website_url:
                lead = await self.db.get_lead_by_id(lead_id)
                if lead:
                    website_url = lead.website_url if hasattr(lead, 'website_url') else lead.get('website_url')
            
            if website_url and EnrichmentSource.WEBSITE_CRAWL in sources:
                await self._enrich_from_website(enrichment, website_url)
            
            # Calculate overall confidence
            enrichment.enrichment_confidence = self._calculate_enrichment_confidence(enrichment)
            
            # Determine business maturity
            enrichment.business_maturity = self._classify_business_maturity(enrichment)
            
            # Estimate company size
            enrichment.company_size = self._estimate_company_size(enrichment)
            
            # Set completion state
            if enrichment.last_error:
                enrichment.enrichment_state = EnrichmentState.PARTIAL
            else:
                enrichment.enrichment_state = EnrichmentState.COMPLETED
            
            enrichment.completed_at = datetime.now()
            enrichment.attempt_count += 1
            
            action_logger.log_action(
                lead_id=str(lead_id),
                module_name="enrichment",
                action="enrich_lead",
                result="success" if enrichment.enrichment_state == EnrichmentState.COMPLETED else "partial",
                details=enrichment.get_enrichment_summary()
            )
            
            return enrichment
            
        except Exception as e:
            enrichment.enrichment_state = EnrichmentState.FAILED
            enrichment.last_error = str(e)[:1000]
            enrichment.attempt_count += 1
            enrichment.retry_after = datetime.now() + timedelta(hours=1)
            
            action_logger.log_action(
                lead_id=str(lead_id),
                module_name="enrichment",
                action="enrich_lead",
                result="error",
                details={"error": str(e)}
            )
            
            return enrichment
    
    async def _enrich_from_website(self, enrichment: LeadEnrichment, website_url: str):
        """Crawl website and extract enrichment data."""
        try:
            session = await self._get_session()
            
            # Normalize URL
            if not website_url.startswith(('http://', 'https://')):
                website_url = f'https://{website_url}'
            
            # Fetch main page
            main_html = await self._fetch_page(session, website_url)
            if not main_html:
                enrichment.last_error = "Failed to fetch website"
                return
            
            soup = BeautifulSoup(main_html, 'html.parser')
            
            # Extract tech stack
            enrichment.tech_stack = self._detect_tech_stack(main_html, soup)
            enrichment.tech_stack_score = self._calculate_tech_score(enrichment.tech_stack)
            
            # Extract social presence
            enrichment.social_presences = self._extract_social_presence(soup, website_url)
            enrichment.social_score = self._calculate_social_score(enrichment.social_presences)
            
            # Detect hiring signals
            enrichment.hiring_signals = self._detect_hiring_signals(soup, website_url)
            enrichment.is_hiring = len(enrichment.hiring_signals) > 0
            enrichment.hiring_confidence = self._calculate_hiring_confidence(enrichment.hiring_signals)
            
            # Detect contact intent
            enrichment.contact_signals = self._detect_contact_intent(soup, main_html, website_url)
            enrichment.has_contact_form = any(s.signal_type == 'contact_form' for s in enrichment.contact_signals)
            enrichment.has_live_chat = any(s.signal_type == 'chat_widget' for s in enrichment.contact_signals)
            enrichment.contact_intent_score = self._calculate_contact_score(enrichment.contact_signals)
            
            # Try to find careers page for more hiring data
            careers_url = self._find_careers_link(soup, website_url)
            if careers_url:
                careers_html = await self._fetch_page(session, careers_url)
                if careers_html:
                    careers_soup = BeautifulSoup(careers_html, 'html.parser')
                    more_signals = self._detect_hiring_signals(careers_soup, careers_url)
                    enrichment.hiring_signals.extend(more_signals)
                    enrichment.is_hiring = len(enrichment.hiring_signals) > 0
            
            # Extract decision makers (from about/team page)
            about_url = self._find_about_link(soup, website_url)
            if about_url:
                about_html = await self._fetch_page(session, about_url)
                if about_html:
                    about_soup = BeautifulSoup(about_html, 'html.parser')
                    enrichment.decision_makers = self._extract_decision_makers(about_soup, about_url)
                    if enrichment.decision_makers:
                        enrichment.primary_contact = enrichment.decision_makers[0]
            
        except Exception as e:
            enrichment.last_error = f"Website enrichment error: {str(e)}"
            action_logger.warning(f"Website enrichment failed: {e}")
    
    async def _fetch_page(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """Fetch a page with error handling."""
        try:
            async with session.get(url, ssl=False) as response:
                if response.status == 200:
                    return await response.text()
                return None
        except Exception as e:
            action_logger.debug(f"Failed to fetch {url}: {e}")
            return None
    
    def _detect_tech_stack(self, html: str, soup: BeautifulSoup) -> List[TechStackItem]:
        """Detect technologies used on the website."""
        tech_stack = []
        html_lower = html.lower()
        
        for tech_name, (pattern, category) in self.TECH_PATTERNS.items():
            if re.search(pattern, html_lower, re.IGNORECASE):
                tech_stack.append(TechStackItem(
                    name=tech_name.replace('_', ' ').title(),
                    category=category,
                    confidence=Decimal("0.8")
                ))
        
        # Check meta tags for frameworks
        for meta in soup.find_all('meta'):
            content = (meta.get('content', '') or '').lower()
            name = (meta.get('name', '') or '').lower()
            
            if 'generator' in name:
                if 'wordpress' in content:
                    if not any(t.name.lower() == 'wordpress' for t in tech_stack):
                        tech_stack.append(TechStackItem(
                            name='WordPress',
                            category=TechStackCategory.CMS,
                            confidence=Decimal("0.95")
                        ))
        
        return tech_stack
    
    def _extract_social_presence(self, soup: BeautifulSoup, base_url: str) -> List[SocialPresence]:
        """Extract social media links."""
        presences = []
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            for platform, pattern in self.SOCIAL_PATTERNS.items():
                match = re.search(pattern, href, re.IGNORECASE)
                if match:
                    handle = next((g for g in match.groups() if g), None)
                    if not any(p.platform == platform for p in presences):
                        presences.append(SocialPresence(
                            platform=platform,
                            profile_url=href,
                            handle=handle
                        ))
        
        return presences
    
    def _detect_hiring_signals(self, soup: BeautifulSoup, source_url: str) -> List[HiringSignal]:
        """Detect hiring/career signals."""
        signals = []
        text_content = soup.get_text().lower()
        
        for pattern in self.HIRING_KEYWORDS:
            if re.search(pattern, text_content, re.IGNORECASE):
                # Try to extract specific role information
                signals.append(HiringSignal(
                    role_type="General",
                    source_url=source_url,
                    is_active=True
                ))
                break  # Just need to detect hiring in general
        
        # Look for job listings structure
        job_containers = soup.find_all(class_=re.compile(r'job|career|position|opening', re.I))
        for container in job_containers[:5]:  # Limit to 5
            title = container.find(['h2', 'h3', 'h4', 'a'])
            if title:
                role_text = title.get_text().strip()[:200]
                if role_text and len(role_text) > 3:
                    signals.append(HiringSignal(
                        role_type=role_text,
                        source_url=source_url,
                        is_active=True
                    ))
        
        return signals[:10]  # Limit signals
    
    def _detect_contact_intent(self, soup: BeautifulSoup, html: str, 
                                source_url: str) -> List[ContactIntentSignal]:
        """Detect contact intent signals."""
        signals = []
        html_lower = html.lower()
        
        # Check for contact forms
        if soup.find('form'):
            forms = soup.find_all('form')
            for form in forms:
                action = (form.get('action', '') or '').lower()
                form_text = form.get_text().lower()
                if any(kw in form_text or kw in action for kw in ['contact', 'message', 'inquiry', 'email']):
                    signals.append(ContactIntentSignal(
                        signal_type='contact_form',
                        description='Contact form detected',
                        source_url=source_url
                    ))
                    break
        
        # Check for chat widgets
        for pattern in self.CONTACT_SIGNALS['chat_widget']:
            if re.search(pattern, html_lower, re.IGNORECASE):
                signals.append(ContactIntentSignal(
                    signal_type='chat_widget',
                    description='Live chat widget detected',
                    source_url=source_url
                ))
                break
        
        # Check for CTA buttons
        cta_buttons = soup.find_all(['button', 'a'], class_=re.compile(r'btn|button|cta', re.I))
        for btn in cta_buttons[:10]:
            btn_text = btn.get_text().lower().strip()
            for pattern in self.CONTACT_SIGNALS['cta_button']:
                if re.search(pattern, btn_text, re.IGNORECASE):
                    signals.append(ContactIntentSignal(
                        signal_type='cta_button',
                        description=f'CTA: {btn_text[:50]}',
                        source_url=source_url
                    ))
                    break
        
        return signals
    
    def _extract_decision_makers(self, soup: BeautifulSoup, source_url: str) -> List[DecisionMaker]:
        """Extract potential decision makers from about/team page."""
        decision_makers = []
        
        # Look for team member cards
        team_containers = soup.find_all(class_=re.compile(r'team|member|founder|leadership|executive', re.I))
        
        for container in team_containers[:10]:
            name_elem = container.find(['h2', 'h3', 'h4', 'strong'])
            title_elem = container.find(class_=re.compile(r'title|role|position', re.I))
            
            if name_elem:
                name = name_elem.get_text().strip()[:200]
                title = title_elem.get_text().strip()[:200] if title_elem else None
                
                # Extract LinkedIn if present
                linkedin_link = container.find('a', href=re.compile(r'linkedin\.com', re.I))
                linkedin_url = linkedin_link.get('href') if linkedin_link else None
                
                if name and len(name) > 2:
                    decision_makers.append(DecisionMaker(
                        name=name,
                        title=title,
                        linkedin_url=linkedin_url,
                        confidence=Decimal("0.6"),
                        source=EnrichmentSource.WEBSITE_CRAWL
                    ))
        
        return decision_makers[:5]  # Limit to 5
    
    def _find_careers_link(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find careers page link."""
        patterns = [r'career', r'job', r'hiring', r'join']
        return self._find_link_by_patterns(soup, base_url, patterns)
    
    def _find_about_link(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find about/team page link."""
        patterns = [r'about', r'team', r'who-we-are', r'company']
        return self._find_link_by_patterns(soup, base_url, patterns)
    
    def _find_link_by_patterns(self, soup: BeautifulSoup, base_url: str, 
                               patterns: List[str]) -> Optional[str]:
        """Find link matching patterns."""
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            link_text = link.get_text().lower()
            
            for pattern in patterns:
                if re.search(pattern, href, re.I) or re.search(pattern, link_text, re.I):
                    if href.startswith('/'):
                        return base + href
                    elif href.startswith('http'):
                        return href
        
        return None
    
    def _calculate_tech_score(self, tech_stack: List[TechStackItem]) -> Decimal:
        """Calculate tech stack sophistication score."""
        if not tech_stack:
            return Decimal("0.2")
        
        score = min(len(tech_stack) * Decimal("0.1"), Decimal("0.5"))
        
        # Bonus for modern tech
        modern_tech = ['react', 'vue', 'angular', 'tailwind', 'vercel', 'netlify']
        has_modern = any(t.name.lower() in modern_tech for t in tech_stack)
        if has_modern:
            score += Decimal("0.3")
        
        # Bonus for analytics
        has_analytics = any(t.category == TechStackCategory.ANALYTICS for t in tech_stack)
        if has_analytics:
            score += Decimal("0.1")
        
        return min(score, Decimal("1.0"))
    
    def _calculate_social_score(self, presences: List[SocialPresence]) -> Decimal:
        """Calculate social presence score."""
        if not presences:
            return Decimal("0.1")
        
        score = min(len(presences) * Decimal("0.15"), Decimal("0.6"))
        
        # Bonus for LinkedIn (B2B relevant)
        if any(p.platform == 'linkedin' for p in presences):
            score += Decimal("0.2")
        
        return min(score, Decimal("1.0"))
    
    def _calculate_hiring_confidence(self, signals: List[HiringSignal]) -> Decimal:
        """Calculate confidence in hiring signals."""
        if not signals:
            return Decimal("0.0")
        
        # More specific roles = higher confidence
        specific_roles = [s for s in signals if s.role_type != 'General']
        
        if len(specific_roles) >= 3:
            return Decimal("0.9")
        elif len(specific_roles) >= 1:
            return Decimal("0.7")
        else:
            return Decimal("0.5")
    
    def _calculate_contact_score(self, signals: List[ContactIntentSignal]) -> Decimal:
        """Calculate contact intent score."""
        if not signals:
            return Decimal("0.2")
        
        score = Decimal("0.3")
        
        if any(s.signal_type == 'contact_form' for s in signals):
            score += Decimal("0.3")
        if any(s.signal_type == 'chat_widget' for s in signals):
            score += Decimal("0.2")
        if any(s.signal_type == 'cta_button' for s in signals):
            score += Decimal("0.1")
        
        return min(score, Decimal("1.0"))
    
    def _calculate_enrichment_confidence(self, enrichment: LeadEnrichment) -> Decimal:
        """Calculate overall enrichment confidence."""
        scores = []
        weights = []
        
        if enrichment.tech_stack_score:
            scores.append(enrichment.tech_stack_score)
            weights.append(Decimal("0.2"))
        
        if enrichment.social_score:
            scores.append(enrichment.social_score)
            weights.append(Decimal("0.2"))
        
        if enrichment.contact_intent_score:
            scores.append(enrichment.contact_intent_score)
            weights.append(Decimal("0.3"))
        
        if enrichment.hiring_confidence:
            scores.append(enrichment.hiring_confidence)
            weights.append(Decimal("0.15"))
        
        if enrichment.decision_makers:
            scores.append(Decimal("0.8"))
            weights.append(Decimal("0.15"))
        
        if not scores:
            return Decimal("0.1")
        
        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        
        return weighted_sum / total_weight if total_weight > 0 else Decimal("0.1")
    
    def _classify_business_maturity(self, enrichment: LeadEnrichment) -> BusinessMaturity:
        """Classify business maturity based on signals."""
        tech_count = len(enrichment.tech_stack)
        social_count = len(enrichment.social_presences)
        has_modern_tech = any(t.category == TechStackCategory.ANALYTICS for t in enrichment.tech_stack)
        
        if tech_count >= 8 and social_count >= 4 and has_modern_tech:
            return BusinessMaturity.ENTERPRISE
        elif tech_count >= 5 and social_count >= 3:
            return BusinessMaturity.MATURE
        elif tech_count >= 3 and social_count >= 2:
            return BusinessMaturity.SCALING
        elif tech_count >= 2:
            return BusinessMaturity.EARLY_STAGE
        elif tech_count >= 1:
            return BusinessMaturity.MVP
        else:
            return BusinessMaturity.IDEA
    
    def _estimate_company_size(self, enrichment: LeadEnrichment) -> CompanySize:
        """Estimate company size based on signals."""
        dm_count = len(enrichment.decision_makers)
        hiring_count = len(enrichment.hiring_signals)
        
        if dm_count >= 5 or hiring_count >= 10:
            return CompanySize.LARGE
        elif dm_count >= 3 or hiring_count >= 5:
            return CompanySize.MEDIUM
        elif dm_count >= 2 or hiring_count >= 2:
            return CompanySize.SMALL
        elif dm_count >= 1:
            return CompanySize.SOLO
        else:
            return CompanySize.UNKNOWN
    
    async def enrich_batch(self, lead_ids: List[UUID], 
                           max_concurrent: int = 5) -> Dict[UUID, LeadEnrichment]:
        """
        Enrich multiple leads concurrently.
        
        Args:
            lead_ids: List of lead IDs to enrich
            max_concurrent: Maximum concurrent enrichment tasks
        
        Returns:
            Dict mapping lead_id to enrichment result
        """
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_with_limit(lead_id: UUID):
            async with semaphore:
                await asyncio.sleep(1)  # Rate limiting
                return await self.enrich_lead(lead_id)
        
        tasks = [enrich_with_limit(lid) for lid in lead_ids]
        enrichments = await asyncio.gather(*tasks, return_exceptions=True)
        
        for lead_id, enrichment in zip(lead_ids, enrichments):
            if isinstance(enrichment, Exception):
                results[lead_id] = LeadEnrichment(
                    lead_id=lead_id,
                    enrichment_state=EnrichmentState.FAILED,
                    last_error=str(enrichment)
                )
            else:
                results[lead_id] = enrichment
        
        return results
