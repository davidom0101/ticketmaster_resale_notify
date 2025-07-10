"""Command-line interface for Ticketmaster Resale Notifier."""
import argparse
import asyncio
import logging
import sys
from typing import List, Optional

from ticketmaster_resale_notify.app import TicketMonitor, create_default_config, load_config
from ticketmaster_resale_notify.models import AppConfig

def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.
    
    Args:
        args: List of command line arguments. If None, uses sys.argv[1:].
        
    Returns:
        Parsed arguments.
    """
    # Load default config to get default values
    default_config = create_default_config()
    
    parser = argparse.ArgumentParser(
        description="Monitor Ticketmaster for resale tickets and get notified when available.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Event configuration
    event_group = parser.add_argument_group('Event Configuration')
    event_group.add_argument(
        '--event-url',
        type=str,
        action='append',
        help='URL of the Ticketmaster event page to monitor (can be specified multiple times)',
    )
    
    # Notification configuration
    notification_group = parser.add_argument_group('Notification Configuration')
    notification_group.add_argument(
        '--ntfy-topic',
        type=str,
        help='ntfy.sh topic for notifications',
    )
    notification_group.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='maximum number of retries for failed operations',
    )
    notification_group.add_argument(
        '--retry-delay',
        type=int,
        default=5,
        help='initial delay between retries in seconds',
    )
    
    # Check interval configuration
    interval_group = parser.add_argument_group('Check Interval')
    interval_group.add_argument(
        '--min-interval',
        type=float,
        default=default_config.check_interval[0],
        help='Minimum interval between checks in minutes',
    )
    interval_group.add_argument(
        '--max-interval',
        type=float,
        default=default_config.check_interval[1],
        help='Maximum interval between checks in minutes',
    )
    
    # Browser configuration
    browser_group = parser.add_argument_group('Browser Configuration')
    browser_group.add_argument(
        '--headless',
        action='store_true',
        default=default_config.scraper.headless,
        help='Run browser in headless mode',
    )
    browser_group.add_argument(
        '--no-headless',
        dest='headless',
        action='store_false',
        help='Run browser with GUI',
    )
    browser_group.add_argument(
        '--browser-timeout',
        type=int,
        default=default_config.browser_timeout,
        help='Seconds to keep browser open after finding tickets',
    )
    
    # Logging configuration
    log_group = parser.add_argument_group('Logging')
    log_group.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default=default_config.log_level,
        help='Logging level',
    )
    log_group.add_argument(
        '--verbose', '-v',
        action='store_const',
        const='DEBUG',
        dest='log_level',
        help='Enable verbose output (same as --log-level DEBUG)',
    )
    
    # Version and info
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0',
        help='show version and exit',
    )
    
    if args is None:
        args = sys.argv[1:]
    return parser.parse_args(args)

def create_config_from_args(args: argparse.Namespace) -> AppConfig:
    """Create a configuration from command line arguments.
    
    Args:
        args: Parsed command line arguments.
        
    Returns:
        AppConfig: The application configuration.
    """
    # Start with default config
    config = create_default_config()
    
    # Update with command line arguments
    if args.event_url:
        config.event_urls = args.event_url
    
    # Update notification settings
    if hasattr(args, 'ntfy_topic') and args.ntfy_topic:
        config.notification.topic = args.ntfy_topic
        config.notification.enabled = True
    
    # Update check interval
    if hasattr(args, 'min_interval') and hasattr(args, 'max_interval'):
        config.check_interval = (args.min_interval, args.max_interval)
    
    # Update browser settings
    if hasattr(args, 'headless') and args.headless is not None:
        config.scraper.headless = args.headless
    
    if hasattr(args, 'browser_timeout') and args.browser_timeout is not None:
        config.browser_timeout = args.browser_timeout
    
    # Update logging
    if hasattr(args, 'log_level') and args.log_level is not None:
        config.log_level = args.log_level
    
    # Update retry settings
    if hasattr(args, 'max_retries') and args.max_retries is not None:
        config.max_retries = args.max_retries
        config.notification.retry_attempts = args.max_retries
    
    if hasattr(args, 'retry_delay') and args.retry_delay is not None:
        config.notification.retry_delay = args.retry_delay
    
    return config

def configure_logging(level: str = 'INFO') -> None:
    """Configure logging for the application.
    
    Args:
        level: Logging level as a string (e.g., 'INFO', 'DEBUG').
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    # Set log level for Playwright to WARNING to reduce noise
    logging.getLogger('playwright').setLevel(logging.WARNING)

def print_config(config: AppConfig) -> None:
    """Print the current configuration."""
    print("\n=== Ticketmaster Resale Notifier ===")
    print("\nEvent URLs:")
    for url in config.event_urls:
        print(f"  - {url}")
    
    print("\nCheck Interval:")
    print(f"  {config.check_interval[0]:.1f}-{config.check_interval[1]:.1f} minutes")
    
    print("\nBrowser Configuration:")
    print(f"  Headless: {'enabled' if config.scraper.headless else 'disabled'}")
    print(f"  Browser Timeout: {config.browser_timeout} seconds")
    
    print("\nNotification Configuration:")
    if config.notification.topic:
        print(f"  ntfy.sh Topic: {config.notification.topic}")
    else:
        print("  Notifications: Disabled (no topic specified)")
    
    print(f"\nLog Level: {config.log_level}")
    print("=" * 32 + "\n")

async def async_main() -> None:
    """Async entry point for the CLI."""
    # Parse command line arguments
    args = parse_args()
    
    # Load configuration from environment variables first
    config = load_config()
    
    # Override with command line arguments if provided
    cli_config = create_config_from_args(args)
    
    # Update config with CLI values (only if they were explicitly provided)
    if args.event_url:
        config.event_urls = cli_config.event_urls
    
    if args.ntfy_topic:
        config.notification.topic = cli_config.notification.topic
    
    import sys
    # Only override headless if explicitly set in CLI
    if '--headless' in sys.argv or '--no-headless' in sys.argv:
        config.scraper.headless = cli_config.scraper.headless
    
    if args.browser_timeout:
        config.browser_timeout = cli_config.browser_timeout
    
    if args.max_retries:
        config.max_retries = cli_config.max_retries
        config.notification.retry_attempts = cli_config.max_retries
    
    if args.retry_delay:
        config.notification.retry_delay = cli_config.notification.retry_delay
    
    if args.log_level:
        config.log_level = cli_config.log_level
    
    # Configure logging
    configure_logging(level=config.log_level)
    logger = logging.getLogger(__name__)
    
    # Check if we have any event URLs to monitor
    if not config.event_urls:
        logger.error("❌ No event URLs provided. Please set TICKETMASTER_URL in .env or use --event-url")
        return 1
    
    try:
        # Print configuration
        print_config(config)
        
        # Create and run the monitor
        monitor = TicketMonitor(config)
        await monitor.run()
        
    except KeyboardInterrupt:
        logger.info("\n👋 Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0

def main() -> int:
    """Main entry point for CLI."""
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user")
        return 0

if __name__ == "__main__":
    sys.exit(main())
