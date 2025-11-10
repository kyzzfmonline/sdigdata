"""Email service for sending password reset and other emails."""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import asyncio
from datetime import datetime, timedelta
import secrets
import hashlib

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_tls = settings.SMTP_TLS
        self.from_email = settings.FROM_EMAIL
        self.from_name = settings.FROM_NAME

    async def send_password_reset_email(
        self, to_email: str, reset_token: str, username: str
    ) -> bool:
        """
        Send password reset email.

        Args:
            to_email: Recipient email address
            reset_token: Password reset token
            username: Username for personalization

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Password Reset - SDIGdata"
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email

            # Create reset link (assuming frontend URL)
            reset_link = (
                f"{self._get_frontend_url()}/reset-password?token={reset_token}"
            )

            # HTML content
            html = f"""
            <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>Hello {username},</p>
                <p>You have requested to reset your password for your SDIGdata account.</p>
                <p>Please click the link below to reset your password:</p>
                <p><a href="{reset_link}" style="background-color: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't request this password reset, please ignore this email.</p>
                <br>
                <p>Best regards,<br>SDIGdata Team</p>
            </body>
            </html>
            """

            # Text content
            text = f"""
            Password Reset Request

            Hello {username},

            You have requested to reset your password for your SDIGdata account.

            Please use the following link to reset your password:
            {reset_link}

            This link will expire in 24 hours.

            If you didn't request this password reset, please ignore this email.

            Best regards,
            SDIGdata Team
            """

            # Attach parts
            part1 = MIMEText(text, "plain")
            part2 = MIMEText(html, "html")
            msg.attach(part1)
            msg.attach(part2)

            # Send email in thread pool to avoid blocking
            await asyncio.get_event_loop().run_in_executor(
                None, self._send_email_sync, msg.as_string()
            )

            logger.info(f"Password reset email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send password reset email to {to_email}: {str(e)}")
            return False

    def _send_email_sync(self, email_content: str) -> None:
        """Send email synchronously (called from thread pool)."""
        try:
            # Create SSL context
            context = ssl.create_default_context()

            # Connect to SMTP server
            if self.smtp_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls(context=context)
            else:
                server = smtplib.SMTP_SSL(
                    self.smtp_server, self.smtp_port, context=context
                )

            # Login if credentials provided
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)

            # Send email
            server.sendmail(self.from_email, [self.from_email], email_content)
            server.quit()

        except Exception as e:
            logger.error(f"SMTP error: {str(e)}")
            raise

    def _get_frontend_url(self) -> str:
        """Get frontend URL based on environment."""
        if settings.ENVIRONMENT == "production":
            return "https://app.sdigdata.gov.gh"
        elif settings.ENVIRONMENT == "staging":
            return "https://staging.sdigdata.gov.gh"
        else:
            return "http://localhost:3000"

    @staticmethod
    def generate_reset_token() -> str:
        """Generate a secure random token for password reset."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def get_token_expiry() -> datetime:
        """Get token expiry datetime."""
        return datetime.utcnow() + timedelta(
            hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
        )


# Global email service instance
email_service = EmailService()
