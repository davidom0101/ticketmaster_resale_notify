"""Tests for the browser module."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ticketmaster_resale_notify.models import ScraperConfig
from ticketmaster_resale_notify.browser import BrowserManager


class TestBrowserManager:
    """Tests for the BrowserManager class."""
    
    @pytest.fixture
    def config(self):
        """Create a test ScraperConfig."""
        return ScraperConfig(
            headless=True,
            timeout=10,
            user_agent="test-user-agent",
            viewport=(800, 600),
            timezone="UTC"
        )
    
    @pytest.fixture
    async def browser_manager(self, config):
        """Create a BrowserManager instance for testing."""
        manager = BrowserManager(config)
        # Mock the async context manager methods
        manager.__aenter__ = AsyncMock(return_value=manager)
        manager.__aexit__ = AsyncMock(return_value=None)
        return manager
    
    @pytest.mark.asyncio
    async def test_setup_creates_browser_and_context(self, config):
        """Test that setup creates a browser and context with correct settings."""
        with patch('playwright.async_api.async_playwright') as mock_playwright:
            # Setup mocks
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            
            mock_async_playwright = AsyncMock()
            mock_playwright.return_value = mock_async_playwright
            
            mock_async_playwright.start.return_value = mock_async_playwright
            mock_async_playwright.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page
            
            # Create and setup manager
            manager = BrowserManager(config)
            await manager.setup()
            
            # Assert browser was created with correct args
            mock_async_playwright.chromium.launch.assert_called_once_with(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )
            
            # Assert context was created with correct args
            mock_browser.new_context.assert_called_once()
            call_kwargs = mock_browser.new_context.call_args[1]
            assert call_kwargs["user_agent"] == "test-user-agent"
            assert call_kwargs["viewport"] == {'width': 800, 'height': 600}
            assert call_kwargs["timezone_id"] == "UTC"
            
            # Assert page was created and timeout set
            mock_context.new_page.assert_called_once()
            mock_page.set_default_timeout.assert_called_once_with(10000)  # 10s in ms
    
    @pytest.mark.asyncio
    async def test_cleanup_closes_resources(self, browser_manager):
        """Test that cleanup closes all resources properly."""
        # Setup mocks
        browser_manager.playwright = AsyncMock()
        browser_manager.browser = AsyncMock()
        browser_manager.context = AsyncMock()
        browser_manager.page = AsyncMock()
        
        # Call cleanup
        await browser_manager.cleanup()
        
        # Assert resources were closed
        browser_manager.page.close.assert_awaited_once()
        browser_manager.context.close.assert_awaited_once()
        browser_manager.browser.close.assert_awaited_once()
        browser_manager.playwright.stop.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_navigate_calls_page_goto(self, browser_manager):
        """Test that navigate calls page.goto with correct arguments."""
        # Setup mocks
        mock_page = AsyncMock()
        browser_manager.page = mock_page
        
        # Call navigate
        url = "https://example.com"
        await browser_manager.navigate(url, "load")
        
        # Assert page.goto was called with correct args
        mock_page.goto.assert_awaited_once_with(url, wait_until="load")
    
    @pytest.mark.asyncio
    async def test_handle_cookie_consent_clicks_button(self, browser_manager):
        """Test that handle_cookie_consent clicks the accept button if present."""
        # Setup mocks
        mock_page = AsyncMock()
        mock_button = AsyncMock()
        
        browser_manager.page = mock_page
        mock_page.get_by_role.return_value = mock_button
        mock_button.is_visible.return_value = True
        
        # Call handle_cookie_consent
        result = await browser_manager.handle_cookie_consent()
        
        # Assert button was clicked
        assert result is True
        mock_button.click.assert_awaited_once()
        mock_page.get_by_role.assert_called_once_with("button", name="Accept Cookies")
    
    @pytest.mark.asyncio
    async def test_handle_cookie_consent_no_button(self, browser_manager):
        """Test that handle_cookie_consent handles missing button gracefully."""
        # Setup mocks
        mock_page = AsyncMock()
        browser_manager.page = mock_page
        mock_page.get_by_role.side_effect = Exception("Button not found")
        
        # Call handle_cookie_consent
        result = await browser_manager.handle_cookie_consent()
        
        # Assert no button was found
        assert result is False
    
    @pytest.mark.asyncio
    async def test_wait_for_selector(self, browser_manager):
        """Test wait_for_selector calls page.wait_for_selector with correct args."""
        # Setup mocks
        mock_page = AsyncMock()
        browser_manager.page = mock_page
        
        # Call wait_for_selector with default args
        selector = ".test-selector"
        await browser_manager.wait_for_selector(selector)
        
        # Assert wait_for_selector was called with correct args
        mock_page.wait_for_selector.assert_awaited_once_with(
            selector,
            state="visible",
            timeout=10000  # 10s in ms (from config)
        )
    
    @pytest.mark.asyncio
    async def test_click_button(self, browser_manager):
        """Test click_button calls page.click with correct args."""
        # Setup mocks
        mock_page = AsyncMock()
        browser_manager.page = mock_page
        
        # Call click_button
        selector = "button.primary"
        await browser_manager.click_button(selector, timeout=5)
        
        # Assert click was called with correct args
        mock_page.click.assert_awaited_once_with(selector, timeout=5000)  # 5s in ms
