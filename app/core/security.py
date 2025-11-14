"""
Modern security utilities using Argon2 password hashing.

Argon2 is the winner of the Password Hashing Competition (2015) and is recommended by:
- OWASP (Open Web Application Security Project)
- NIST (National Institute of Standards and Technology)
- IETF (Internet Engineering Task Force)

It's significantly more secure than bcrypt/scrypt and provides better protection against:
- GPU-based attacks
- Side-channel attacks
- Memory-hardness attacks
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Initialize Argon2id with secure parameters
# Argon2id is the hybrid version combining Argon2i and Argon2d
ph = PasswordHasher(
    time_cost=3,  # Number of iterations (recommended: 3-4 for 2024)
    memory_cost=65536,  # Memory usage in KiB (64 MB - good balance)
    parallelism=4,  # Number of parallel threads
    hash_len=32,  # Length of the hash in bytes
    salt_len=16,  # Length of the salt in bytes
    type=Type.ID,  # Argon2id (hybrid version - most secure)
)


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.

    Args:
        password: Plain text password

    Returns:
        Hashed password string in PHC string format
        Example: $argon2id$v=19$m=65536,t=3,p=4$...
    """
    try:
        return ph.hash(password)
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash using constant-time comparison.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Argon2 hashed password

    Returns:
        True if password matches, False otherwise
    """
    try:
        # Verify Argon2 hash
        ph.verify(hashed_password, plain_password)

        # Check if hash needs rehashing (e.g., if security parameters changed)
        if ph.check_needs_rehash(hashed_password):
            logger.info("Password hash needs rehashing with updated parameters")
            # Note: In production, you should rehash and update in database on next login

        return True

    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def create_access_token(
    data: dict, expires_delta: timedelta | None = None
) -> str | bytes:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Decode and verify a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None
