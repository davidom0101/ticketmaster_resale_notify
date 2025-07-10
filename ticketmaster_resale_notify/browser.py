"""
Browser management and page interactions for Ticketmaster.
"""
import asyncio
import logging
from typing import Optional, Tuple

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError
)

from .models import ScraperConfig

logger = logging.getLogger(__name__)

class BrowserManager:
    """Manages browser instances and page interactions."""
    
    def __init__(self, config: ScraperConfig):
        """Initialize with scraper configuration."""
        self.config = config
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
    
    async def setup(self) -> None:
        """Set up the browser and context."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.config.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent=self.config.user_agent,
            viewport={'width': self.config.viewport[0], 'height': self.config.viewport[1]},
            timezone_id=self.config.timezone,
            java_script_enabled=True,
            bypass_csp=True,
        )
        
        # Add stealth to avoid detection
        await self.context.add_init_script("""
        delete navigator.__proto__.webdriver;
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)
        
        self.page = await self.context.new_page()
        
        # Set default timeout
        self.page.set_default_timeout(self.config.timeout * 1000)  # Convert to ms
    
    async def cleanup(self) -> None:
        """Clean up browser resources."""
        if self.page and not self.page.is_closed():
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def navigate(self, url: str, wait_until: str = 'domcontentloaded', wait_after: int = 0) -> None:
        """Navigate to a URL.
        
        Args:
            url: The URL to navigate to
            wait_until: When to consider navigation succeeded ('load', 'domcontentloaded', 'networkidle')
            wait_after: Additional seconds to wait after page load (default: 0)
        """
        if not self.page:
            raise RuntimeError("Browser not initialized. Call setup() first.")
        
        logger.info(f"🌐 Navigating to {url}")
        await self.page.goto(url, wait_until=wait_until)
        
        # Wait additional time if specified (for initial page load)
        if wait_after > 0:
            logger.info(f"⏳ Waiting {wait_after} seconds for page to fully load...")
            await asyncio.sleep(wait_after)
    
    async def clear_storage(self) -> None:
        """Clear browser cookies and storage."""
        if not self.page:
            return
            
        try:
            # Clear cookies
            await self.page.context.clear_cookies()
            
            # Clear local storage and session storage
            await self.page.evaluate("""
                () => {
                    localStorage.clear();
                    sessionStorage.clear();
                }
            """)
            
            logger.info("✅ Cleared cookies and storage")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not clear browser storage: {e}")
    
    async def handle_cookie_consent(self) -> bool:
        """Handle cookie consent dialog if present."""
        if not self.page:
            return False
            
        logger.info("🔍 Checking for cookie consent prompt...")
        try:
            # Try different selectors for cookie consent button
            selectors = [
                'button:has-text("Accept Cookies")',
                'button:has-text("Accept All")',
                'button[id*="cookie" i]',
                'button[class*="cookie" i]',
                'button[data-testid*="cookie" i]'
            ]
            
            for selector in selectors:
                try:
                    button = self.page.locator(selector)
                    if await button.is_visible(timeout=2000):
                        logger.info(f"🖱 Clicking cookie consent button with selector: {selector}")
                        await button.click()
                        await asyncio.sleep(1)  # Wait for any animations
                        return True
                except Exception as e:
                    logger.debug(f"Cookie consent button not found with selector {selector}: {e}")
            
            logger.info("ℹ️ No cookie consent prompt found")
            return False
        
        except Exception as e:
            logger.warning(f"⚠️ Could not handle cookie consent: {e}")
            return False
    
    async def take_screenshot(self, path: str = "screenshot.png") -> None:
        """Take a screenshot of the current page."""
        if self.page:
            await self.page.screenshot(path=path)
            logger.debug(f"📸 Screenshot saved to {path}")
    
    async def wait_for_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: Optional[float] = None
    ) -> bool:
        """Wait for a selector to be present in the page."""
        if not self.page:
            return False
            
        try:
            await self.page.wait_for_selector(
                selector,
                state=state,
                timeout=(timeout or self.config.timeout) * 1000  # Convert to ms
            )
            return True
        except PlaywrightTimeoutError:
            logger.warning(f"Timeout waiting for selector: {selector}")
            return False
    
    async def click_button(self, selector: str, timeout: Optional[float] = None) -> bool:
        """Click a button by selector."""
        if not self.page:
            return False
            
        try:
            await self.page.click(selector, timeout=(timeout or self.config.timeout) * 1000)
            return True
        except Exception as e:
            logger.warning(f"Failed to click {selector}: {e}")
            return False
