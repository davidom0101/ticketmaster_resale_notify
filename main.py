"""Ticketmaster Resale Notifier

Monitors Ticketmaster for resale tickets and sends notifications when available.
"""
import asyncio
import logging
import signal
import sys
from typing import Optional

def main() -> int:
    """Main entry point that runs the CLI with proper asyncio setup."""
    try:
        # Import here to avoid circular imports
        from ticketmaster_resale_notify.cli import async_main
        
        # Run the async main function
        return asyncio.run(async_main())
            
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
