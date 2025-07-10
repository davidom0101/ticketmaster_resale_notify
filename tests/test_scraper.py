"""Tests for the scraper module."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ticketmaster_resale_notify.models import ScraperConfig, Event, Ticket
from ticketmaster_resale_notify.scraper import TicketScraper


class TestTicketScraper:
    """Tests for the TicketScraper class."""
    
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
    def event_url(self):
        """Return a test event URL."""
        return "https://www.ticketmaster.com/event/1A0056D9A5E43E3F"
    
    @pytest.fixture
    async def scraper(self, config):
        """Create a TicketScraper instance for testing."""
        async with TicketScraper(config) as scraper:
            scraper.browser_manager = AsyncMock()
            scraper.browser_manager.page = AsyncMock()
            yield scraper
    
    @pytest.mark.asyncio
    async def test_get_event_info_success(self, scraper, event_url):
        """Test successful event info retrieval."""
        # Setup mocks
        mock_page = scraper.browser_manager.page
        mock_page.query_selector.side_effect = [
            MagicMock(text_content=AsyncMock(return_value="Test Event")),  # h1
            MagicMock(text_content=AsyncMock(return_value="Dec 31, 2023")),  # date
            MagicMock(text_content=AsyncMock(return_value="Test Venue"))   # venue
        ]
        
        # Call get_event_info
        event = await scraper.get_event_info(event_url)
        
        # Assert event was created with correct data
        assert event is not None
        assert event.url == event_url
        assert event.name == "Test Event"
        assert event.venue == "Test Venue"
        
        # Assert navigation and cookie handling were called
        scraper.browser_manager.navigate.assert_awaited_once_with(event_url, "domcontentloaded")
        scraper.browser_manager.handle_cookie_consent.assert_awaited_once()
    
    @pytest.mark.asyncode
    async def test_find_tickets_click_success(self, scraper, event_url):
        """Test successful ticket finding with button click."""
        # Setup mocks
        mock_browser = scraper.browser_manager
        mock_page = mock_browser.page
        
        # Mock button click and ticket elements
        mock_browser._click_find_tickets = AsyncMock(return_value=True)
        mock_ticket = MagicMock()
        mock_page.query_selector_all.return_value = [mock_ticket]
        
        # Mock ticket parsing
        expected_ticket = Ticket(
            event=Event(url=event_url),
            section="A",
            price=99.99,
            is_verified_resale=True
        )
        scraper._parse_ticket_element = AsyncMock(return_value=expected_ticket)
        
        # Call find_tickets
        tickets = await scraper.find_tickets(event_url)
        
        # Assert tickets were found and parsed
        assert len(tickets) == 1
        assert tickets[0] == expected_ticket
        
        # Assert button was clicked and page was waited on
        mock_browser._click_find_tickets.assert_awaited_once()
        asyncio.sleep.assert_awaited_once_with(5)  # Wait for tickets to load
    
    @pytest.mark.asyncio
    async def test_click_find_tickets_success(self, scraper):
        """Test successful finding and clicking of the find tickets button."""
        # Setup mocks
        mock_page = scraper.browser_manager.page
        mock_page.is_visible.side_effect = [False, True]  # First selector fails, second succeeds
        
        # Call _click_find_tickets
        result = await scraper._click_find_tickets()
        
        # Assert button was clicked
        assert result is True
        mock_page.click.assert_awaited_once()
        assert mock_page.is_visible.call_count == 2  # Tried two selectors
    
    @pytest.mark.asyncio
    async def test_parse_ticket_element(self, scraper, event_url):
        """Test parsing of a ticket element."""
        # Create a mock ticket element
        mock_element = AsyncMock()
        
        # Setup element query results
        mock_section = MagicMock()
        mock_section.text_content.return_value = "Section A"
        
        mock_price = MagicMock()
        mock_price.text_content.return_value = "€99.99"
        
        mock_element.query_selector.side_effect = [
            mock_section,  # section
            mock_price,    # price
            None,          # verified resale (not found)
        ]
        
        # Create a test event
        event = Event(url=event_url, name="Test Event")
        
        # Call _parse_ticket_element
        ticket = await scraper._parse_ticket_element(mock_element, event)
        
        # Assert ticket was parsed correctly
        assert ticket is not None
        assert ticket.event == event
        assert ticket.section == "Section A"
        assert ticket.price == 99.99
        assert ticket.is_verified_resale is False
    
    @pytest.mark.asyncio
    async def test_check_for_resale_tickets(self, scraper, event_url):
        """Test filtering for verified resale tickets."""
        # Create test tickets
        regular_ticket = Ticket(
            event=Event(url=event_url),
            section="A",
            price=99.99,
            is_verified_resale=False
        )
        
        resale_ticket = Ticket(
            event=Event(url=event_url),
            section="B",
            price=149.99,
            is_verified_resale=True
        )
        
        # Mock find_tickets to return both tickets
        scraper.find_tickets = AsyncMock(return_value=[regular_ticket, resale_ticket])
        
        # Call check_for_resale_tickets
        resale_tickets = await scraper.check_for_resale_tickets(event_url)
        
        # Assert only resale ticket was returned
        assert len(resale_tickets) == 1
        assert resale_tickets[0].is_verified_resale is True
        assert resale_tickets[0].section == "B"
