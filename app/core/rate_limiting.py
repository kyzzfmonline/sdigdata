"""Rate limiting for API endpoints to prevent abuse."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
import threading


class RateLimiter:
    """
    Simple in-memory rate limiter for login attempts and API calls.

    For production, consider using Redis for distributed rate limiting.
    """

    def __init__(self) -> None:
        self._attempts: dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()

    def is_rate_limited(
        self, identifier: str, max_attempts: int, window_seconds: int
    ) -> tuple[bool, int | None]:
        """
        Check if an identifier is rate limited.

        Args:
            identifier: Unique identifier (e.g., username, IP address)
            max_attempts: Maximum attempts allowed in the window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_limited, retry_after_seconds)
        """
        with self._lock:
            now = datetime.now(UTC)
            cutoff = now - timedelta(seconds=window_seconds)

            # Remove old attempts
            self._attempts[identifier] = [
                timestamp
                for timestamp in self._attempts[identifier]
                if timestamp > cutoff
            ]

            # Check if rate limited
            if len(self._attempts[identifier]) >= max_attempts:
                # Calculate retry time
                oldest_attempt = min(self._attempts[identifier])
                retry_after = (
                    oldest_attempt + timedelta(seconds=window_seconds) - now
                ).total_seconds()
                return True, int(max(1, retry_after))

            return False, None

    def record_attempt(self, identifier: str) -> None:
        """Record an attempt for the given identifier."""
        with self._lock:
            self._attempts[identifier].append(datetime.now(UTC))

    def reset(self, identifier: str) -> None:
        """Reset rate limiting for an identifier (e.g., after successful login)."""
        with self._lock:
            if identifier in self._attempts:
                del self._attempts[identifier]

    def cleanup_old_entries(self, max_age_seconds: int = 3600) -> None:
        """
        Clean up old entries to prevent memory bloat.

        Args:
            max_age_seconds: Remove entries older than this
        """
        with self._lock:
            cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
            identifiers_to_remove = []

            for identifier, attempts in self._attempts.items():
                # Remove old attempts
                self._attempts[identifier] = [
                    timestamp for timestamp in attempts if timestamp > cutoff
                ]

                # Mark empty lists for removal
                if not self._attempts[identifier]:
                    identifiers_to_remove.append(identifier)

            # Remove empty entries
            for identifier in identifiers_to_remove:
                del self._attempts[identifier]


class LoginRateLimiter:
    """Specialized rate limiter for login attempts."""

    # Rate limiting configuration
    MAX_ATTEMPTS_PER_USERNAME = 5
    MAX_ATTEMPTS_PER_IP = 10
    WINDOW_SECONDS = 300  # 5 minutes
    LOCKOUT_DURATION = 900  # 15 minutes

    def __init__(self) -> None:
        self.username_limiter = RateLimiter()
        self.ip_limiter = RateLimiter()
        self._lockouts: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def check_login_allowed(
        self, username: str, ip_address: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Check if a login attempt is allowed.

        Args:
            username: Username attempting to log in
            ip_address: IP address of the request

        Returns:
            Tuple of (is_allowed, error_message)
        """
        # Check if account is locked out
        if self._is_locked_out(username):
            lockout_time = self._lockouts.get(username)
            if lockout_time:
                remaining = int((lockout_time - datetime.now(UTC)).total_seconds())
                if remaining > 0:
                    return (
                        False,
                        f"Account temporarily locked. Try again in {remaining} seconds",
                    )

        # Check username rate limit
        username_limited, username_retry = self.username_limiter.is_rate_limited(
            username, self.MAX_ATTEMPTS_PER_USERNAME, self.WINDOW_SECONDS
        )

        if username_limited:
            # Lock out the account
            self._lockout_account(username)
            return (
                False,
                f"Too many failed attempts. Account locked for {self.LOCKOUT_DURATION // 60} minutes",
            )

        # Check IP rate limit
        if ip_address:
            ip_limited, ip_retry = self.ip_limiter.is_rate_limited(
                ip_address, self.MAX_ATTEMPTS_PER_IP, self.WINDOW_SECONDS
            )

            if ip_limited:
                return (
                    False,
                    f"Too many requests from your IP. Try again in {ip_retry} seconds",
                )

        return True, None

    def record_failed_attempt(
        self, username: str, ip_address: str | None = None
    ) -> None:
        """Record a failed login attempt."""
        self.username_limiter.record_attempt(username)
        if ip_address:
            self.ip_limiter.record_attempt(ip_address)

    def record_successful_login(
        self, username: str, ip_address: str | None = None
    ) -> None:
        """Reset rate limiting after successful login."""
        self.username_limiter.reset(username)
        if ip_address:
            self.ip_limiter.reset(ip_address)

        # Remove lockout
        with self._lock:
            if username in self._lockouts:
                del self._lockouts[username]

    def _is_locked_out(self, username: str) -> bool:
        """Check if an account is currently locked out."""
        with self._lock:
            if username in self._lockouts:
                if datetime.now(UTC) < self._lockouts[username]:
                    return True
                else:
                    # Lockout expired
                    del self._lockouts[username]
            return False

    def _lockout_account(self, username: str) -> None:
        """Lock out an account."""
        with self._lock:
            self._lockouts[username] = datetime.now(UTC) + timedelta(
                seconds=self.LOCKOUT_DURATION
            )

    def cleanup(self) -> None:
        """Clean up old entries."""
        self.username_limiter.cleanup_old_entries()
        self.ip_limiter.cleanup_old_entries()

        # Clean up expired lockouts
        with self._lock:
            expired = [
                username
                for username, expiry in self._lockouts.items()
                if datetime.now(UTC) >= expiry
            ]
            for username in expired:
                del self._lockouts[username]


class AnonymousSubmissionRateLimiter:
    """Specialized rate limiter for anonymous form submissions."""

    # Rate limiting configuration for anonymous submissions
    MAX_SUBMISSIONS_PER_IP = 10  # 10 submissions per hour
    WINDOW_SECONDS = 3600  # 1 hour

    def __init__(self) -> None:
        self.ip_limiter = RateLimiter()

    def check_submission_allowed(self, ip_address: str) -> tuple[bool, str | None]:
        """
        Check if an anonymous submission is allowed from this IP.

        Args:
            ip_address: IP address of the request

        Returns:
            Tuple of (is_allowed, error_message)
        """
        limited, retry_after = self.ip_limiter.is_rate_limited(
            ip_address, self.MAX_SUBMISSIONS_PER_IP, self.WINDOW_SECONDS
        )

        if limited:
            return (
                False,
                f"Too many submissions from your IP. Try again in {retry_after} seconds",
            )

        return True, None

    def record_submission(self, ip_address: str) -> None:
        """Record an anonymous submission."""
        self.ip_limiter.record_attempt(ip_address)

    def cleanup(self) -> None:
        """Clean up old entries."""
        self.ip_limiter.cleanup_old_entries()


# Global rate limiter instances
login_rate_limiter = LoginRateLimiter()
anonymous_rate_limiter = AnonymousSubmissionRateLimiter()
