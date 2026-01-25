"""
Website & Email Analyzer Module - Enhanced

Visits business websites to:
1. Detect website quality (missing, outdated, no CTA)
2. Extract public emails with confidence scoring
3. Track extraction source (which page, which method)
4. Handle obfuscated emails
5. Crawl multiple pages for better coverage

Only scrapes publicly visible data. No brute force.
"""

import re
import json
import asyncio
from typing import Optional, List, Dict, Tuple, Set
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, asdict
from enum import Enum

import aiohttp
from bs4 import BeautifulSoup

from ..config.settings import settings
from .logger import action_logger
from ..services.db_service import DatabaseService


class EmailConfidence(str, Enum):
    """Confidence level of email extraction."""
    HIGH = "high"      # From mailto: link or matching domain
    MEDIUM = "medium"  # Found on contact page, valid format
    LOW = "low"        # Generic format, different domain


@dataclass
class ExtractedEmail:
    """Represents an extracted email with metadata."""
    email: str
    confidence: EmailConfidence
    source_url: str
    source_method: str  # 'mailto', 'regex', 'obfuscated'
    matches_domain: bool
    prefix_priority: int  # Lower is better (contact=1, info=2, etc.)


class WebsiteAnalyzerModule:
    """
    Analyzes websites and extracts contact emails.
    Updates lead tags and emails based on findings.
    """
    
    # Email regex patterns - more comprehensive
    EMAIL_PATTERNS = [
        r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',  # Standard
    ]
    
    # Obfuscation patterns to decode
    OBFUSCATION_PATTERNS = [
        (r'\[at\]', '@'),
        (r'\(at\)', '@'),
        (r'\s*\[at\]\s*', '@'),
        (r'\s*at\s+', '@'),  # "email at domain.com"
        (r'\[dot\]', '.'),
        (r'\(dot\)', '.'),
        (r'\s*\[dot\]\s*', '.'),
        (r'&#64;', '@'),  # HTML entity
        (r'&#x40;', '@'),  # Hex HTML entity
        (r'%40', '@'),     # URL encoded
    ]
    
    # Pages to check for contact info (in priority order)
    CONTACT_PAGES = [
        '/contact',
        '/contact-us',
        '/contactus',
        '/contact.html',
        '/connect',
        '/reach-us',
        '/reach-out',
        '/about',
        '/about-us',
        '/aboutus',
        '/about.html',
        '/get-in-touch',
        '/support',
        '/help',
        '/team',
    ]
    
    # Email prefix priorities (lower = better)
    PREFIX_PRIORITIES = {
        'contact': 1,
        'info': 2,
        'hello': 3,
        'sales': 4,
        'support': 5,
        'office': 6,
        'admin': 7,
        'help': 8,
        'team': 9,
        'general': 10,
    }
    
    # Known bad email patterns - enhanced
    INVALID_PATTERNS = [
        # Placeholder domains
        'example.com', 'test.com', 'domain.com', 'yoursite.com',
        'sampledomain.com', 'placeholder.com',
        # Placeholder emails
        'email@email', 'your@email', 'name@company', 'you@',
        'user@', 'test@', 'sample@', 'demo@',
        # File extensions in email (false positives)
        '.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.svg', 
        '.webp', '.ico', '.woff', '.ttf', '.eot',
        # Tech/framework domains (false positives from source code)
        'wixpress.com', 'wix.com', 'sentry.io', 'sentry-cdn',
        'cloudflare.com', 'cloudflareinsights.com',
        'google-analytics.com', 'googleusercontent.com',
        'facebook.com', 'twitter.com', 'instagram.com',
        'schema.org', 'w3.org', 'jquery.com',
        'bootstrap', 'fontawesome', 'jsdelivr.net', 'unpkg.com',
        'cdnjs.cloudflare.com', 'fonts.googleapis.com',
        'node_modules', 'webpack', 'npm',
        '-original.', '-copy.',
        # Version/build strings
        '@2x.', '@3x.',
    ]
    
    def __init__(self):
        self.db = DatabaseService()
        self.timeout = 15
        self.request_delay = (1.0, 2.0)
        self.max_pages_per_site = 5  # Limit crawl depth
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    async def _async_random_delay(self):
        """Add random delay between requests."""
        import random
        await asyncio.sleep(random.uniform(*self.request_delay))
    
    async def analyze_all_pending(self, stop_check: Optional[callable] = None) -> Dict:
        """
        Analyze all leads with websites that haven't been fully analyzed.
        """
        leads = await self.db.get_all_leads()
        to_analyze = [
            l for l in leads 
            if l.get('website_url') and not l.get('email')
            and l.get('review_status') == 'pending'
        ]
        
        analyzed = 0
        emails_found = 0
        high_confidence = 0
        errors = 0
        
        action_logger.info(f"Analyzing {len(to_analyze)} leads with websites")
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            for lead in to_analyze:
                if stop_check and stop_check():
                    break
                
                result = await self.analyze_lead(lead, session)
                
                if result.get('success'):
                    analyzed += 1
                    if result.get('email'):
                        emails_found += 1
                        if result.get('confidence') == EmailConfidence.HIGH.value:
                            high_confidence += 1
                else:
                    errors += 1
                
                await self._async_random_delay()
        
        action_logger.log_action(
            lead_id=None,
            module_name="website_analyzer",
            action="analyze_batch",
            result="success",
            details={
                "analyzed": analyzed,
                "emails_found": emails_found,
                "high_confidence": high_confidence,
                "errors": errors
            }
        )
        
        return {
            "analyzed": analyzed,
            "emails_found": emails_found,
            "high_confidence": high_confidence,
            "errors": errors
        }
    
    async def analyze_lead(self, lead: Dict, session: aiohttp.ClientSession) -> Dict:
        """
        Analyze a single lead's website with enhanced email extraction.
        """
        lead_id = lead.get('lead_id')
        website_url = lead.get('website_url', '')
        
        if not website_url:
            await self.db.update_lead(lead_id, {'tag': 'no_website'})
            return {'success': True, 'email': None, 'tag': 'no_website'}
        
        # Normalize URL
        if not website_url.startswith(('http://', 'https://')):
            website_url = 'https://' + website_url
        
        try:
            parsed_url = urlparse(website_url)
            site_domain = parsed_url.netloc.replace('www.', '').lower()
            
            all_emails: List[ExtractedEmail] = []
            pages_crawled = 0
            
            # 1. Fetch and analyze homepage
            response_text, final_url = await self._fetch_page(session, website_url)
            
            if not response_text:
                await self.db.update_lead(lead_id, {'tag': 'website_unreachable'})
                return {'success': True, 'email': None, 'tag': 'website_unreachable'}
            
            pages_crawled += 1
            soup = BeautifulSoup(response_text, 'html.parser')
            
            # Extract emails from homepage
            homepage_emails = self._extract_emails_enhanced(
                response_text, final_url, site_domain
            )
            all_emails.extend(homepage_emails)
            
            # 2. Crawl contact pages if no high-confidence email found
            if not any(e.confidence == EmailConfidence.HIGH for e in all_emails):
                for contact_path in self.CONTACT_PAGES:
                    if pages_crawled >= self.max_pages_per_site:
                        break
                    
                    contact_url = urljoin(final_url, contact_path)
                    c_text, c_final_url = await self._fetch_page(session, contact_url)
                    
                    if c_text:
                        pages_crawled += 1
                        page_emails = self._extract_emails_enhanced(
                            c_text, c_final_url, site_domain
                        )
                        all_emails.extend(page_emails)
                        
                        # Stop if we found a high-confidence email
                        if any(e.confidence == EmailConfidence.HIGH for e in page_emails):
                            break
                    
                    await asyncio.sleep(0.3)
            
            # 3. Determine tag
            page_text = soup.get_text().lower()
            tag = self._determine_tag(final_url, page_text, soup)
            
            # 4. Select best email
            best_email = self._select_best_email(all_emails, site_domain)
            
            # 5. Build update dict
            updates = {'tag': tag}
            extraction_metadata = {}
            
            if best_email:
                updates['email'] = best_email.email
                updates['discovery_confidence'] = best_email.confidence.value
                extraction_metadata = {
                    'source_url': best_email.source_url,
                    'source_method': best_email.source_method,
                    'matches_domain': best_email.matches_domain,
                    'total_emails_found': len(all_emails),
                    'pages_crawled': pages_crawled
                }
            
            await self.db.update_lead(lead_id, updates)
            
            action_logger.log_action(
                lead_id=lead_id,
                module_name="website_analyzer",
                action="analyze",
                result="success",
                details={
                    "tag": tag,
                    "email_found": bool(best_email),
                    "confidence": best_email.confidence.value if best_email else None,
                    "website": website_url,
                    "pages_crawled": pages_crawled,
                    **extraction_metadata
                }
            )
            
            return {
                'success': True,
                'email': best_email.email if best_email else None,
                'confidence': best_email.confidence.value if best_email else None,
                'tag': tag,
                'extraction_metadata': extraction_metadata
            }
            
        except Exception as e:
            action_logger.log_action(
                lead_id=lead_id,
                module_name="website_analyzer",
                action="analyze",
                result="error",
                details={"error": str(e)}
            )
            return {
                'success': False,
                'email': None,
                'tag': 'unknown',
                'error': str(e)
            }
    
    async def _fetch_page(
        self, 
        session: aiohttp.ClientSession, 
        url: str
    ) -> Tuple[Optional[str], str]:
        """Fetch a page with error handling. Returns (text, final_url)."""
        try:
            async with session.get(
                url, 
                timeout=aiohttp.ClientTimeout(total=self.timeout), 
                ssl=False,
                allow_redirects=True
            ) as response:
                if response.status == 200:
                    # Check content type
                    content_type = response.headers.get('content-type', '')
                    if 'text/html' in content_type or 'text/plain' in content_type:
                        text = await response.text()
                        return text, str(response.url)
        except asyncio.TimeoutError:
            pass
        except aiohttp.ClientError:
            pass
        except Exception:
            pass
        return None, url
    
    def _extract_emails_enhanced(
        self, 
        html: str, 
        source_url: str,
        site_domain: str
    ) -> List[ExtractedEmail]:
        """
        Extract email addresses from HTML with confidence scoring.
        """
        extracted: List[ExtractedEmail] = []
        seen: Set[str] = set()
        
        # Decode obfuscated patterns first
        decoded_html = html
        for pattern, replacement in self.OBFUSCATION_PATTERNS:
            decoded_html = re.sub(pattern, replacement, decoded_html, flags=re.IGNORECASE)
        
        # 1. Extract from mailto: links (highest confidence)
        mailto_pattern = r'mailto:([^\s"\'<>?&]+)'
        for match in re.finditer(mailto_pattern, decoded_html, re.IGNORECASE):
            email = match.group(1).split('?')[0].strip()
            email = email.lower()
            
            if email not in seen and self._is_valid_email(email):
                seen.add(email)
                extracted.append(ExtractedEmail(
                    email=email,
                    confidence=self._calculate_confidence(email, site_domain, is_mailto=True),
                    source_url=source_url,
                    source_method='mailto',
                    matches_domain=self._email_matches_domain(email, site_domain),
                    prefix_priority=self._get_prefix_priority(email)
                ))
        
        # 2. Extract from text using regex patterns
        for pattern in self.EMAIL_PATTERNS:
            for match in re.finditer(pattern, decoded_html, re.IGNORECASE):
                email = match.group(0).lower().strip()
                
                # Clean up trailing punctuation
                email = email.rstrip('.,;:')
                
                if email not in seen and self._is_valid_email(email):
                    seen.add(email)
                    extracted.append(ExtractedEmail(
                        email=email,
                        confidence=self._calculate_confidence(email, site_domain, is_mailto=False),
                        source_url=source_url,
                        source_method='regex',
                        matches_domain=self._email_matches_domain(email, site_domain),
                        prefix_priority=self._get_prefix_priority(email)
                    ))
        
        return extracted
    
    def _calculate_confidence(
        self, 
        email: str, 
        site_domain: str, 
        is_mailto: bool
    ) -> EmailConfidence:
        """Calculate confidence level for an extracted email."""
        matches_domain = self._email_matches_domain(email, site_domain)
        prefix = email.split('@')[0].lower()
        is_business_prefix = prefix in self.PREFIX_PRIORITIES
        
        if is_mailto and matches_domain:
            return EmailConfidence.HIGH
        elif matches_domain and is_business_prefix:
            return EmailConfidence.HIGH
        elif matches_domain:
            return EmailConfidence.MEDIUM
        elif is_mailto:
            return EmailConfidence.MEDIUM
        elif is_business_prefix:
            return EmailConfidence.MEDIUM
        else:
            return EmailConfidence.LOW
    
    def _email_matches_domain(self, email: str, site_domain: str) -> bool:
        """Check if email domain matches site domain."""
        email_domain = email.split('@')[1].lower() if '@' in email else ''
        
        # Exact match
        if email_domain == site_domain:
            return True
        
        # Handle www prefix
        if email_domain == 'www.' + site_domain:
            return True
        if 'www.' + email_domain == site_domain:
            return True
        
        # Handle subdomains (e.g., mail.domain.com)
        if email_domain.endswith('.' + site_domain):
            return True
        
        return False
    
    def _get_prefix_priority(self, email: str) -> int:
        """Get priority score for email prefix (lower is better)."""
        prefix = email.split('@')[0].lower() if '@' in email else ''
        return self.PREFIX_PRIORITIES.get(prefix, 100)
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email format and filter out false positives."""
        if not email or '@' not in email:
            return False
        
        email = email.lower()
        
        # Check against invalid patterns
        for pattern in self.INVALID_PATTERNS:
            if pattern in email:
                return False
        
        # Must have valid TLD (at least 2 chars)
        parts = email.split('@')
        if len(parts) != 2:
            return False
        
        domain = parts[1]
        if '.' not in domain:
            return False
        
        tld = domain.split('.')[-1]
        if len(tld) < 2 or len(tld) > 10:
            return False
        
        # Basic format validation
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            return False
        
        # No consecutive dots or dashes
        if '..' in email or '--' in email:
            return False
        
        return True
    
    def _select_best_email(
        self, 
        emails: List[ExtractedEmail],
        site_domain: str
    ) -> Optional[ExtractedEmail]:
        """
        Select the best email from extracted list.
        Priority: matches domain > high confidence > priority prefix > first found
        """
        if not emails:
            return None
        
        # Sort by: matches_domain (desc), confidence (desc), prefix_priority (asc)
        def sort_key(e: ExtractedEmail):
            confidence_order = {
                EmailConfidence.HIGH: 0,
                EmailConfidence.MEDIUM: 1,
                EmailConfidence.LOW: 2
            }
            return (
                not e.matches_domain,  # True = 1, False = 0, so "not" makes matches_domain first
                confidence_order.get(e.confidence, 3),
                e.prefix_priority
            )
        
        sorted_emails = sorted(emails, key=sort_key)
        return sorted_emails[0] if sorted_emails else None
    
    def _determine_tag(self, url: str, page_text: str, soup: BeautifulSoup) -> str:
        """
        Determine the classification tag based on website analysis.
        """
        # Check for common CMS/builder indicators
        html_str = str(soup).lower()
        
        if 'wordpress' in html_str or 'wp-content' in html_str:
            return 'wordpress_site'
        if 'wix.com' in html_str or 'wixsite' in html_str:
            return 'wix_site'
        if 'squarespace' in html_str:
            return 'squarespace_site'
        if 'shopify' in html_str:
            return 'shopify_site'
        if 'webflow' in html_str:
            return 'webflow_site'
        
        # Check for contact indicators
        has_contact = any(word in page_text for word in [
            'contact', 'touch', 'reach', 'email us', 'call us', 'phone'
        ])
        
        has_form = soup.find('form') is not None
        
        # Check for business indicators
        has_services = any(word in page_text for word in [
            'services', 'products', 'pricing', 'plans', 'solutions', 'offerings'
        ])
        
        has_about = any(word in page_text for word in [
            'about us', 'our team', 'our story', 'who we are', 'mission'
        ])
        
        if has_form and has_contact:
            return 'active_business'
        elif has_services and has_about:
            return 'established_business'
        elif has_contact:
            return 'basic_presence'
        else:
            return 'minimal_site'
