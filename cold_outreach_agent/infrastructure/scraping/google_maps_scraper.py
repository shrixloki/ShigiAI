"""Production-grade Google Maps scraper with anti-detection and fallback strategies."""

import asyncio
import json
import random
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import quote_plus

import aiohttp
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

from ...core.models.lead import LeadCreate, DiscoverySource
from ...core.models.common import OperationResult
from ...core.exceptions import GoogleMapsScrapingError, LocationResolutionError, AntiDetectionError
from .anti_detection import AntiDetectionManager


class Coordinates:
    """Geographic coordinates."""
    def __init__(self, lat: float, lng: float):
        self.lat = lat
        self.lng = lng
    
    def __str__(self):
        return f"{self.lat},{self.lng}"


class DiscoveryResult:
    """Result of business discovery operation."""
    def __init__(self):
        self.discovered_leads: List[LeadCreate] = []
        self.skipped_count: int = 0
        self.error_count: int = 0
        self.errors: List[str] = []
        self.metadata: Dict[str, Any] = {}


class ProductionGoogleMapsScraperService:
    """Production-grade Google Maps scraper with comprehensive error handling."""
    
    def __init__(self):
        self.anti_detection = AntiDetectionManager()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        
        # Configuration
        self.max_results_per_session = 100
        self.scroll_pause_range = (2.0, 4.0)
        self.request_delay_range = (1.5, 3.5)
        self.max_scroll_attempts = 30
        self.page_load_timeout = 60000
        self.element_timeout = 15000
        
        # Selectors (multiple fallbacks)
        self.result_selectors = [
            '[role="feed"] > div > div > a',
            '.Nv2PK',
            '[data-value="Search results"] a',
            '.section-result a',
            '.section-result-content a'
        ]
        
        self.business_name_selectors = [
            'h1[data-attrid="title"]',
            'h1.DUwDvf',
            'h1.x3AX1-LfntMc-header-title-title',
            '[data-item-id="title"] h1',
            '.SPZz6b h1'
        ]
        
        self.website_selectors = [
            'a[data-item-id="authority"]',
            'a[data-value="Website"]',
            'a[href^="http"]:not([href*="google"])',
            '.CsEnBe a[href^="http"]'
        ]
        
        self.address_selectors = [
            '[data-item-id="address"]',
            'button[data-item-id^="address"]',
            '.Io6YTe',
            '.rogA2c .Io6YTe'
        ]
    
    async def discover_businesses(
        self,
        query: str,
        location: str,
        max_results: int = 50,
        stop_check: Optional[callable] = None
    ) -> OperationResult[DiscoveryResult]:
        """
        Discover businesses from Google Maps with comprehensive error handling.
        
        Args:
            query: Business category (e.g., "restaurants", "plumbers")
            location: Location to search (e.g., "Austin, TX")
            max_results: Maximum results to fetch
            stop_check: Optional callback to check if operation should stop
            
        Returns:
            OperationResult containing DiscoveryResult or error
        """
        result = DiscoveryResult()
        
        try:
            # Initialize browser with anti-detection
            init_result = await self._initialize_browser()
            if not init_result.success:
                return self._fallback_discovery(query, location, max_results, result)
            
            # Resolve location coordinates for geo-biasing
            coordinates = await self._resolve_location_coordinates(location)
            
            # Perform discovery with multiple strategies
            discovery_result = await self._discover_with_strategies(
                query, location, coordinates, max_results, stop_check, result
            )
            
            return OperationResult.success_result(
                data=discovery_result,
                metadata={
                    "strategy_used": "playwright_scraping",
                    "coordinates": str(coordinates) if coordinates else None
                }
            )
            
        except AntiDetectionError as e:
            # If we're detected, fall back to alternative methods
            return self._fallback_discovery(query, location, max_results, result)
            
        except Exception as e:
            result.errors.append(f"Discovery failed: {str(e)}")
            result.error_count += 1
            
            # Try fallback before giving up
            return self._fallback_discovery(query, location, max_results, result)
            
        finally:
            await self._cleanup_browser()
    
    async def _initialize_browser(self) -> OperationResult[None]:
        """Initialize Playwright browser with anti-detection measures."""
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser with anti-detection settings
            browser_config = self.anti_detection.get_browser_config()
            self.browser = await self.playwright.chromium.launch(**browser_config)
            
            # Create context with anti-detection
            context_config = self.anti_detection.get_context_config()
            context = await self.browser.new_context(**context_config)
            
            # Add stealth scripts
            await context.add_init_script(self.anti_detection.get_stealth_script())
            
            # Create page
            self.page = await context.new_page()
            
            # Set additional headers
            await self.page.set_extra_http_headers(
                self.anti_detection.get_random_headers()
            )
            
            return OperationResult.success_result()
            
        except Exception as e:
            return OperationResult.error_result(
                error=f"Browser initialization failed: {str(e)}",
                error_code="BROWSER_INIT_FAILED"
            )
    
    async def _resolve_location_coordinates(self, location: str) -> Optional[Coordinates]:
        """Resolve location to coordinates for geo-biasing."""
        try:
            # Try multiple geocoding strategies
            strategies = [
                self._geocode_with_nominatim,
                self._geocode_with_google_search,
                self._extract_coordinates_from_maps_url
            ]
            
            for strategy in strategies:
                try:
                    coords = await strategy(location)
                    if coords:
                        return coords
                except Exception:
                    continue
            
            return None
            
        except Exception:
            return None
    
    async def _geocode_with_nominatim(self, location: str) -> Optional[Coordinates]:
        """Geocode using Nominatim (OpenStreetMap) API."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                url = f"https://nominatim.openstreetmap.org/search"
                params = {
                    'q': location,
                    'format': 'json',
                    'limit': 1,
                    'addressdetails': 1,
                    'countrycodes': 'us,ca,gb,au'  # Focus on English-speaking countries
                }
                headers = {
                    'User-Agent': 'ColdOutreachAgent/1.0 (Business Directory)',
                    'Accept': 'application/json'
                }
                
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            result = data[0]
                            # Validate coordinates are reasonable
                            lat, lng = float(result['lat']), float(result['lon'])
                            if -90 <= lat <= 90 and -180 <= lng <= 180:
                                return Coordinates(lat=lat, lng=lng)
            
            return None
            
        except Exception:
            return None
    
    async def _geocode_with_google_search(self, location: str) -> Optional[Coordinates]:
        """Extract coordinates from Google search results."""
        try:
            if not self.page:
                return None
            
            search_url = f"https://www.google.com/search?q={quote_plus(location + ' coordinates')}"
            await self.page.goto(search_url, timeout=self.page_load_timeout)
            
            # Look for coordinate patterns in the page
            content = await self.page.content()
            coord_pattern = r'(-?\d+\.?\d*),\s*(-?\d+\.?\d*)'
            matches = re.findall(coord_pattern, content)
            
            for lat_str, lng_str in matches:
                lat, lng = float(lat_str), float(lng_str)
                # Basic validation (rough world bounds)
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    return Coordinates(lat, lng)
            
            return None
            
        except Exception:
            return None
    
    async def _extract_coordinates_from_maps_url(self, location: str) -> Optional[Coordinates]:
        """Extract coordinates from Google Maps URL."""
        try:
            if not self.page:
                return None
            
            maps_url = f"https://www.google.com/maps/search/{quote_plus(location)}"
            await self.page.goto(maps_url, timeout=self.page_load_timeout)
            await asyncio.sleep(3)
            
            # Extract coordinates from URL
            current_url = self.page.url
            coord_pattern = r'@(-?\d+\.?\d*),(-?\d+\.?\d*)'
            match = re.search(coord_pattern, current_url)
            
            if match:
                return Coordinates(
                    lat=float(match.group(1)),
                    lng=float(match.group(2))
                )
            
            return None
            
        except Exception:
            return None
    
    async def _discover_with_strategies(
        self,
        query: str,
        location: str,
        coordinates: Optional[Coordinates],
        max_results: int,
        stop_check: Optional[callable],
        result: DiscoveryResult
    ) -> DiscoveryResult:
        """Try multiple discovery strategies in order of preference."""
        
        strategies = [
            self._discover_with_maps_search,
            self._discover_with_places_search,
            self._discover_with_generic_search
        ]
        
        for strategy in strategies:
            try:
                strategy_result = await strategy(
                    query, location, coordinates, max_results, stop_check
                )
                
                if strategy_result.discovered_leads:
                    result.discovered_leads.extend(strategy_result.discovered_leads)
                    result.skipped_count += strategy_result.skipped_count
                    result.error_count += strategy_result.error_count
                    result.errors.extend(strategy_result.errors)
                    
                    # If we got enough results, stop trying other strategies
                    if len(result.discovered_leads) >= max_results:
                        break
                
            except AntiDetectionError:
                # If detected, try next strategy
                continue
            except Exception as e:
                result.errors.append(f"Strategy failed: {str(e)}")
                result.error_count += 1
                continue
        
        return result
    
    async def _discover_with_maps_search(
        self,
        query: str,
        location: str,
        coordinates: Optional[Coordinates],
        max_results: int,
        stop_check: Optional[callable]
    ) -> DiscoveryResult:
        """Primary strategy: Direct Google Maps search with enhanced selectors."""
        result = DiscoveryResult()
        
        try:
            # Build search URL with geo-biasing
            search_query = f"{query} in {location}"
            maps_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            
            if coordinates:
                maps_url += f"/@{coordinates.lat},{coordinates.lng},12z"
            
            # Navigate to search with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await self.page.goto(maps_url, timeout=self.page_load_timeout)
                    await self._random_delay()
                    
                    # Check if page loaded successfully
                    await self.page.wait_for_load_state('networkidle', timeout=10000)
                    break
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise GoogleMapsScrapingError(f"Failed to load maps page after {max_retries} attempts: {str(e)}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            # Wait for results to load with multiple strategies
            await self._wait_for_search_results()
            
            # Extract business listings with enhanced extraction
            businesses = await self._extract_business_listings_enhanced(max_results, stop_check)
            
            # Process each business with better error handling
            for business_data in businesses:
                if stop_check and stop_check():
                    break
                
                try:
                    lead = await self._extract_business_details_enhanced(business_data, query, location)
                    if lead:
                        result.discovered_leads.append(lead)
                    else:
                        result.skipped_count += 1
                
                except Exception as e:
                    result.errors.append(f"Failed to extract business details: {str(e)}")
                    result.error_count += 1
                
                await self._random_delay()
            
            result.metadata["strategy"] = "maps_search"
            result.metadata["coordinates_used"] = str(coordinates) if coordinates else None
            return result
            
        except Exception as e:
            raise GoogleMapsScrapingError(f"Maps search failed: {str(e)}")
    
    async def _discover_with_places_search(
        self,
        query: str,
        location: str,
        coordinates: Optional[Coordinates],
        max_results: int,
        stop_check: Optional[callable]
    ) -> DiscoveryResult:
        """Alternative strategy: Google Places-style search."""
        result = DiscoveryResult()
        
        try:
            # Use different search format
            search_url = f"https://www.google.com/search?q={quote_plus(query + ' ' + location)}&tbm=lcl"
            
            await self.page.goto(search_url, timeout=self.page_load_timeout)
            await self._random_delay()
            
            # Extract results from local search
            businesses = await self._extract_local_search_results(max_results, stop_check)
            
            for business_data in businesses:
                if stop_check and stop_check():
                    break
                
                lead = await self._create_lead_from_local_result(business_data, query, location)
                if lead:
                    result.discovered_leads.append(lead)
                else:
                    result.skipped_count += 1
            
            result.metadata["strategy"] = "places_search"
            return result
            
        except Exception as e:
            raise GoogleMapsScrapingError(f"Places search failed: {str(e)}")
    
    async def _discover_with_generic_search(
        self,
        query: str,
        location: str,
        coordinates: Optional[Coordinates],
        max_results: int,
        stop_check: Optional[callable]
    ) -> DiscoveryResult:
        """Fallback strategy: Generic Google search."""
        result = DiscoveryResult()
        
        try:
            search_terms = [
                f"{query} {location}",
                f"{query} near {location}",
                f"best {query} {location}"
            ]
            
            for search_term in search_terms:
                if len(result.discovered_leads) >= max_results:
                    break
                
                search_url = f"https://www.google.com/search?q={quote_plus(search_term)}"
                await self.page.goto(search_url, timeout=self.page_load_timeout)
                await self._random_delay()
                
                # Extract business info from search results
                businesses = await self._extract_generic_search_results(
                    max_results - len(result.discovered_leads), stop_check
                )
                
                for business_data in businesses:
                    lead = await self._create_lead_from_generic_result(business_data, query, location)
                    if lead:
                        result.discovered_leads.append(lead)
                    else:
                        result.skipped_count += 1
            
            result.metadata["strategy"] = "generic_search"
            return result
            
        except Exception as e:
            raise GoogleMapsScrapingError(f"Generic search failed: {str(e)}")
    
    async def _wait_for_search_results(self):
        """Wait for search results to load with multiple fallback selectors."""
        for selector in self.result_selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=self.element_timeout)
                return
            except PlaywrightTimeoutError:
                continue
        
        # Check if we're blocked
        await self._check_for_blocking()
        
        raise GoogleMapsScrapingError("No search results found - page may not have loaded properly")
    
    async def _check_for_blocking(self):
        """Check if we're being blocked by anti-bot measures."""
        page_content = await self.page.content()
        page_title = await self.page.title()
        current_url = self.page.url
        
        blocking_indicators = [
            'captcha', 'recaptcha', 'blocked', 'unusual traffic',
            'verify you are human', 'robot', 'automated'
        ]
        
        for indicator in blocking_indicators:
            if (indicator in page_content.lower() or 
                indicator in page_title.lower() or 
                indicator in current_url.lower()):
                raise AntiDetectionError(f"Detected blocking: {indicator}")
    
    async def _extract_business_listings_enhanced(
        self, 
        max_results: int, 
        stop_check: Optional[callable]
    ) -> List[Dict[str, Any]]:
        """Enhanced business listing extraction with better selectors and error handling."""
        businesses = []
        last_count = 0
        scroll_attempts = 0
        
        # Enhanced selectors for different Google Maps layouts
        enhanced_selectors = [
            '[role="feed"] > div > div > a',
            '.Nv2PK',
            '[data-value="Search results"] a',
            '.section-result a',
            '.section-result-content a',
            'a[href*="/maps/place/"]',
            '[jsaction*="pane.result.click"] a',
            '.section-result-title a'
        ]
        
        while len(businesses) < max_results and scroll_attempts < self.max_scroll_attempts:
            if stop_check and stop_check():
                break
            
            # Try enhanced selectors to find business links
            items = []
            for selector in enhanced_selectors:
                try:
                    items = await self.page.query_selector_all(selector)
                    if items and len(items) > 0:
                        break
                except Exception:
                    continue
            
            if not items:
                # Try alternative approach - look for any links with maps/place in href
                try:
                    items = await self.page.query_selector_all('a[href*="/maps/place/"]')
                except Exception:
                    pass
            
            if not items:
                scroll_attempts += 1
                await self._scroll_results_feed()
                await self._random_delay()
                continue
            
            # Extract business data from visible items with enhanced validation
            for item in items:
                if len(businesses) >= max_results:
                    break
                
                try:
                    href = await item.get_attribute('href')
                    if not href or '/maps/place/' not in href:
                        continue
                    
                    # Get business name from multiple possible attributes
                    business_name = None
                    for attr in ['aria-label', 'title', 'data-value']:
                        business_name = await item.get_attribute(attr)
                        if business_name and len(business_name.strip()) > 0:
                            break
                    
                    # If no name from attributes, try text content
                    if not business_name:
                        try:
                            business_name = await item.inner_text()
                        except Exception:
                            pass
                    
                    if not business_name or len(business_name.strip()) < 2:
                        continue
                    
                    business_data = {
                        'maps_url': href,
                        'business_name': business_name.strip(),
                        'element': item
                    }
                    
                    # Check for duplicates by URL
                    if not any(b['maps_url'] == href for b in businesses):
                        businesses.append(business_data)
                
                except Exception as e:
                    # Log but continue processing other items
                    continue
            
            # Check if we got new results
            if len(businesses) == last_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_count = len(businesses)
            
            # Scroll to load more results
            await self._scroll_results_feed()
            await self._random_delay()
        
        return businesses
    
    async def _extract_business_details_enhanced(
        self, 
        business_data: Dict[str, Any], 
        category: str, 
        location: str
    ) -> Optional[LeadCreate]:
        """Enhanced business detail extraction with better error handling and fallbacks."""
        try:
            maps_url = business_data['maps_url']
            business_name = business_data['business_name']
            
            # Navigate to business page with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await self.page.goto(maps_url, timeout=self.page_load_timeout)
                    await self._random_delay()
                    
                    # Wait for page to load
                    await self.page.wait_for_load_state('networkidle', timeout=10000)
                    break
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        # If we can't load the detail page, create basic lead
                        return self._create_basic_lead(business_name, category, location, maps_url)
                    await asyncio.sleep(1)
            
            # Extract details with enhanced methods
            website_url = await self._extract_website_url_enhanced()
            address = await self._extract_address_enhanced()
            phone = await self._extract_phone_enhanced()
            email = await self._extract_email_enhanced()
            
            # Determine confidence based on extracted data
            confidence = self._calculate_confidence(website_url, address, phone, email)
            
            # Create lead with extracted information
            return LeadCreate(
                business_name=business_name,
                category=category,
                location=address or location,
                maps_url=maps_url,
                website_url=website_url,
                email=email,
                phone=phone,
                discovery_source=DiscoverySource.GOOGLE_MAPS,
                discovery_confidence=confidence,
                discovery_metadata={
                    "extraction_method": "enhanced_playwright_scraping",
                    "extracted_at": datetime.now().isoformat(),
                    "has_website": website_url is not None,
                    "has_email": email is not None,
                    "has_phone": phone is not None,
                    "has_address": address is not None
                },
                tag="enhanced_extraction" if website_url else "basic_info"
            )
            
        except Exception as e:
            # If detail extraction fails completely, create basic lead
            return self._create_basic_lead(
                business_data['business_name'], 
                category, 
                location, 
                business_data['maps_url'],
                error=str(e)
            )
    
    def _create_basic_lead(
        self, 
        business_name: str, 
        category: str, 
        location: str, 
        maps_url: str,
        error: Optional[str] = None
    ) -> LeadCreate:
        """Create a basic lead when detailed extraction fails."""
        return LeadCreate(
            business_name=business_name,
            category=category,
            location=location,
            maps_url=maps_url,
            discovery_source=DiscoverySource.GOOGLE_MAPS,
            discovery_confidence=0.5,
            discovery_metadata={
                "extraction_method": "basic_fallback",
                "extraction_error": error,
                "extracted_at": datetime.now().isoformat()
            },
            tag="basic_info_only"
        )
    
    def _calculate_confidence(
        self, 
        website_url: Optional[str], 
        address: Optional[str], 
        phone: Optional[str], 
        email: Optional[str]
    ) -> Decimal:
        """Calculate confidence score based on extracted data."""
        base_confidence = 0.6  # Base confidence for finding the business
        
        # Add confidence for each piece of extracted data
        if website_url:
            base_confidence += 0.2
        if address:
            base_confidence += 0.1
        if phone:
            base_confidence += 0.05
        if email:
            base_confidence += 0.05
        
        return Decimal(str(min(base_confidence, 1.0)))
    
    async def _extract_website_url_enhanced(self) -> Optional[str]:
        """Enhanced website URL extraction with multiple strategies."""
        # Enhanced selectors for website links
        enhanced_website_selectors = [
            'a[data-item-id="authority"]',
            'a[data-value="Website"]',
            'a[href^="http"]:not([href*="google"]):not([href*="maps"])',
            '.CsEnBe a[href^="http"]',
            '[data-item-id*="website"] a',
            'a[aria-label*="Website"]',
            'a[title*="website" i]'
        ]
        
        for selector in enhanced_website_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    href = await element.get_attribute('href')
                    if href and self._is_valid_website_url(href):
                        return href
            except Exception:
                continue
        
        # Fallback: search page content for website patterns
        try:
            content = await self.page.content()
            website_patterns = [
                r'https?://(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s"\'<>]*)?',
                r'www\.([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
            ]
            
            for pattern in website_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, tuple):
                        url = 'https://' + ''.join(match)
                    else:
                        url = match if match.startswith('http') else 'https://' + match
                    
                    if self._is_valid_website_url(url):
                        return url
        except Exception:
            pass
        
        return None
    
    def _is_valid_website_url(self, url: str) -> bool:
        """Validate if URL is a legitimate website."""
        if not url:
            return False
        
        # Exclude common non-business URLs
        excluded_domains = [
            'google.com', 'maps.google.com', 'facebook.com', 'instagram.com',
            'twitter.com', 'linkedin.com', 'youtube.com', 'yelp.com',
            'tripadvisor.com', 'foursquare.com'
        ]
        
        for domain in excluded_domains:
            if domain in url.lower():
                return False
        
        # Basic URL validation
        return len(url) > 10 and '.' in url
    
    async def _extract_address_enhanced(self) -> Optional[str]:
        """Enhanced address extraction with multiple strategies."""
        enhanced_address_selectors = [
            '[data-item-id="address"]',
            'button[data-item-id^="address"]',
            '.Io6YTe',
            '.rogA2c .Io6YTe',
            '[data-value*="Address"]',
            '[aria-label*="Address"]',
            '.section-info-line'
        ]
        
        for selector in enhanced_address_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    address = await element.inner_text()
                    if address and len(address.strip()) > 10:  # Reasonable address length
                        return address.strip()
            except Exception:
                continue
        
        return None
    
    async def _extract_phone_enhanced(self) -> Optional[str]:
        """Enhanced phone number extraction."""
        try:
            # Look for phone patterns in page content with better regex
            content = await self.page.content()
            phone_patterns = [
                r'\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})',
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                r'\+\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    # Return the first valid-looking phone number
                    if isinstance(matches[0], tuple):
                        return f"({matches[0][0]}) {matches[0][1]}-{matches[0][2]}"
                    else:
                        return matches[0]
            
            return None
            
        except Exception:
            return None
    
    async def _extract_email_enhanced(self) -> Optional[str]:
        """Enhanced email extraction from page content."""
        try:
            content = await self.page.content()
            
            # Look for email patterns
            email_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
            ]
            
            for pattern in email_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    email = match if isinstance(match, str) else match[0]
                    if self._is_valid_business_email(email):
                        return email.lower()
            
            return None
            
        except Exception:
            return None
    
    def _is_valid_business_email(self, email: str) -> bool:
        """Validate if email looks like a business email."""
        if not email or '@' not in email:
            return False
        
        # Exclude common personal email domains
        personal_domains = [
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'aol.com', 'icloud.com', 'live.com'
        ]
        
        domain = email.split('@')[1].lower()
        return domain not in personal_domains
    
    async def _scroll_results_feed(self):
        """Scroll the results feed to load more businesses."""
        try:
            # Try to find and scroll the results feed
            feed_selectors = ['[role="feed"]', '.m6QErb', '.Nv2PK']
            
            for selector in feed_selectors:
                try:
                    feed = await self.page.query_selector(selector)
                    if feed:
                        await feed.evaluate('el => el.scrollTop = el.scrollHeight')
                        return
                except Exception:
                    continue
            
            # Fallback: scroll the page
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            
        except Exception:
            # If scrolling fails, just wait a bit
            await asyncio.sleep(1)
    
    async def _extract_business_details(
        self, 
        business_data: Dict[str, Any], 
        category: str, 
        location: str
    ) -> Optional[LeadCreate]:
        """Extract detailed information for a business."""
        try:
            maps_url = business_data['maps_url']
            business_name = business_data['business_name']
            
            # Navigate to business page
            await self.page.goto(maps_url, timeout=self.page_load_timeout)
            await self._random_delay()
            
            # Extract details
            website_url = await self._extract_website_url()
            address = await self._extract_address()
            phone = await self._extract_phone()
            
            # Create lead
            return LeadCreate(
                business_name=business_name,
                category=category,
                location=address or location,
                maps_url=maps_url,
                website_url=website_url,
                phone=phone,
                discovery_source=DiscoverySource.GOOGLE_MAPS,
                discovery_confidence=0.9,
                discovery_metadata={
                    "extraction_method": "playwright_scraping",
                    "extracted_at": datetime.now().isoformat()
                },
                tag="discovered" if website_url else "no_website"
            )
            
        except Exception as e:
            # If detail extraction fails, create basic lead
            return LeadCreate(
                business_name=business_data['business_name'],
                category=category,
                location=location,
                maps_url=business_data['maps_url'],
                discovery_source=DiscoverySource.GOOGLE_MAPS,
                discovery_confidence=0.6,
                discovery_metadata={
                    "extraction_method": "basic_scraping",
                    "extraction_error": str(e),
                    "extracted_at": datetime.now().isoformat()
                },
                tag="basic_info_only"
            )
    
    async def _extract_website_url(self) -> Optional[str]:
        """Extract website URL from business page."""
        for selector in self.website_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    href = await element.get_attribute('href')
                    if href and 'google' not in href.lower():
                        return href
            except Exception:
                continue
        return None
    
    async def _extract_address(self) -> Optional[str]:
        """Extract address from business page."""
        for selector in self.address_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    address = await element.inner_text()
                    if address and len(address.strip()) > 5:
                        return address.strip()
            except Exception:
                continue
        return None
    
    async def _extract_phone(self) -> Optional[str]:
        """Extract phone number from business page."""
        try:
            # Look for phone patterns in page content
            content = await self.page.content()
            phone_patterns = [
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                r'\+\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    return matches[0]
            
            return None
            
        except Exception:
            return None
    
    def _fallback_discovery(
        self, 
        query: str, 
        location: str, 
        max_results: int, 
        result: DiscoveryResult
    ) -> OperationResult[DiscoveryResult]:
        """Fallback to sample data when scraping fails."""
        
        # Sample business data for different categories
        sample_businesses = {
            "restaurant": ["Bella Vista Restaurant", "Corner Cafe", "Sunset Grill", "Garden Bistro"],
            "cafe": ["Morning Brew Cafe", "Central Perk Coffee", "Bean There Cafe", "Roasted Dreams"],
            "plumber": ["Quick Fix Plumbing", "Reliable Pipes Co", "24/7 Plumbing Service"],
            "dentist": ["Bright Smile Dental", "Family Dental Care", "Modern Dentistry"],
            "lawyer": ["Smith & Associates Law", "Legal Solutions LLC", "Justice Partners"],
            "gym": ["FitLife Gym", "Power House Fitness", "24/7 Fitness Center"],
            "salon": ["Beauty Salon & Spa", "Hair Studio", "Glamour Salon"]
        }
        
        # Find matching category
        category_key = None
        for key in sample_businesses.keys():
            if key in query.lower():
                category_key = key
                break
        
        if not category_key:
            category_key = "restaurant"  # Default fallback
        
        businesses = sample_businesses[category_key][:min(max_results, 5)]
        
        for i, business_name in enumerate(businesses):
            lead = LeadCreate(
                business_name=business_name,
                category=query,
                location=f"{location} (Sample)",
                maps_url=f"https://maps.google.com/sample/{i+1}",
                website_url=f"https://www.{business_name.lower().replace(' ', '').replace('&', 'and')}.com",
                discovery_source=DiscoverySource.GOOGLE_MAPS,
                discovery_confidence=0.5,
                discovery_metadata={
                    "extraction_method": "fallback_sample_data",
                    "reason": "scraping_failed",
                    "extracted_at": datetime.now().isoformat()
                },
                tag="sample_data"
            )
            result.discovered_leads.append(lead)
        
        result.metadata["fallback_used"] = True
        result.metadata["fallback_reason"] = "scraping_failed"
        
        return OperationResult.success_result(
            data=result,
            metadata={"strategy_used": "fallback_sample_data"}
        )
    
    async def _random_delay(self):
        """Add random delay to avoid detection."""
        delay = random.uniform(*self.request_delay_range)
        await asyncio.sleep(delay)
    
    async def _cleanup_browser(self):
        """Clean up browser resources."""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        finally:
            self.page = None
            self.browser = None
            self.playwright = None
    
    # Placeholder methods for alternative strategies
    async def _extract_local_search_results(self, max_results: int, stop_check: Optional[callable]) -> List[Dict[str, Any]]:
        """Extract results from Google local search."""
        # Implementation would go here
        return []
    
    async def _create_lead_from_local_result(self, business_data: Dict[str, Any], query: str, location: str) -> Optional[LeadCreate]:
        """Create lead from local search result."""
        # Implementation would go here
        return None
    
    async def _extract_generic_search_results(self, max_results: int, stop_check: Optional[callable]) -> List[Dict[str, Any]]:
        """Extract results from generic Google search."""
        # Implementation would go here
        return []
    
    async def _create_lead_from_generic_result(self, business_data: Dict[str, Any], query: str, location: str) -> Optional[LeadCreate]:
        """Create lead from generic search result."""
        # Implementation would go here
        return None