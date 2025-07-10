"""Ticketmaster Resale Notifier package.

This package provides tools to monitor Ticketmaster for resale tickets
and send notifications when they become available.
"""

__version__ = "0.1.0"

# Import key components to make them available at the package level
from .app import main
from .models import AppConfig, Event, Ticket, ScraperConfig, NotificationConfig
from .notifications import NotificationManager, NtfyNotificationService
from .scraper import TicketScraper
from .browser import BrowserManager

__all__ = [
    'main',
    'AppConfig',
    'Event',
    'Ticket',
    'ScraperConfig',
    'NotificationConfig',
    'NotificationManager',
    'NtfyNotificationService',
    'TicketScraper',
    'BrowserManager',
]
