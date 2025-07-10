"""Tests for the notifications module."""
import pytest
import httpx
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from ticketmaster_resale_notify.models import Notification, NotificationConfig
from ticketmaster_resale_notify.notifications import (
    NotificationService, NtfyNotificationService, NotificationManager
)


class TestNotificationService:
    """Tests for the base NotificationService class."""
    
    @pytest.fixture
    def mock_service(self):
        """Create a mock NotificationService instance for testing."""
        class MockService(NotificationService):
            async def _send_impl(self, notification):
                return True
        
        return MockService(NotificationConfig())
    
    @pytest.mark.asyncio
    async def test_send_success(self, mock_service):
        """Test successful send with retry logic."""
        notification = Notification(title="Test", message="Test message")
        result = await mock_service.send(notification)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_send_with_retry(self, mock_service):
        """Test send with retry logic on failure."""
        # Make the first two attempts fail, then succeed
        mock_service._send_impl = AsyncMock(
            side_effect=[Exception("Failed"), Exception("Failed"), True]
        )
        
        notification = Notification(title="Test", message="Test message")
        result = await mock_service.send(notification)
        
        assert result is True
        assert mock_service._send_impl.await_count == 3


class TestNtfyNotificationService:
    """Tests for the NtfyNotificationService class."""
    
    @pytest.fixture
    def service(self):
        """Create an NtfyNotificationService instance for testing."""
        return NtfyNotificationService(
            topic="test-topic",
            config=NotificationConfig()
        )
    
    @pytest.mark.asyncio
    async def test_send_impl_success(self, service):
        """Test successful notification sending."""
        notification = Notification(
            title="Test Title",
            message="Test message",
            priority=3,
            tags=["test"],
            actions=[{"action": "view", "label": "View", "url": "https://example.com"}]
        )
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            result = await service._send_impl(notification)
            
            assert result is True
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert kwargs["headers"]["Title"] == "Test Title"
            assert kwargs["headers"]["Priority"] == "3"
            assert "test" in kwargs["headers"]["Tags"]
            assert "Actions" in kwargs["headers"]
    
    @pytest.mark.asyncio
    async def test_send_impl_http_error(self, service):
        """Test notification sending with HTTP error."""
        notification = Notification(title="Test", message="Test message")
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPError("Error")
            mock_post.return_value = mock_response
            
            with pytest.raises(httpx.HTTPError):
                await service._send_impl(notification)


class TestNotificationManager:
    """Tests for the NotificationManager class."""
    
    @pytest.fixture
    def notification_manager(self):
        """Create a NotificationManager instance for testing."""
        config = NotificationConfig(
            enabled=True,
            service="ntfy",
            topic="test-topic"
        )
        return NotificationManager(config)
    
    @pytest.mark.asyncio
    async def test_send_notification_success(self, notification_manager):
        """Test successful notification sending through the manager."""
        # Patch the service's send method
        mock_service = AsyncMock()
        mock_service.send.return_value = True
        notification_manager.services = [mock_service]
        
        result = await notification_manager.send_notification(
            title="Test",
            message="Test message"
        )
        
        assert result is True
        mock_service.send.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_send_notification_no_services(self, notification_manager):
        """Test notification sending with no services configured."""
        notification_manager.services = []
        
        result = await notification_manager.send_notification(
            title="Test",
            message="Test message"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_notification_service_error(self, notification_manager):
        """Test notification sending when a service raises an exception."""
        mock_service = AsyncMock()
        mock_service.send.side_effect = Exception("Service error")
        notification_manager.services = [mock_service]
        
        with patch("ticketmaster_resale_notify.notifications.logger") as mock_logger:
            result = await notification_manager.send_notification(
                title="Test",
                message="Test message"
            )
            
            assert result is False
            mock_logger.error.assert_called()
