"""Authentication routes."""

from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, field_validator
import asyncpg

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.logging_config import security_logger, get_logger
from app.core.responses import success_response, error_response
from app.core.validation import PasswordValidator, UsernameValidator, sanitize_string
from app.core.rate_limiting import login_rate_limiter
from app.services.users import (
    create_user,
    get_user_by_username,
    get_user_by_id,
    update_user_last_login,
)
from app.services.organizations import get_first_organization
from app.services.permissions import PermissionChecker
from app.api.deps import require_admin, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)


class RegisterRequest(BaseModel):
    """User registration request with validation."""

    username: str = Field(
        ..., min_length=3, max_length=50, description="Username (3-50 characters)"
    )
    password: str = Field(
        ..., min_length=8, max_length=128, description="Password (min 8 characters)"
    )
    role: str = Field(..., description="User role: 'admin' or 'agent'")
    organization_id: str = Field(..., description="Organization UUID")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        v = sanitize_string(v, max_length=50)
        is_valid, error = UsernameValidator.validate(v)
        if not is_valid:
            raise ValueError(error)
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, error = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError(error)
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role value."""
        v = sanitize_string(v, max_length=20)
        if v not in ["admin", "agent"]:
            raise ValueError("Role must be 'admin' or 'agent'")
        return v


class LoginRequest(BaseModel):
    """User login request."""

    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=128)

    @field_validator("username", "password")
    @classmethod
    def sanitize_field(cls, v: str) -> str:
        """Sanitize input fields."""
        return sanitize_string(v, max_length=128)


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    http_request: Request,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Register a new user (admin only) with comprehensive validation.

    **Security Features:**
    - Password strength validation (min 8 chars, uppercase, lowercase, digit, special char)
    - Username format validation
    - Duplicate username check
    - Audit logging
    - Input sanitization

    **Request Body:**
    ```json
    {
        "username": "john_agent",
        "password": "SecurePass123!",
        "role": "agent",
        "organization_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    ```

    **Response:**
    ```json
    {
        "id": "...",
        "username": "john_agent",
        "role": "agent",
        "organization_id": "...",
        "created_at": "2025-11-03T10:00:00"
    }
    ```
    """
    logger.info(
        f"User registration attempt by admin {admin_user['username']} for new user: {request.username}"
    )

    try:
        # Check if username already exists
        existing_user = await get_user_by_username(conn, request.username)
        if existing_user:
            logger.warning(
                f"Registration failed: username already exists - {request.username}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

        # Hash password
        password_hash = hash_password(request.password)

        # Create user
        user = await create_user(
            conn,
            username=request.username,
            password_hash=password_hash,
            role=request.role,
            organization_id=UUID(request.organization_id),
        )

        # Log user registration
        security_logger.log_user_registration(
            username=request.username,
            role=request.role,
            created_by=admin_user["id"],
            organization_id=request.organization_id,
        )

        logger.info(
            f"User registered successfully: {request.username} (role: {request.role})"
        )

        return success_response(data=user)

    except HTTPException:
        raise
    except ValueError as e:
        # Validation error from Pydantic
        logger.warning(f"Registration validation error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Registration error for user {request.username}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during registration. Please try again later.",
        )


@router.post("/login")
async def login(
    request: LoginRequest,
    http_request: Request,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Authenticate user and return JWT token with rate limiting and security logging.

    **Security Features:**
    - Rate limiting: Max 5 attempts per username per 5 minutes
    - IP-based rate limiting: Max 10 attempts per IP per 5 minutes
    - Account lockout: 15 minutes after max failed attempts
    - Comprehensive audit logging
    - Constant-time password comparison

    **Request Body:**
    ```json
    {
        "username": "john_agent",
        "password": "securepass123"
    }
    ```

    **Response:**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "user": {
            "id": "...",
            "username": "john_agent",
            "role": "agent",
            "organization_id": "..."
        }
    }
    ```
    """
    # Get client IP address
    client_ip = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    logger.info(f"Login attempt for user: {request.username} from IP: {client_ip}")

    try:
        # Check rate limiting
        allowed, error_msg = login_rate_limiter.check_login_allowed(
            request.username, client_ip
        )

        if not allowed:
            security_logger.log_login_attempt(
                username=request.username,
                success=False,
                ip_address=client_ip,
                user_agent=user_agent,
                reason="rate_limited",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg,
            )

        # Get user by username
        user = await get_user_by_username(conn, request.username)

        # Use constant-time comparison to prevent timing attacks
        # Always verify password even if user doesn't exist to prevent timing-based user enumeration
        if user:
            password_hash = user["password_hash"]
            user_exists = True
        else:
            # Use a dummy hash with same format to maintain constant time
            # This hash will never match, but verification takes same time
            password_hash = "$argon2id$v=19$m=65536,t=3,p=4$dHVtbXlzYWx0MTIzNDU2Nzg$dummyhashpreventtimingatttack1234567890abcdef"
            user_exists = False

        # Always verify password (constant time whether user exists or not)
        password_valid = verify_password(request.password, password_hash)

        # Check if authentication succeeded
        if not (user_exists and password_valid):
            # Record failed attempt
            login_rate_limiter.record_failed_attempt(request.username, client_ip)
            reason = "invalid_username" if not user_exists else "invalid_password"
            security_logger.log_login_attempt(
                username=request.username,
                success=False,
                ip_address=client_ip,
                user_agent=user_agent,
                reason=reason,
            )
            logger.warning(f"Login failed: {reason} - {request.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        # Successful login - reset rate limiting
        login_rate_limiter.record_successful_login(request.username, client_ip)

        # Update last login timestamp
        user_id = user["id"] if isinstance(user["id"], UUID) else UUID(user["id"])
        await update_user_last_login(conn, user_id)

        # Create access token
        access_token = create_access_token(data={"sub": str(user["id"])})

        # Log successful login
        security_logger.log_login_attempt(
            username=request.username,
            success=True,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        security_logger.log_token_creation(str(user["id"]), "access")

        logger.info(f"Login successful for user: {request.username}")

        # Get user permissions and roles
        checker = PermissionChecker(conn)
        permissions = await checker.get_user_permissions(user_id)
        roles = await checker.get_user_roles(user_id)

        # Remove password hash from user data
        user_data = {k: v for k, v in user.items() if k != "password_hash"}

        return success_response(
            data={
                "access_token": access_token,
                "token_type": "bearer",
                "user": user_data,
                "permissions": permissions,
                "roles": roles,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Login error for user {request.username}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login. Please try again later.",
        )


class BootstrapAdminRequest(BaseModel):
    """Bootstrap admin creation request."""

    username: str = Field(
        ..., min_length=3, max_length=50, description="Admin username (3-50 characters)"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Admin password (min 8 characters)",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        v = sanitize_string(v, max_length=50)
        is_valid, error = UsernameValidator.validate(v)
        if not is_valid:
            raise ValueError(error)
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, error = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError(error)
        return v


@router.post(
    "/bootstrap-admin", response_model=dict, status_code=status.HTTP_201_CREATED
)
async def bootstrap_admin(
    request: BootstrapAdminRequest,
    http_request: Request,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Create the first admin user (bootstrap endpoint).

    This endpoint allows creating an admin user when no admins exist in the system.
    Once an admin exists, this endpoint will return an error and you must use
    the /auth/register endpoint (which requires admin authentication).

    **Security Features:**
    - Only works if NO admin users exist
    - Password strength validation (min 8 chars, uppercase, lowercase, digit, special char)
    - Username format validation
    - Duplicate username check
    - Audit logging
    - Input sanitization

    **Request Body:**
    ```json
    {
        "username": "admin",
        "password": "SecurePass123!"
    }
    ```

    **Response:**
    ```json
    {
        "id": "...",
        "username": "admin",
        "role": "admin",
        "organization_id": "...",
        "created_at": "2025-11-04T10:00:00"
    }
    ```
    """
    logger.info(f"Bootstrap admin creation attempt for username: {request.username}")

    try:
        # Check if any admin users already exist
        admin_count = (
            await conn.fetchval("SELECT COUNT(*) FROM users WHERE role = 'admin'") or 0
        )

        if admin_count > 0:
            logger.warning(
                f"Bootstrap admin creation blocked: {admin_count} admin(s) already exist"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create bootstrap admin: admin users already exist. Use /auth/register with admin authentication instead.",
            )

        # Check if username already exists
        existing_user = await get_user_by_username(conn, request.username)
        if existing_user:
            logger.warning(
                f"Bootstrap admin creation failed: username already exists - {request.username}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

        # Get the first organization (or create one if none exists)
        organization = await get_first_organization(conn)
        if not organization:
            logger.info("No organization found, creating default organization")
            from app.services.organizations import create_organization

            organization = await create_organization(
                conn,
                name="Default Organization",
                logo_url=None,
                primary_color="#1976d2",
            )

        # Hash password
        password_hash = hash_password(request.password)

        # Create admin user
        org_id = (
            organization["id"]
            if isinstance(organization["id"], UUID)
            else UUID(organization["id"])
        )
        user = await create_user(
            conn,
            username=request.username,
            password_hash=password_hash,
            role="admin",
            organization_id=org_id,
        )

        # Log user registration
        security_logger.log_user_registration(
            username=request.username,
            role="admin",
            created_by="system_bootstrap",
            organization_id=str(organization["id"]),
        )

        logger.info(f"Bootstrap admin created successfully: {request.username}")

        return user

    except HTTPException:
        raise
    except ValueError as e:
        # Validation error from Pydantic
        logger.warning(f"Bootstrap admin validation error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Bootstrap admin creation error for user {request.username}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during admin creation. Please try again later.",
        )


@router.get("/verify", response_model=dict)
async def verify_token(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Verify JWT token and return user information.

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "valid": true,
            "user": {
                "id": "...",
                "username": "john_agent",
                "role": "agent",
                "organization_id": "..."
            }
        }
    }
    ```
    """
    user_data = {k: v for k, v in current_user.items() if k != "password_hash"}
    return success_response(data={"valid": True, "user": user_data})


@router.post("/logout", response_model=dict)
async def logout(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Logout user (client-side token removal).

    Since we're using JWT tokens (stateless), logout is handled client-side
    by removing the token. This endpoint confirms the logout action.

    **Response:**
    ```json
    {
        "success": true,
        "message": "Logged out successfully"
    }
    ```
    """
    logger.info(f"User logged out: {current_user['username']}")
    security_logger.log_logout(current_user["id"], current_user["username"])

    return success_response(message="Logged out successfully")


@router.post("/refresh")
async def refresh_token(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Refresh JWT access token.

    Accepts a valid JWT token in the Authorization header and returns a new
    access token with a fresh expiration time. This allows users to maintain
    their session without re-authenticating.

    **Security Notes:**
    - Requires a valid, non-expired JWT token
    - Returns 401 if token is invalid or expired
    - Generates a new token with fresh expiration time
    - User information is re-validated from the database

    **Request Headers:**
    ```
    Authorization: Bearer <current_jwt_token>
    ```

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "user": {
                "id": "...",
                "username": "john_agent",
                "role": "agent",
                "organization_id": "..."
            }
        }
    }
    ```

    **Error Response (401):**
    ```json
    {
        "success": false,
        "message": "Invalid authentication credentials",
        "data": null,
        "errors": null
    }
    ```
    """
    logger.info(f"Token refresh requested for user: {current_user['username']}")

    try:
        # Create new access token with fresh expiration
        access_token = create_access_token(data={"sub": str(current_user["id"])})

        # Log token refresh
        security_logger.log_token_creation(str(current_user["id"]), "access")

        logger.info(
            f"Token refreshed successfully for user: {current_user['username']}"
        )

        # Remove password hash from user data (if present)
        user_data = {k: v for k, v in current_user.items() if k != "password_hash"}

        return success_response(
            data={
                "access_token": access_token,
                "token_type": "bearer",
                "user": user_data,
            }
        )

    except Exception as e:
        logger.error(
            f"Token refresh error for user {current_user.get('username', 'unknown')}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while refreshing token. Please try again later.",
        )


class PasswordResetRequest(BaseModel):
    """Password reset request."""

    email: str = Field(..., max_length=255, description="User email address")


@router.post("/password-reset", response_model=dict)
async def request_password_reset(
    request: PasswordResetRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Request password reset (sends reset email).

    Note: This is a placeholder implementation. In production, this should:
    1. Generate a secure reset token
    2. Store it in the database with expiration
    3. Send email with reset link

    **Request Body:**
    ```json
    {
        "email": "user@example.com"
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "message": "If an account exists with that email, a password reset link has been sent."
    }
    ```
    """
    logger.info(f"Password reset requested for email: {request.email}")

    # For security, always return success even if email doesn't exist
    # This prevents user enumeration attacks
    return success_response(
        message="If an account exists with that email, a password reset link has been sent."
    )


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, error = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError(error)
        return v


@router.post("/password-reset/confirm", response_model=dict)
async def confirm_password_reset(
    request: PasswordResetConfirm,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Confirm password reset with token.

    Note: This is a placeholder implementation. In production, this should:
    1. Validate the reset token
    2. Check token expiration
    3. Update user password
    4. Invalidate the token

    **Request Body:**
    ```json
    {
        "token": "reset_token_here",
        "new_password": "NewSecurePassword123!"
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "message": "Password reset successful"
    }
    ```
    """
    logger.info("Password reset confirmation attempt")

    # Placeholder: In production, validate token and update password
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset functionality requires email service configuration",
    )
