"""
Hunter Module - Map Discovery Agent

Discovers businesses from Google Maps search queries.
Extracts: business name, category, address, website, maps URL.
Does NOT send emails - only populates leads with review_status='pending'.
"""

import re
import time
import random
import asyncio
from typing import Optional, List, Dict
from datetime import datetime

from config.settings import settings
from modules.logger import action_logger
from services.db_service import DatabaseService


class HunterModule:
    """
    Discovers businesses from map sources.
    All discovered leads start with review_status='pending'.
    NO EMAILS ARE SENT BY THIS MODULE.
    """
    
    def __init__(self):
        self.db = DatabaseService()
        self.browser = None
        self.page = None
        self.max_results_per_run = 50
        self.request_delay = (1.5, 3.0)  # Random delay range
    
    async def _async_random_delay(self):
        delay = random.uniform(*self.request_delay)
        await asyncio.sleep(delay)
    
    async def _init_browser(self):
        """Initialize Playwright browser with better anti-detection."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(
                headless=False, # Headless=False often helps with bot detection
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            context = await self.browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                }
            )
            
            # Add stealth settings
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                window.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)
            
            self.page = await context.new_page()
            return True
        except Exception as e:
            action_logger.error(f"Failed to init browser: {e}")
            return False
    
    async def _close_browser(self):
        """Close browser and cleanup."""
        try:
            if self.browser:
                await self.browser.close()
            if hasattr(self, '_playwright'):
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self.browser = None
            self.page = None
    
    async def discover_from_maps(
        self,
        query: str,
        location: str,
        max_results: Optional[int] = None,
        stop_check: Optional[callable] = None
    ) -> Dict:
        """
        Discover businesses from Google Maps.
        
        Args:
            query: Business category (e.g., "restaurants", "plumbers")
            location: Location to search (e.g., "Austin, TX")
            max_results: Maximum results to fetch (default: 50)
            stop_check: Callable that returns True if we should stop
        
        Returns:
            {discovered: int, skipped: int, errors: list, location_info: dict}
        """
        from services.location_service import get_location_service
        
        max_results = max_results or self.max_results_per_run
        discovered = 0
        skipped = 0
        errors = []
        
        # Validate and normalize location
        location_service = get_location_service()
        location_result = location_service.validate_and_normalize(location)
        
        action_logger.log_action(
            lead_id=None,
            module_name="hunter",
            action="discover_start",
            result="info",
            details={
                "query": query, 
                "original_location": location,
                "normalized_location": location_result.normalized,
                "location_confidence": location_result.confidence.value,
                "max_results": max_results
            }
        )
        
        if location_result.error:
            errors.append(f"Location error: {location_result.error}")
            return {
                "discovered": 0,
                "skipped": 0,
                "errors": errors,
                "location_info": {
                    "original": location,
                    "error": location_result.error
                }
            }
        
        try:
            if not await self._init_browser():
                raise Exception("Browser initialization failed")
            
            # Try primary normalized location
            search_result = await self._perform_search(
                query, 
                location_result.search_query, 
                max_results, 
                stop_check
            )
            discovered = search_result["discovered"]
            skipped = search_result["skipped"]
            errors.extend(search_result["errors"])
            
            # If no results, try fallback locations
            if discovered == 0:
                fallbacks = location_service.get_fallback_locations(location_result)
                
                for fallback_location in fallbacks:
                    if stop_check and stop_check():
                        break
                    
                    action_logger.info(f"No results for {location_result.search_query}. Trying fallback: {fallback_location}")
                    
                    search_result = await self._perform_search(
                        query, 
                        fallback_location, 
                        max_results, 
                        stop_check
                    )
                    
                    if search_result["discovered"] > 0:
                        discovered = search_result["discovered"]
                        skipped = search_result["skipped"]
                        errors.extend(search_result["errors"])
                        
                        # Log that fallback was used
                        action_logger.log_action(
                            lead_id=None,
                            module_name="hunter",
                            action="discover_fallback_used",
                            result="success",
                            details={
                                "original_location": location,
                                "fallback_location": fallback_location,
                                "discovered": discovered
                            }
                        )
                        break
            
        except Exception as e:
            errors.append(f"Discovery error: {str(e)}")
            action_logger.error(f"Discovery failed: {e}")
        
        finally:
            await self._close_browser()
        
        # Log final results
        action_logger.log_action(
            lead_id=None,
            module_name="hunter",
            action="discover_complete",
            result="success" if discovered > 0 else "warning",
            details={
                "discovered": discovered,
                "skipped": skipped,
                "errors_count": len(errors),
                "location_confidence": location_result.confidence.value
            }
        )
        
        return {
            "discovered": discovered,
            "skipped": skipped,
            "errors": errors[:10],  # Limit error list
            "location_info": {
                "original": location,
                "normalized": location_result.normalized,
                "confidence": location_result.confidence.value,
                "city": location_result.city,
                "region": location_result.region,
                "country": location_result.country
            }
        }

    async def _perform_search(self, query, location, max_results, stop_check):
        """
        Helper to run the search and extraction loop.
        
        Returns:
            dict with {discovered: int, skipped: int, errors: list}
        """
        discovered = 0
        skipped = 0
        errors = []
        
        search_query = f"{query} near {location}"
        maps_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
        
        action_logger.info(f"Navigating to: {maps_url}")
        
        try:
            await self.page.goto(maps_url, wait_until='domcontentloaded', timeout=60000)
            await self.page.wait_for_timeout(3000)
        except Exception as e:
            action_logger.error(f"Navigation failed: {e}")
            errors.append(f"Navigation failed: {str(e)}")
            return {"discovered": 0, "skipped": 0, "errors": errors}

        # Wait for results - try multiple selectors
        selectors_to_try = [
            '[role="feed"]',
            '.Nv2PK',
            'div[aria-label^="Results for"]',
            '.m6QErb.DxyBCb',
            'div.Nv2PK'
        ]
        
        results_loaded = False
        for selector in selectors_to_try:
            try:
                await self.page.wait_for_selector(selector, timeout=10000)
                results_loaded = True
                break
            except Exception:
                continue
        
        if not results_loaded:
            current_url = self.page.url if self.page else ""
            if 'consent' in current_url.lower():
                action_logger.warning("Consent form detected, attempting to handle...")
                # Try to click reject/accept buttons
                try:
                    reject_btn = await self.page.query_selector('button[aria-label*="Reject"]')
                    if reject_btn:
                        await reject_btn.click()
                        await self.page.wait_for_timeout(2000)
                except:
                    pass
            
            errors.append(f"No search results found for: {search_query}")
            return {"discovered": 0, "skipped": 0, "errors": errors}
        
        await self._async_random_delay()
        
        # Scroll and Extract
        businesses = []
        scroll_attempts = 0
        max_scroll_attempts = 20
        last_count = 0
        
        while len(businesses) < max_results and scroll_attempts < max_scroll_attempts:
            if stop_check and stop_check():
                break
            
            # Find all links that look like business listings
            items = await self.page.query_selector_all('a[href*="/maps/place/"]')
            
            for item in items:
                if len(businesses) >= max_results:
                    break
                
                try:
                    href = await item.get_attribute('href')
                    aria_label = await item.get_attribute('aria-label')
                    
                    if href and aria_label:
                        # Avoid duplicates in this run
                        if not any(b['maps_url'] == href for b in businesses):
                            businesses.append({
                                'maps_url': href,
                                'business_name': aria_label
                            })
                except Exception:
                    continue
            
            if len(businesses) == last_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_count = len(businesses)
            
            # Scroll the feed div
            feed = await self.page.query_selector('[role="feed"]')
            if feed:
                await feed.evaluate('el => el.scrollTop = el.scrollHeight')
                await self.page.wait_for_timeout(2000)
            else:
                # Fallback: Body scroll
                await self.page.keyboard.press("PageDown")
                await self.page.wait_for_timeout(1000)
        
        action_logger.info(f"Found {len(businesses)} potential leads in {location}. Extracting details...")
        
        for i, biz in enumerate(businesses):
            if stop_check and stop_check():
                break
            
            try:
                res = await self._extract_business_details(biz, query, location)
                if res == "discovered":
                    discovered += 1
                elif res == "skipped":
                    skipped += 1
                else:
                    errors.append(res)
                
                await self._async_random_delay()
                
            except Exception as e:
                errors.append(f"Error processing {biz.get('business_name')}: {e}")

        return {"discovered": discovered, "skipped": skipped, "errors": errors}
    
    async def _extract_business_details(
        self,
        biz: Dict,
        category: str,
        location: str
    ) -> str:
        """
        Extract full details for a business.
        Returns: "discovered", "skipped", or error message
        """
        maps_url = biz.get('maps_url', '')
        business_name = biz.get('business_name', '')
        
        # Check for duplicates (DB is async now)
        if await self.db.lead_exists_by_maps_url(maps_url):
            return "skipped"
        
        if await self.db.lead_exists_by_business_location(business_name, location):
            return "skipped"
        
        # Navigate to business page
        try:
            await self.page.goto(maps_url, wait_until='domcontentloaded', timeout=30000)
            await self.page.wait_for_timeout(2000)
        except Exception as e:
            # Fallback: create basic lead
            lead_data = {
                "business_name": business_name,
                "category": category,
                "location": location,
                "maps_url": maps_url,
                "website_url": "",
                "email": "",
                "discovery_source": "maps",
                "discovery_confidence": "low",
                "tag": "no_website",
                "review_status": "pending",
                "outreach_status": "not_sent",
                "discovered_at": datetime.now().isoformat()
            }
            try:
                await self.db.add_lead(lead_data)
                return "discovered"
            except Exception as db_e:
                return f"DB insert failed: {str(db_e)}"
        
        # Extract details
        website_url = ""
        address = ""
        
        try:
            # Try to find website link
            # Look for new data-item-id="authority" or just common link patterns
            website_buttons = await self.page.query_selector_all('a[data-item-id="authority"]')
            if website_buttons:
                website_url = await website_buttons[0].get_attribute('href') or ""
            
            if not website_url:
                # Look for link with 'Website' text or globe icon
                # Very heuristic.
                candidates = await self.page.query_selector_all('a[href^="http"]')
                for c in candidates:
                    txt = await c.inner_text()
                    href = await c.get_attribute('href')
                    if href and "google.com" not in href and ("website" in txt.lower() or len(txt) < 30):
                         # likely the website
                         website_url = href
                         break

            # Address
            address_elem = await self.page.query_selector('[data-item-id="address"]')
            if address_elem:
                address = await address_elem.inner_text()
            else:
                # fallback
                 addr_bs = await self.page.query_selector_all('button[data-item-id^="address"]')
                 if addr_bs:
                     address = await addr_bs[0].inner_text()
        
        except Exception as e:
             action_logger.warning(f"Detail extraction issue: {e}")
        
        tag = "no_website" if not website_url else "unknown"
        confidence = "high" if website_url or address else "medium"
        
        lead_data = {
            "business_name": business_name,
            "category": category,
            "location": address or location,
            "maps_url": maps_url,
            "website_url": website_url,
            "email": "",
            "discovery_source": "maps",
            "discovery_confidence": confidence,
            "tag": tag,
            "review_status": "pending", 
            "outreach_status": "not_sent",
            "discovered_at": datetime.now().isoformat()
        }
        
        try:
            await self.db.add_lead(lead_data)
            
            # Log specific success
            action_logger.log_action(
                lead_id=None,
                module_name="hunter",
                action="discover_one",
                result="success",
                details={"business": business_name, "has_website": bool(website_url)}
            )
            return "discovered"
        except Exception as e:
            return f"DB insert failed: {str(e)}"
    
    def discover_sync(self, *args, **kwargs):
        """No longer supported. Use async."""
        raise NotImplementedError("Use discover_from_maps (async) instead")
