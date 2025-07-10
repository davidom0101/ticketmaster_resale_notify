"""Data models and types for the Ticketmaster Resale Notifier."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any


@dataclass
class Event:
    """Represents a Ticketmaster event."""
    url: str
    name: Optional[str] = None
    date: Optional[datetime] = None
    venue: Optional[str] = None


@dataclass
class Ticket:
    """Represents a ticket listing."""
    event: Event
    section: str
    row: Optional[str] = None
    price: Optional[float] = None
    quantity: int = 1
    is_verified_resale: bool = False
    listing_url: Optional[str] = None


@dataclass
class Notification:
    """Represents a notification to be sent."""
    title: str
    message: str
    priority: int = 3  # 1=min, 3=default, 5=max
    tags: Optional[List[str]] = None
    actions: Optional[List[Dict[str, Any]]] = None


@dataclass
class ScraperConfig:
    """Configuration for the scraper."""
    headless: bool = False
    timeout: int = 30
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )
    viewport: Tuple[int, int] = (1280, 720)
    timezone: str = "Europe/Dublin"


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    enabled: bool = True
    service: str = "ntfy"  # 'ntfy', 'discord', 'email', etc.
    topic: Optional[str] = None
    webhook_url: Optional[str] = None
    email: Optional[str] = None
    retry_attempts: int = 3
    retry_delay: int = 5  # seconds


@dataclass
class AppConfig:
    """Main application configuration."""
    event_urls: List[str]
    check_interval: Tuple[float, float] = (8.0, 12.0)  # min, max in minutes
    browser_timeout: int = 360  # seconds
    max_retries: int = 3
    log_level: str = "INFO"
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
