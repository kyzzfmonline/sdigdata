"""Input validation utilities for authentication and security."""

import re


class PasswordValidator:
    """Validate password strength and complexity."""

    MIN_LENGTH = 8
    MAX_LENGTH = 128

    # Password strength requirements
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True

    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Common passwords to reject
    COMMON_PASSWORDS = {
        "password",
        "123456",
        "12345678",
        "qwerty",
        "abc123",
        "monkey",
        "letmein",
        "trustno1",
        "dragon",
        "baseball",
        "iloveyou",
        "master",
        "sunshine",
        "ashley",
        "bailey",
        "passw0rd",
        "shadow",
        "123123",
        "654321",
        "superman",
        "qazwsx",
        "michael",
        "football",
        "admin",
        "admin123",
    }

    @classmethod
    def validate(cls, password: str) -> tuple[bool, str | None]:
        """
        Validate password strength.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check length
        if len(password) < cls.MIN_LENGTH:
            return False, f"Password must be at least {cls.MIN_LENGTH} characters long"

        if len(password) > cls.MAX_LENGTH:
            return False, f"Password must not exceed {cls.MAX_LENGTH} characters"

        # Check for common passwords
        if password.lower() in cls.COMMON_PASSWORDS:
            return (
                False,
                "This password is too common. Please choose a stronger password",
            )

        # Check complexity requirements
        if cls.REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"

        if cls.REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"

        if cls.REQUIRE_DIGIT and not re.search(r"\d", password):
            return False, "Password must contain at least one digit"

        if cls.REQUIRE_SPECIAL and not any(c in cls.SPECIAL_CHARS for c in password):
            return (
                False,
                f"Password must contain at least one special character ({cls.SPECIAL_CHARS})",
            )

        # Check for sequential characters (e.g., "abc", "123") - only check for 4+ chars
        if cls._has_sequential_chars(password, length=4):
            return (
                False,
                "Password must not contain long sequential patterns (e.g., 'abcd', '1234')",
            )

        return True, None

    @staticmethod
    def _has_sequential_chars(password: str, length: int = 4) -> bool:
        """Check if password contains sequential characters."""
        password_lower = password.lower()

        for i in range(len(password_lower) - length + 1):
            substring = password_lower[i : i + length]

            # Check for sequential numbers
            if substring.isdigit():
                nums = [int(c) for c in substring]
                if all(nums[j] + 1 == nums[j + 1] for j in range(len(nums) - 1)):
                    return True
                if all(nums[j] - 1 == nums[j + 1] for j in range(len(nums) - 1)):
                    return True

            # Check for sequential letters
            if substring.isalpha():
                ascii_vals = [ord(c) for c in substring]
                if all(
                    ascii_vals[j] + 1 == ascii_vals[j + 1]
                    for j in range(len(ascii_vals) - 1)
                ):
                    return True
                if all(
                    ascii_vals[j] - 1 == ascii_vals[j + 1]
                    for j in range(len(ascii_vals) - 1)
                ):
                    return True

        return False


class UsernameValidator:
    """Validate username format and constraints."""

    MIN_LENGTH = 3
    MAX_LENGTH = 50

    # Allow alphanumeric, underscore, hyphen, and period
    VALID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")

    # Reserved usernames
    RESERVED_USERNAMES = {
        "admin",
        "root",
        "system",
        "api",
        "app",
        "test",
        "user",
        "guest",
        "null",
        "undefined",
        "administrator",
    }

    @classmethod
    def validate(cls, username: str) -> tuple[bool, str | None]:
        """
        Validate username format.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check length
        if len(username) < cls.MIN_LENGTH:
            return False, f"Username must be at least {cls.MIN_LENGTH} characters long"

        if len(username) > cls.MAX_LENGTH:
            return False, f"Username must not exceed {cls.MAX_LENGTH} characters"

        # Check pattern
        if not cls.VALID_PATTERN.match(username):
            return (
                False,
                "Username can only contain letters, numbers, dots, hyphens, and underscores",
            )

        # Note: Reserved username check removed - "admin" is a valid existing user
        # If you need to prevent registration of reserved names, check at registration time
        # against existing users in the database

        # Can't start or end with special characters
        if username[0] in "._-" or username[-1] in "._-":
            return False, "Username cannot start or end with a special character"

        # Can't have consecutive special characters
        if any(
            a in "._-" and b in "._-"
            for a, b in zip(username, username[1:], strict=False)
        ):
            return False, "Username cannot contain consecutive special characters"

        return True, None


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize string input by removing potentially dangerous content.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not value:
        return ""

    # Truncate to max length
    value = value[:max_length]

    # Remove null bytes
    value = value.replace("\x00", "")

    # Strip leading/trailing whitespace
    value = value.strip()

    return value


def validate_uuid(value: str) -> bool:
    """Validate UUID format."""
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    return bool(uuid_pattern.match(value))
