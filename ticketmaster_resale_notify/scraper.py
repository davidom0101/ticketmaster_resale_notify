"""
Ticket scraping logic for Ticketmaster.
"""
import asyncio
import logging
import random
from datetime import datetime
from typing import List, Optional, Dict, Any

from playwright.async_api import Page

from .models import Event, Ticket, ScraperConfig
from .browser import BrowserManager

logger = logging.getLogger(__name__)

class TicketScraper:
    """Scrapes ticket information from Ticketmaster."""
    
    def __init__(self, config: ScraperConfig):
        """Initialize with scraper configuration."""
        self.config = config
        self.browser_manager: Optional[BrowserManager] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.browser_manager = BrowserManager(self.config)
        await self.browser_manager.setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser_manager:
            await self.browser_manager.cleanup()
    
    async def get_event_info(self, url: str) -> Optional[Event]:
        """Get event information from the event page."""
        if not self.browser_manager or not self.browser_manager.page:
            raise RuntimeError("Browser not initialized")
        
        page = self.browser_manager.page
        
        try:
            # Navigate to the event page
            await self.browser_manager.navigate(url)
            
            # Handle cookie consent if present
            await self.browser_manager.handle_cookie_consent()
            
            # Extract event information
            event = Event(url=url)
            
            # Try to get event name
            try:
                name_elem = await page.query_selector('h1')
                if name_elem:
                    event.name = await name_elem.text_content()
                    logger.info(f"Found event: {event.name}")
            except Exception as e:
                logger.warning(f"Could not extract event name: {e}")
            
            # Try to get event date and venue (these selectors are just examples)
            try:
                date_elem = await page.query_selector('div.event-date')
                if date_elem:
                    date_str = await date_elem.text_content()
                    # Parse date string to datetime (implementation needed)
                    # event.date = parse_date(date_str)
                    pass
                
                venue_elem = await page.query_selector('div.event-venue')
                if venue_elem:
                    event.venue = (await venue_elem.text_content() or '').strip()
            except Exception as e:
                logger.warning(f"Could not extract event date/venue: {e}")
            
            return event
            
        except Exception as e:
            logger.error(f"Error getting event info: {e}", exc_info=True)
            return None
    
    async def find_tickets(self, event_url: str) -> List[Ticket]:
        """Find available tickets for an event.
        
        Args:
            event_url: URL of the event page to scrape
            
        Returns:
            List of found Ticket objects
        """
        if not self.browser_manager or not self.browser_manager.page:
            logger.error("❌ Browser not initialized")
            return []
        
        page = self.browser_manager.page
        tickets: List[Ticket] = []
        event = None
        
        try:
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"🚀 STARTING NEW TICKET SEARCH - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 80)
            
            # 1. Clear cookies and storage first
            logger.info("\n🧹 CLEARING BROWSER STORAGE")
            await self.browser_manager.clear_storage()
            
            # 2. Navigate to the event page
            logger.info(f"\n🌐 NAVIGATING TO EVENT PAGE")
            logger.info(f"   URL: {event_url}")
            
            # 3. Initial page load with extended wait time (10-15 seconds)
            initial_wait = random.randint(10, 15)
            logger.info(f"⏳ Waiting {initial_wait} seconds for page to load...")
            await self.browser_manager.navigate(
                event_url, 
                wait_until='domcontentloaded',
                wait_after=initial_wait
            )
            
            # 4. Handle cookie consent if present (with delay)
            logger.info("\n🔍 CHECKING FOR COOKIE CONSENT")
            await asyncio.sleep(2)  # Wait for any cookie banners to appear
            await self.browser_manager.handle_cookie_consent()
            
            # Small delay after cookie consent
            await asyncio.sleep(2)
            
            # 5. Check for quantity stepper
            logger.info("\n🔍 CHECKING FOR QUANTITY STEPPER")
            quantity_stepper_clicked = await self._click_quantity_stepper()
            
            if quantity_stepper_clicked:
                # Small delay after clicking quantity stepper
                await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # 6. Look for the ticket selection button
            logger.info("\n🔍 LOOKING FOR TICKET SELECTION BUTTON")
            find_tickets_clicked = await self._click_find_tickets()
            
            if not find_tickets_clicked:
                logger.error("\n❌ ERROR: Could not find or click ticket selection button")
                logger.info("Trying to take a screenshot of the current page...")
                try:
                    await self.browser_manager.take_screenshot("ticket_button_not_found.png")
                    logger.info("Screenshot saved as 'ticket_button_not_found.png'")
                except Exception as e:
                    logger.error(f"Could not take screenshot: {e}")
                return tickets
            
            # 7. Wait for tickets to load (10-15 seconds)
            wait_time = random.randint(10, 15)
            logger.info(f"\n⏳ WAITING {wait_time} SECONDS FOR TICKETS TO LOAD")
            await asyncio.sleep(wait_time)
            
            # 8. Run simple resale ticket check first (user requested minimal selector logic)
            logger.info("\n🔍 RUNNING SIMPLE VERIFIED RESALE CHECK")
            simple_tickets = await self._simple_resale_check(page, event)
            if simple_tickets:
                logger.info(f"   ✅ Simple check found {len(simple_tickets)} verified resale ticket(s)")
                return simple_tickets
            logger.info("   ❌ Simple check did not find verified resale tickets – ending search early")
            return []
            # 9. Take a screenshot for debugging
            try:
                await self.browser_manager.take_screenshot("after_ticket_load.png")
            except Exception as e:
                logger.debug(f"Could not take screenshot: {e}")
            
            # 9. Check for ticket listings or no results messages
            logger.info("\n🔍 CHECKING FOR TICKET LISTINGS")
            try:
                await page.wait_for_selector(
                    'ul[data-testid="ticket-list"], '  # Main ticket list
                    'div[data-testid="ticket-item"], '  # Individual ticket item
                    'div.no-results, '  # No results
                    'div.error-message, '  # Error messages
                    'div[data-testid="no-tickets-available"], '  # No tickets
                    ':has-text("no tickets"), '  # Text-based
                    ':has-text("sold out"), '  # Sold out
                    ':has-text("unavailable"), '  # Unavailable
                    ':has-text("no matches")',  # No matches
                    timeout=15000  # 15 second timeout for the actual selector check
                )
            except Exception as e:
                logger.warning(f"   Could not find ticket listings or results: {e}")
            
            # 10. Check for "no tickets" messages first
            no_tickets_selectors = [
                'div.no-results',
                'div.error-message',
                'div[data-testid="no-tickets-available"]',
                ':has-text("no tickets")',
                ':has-text("sold out")',
                ':has-text("unavailable")',
                ':has-text("no matches")',
                ':has-text("No tickets available")',
                ':has-text("No tickets found")'
            ]
            
            for selector in no_tickets_selectors:
                try:
                    no_tickets = await page.query_selector(selector)
                    if no_tickets and await no_tickets.is_visible():
                        message = await no_tickets.text_content()
                        logger.warning(f"\n⚠️  TICKETS NOT AVAILABLE: {message.strip()}")
                        return []
                except Exception as e:
                    logger.debug(f"   Error checking {selector}: {e}")
            
            # 11. Look for ticket listings
            logger.info("\n🔍 SEARCHING FOR AVAILABLE TICKETS")
            
            # First try to find list items with role="button" (ticket elements)
            ticket_elements = await page.query_selector_all('li[role="button"]')
            
            if ticket_elements:
                logger.info(f"   Found {len(ticket_elements)} ticket elements with role='button'")
            else:
                # Fallback to other selectors if no elements found with role="button"
                ticket_selectors = [
                    'div[data-testid="ticket-item"]',
                    'div.ticket-item',
                    'div.ticket',
                    'div.offer'
                ]
                
                for selector in ticket_selectors:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        logger.info(f"   Found {len(elements)} elements with selector: {selector}")
                        ticket_elements = elements
                        break
            
            if not ticket_elements:
                logger.warning("   No ticket elements found with standard selectors")
                logger.info("   Taking screenshot of current page...")
                try:
                    await self.browser_manager.take_screenshot("no_ticket_elements_found.png")
                except Exception as e:
                    logger.error(f"   Could not take screenshot: {e}")
            
            # 12. Parse each ticket element
            logger.info(f"\n🔍 PARSING {len(ticket_elements)} TICKET LISTINGS")
            for i, element in enumerate(ticket_elements, 1):
                try:
                    logger.info(f"\n   --- TICKET #{i} ---")
                    ticket = await self._parse_ticket_element(element, event)
                    if ticket:
                        tickets.append(ticket)
                        logger.info(f"   ✅ ADDED: Section {ticket.section}" + 
                                  (f", Row {ticket.row}" if ticket.row else "") + 
                                  (f", Price: €{ticket.price:,.2f}" if ticket.price else ""))
                except Exception as e:
                    logger.warning(f"   ❌ Error parsing ticket #{i}: {e}")
                    logger.debug("", exc_info=True)
            
            logger.info("\n" + "=" * 80)
            logger.info(f"🏁 SEARCH COMPLETE - Found {len(tickets)} ticket(s)")
            logger.info("=" * 80 + "\n")
            
            return tickets
            
        except Exception as e:
            logger.error("\n❌ ERROR IN TICKET SEARCH PROCESS")
            logger.error(f"   Type: {type(e).__name__}")
            logger.error(f"   Message: {str(e)}")
            logger.error("\nStack trace:", exc_info=True)
            logger.info("\nTaking screenshot of error page...")
            try:
                await self.browser_manager.take_screenshot("error_occurred.png")
            except Exception as screenshot_error:
                logger.error(f"   Could not take screenshot: {screenshot_error}")
            
            return []
    
    async def _click_quantity_stepper(self) -> bool:
        """Click the quantity stepper if present."""
        if not self.browser_manager or not self.browser_manager.page:
            return False
            
        page = self.browser_manager.page
        
        try:
            logger.info("   🔍 Looking for quantity stepper...")
            # First try the specific selector that worked before
            quantity_stepper = page.locator('[data-testid="quantityStepper"]')
            if await quantity_stepper.count() > 0:
                logger.info("   🖱 Found quantity stepper using data-testid")
                await quantity_stepper.locator('button').first.click()
                logger.info("   ✅ Clicked quantity stepper")
                return True
                
            # Fallback to other selectors if the first one fails
            logger.info("   Trying alternative selectors for quantity stepper...")
            quantity_selectors = [
                'button[data-testid="quantity-stepper-increase-button"]',
                'button[aria-label="Increase quantity"]',
                'button.quantity-stepper-increase',
                'button.quantity-up',
                'button.plus',
                'button:has-text("+")'
            ]
            
            for selector in quantity_selectors:
                try:
                    logger.debug(f"   Checking for quantity stepper: {selector}")
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.info(f"   🖱 Found quantity stepper: {selector}")
                        await element.scroll_into_view_if_needed()
                        await asyncio.sleep(1)  # Small delay before clicking
                        await element.click()
                        logger.info("   ✅ Clicked quantity stepper")
                        return True
                except Exception as e:
                    logger.debug(f"   Could not click quantity stepper {selector}: {e}")
            
            logger.info("   ℹ️ No quantity stepper found")
            return False
            
        except Exception as e:
            logger.warning(f"   ❌ Error while handling quantity stepper: {e}")
            return False
    
    async def _click_find_tickets(self) -> bool:
        """Click the 'Find Tickets' button if present.
        
        Returns:
            bool: True if the button was found and clicked, False otherwise
        """
        if not self.browser_manager or not self.browser_manager.page:
            return False
            
        page = self.browser_manager.page
        
        # Enhanced selectors for finding ticket buttons with test IDs and common patterns first
        selectors = [
            # Test ID based selectors (most reliable)
            {'selector': 'button[data-testid="findTicketsBtn"]', 'name': 'findTicketsBtn testid'},
            {'selector': 'button[data-testid="find-tickets-button"]', 'name': 'find-tickets-button testid'},
            {'selector': 'button[data-testid="ticket-button"]', 'name': 'ticket-button testid'},
            
            # Text-based selectors
            {'selector': 'button:has-text("Find Tickets")', 'name': 'Find Tickets text'},
            {'selector': 'a:has-text("Find Tickets")', 'name': 'Find Tickets link'},
            {'selector': 'button:has-text("Find tickets")', 'name': 'Find tickets (lowercase)'},
            
            # Common button classes and attributes
            {'selector': 'button.primary', 'name': 'primary button class'},
            {'selector': 'button.primary:visible', 'name': 'visible primary button'},
            {'selector': 'button[data-tracking="find_tickets"]', 'name': 'find_tracks tracking'},
            
            # Fallback selectors
            {'selector': '.find-tickets-button', 'name': 'find-tickets-button class'},
            {'selector': 'button:has-text("Search")', 'name': 'Search button'},
            {'selector': 'button:has-text("Get Tickets")', 'name': 'Get Tickets button'},
            {'selector': 'button:has-text("Buy Tickets")', 'name': 'Buy Tickets button'},
            {'selector': 'button:has-text("Continue")', 'name': 'Continue button'},
            {'selector': 'button:has-text("Next")', 'name': 'Next button'},
            
            # Generic selectors (last resort)
            {'selector': 'button:has-text("ticket" i)', 'name': 'any ticket button (case-insensitive)'},
            {'selector': 'a:has-text("ticket" i)', 'name': 'any ticket link (case-insensitive)'}
        ]
        
        logger.info("🔍 Looking for ticket selection button...")
        
        for btn in selectors:
            selector = btn['selector']
            logger.info(f"  🔘 Trying {btn['name']} selector: {selector}")
            
            try:
                # Check if element is visible and clickable
                element = page.locator(selector)
                if not await element.is_visible(timeout=5000):  # Increased timeout for initial visibility check
                    logger.debug(f"  ❌ Button not visible with {btn['name']} selector")
                    continue
                
                logger.info(f"  ✅ Found button with {btn['name']} selector")
                
                # Scroll into view if needed
                logger.info("  🖱 Scrolling button into view...")
                await element.scroll_into_view_if_needed()
                
                # Add a small random delay between 3-4 seconds before clicking
                click_delay = random.uniform(3.0, 4.0)
                logger.info(f"  ⏳ Waiting {click_delay:.1f}s before clicking...")
                await asyncio.sleep(click_delay)
                
                # Click the button with a small delay to mimic human behavior
                logger.info(f"  🖱 Clicking button with {btn['name']} selector")
                await element.click(delay=random.randint(100, 300))  # Random delay between 100-300ms
                
                # Wait for the page to process the click (5-10 seconds max)
                wait_time = random.randint(5, 10)
                logger.info(f"  ⏳ Waiting {wait_time} seconds for tickets to load...")
                await asyncio.sleep(wait_time)
                
                return True
                
            except Exception as e:
                logger.debug(f"  ⚠️ Error with {btn['name']} selector: {e}")
                continue
        
        logger.warning("❌ Could not find any clickable ticket selection buttons")
        return False
    
    async def _parse_ticket_element(self, element, event: Event) -> Optional[Ticket]:
        """Detailed parsing (kept for fallback)"""

        """Parse a ticket element into a Ticket object."""
        try:
            # Common selectors for different parts of a ticket
            selectors = {
                'section': [
                    '[data-testid="ticket-section"]',
                    '.ticket-section',
                    '.ticket-listing-section',
                    '.section-details',
                    '.section',
                    'dl[class*="InlineList"] dd',  # Section is often in a definition list
                    'div[class*="SectionInfo"]'    # Sometimes in a section info div
                ],
                'price': [
                    'div[data-testid="ticket-price"]',
                    '.ticket-price',
                    '.price',
                    '.ticket-price-amount',
                    '.price-amount',
                    'span[class*="Price"]',
                    'div[class*="Price"]'
                ],
                'row': [
                    '[data-testid="ticket-row"]',
                    '.ticket-row',
                    '.row-details',
                    '.row',
                    '.ticket-listing-row',
                    'div[class*="RowInfo"]'  # Sometimes row is in a row info div
                ],
                'verified': [
                    'div[data-testid="ticketTypeInfo"]',  # Check for ticket type info container
                    'span:has-text("Verified Resale Ticket")',  # Direct text match
                    '.verified-resale',
                    '.resale-badge',
                    '.resale',
                    '.ticket-badge',
                    '.badge--resale',
                    '[data-testid="resale"]'
                ]
            }
            
            # Helper function to find first matching element
            async def find_first_match(keys):
                for key in keys:
                    elem = await element.query_selector(key)
                    if elem:
                        return elem
                return None
            
            # Extract section
            section_elem = await find_first_match(selectors['section'])
            if not section_elem:
                logger.debug("Could not find section element in ticket")
                return None
                
            section = (await section_elem.text_content() or '').strip()
            
            # Extract price
            price_elem = await find_first_match(selectors['price'])
            if not price_elem:
                logger.debug(f"Could not find price element in ticket for section: {section}")
                return None
                
            price_text = (await price_elem.text_content() or '').strip()
            
            # Parse price (handle different currency formats)
            price = None
            try:
                # Remove all non-numeric characters except decimal point
                price_str = ''.join(c for c in price_text if c.isdigit() or c in '.,')
                # Handle European format (1.234,56) vs US format (1,234.56)
                if ',' in price_str and '.' in price_str:
                    if price_str.find(',') < price_str.find('.'):  # European format
                        price_str = price_str.replace('.', '').replace(',', '.')
                    else:  # US format
                        price_str = price_str.replace(',', '')
                else:
                    price_str = price_str.replace(',', '.')
                
                price = float(price_str)
                logger.debug(f"Parsed price '{price_text}' as {price}")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Could not parse price '{price_text}': {e}")
            
            # Extract row if available
            row = None
            row_elem = await find_first_match(selectors['row'])
            if row_elem:
                row = (await row_elem.text_content() or '').strip()
            
            # Check if it's a verified resale ticket
            is_verified = False
            
            # Get all spans in the element and check for 'Verified Resale Ticket' text
            spans = await element.query_selector_all('span')
            for span in spans:
                try:
                    text = (await span.text_content() or '').strip()
                    if text == "Verified Resale Ticket":
                        logger.info(f"✅ Found verified resale ticket in section: {section}")
                        is_verified = True
                        break
                except Exception as e:
                    logger.debug(f"Error checking span for verified text: {e}")
            
            # If not found, check other selectors as fallback
            if not is_verified:
                is_verified = any(
                    await asyncio.gather(
                        *[element.query_selector(sel) is not None for sel in selectors['verified']]
                    )
                )
                if is_verified:
                    logger.info(f"✅ Found verified resale ticket (fallback) in section: {section}")
            
            return Ticket(
                event=event,
                section=section,
                row=row,
                price=price,
                is_verified_resale=is_verified,
                quantity=1  # Default quantity
            )
            
        except Exception as e:
            logger.error(f"Error parsing ticket element: {e}", exc_info=True)
            return None
    
    async def _simple_resale_check(self, page: Page, event: Optional[Event]) -> List[Ticket]:
        """User-requested minimal check for verified resale tickets.
        Looks only for li[role="button"] elements containing a span with text
        exactly equal to "Verified Resale Ticket". Returns basic Ticket objects.
        """
        tickets: List[Ticket] = []
        try:
            ticket_elements = await page.query_selector_all('li[role="button"]')
            for idx, li in enumerate(ticket_elements, 1):
                spans = await li.query_selector_all('span')
                for span in spans:
                    text = (await span.text_content() or '').strip()
                    if text == "Verified Resale Ticket":
                        # try to get section information
                        section_text = None
                        try:
                            dt_elements = await li.query_selector_all('dt')
                            for dt in dt_elements:
                                dt_text = (await dt.text_content() or '').strip()
                                if dt_text == "Section":
                                    dd_handle = await dt.evaluate_handle('el => el.nextElementSibling')
                                    if dd_handle:
                                        section_text = (await dd_handle.text_content() or '').strip()
                                    break
                        except Exception:
                            pass
                        tickets.append(
                            Ticket(
                                event=event,
                                section=section_text or "N/A",
                                row=None,
                                price=None,
                                is_verified_resale=True,
                                quantity=1,
                            )
                        )
                        break  # stop scanning spans for this li
        except Exception as e:
            logger.warning(f"Simple resale check error: {e}")
        return tickets

    async def check_for_resale_tickets(self, event_url: str) -> List[Ticket]:
        """Check for resale tickets for an event."""
        all_tickets = await self.find_tickets(event_url)
        return [t for t in all_tickets if t.is_verified_resale]
