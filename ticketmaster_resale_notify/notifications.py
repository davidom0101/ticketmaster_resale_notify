"""
Notification handling for the Ticketmaster Resale Notifier.
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any

import httpx
from pydantic import BaseModel, HttpUrl, Field

from .models import Notification, NotificationConfig

logger = logging.getLogger(__name__)

class NotificationService:
    """Base class for notification services."""
    
    def __init__(self, config: NotificationConfig):
        self.config = config
        self.retry_attempts = config.retry_attempts
        self.retry_delay = config.retry_delay
    
    async def send(self, notification: Notification) -> bool:
        """Send a notification with retry logic."""
        for attempt in range(1, self.retry_attempts + 1):
            try:
                return await self._send_impl(notification)
            except Exception as e:
                if attempt == self.retry_attempts:
                    logger.error(
                        f"Failed to send notification after {self.retry_attempts} attempts: {e}"
                    )
                    return False
                
                delay = self.retry_delay * attempt
                logger.warning(
                    f"Attempt {attempt}/{self.retry_attempts} failed. Retrying in {delay}s... Error: {e}"
                )
                await asyncio.sleep(delay)
        
        return False
    
    async def _send_impl(self, notification: Notification) -> bool:
        """Implementation of the notification sending logic."""
        raise NotImplementedError("Subclasses must implement this method")


class NtfyNotificationService(NotificationService):
    """Notification service for ntfy.sh."""
    
    def __init__(self, topic: str, **kwargs):
        super().__init__(**kwargs)
        self.topic = topic
        self.base_url = f"https://ntfy.sh/{self.topic}"
    
    async def _send_impl(self, notification: Notification) -> bool:
        """Send notification via ntfy.sh."""
        # Always use a fixed ASCII title to avoid header encoding issues
        headers = {
            "Title": "Ticketmaster Resale Ticket Available"
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.base_url,
                data=notification.message.encode("utf-8"),
                headers=headers
            )
            response.raise_for_status()
            return True


class NotificationManager:
    """Manages different notification services."""
    
    def __init__(self, config: NotificationConfig):
        self.config = config
        self.services: List[NotificationService] = []
        self._setup_services()
    
    def _setup_services(self) -> None:
        """Set up notification services based on config."""
        if not self.config.enabled:
            logger.warning("Notifications are disabled in config")
            return
        
        if self.config.service.lower() == "ntfy" and self.config.topic:
            self.services.append(NtfyNotificationService(
                topic=self.config.topic,
                config=self.config
            ))
        else:
            logger.warning(f"No valid notification service configured")
    
    async def send_notification(
        self,
        title: str,
        message: str,
        priority: int = 3,
        tags: Optional[List[str]] = None,
        actions: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send a notification using all available services."""
        if not self.services:
            logger.warning("No notification services configured")
            return False
        
        notification = Notification(
            title=title,
            message=message,
            priority=priority,
            tags=tags,
            actions=actions
        )
        
        results = await asyncio.gather(
            *(service.send(notification) for service in self.services),
            return_exceptions=True
        )
        
        # Log any failures
        for service, result in zip(self.services, results):
            if isinstance(result, Exception):
                logger.error(
                    f"Error sending notification via {service.__class__.__name__}: {result}",
                    exc_info=result
                )
        
        return any(not isinstance(r, Exception) and r for r in results)


def create_notification_manager(config: NotificationConfig) -> NotificationManager:
    """Create a notification manager with the given config."""
    return NotificationManager(config)
