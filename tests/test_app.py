"""Tests for the main application module."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from ticketmaster_resale_notify.models import AppConfig, Event, Ticket, ScraperConfig, NotificationConfig
from ticketmaster_resale_notify.app import TicketMonitor, load_config, create_default_config


class TestTicketMonitor:
    """Tests for the TicketMonitor class."""
    
    @pytest.fixture
    def config(self):
        """Create a test AppConfig."""
        return AppConfig(
            event_urls=["https://example.com/event/1"],
            check_interval=(1, 2),  # Shorter for testing
            browser_timeout=60,
            max_retries=2,
            log_level="INFO",
            scraper=ScraperConfig(),
            notification=NotificationConfig()
        )
    
    @pytest.fixture
    def monitor(self, config):
        """Create a TicketMonitor instance for testing."""
        return TicketMonitor(config)
    
    @pytest.mark.asyncio
    async def test_run_checks_events(self, monitor, config):
        """Test that run checks all events in the config."""
        # Setup mocks
        monitor.check_event = AsyncMock()
        monitor.shutdown_event.is_set = MagicMock(side_effect=[False, False, True])  # Run twice then stop
        
        # Call run
        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.1)  # Let the task start
        monitor.shutdown_event.set()  # Signal shutdown
        await task  # Wait for task to complete
        
        # Assert check_event was called for each URL
        assert monitor.check_event.await_count == len(config.event_urls) * 2  # Called twice
    
    @pytest.mark.asyncio
    async def test_check_event_success(self, monitor, config):
        """Test successful event checking."""
        # Setup mocks
        event_url = config.event_urls[0]
        mock_scraper = AsyncMock()
        
        # Mock event and tickets
        mock_event = Event(url=event_url, name="Test Event")
        mock_ticket = Ticket(event=mock_event, section="A", price=99.99, is_verified_resale=True)
        
        # Setup scraper methods
        mock_scraper.get_event_info.return_value = mock_event
        mock_scraper.check_for_resale_tickets.return_value = [mock_ticket]
        
        # Patch TicketScraper to return our mock
        with patch('ticketmaster_resale_notify.app.TicketScraper', return_value=mock_scraper) as mock_scraper_cls:
            # Patch notification manager
            with patch.object(monitor.notification_manager, 'send_notification') as mock_send:
                # Call check_event
                await monitor.check_event(event_url)
                
                # Assert scraper was used correctly
                mock_scraper_cls.assert_called_once()
                mock_scraper.get_event_info.assert_awaited_once_with(event_url)
                mock_scraper.check_for_resale_tickets.assert_awaited_once_with(event_url)
                
                # Assert notification was sent
                mock_send.assert_awaited_once()
                args, kwargs = mock_send.await_args
                assert "resale ticket" in args[0]  # Title
                assert "Test Event" in args[1]     # Message
    
    @pytest.mark.asyncio
    async def test_check_event_no_tickets(self, monitor, config):
        """Test event checking when no tickets are found."""
        # Setup mocks
        event_url = config.event_urls[0]
        mock_scraper = AsyncMock()
        
        # Mock event with no tickets
        mock_event = Event(url=event_url, name="Test Event")
        mock_scraper.get_event_info.return_value = mock_event
        mock_scraper.check_for_resale_tickets.return_value = []
        
        # Patch TicketScraper
        with patch('ticketmaster_resale_notify.app.TicketScraper', return_value=mock_scraper):
            # Patch notification manager
            with patch.object(monitor.notification_manager, 'send_notification') as mock_send:
                # Call check_event
                await monitor.check_event(event_url)
                
                # Assert no notification was sent
                mock_send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_resale_tickets_found(self, monitor):
        """Test handling of found resale tickets."""
        # Create test event and tickets
        event = Event(url="https://example.com/event/1", name="Test Event")
        tickets = [
            Ticket(event=event, section="A", row="10", price=99.99, is_verified_resale=True),
            Ticket(event=event, section="B", row="5", price=149.99, is_verified_resale=True)
        ]
        
        # Patch notification manager
        with patch.object(monitor.notification_manager, 'send_notification') as mock_send:
            # Call _handle_resale_tickets_found
            await monitor._handle_resale_tickets_found(event, tickets)
            
            # Assert notification was sent with correct details
            mock_send.assert_awaited_once()
            args, kwargs = mock_send.await_args
            
            # Check notification content
            message = args[1]
            assert "2 resale ticket(s)" in message
            assert "A - €99.99" in message
            assert "B - €150.00" in message  # Price is formatted
            assert "https://example.com/event/1" in message
    
    @pytest.mark.asyncio
    async def test_wait_until_next_check(self, monitor):
        """Test the wait until next check logic."""
        # Set a fixed check interval for testing
        monitor.config.check_interval = (0.1, 0.1)  # 0.1 minutes = 6 seconds
        
        # Record start time
        start_time = asyncio.get_event_loop().time()
        
        # Call _wait_until_next_check with a short timeout
        monitor.shutdown_event.is_set = MagicMock(return_value=False)
        
        # This should wait for approximately 6 seconds
        with patch('asyncio.wait_for') as mock_wait_for:
            await monitor._wait_until_next_check()
            
            # Assert wait_for was called with approximately 6 seconds
            args, _ = mock_wait_for.call_args
            assert 5.9 <= args[1] <= 6.1  # Allow small timing variance


class TestConfigLoading:
    """Tests for configuration loading."""
    
    def test_create_default_config(self):
        """Test creation of default config."""
        config = create_default_config()
        
        assert isinstance(config, AppConfig)
        assert config.event_urls == []
        assert config.check_interval == (8.0, 12.0)
        assert config.browser_timeout == 360
        assert config.max_retries == 3
        assert config.log_level == "INFO"
    
    @patch('os.getenv')
    def test_load_config_defaults(self, mock_getenv):
        """Test loading config with defaults."""
        # Setup mock environment
        mock_getenv.return_value = None
        
        # Load config
        config = load_config()
        
        # Assert defaults are used
        assert config.event_urls == []
        assert config.check_interval == (8.0, 12.0)
    
    @patch('os.getenv')
    def test_load_config_from_env(self, mock_getenv):
        """Test loading config from environment variables."""
        # Setup mock environment
        mock_getenv.side_effect = lambda k, d=None: {
            'TICKETMASTER_URL': 'https://example.com/event/1,https://example.com/event/2',
            'NTFY_TOPIC': 'test-topic',
            'HEADLESS': 'true',
            'CHECK_INTERVAL_MIN': '5,10',
            'BROWSER_TIMEOUT': '120',
            'MAX_RETRIES': '5',
            'LOG_LEVEL': 'DEBUG'
        }.get(k, d)
        
        # Load config
        config = load_config()
        
        # Assert values were loaded from env
        assert config.event_urls == [
            'https://example.com/event/1',
            'https://example.com/event/2'
        ]
        assert config.check_interval == (5.0, 10.0)
        assert config.browser_timeout == 120
        assert config.max_retries == 5
        assert config.log_level == "DEBUG"
        assert config.scraper.headless is True
        assert config.notification.topic == "test-topic"
