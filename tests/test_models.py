"""Tests for the models module."""
import pytest
from datetime import datetime

from ticketmaster_resale_notify.models import (
    Event, Ticket, Notification, ScraperConfig, NotificationConfig, AppConfig
)


def test_event_creation():
    """Test creating an Event instance."""
    event = Event(
        url="https://www.ticketmaster.com/event/1A0056D9A5E43E3F",
        name="Test Event",
        date=datetime(2023, 12, 31, 20, 0),
        venue="Test Venue"
    )
    
    assert event.url == "https://www.ticketmaster.com/event/1A0056D9A5E43E3F"
    assert event.name == "Test Event"
    assert event.date.year == 2023
    assert event.venue == "Test Venue"


def test_ticket_creation():
    """Test creating a Ticket instance."""
    event = Event(url="https://example.com/event/1")
    ticket = Ticket(
        event=event,
        section="A",
        row="10",
        price=99.99,
        quantity=2,
        is_verified_resale=True
    )
    
    assert ticket.event == event
    assert ticket.section == "A"
    assert ticket.row == "10"
    assert ticket.price == 99.99
    assert ticket.quantity == 2
    assert ticket.is_verified_resale is True


def test_notification_creation():
    """Test creating a Notification instance."""
    notification = Notification(
        title="Test Title",
        message="Test Message",
        priority=3,
        tags=["test", "alert"],
        actions=[{"action": "view", "label": "View", "url": "https://example.com"}]
    )
    
    assert notification.title == "Test Title"
    assert notification.message == "Test Message"
    assert notification.priority == 3
    assert "test" in notification.tags
    assert len(notification.actions) == 1


def test_scraper_config_defaults():
    """Test ScraperConfig default values."""
    config = ScraperConfig()
    
    assert config.headless is False
    assert config.timeout == 30
    assert "Mozilla/5.0" in config.user_agent
    assert config.viewport == (1280, 720)
    assert config.timezone == "Europe/Dublin"


def test_notification_config_defaults():
    """Test NotificationConfig default values."""
    config = NotificationConfig()
    
    assert config.enabled is True
    assert config.service == "ntfy"
    assert config.retry_attempts == 3
    assert config.retry_delay == 5


def test_app_config_defaults():
    """Test AppConfig default values."""
    config = AppConfig(event_urls=["https://example.com/event/1"])
    
    assert config.event_urls == ["https://example.com/event/1"]
    assert config.check_interval == (8.0, 12.0)
    assert config.browser_timeout == 360
    assert config.max_retries == 3
    assert config.log_level == "INFO"
    assert isinstance(config.scraper, ScraperConfig)
    assert isinstance(config.notification, NotificationConfig)
