"""Anti-detection measures for web scraping with rotating user agents and stealth techniques."""

import random
from typing import Dict, Any, List


class AntiDetectionManager:
    """Manages anti-detection measures for web scraping."""
    
    def __init__(self):
        self.user_agents = self._get_user_agents()
        self.viewport_sizes = self._get_viewport_sizes()
        self.languages = ["en-US", "en-GB", "en-CA", "en-AU"]
        self.timezones = ["America/New_York", "America/Los_Angeles", "America/Chicago", "Europe/London"]
    
    def _get_user_agents(self) -> List[str]:
        """Get list of realistic user agents."""
        return [
            # Chrome on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            
            # Chrome on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            
            # Firefox on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            
            # Firefox on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            
            # Safari on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
            
            # Edge on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        ]
    
    def _get_viewport_sizes(self) -> List[tuple]:
        """Get list of common viewport sizes."""
        return [
            (1920, 1080),  # Full HD
            (1366, 768),   # Common laptop
            (1536, 864),   # 1.5x scaling
            (1440, 900),   # MacBook Air
            (1280, 720),   # HD
            (1600, 900),   # 16:9 widescreen
            (1920, 1200),  # 16:10 widescreen
        ]
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(self.user_agents)
    
    def get_random_viewport(self) -> tuple:
        """Get a random viewport size."""
        return random.choice(self.viewport_sizes)
    
    def get_browser_config(self) -> Dict[str, Any]:
        """Get browser launch configuration with anti-detection."""
        return {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--user-agent=" + self.get_random_user_agent()
            ]
        }
    
    def get_context_config(self) -> Dict[str, Any]:
        """Get browser context configuration."""
        viewport = self.get_random_viewport()
        
        return {
            "viewport": {"width": viewport[0], "height": viewport[1]},
            "locale": random.choice(self.languages),
            "timezone_id": random.choice(self.timezones),
            "permissions": ["geolocation"],
            "geolocation": {
                "latitude": 40.7128 + random.uniform(-0.1, 0.1),  # NYC area
                "longitude": -74.0060 + random.uniform(-0.1, 0.1)
            },
            "user_agent": self.get_random_user_agent(),
            "java_script_enabled": True,
            "bypass_csp": True,
            "ignore_https_errors": True
        }
    
    def get_random_headers(self) -> Dict[str, str]:
        """Get random HTTP headers."""
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": f"{random.choice(self.languages)},en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
    
    def get_stealth_script(self) -> str:
        """Get JavaScript to inject for stealth browsing."""
        return """
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        
        // Mock plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        
        // Mock languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        
        // Mock permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Mock chrome runtime
        if (!window.chrome) {
            window.chrome = {};
        }
        if (!window.chrome.runtime) {
            window.chrome.runtime = {};
        }
        
        // Hide automation indicators
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        
        // Override toString methods
        const originalToString = Function.prototype.toString;
        Function.prototype.toString = function() {
            if (this === window.navigator.webdriver) {
                return 'function webdriver() { [native code] }';
            }
            return originalToString.call(this);
        };
        
        // Mock screen properties
        Object.defineProperty(screen, 'availTop', { get: () => 0 });
        Object.defineProperty(screen, 'availLeft', { get: () => 0 });
        
        // Add realistic mouse movements
        let mouseX = Math.random() * window.innerWidth;
        let mouseY = Math.random() * window.innerHeight;
        
        setInterval(() => {
            mouseX += (Math.random() - 0.5) * 10;
            mouseY += (Math.random() - 0.5) * 10;
            mouseX = Math.max(0, Math.min(window.innerWidth, mouseX));
            mouseY = Math.max(0, Math.min(window.innerHeight, mouseY));
            
            document.dispatchEvent(new MouseEvent('mousemove', {
                clientX: mouseX,
                clientY: mouseY
            }));
        }, 1000 + Math.random() * 2000);
        
        // Random scrolling
        setInterval(() => {
            if (Math.random() < 0.1) {
                window.scrollBy(0, (Math.random() - 0.5) * 100);
            }
        }, 5000 + Math.random() * 10000);
        """
    
    def get_random_delay_range(self) -> tuple:
        """Get random delay range for human-like behavior."""
        base_delay = random.uniform(1.0, 3.0)
        return (base_delay, base_delay + random.uniform(0.5, 2.0))
    
    def get_scroll_behavior(self) -> Dict[str, Any]:
        """Get random scroll behavior parameters."""
        return {
            "scroll_pause_min": random.uniform(1.0, 2.5),
            "scroll_pause_max": random.uniform(2.5, 4.0),
            "scroll_distance_min": random.randint(200, 400),
            "scroll_distance_max": random.randint(400, 800),
            "scroll_speed": random.uniform(0.5, 1.5)
        }
    
    def should_use_proxy(self) -> bool:
        """Determine if proxy should be used (placeholder for future proxy rotation)."""
        # For now, return False. In production, this could check:
        # - Request count
        # - Time since last request
        # - Detection indicators
        return False
    
    def get_proxy_config(self) -> Dict[str, Any]:
        """Get proxy configuration (placeholder for future implementation)."""
        # This would return proxy settings when proxy rotation is implemented
        return {}
    
    def detect_blocking_indicators(self, page_content: str, page_title: str, url: str) -> List[str]:
        """Detect if the page indicates we're being blocked."""
        indicators = []
        
        content_lower = page_content.lower()
        title_lower = page_title.lower()
        url_lower = url.lower()
        
        # Common blocking indicators
        blocking_terms = [
            "captcha", "recaptcha", "blocked", "unusual traffic",
            "verify you are human", "robot", "automated", "bot",
            "access denied", "forbidden", "rate limit", "too many requests",
            "suspicious activity", "security check", "verification required"
        ]
        
        for term in blocking_terms:
            if (term in content_lower or 
                term in title_lower or 
                term in url_lower):
                indicators.append(term)
        
        # Check for redirect to blocking pages
        blocking_urls = [
            "google.com/sorry", "captcha", "blocked", "denied"
        ]
        
        for blocking_url in blocking_urls:
            if blocking_url in url_lower:
                indicators.append(f"blocked_url:{blocking_url}")
        
        return indicators
    
    def get_recovery_strategies(self) -> List[str]:
        """Get list of recovery strategies when blocking is detected."""
        return [
            "change_user_agent",
            "change_viewport",
            "add_delay",
            "clear_cookies",
            "restart_browser",
            "use_proxy",
            "fallback_method"
        ]
    
    def calculate_request_delay(self, last_request_time: float, base_delay: float = 2.0) -> float:
        """Calculate delay before next request to avoid rate limiting."""
        import time
        
        elapsed = time.time() - last_request_time
        min_delay = base_delay + random.uniform(0.5, 1.5)
        
        if elapsed < min_delay:
            return min_delay - elapsed + random.uniform(0.1, 0.5)
        
        return random.uniform(0.1, 0.5)  # Small random delay even if enough time passed