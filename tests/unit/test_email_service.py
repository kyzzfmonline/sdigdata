"""
Unit tests for email service functions.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.email import EmailService


class TestEmailService:
    """Test EmailService class methods."""

    @pytest.fixture
    def email_service(self):
        """EmailService instance."""
        return EmailService()

    @pytest.mark.asyncio
    async def test_send_password_reset_email_success(self, email_service):
        """Test successful password reset email sending."""
        with patch.object(email_service, "_send_email_sync") as mock_send:
            result = await email_service.send_password_reset_email(
                to_email="test@example.com",
                reset_token="test_token_123",
                username="testuser",
            )

            assert result is True
            mock_send.assert_called_once()
            # Check that email content contains expected elements
            email_content = mock_send.call_args[0][0]
            assert "Password Reset - SDIGdata" in email_content
            assert "test@example.com" in email_content
            assert "test_token_123" in email_content
            assert "testuser" in email_content

    @pytest.mark.asyncio
    async def test_send_password_reset_email_failure(self, email_service):
        """Test password reset email sending failure."""
        with patch.object(email_service, "_send_email_sync") as mock_send:
            mock_send.side_effect = Exception("SMTP error")

            result = await email_service.send_password_reset_email(
                to_email="test@example.com",
                reset_token="test_token_123",
                username="testuser",
            )

            assert result is False

    def test_generate_reset_token(self, email_service):
        """Test reset token generation."""
        token1 = email_service.generate_reset_token()
        token2 = email_service.generate_reset_token()

        assert isinstance(token1, str)
        assert len(token1) > 0
        assert token1 != token2  # Should be unique

    def test_hash_token(self, email_service):
        """Test token hashing."""
        token = "test_token"
        hashed = email_service.hash_token(token)

        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA256 hex length
        assert hashed != token  # Should be different

        # Same token should produce same hash
        hashed2 = email_service.hash_token(token)
        assert hashed == hashed2

    def test_get_token_expiry(self, email_service):
        """Test token expiry calculation."""
        with patch("app.services.email.settings") as mock_settings:
            mock_settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 24

            expiry = email_service.get_token_expiry()

            assert isinstance(expiry, datetime)
            # Should be approximately 24 hours from now
            expected = datetime.now(UTC) + timedelta(hours=24)
            time_diff = abs((expiry - expected).total_seconds())
            assert time_diff < 1  # Within 1 second

    def test_get_frontend_url_production(self, email_service):
        """Test frontend URL for production environment."""
        with patch("app.services.email.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "production"

            url = email_service._get_frontend_url()

            assert url == "https://app.sdigdata.gov.gh"

    def test_get_frontend_url_staging(self, email_service):
        """Test frontend URL for staging environment."""
        with patch("app.services.email.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "staging"

            url = email_service._get_frontend_url()

            assert url == "https://staging.sdigdata.gov.gh"

    def test_get_frontend_url_development(self, email_service):
        """Test frontend URL for development environment."""
        with patch("app.services.email.settings") as mock_settings:
            mock_settings.ENVIRONMENT = "development"

            url = email_service._get_frontend_url()

            assert url == "http://localhost:3000"

    def test_send_email_sync_with_tls(self, email_service):
        """Test synchronous email sending with TLS."""
        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_server = MagicMock()
            mock_smtp_class.return_value = mock_server

            email_service.smtp_tls = True
            email_service.smtp_username = "user"
            email_service.smtp_password = "pass"

            email_service._send_email_sync("test email content")

            mock_smtp_class.assert_called_once_with("localhost", 1025)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user", "pass")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    def test_send_email_sync_without_tls(self, email_service):
        """Test synchronous email sending without TLS."""
        with patch("smtplib.SMTP_SSL") as mock_smtp_ssl_class:
            mock_server = MagicMock()
            mock_smtp_ssl_class.return_value = mock_server

            email_service.smtp_tls = False
            email_service.smtp_username = None
            email_service.smtp_password = None

            email_service._send_email_sync("test email content")

            mock_smtp_ssl_class.assert_called_once()
            mock_server.login.assert_not_called()  # No credentials
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    def test_send_email_sync_smtp_error(self, email_service):
        """Test SMTP error handling."""
        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_server = MagicMock()
            mock_server.starttls.side_effect = Exception("Connection failed")
            mock_smtp_class.return_value = mock_server

            email_service.smtp_tls = True

            with pytest.raises(Exception):
                email_service._send_email_sync("test email content")
