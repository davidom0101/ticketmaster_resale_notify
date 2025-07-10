"""
Main application module for Ticketmaster Resale Notifier.
"""
import asyncio
import logging
import random
import signal
import sys
from datetime import datetime
from typing import List, Optional, Dict, Any

from .models import AppConfig, ScraperConfig, NotificationConfig, Event, Ticket
from .scraper import TicketScraper
from .notifications import create_notification_manager

logger = logging.getLogger(__name__)

class TicketMonitor:
    """Monitors Ticketmaster for resale tickets."""
    
    def __init__(self, config: AppConfig):
        """Initialize with application configuration."""
        self.config = config
        self.shutdown_event = asyncio.Event()
        self.notification_manager = create_notification_manager(config.notification)
        self.scraper_config = config.scraper
        self.check_count = 0
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signals gracefully."""
        logger.warning(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_event.set()
    
    async def run(self) -> None:
        """Run the ticket monitoring loop."""
        logger.info("🚀 Starting Ticketmaster Resale Notifier")
        
        # Check if we have any event URLs to monitor
        if not self.config.event_urls:
            logger.warning("⚠️ No event URLs provided. Use --event-url to specify events to monitor.")
            return
        
        logger.info(f"👀 Monitoring {len(self.config.event_urls)} event(s) for resale tickets")
        
        while not self.shutdown_event.is_set():
            self.check_count += 1
            start_time = datetime.now()
            
            logger.info(f"\n🔄 Starting check #{self.check_count} at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                # Check each event URL
                for event_url in self.config.event_urls:
                    if self.shutdown_event.is_set():
                        break
                    
                    await self.check_event(event_url)
                
                # Calculate next check time if not shutting down
                if not self.shutdown_event.is_set() and self.config.event_urls:
                    await self._wait_until_next_check()
            
            except asyncio.CancelledError:
                logger.info("Monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                if not self.shutdown_event.is_set():
                    # Wait a bit before retrying on error, but not too long
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(asyncio.sleep(60)),
                            timeout=60
                        )
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
        
        logger.info("✅ Ticket monitoring stopped")
    
    async def check_event(self, event_url: str) -> None:
        """Check a single event for resale tickets."""
        logger.info(f"🔍 Checking event: {event_url}")
        
        try:
            async with TicketScraper(self.scraper_config) as scraper:
                # Get event info
                event = await scraper.get_event_info(event_url)
                if not event:
                    logger.error(f"Could not get info for event: {event_url}")
                    return
                
                logger.info(f"🎟️ Event: {event.name or 'Unknown'}")
                if event.date:
                    logger.info(f"📅 Date: {event.date}")
                if event.venue:
                    logger.info(f"🏟️ Venue: {event.venue}")
                
                # Check for resale tickets
                resale_tickets = await scraper.check_for_resale_tickets(event_url)
                
                if resale_tickets:
                    await self._handle_resale_tickets_found(event, resale_tickets)
                else:
                    logger.info("❌ No resale tickets found")
        
        except Exception as e:
            logger.error(f"Error checking event {event_url}: {e}", exc_info=True)
    
    async def _handle_resale_tickets_found(self, event: Event, tickets: List[Ticket]) -> None:
        """Handle the case when resale tickets are found."""
        logger.warning(f"🎉 Found {len(tickets)} resale ticket(s)!")
        
        # Prepare notification message
        message_parts = [
            f"🎟️ {event.name or 'Event'} - {len(tickets)} resale ticket(s) found!"
        ]
        
        # Add ticket details
        for i, ticket in enumerate(tickets[:5], 1):  # Limit to first 5 tickets
            price = f"€{ticket.price:,.2f}" if ticket.price else "Price not available"
            message_parts.append(f"\n{i}. {ticket.section} - {price}")
            if ticket.row:
                message_parts.append(f" (Row {ticket.row})")
        
        if len(tickets) > 5:
            message_parts.append(f"\n... and {len(tickets) - 5} more")
        
        message_parts.append(f"\n\n🔗 {event.url}")
        
        # Send notification
        await self.notification_manager.send_notification(
            title="🎟️ Resale Tickets Available!",
            message="".join(message_parts),
            priority=4,  # High priority
            tags=["ticket", "warning"]
        )
        
        # Log to console
        logger.info("\n".join(message_parts))
    
    async def _wait_until_next_check(self) -> None:
        """Wait until the next check time, or until shutdown is requested."""
        min_interval, max_interval = self.config.check_interval
        wait_minutes = random.uniform(min_interval, max_interval)
        wait_seconds = wait_minutes * 60
        
        next_check = datetime.now().timestamp() + wait_seconds
        next_check_str = datetime.fromtimestamp(next_check).strftime('%H:%M:%S')
        
        logger.info(f"⏳ Next check at ~{next_check_str} (in {wait_minutes:.1f} minutes)")
        
        # Split the wait into smaller chunks to be more responsive to shutdown
        chunk_size = 10  # seconds
        chunks = int(wait_seconds // chunk_size)
        remainder = wait_seconds % chunk_size
        
        try:
            # Wait in chunks to be more responsive to shutdown
            for _ in range(chunks):
                if self.shutdown_event.is_set():
                    return
                await asyncio.sleep(chunk_size)
                
            # Wait for the remainder
            if remainder > 0 and not self.shutdown_event.is_set():
                await asyncio.sleep(remainder)
                
        except asyncio.CancelledError:
            logger.debug("Wait for next check was cancelled")
            raise


def create_default_config() -> AppConfig:
    """Create a default configuration."""
    return AppConfig(
        event_urls=[],
        check_interval=(8.0, 12.0),
        browser_timeout=360,
        max_retries=3,
        log_level="INFO",
        scraper=ScraperConfig(
            headless=False,
            timeout=30
        ),
        notification=NotificationConfig(
            enabled=True,
            service="ntfy",
            topic="ticketmaster_resale_notify"
        )
    )


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    import os
    from dotenv import load_dotenv
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Create config with defaults
    config = create_default_config()
    
    # Override with environment variables if set
    if os.getenv("TICKETMASTER_URL"):
        config.event_urls = [url.strip() for url in os.getenv("TICKETMASTER_URL").split(",")]
    
    if os.getenv("NTFY_TOPIC"):
        config.notification.topic = os.getenv("NTFY_TOPIC")
    
    if os.getenv("HEADLESS"):
        config.scraper.headless = os.getenv("HEADLESS").lower() == "true"
    
    if os.getenv("CHECK_INTERVAL_MIN"):
        try:
            min_val, max_val = map(float, os.getenv("CHECK_INTERVAL_MIN").split(","))
            config.check_interval = (min_val, max_val)
        except (ValueError, AttributeError):
            logger.warning("Invalid CHECK_INTERVAL_MIN format. Using default.")
    
    if os.getenv("BROWSER_TIMEOUT"):
        try:
            config.browser_timeout = int(os.getenv("BROWSER_TIMEOUT"))
        except (ValueError, TypeError):
            logger.warning("Invalid BROWSER_TIMEOUT. Using default.")
    
    if os.getenv("MAX_RETRIES"):
        try:
            config.max_retries = int(os.getenv("MAX_RETRIES"))
        except (ValueError, TypeError):
            logger.warning("Invalid MAX_RETRIES. Using default.")
    
    if os.getenv("LOG_LEVEL"):
        log_level = os.getenv("LOG_LEVEL").upper()
        if log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config.log_level = log_level
    
    return config


async def main() -> None:
    """Main entry point."""
    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Configure logging
    logging.basicConfig(
        level=config.log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('ticketmaster_scraper.log')
        ]
    )
    
    # Create and run the monitor
    monitor = TicketMonitor(config)
    await monitor.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
