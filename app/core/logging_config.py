"""Structured logging configuration for the application."""

from datetime import UTC, datetime
import json
import logging
import sys

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging in production."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        log_data = {
            "timestamp": datetime.now(UTC).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class StandardFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def setup_logging() -> None:
    """Configure application logging based on environment."""
    # Determine log level
    log_level = logging.INFO
    if settings.ENVIRONMENT == "development":
        log_level = logging.DEBUG
    elif settings.ENVIRONMENT == "production":
        log_level = logging.WARNING

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Use JSON formatter in production, standard in development
    if settings.ENVIRONMENT == "production":
        formatter = JSONFormatter()
    else:
        formatter = StandardFormatter()

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set specific log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class SecurityLogger:
    """Specialized logger for security events."""

    def __init__(self) -> None:
        self.logger = get_logger("security")

    def log_login_attempt(
        self,
        username: str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Log a login attempt."""
        extra_fields = {
            "event_type": "login_attempt",
            "username": username,
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        if not success and reason:
            extra_fields["failure_reason"] = reason

        message = f"Login {'succeeded' if success else 'failed'} for user: {username}"

        if success:
            self.logger.info(message, extra={"extra_fields": extra_fields})
        else:
            self.logger.warning(message, extra={"extra_fields": extra_fields})

    def log_token_creation(self, user_id: str, token_type: str = "access") -> None:
        """Log token creation."""
        self.logger.info(
            f"Token created for user: {user_id}",
            extra={
                "extra_fields": {
                    "event_type": "token_created",
                    "user_id": user_id,
                    "token_type": token_type,
                }
            },
        )

    def log_unauthorized_access(
        self,
        resource: str,
        user_id: str | None = None,
        ip_address: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Log unauthorized access attempt."""
        self.logger.warning(
            f"Unauthorized access attempt to: {resource}",
            extra={
                "extra_fields": {
                    "event_type": "unauthorized_access",
                    "resource": resource,
                    "user_id": user_id,
                    "ip_address": ip_address,
                    "reason": reason,
                }
            },
        )

    def log_account_lockout(self, username: str, reason: str) -> None:
        """Log account lockout."""
        self.logger.warning(
            f"Account locked: {username}",
            extra={
                "extra_fields": {
                    "event_type": "account_lockout",
                    "username": username,
                    "reason": reason,
                }
            },
        )

    def log_password_change(self, user_id: str, ip_address: str | None = None) -> None:
        """Log password change."""
        self.logger.info(
            f"Password changed for user: {user_id}",
            extra={
                "extra_fields": {
                    "event_type": "password_change",
                    "user_id": user_id,
                    "ip_address": ip_address,
                }
            },
        )

    def log_user_registration(
        self, username: str, role: str, created_by: str, organization_id: str
    ) -> None:
        """Log new user registration."""
        self.logger.info(
            f"New user registered: {username}",
            extra={
                "extra_fields": {
                    "event_type": "user_registration",
                    "username": username,
                    "role": role,
                    "created_by": created_by,
                    "organization_id": organization_id,
                }
            },
        )

    def log_logout(self, user_id: str, username: str) -> None:
        """Log user logout."""
        self.logger.info(
            f"User logged out: {username}",
            extra={
                "extra_fields": {
                    "event_type": "logout",
                    "user_id": user_id,
                    "username": username,
                }
            },
        )


# Global security logger instance
security_logger = SecurityLogger()
