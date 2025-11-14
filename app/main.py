"""FastAPI main application for SDIGdata backend."""
# type: ignore

from contextlib import asynccontextmanager

import asyncpg
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import (
    analytics,
    api_keys,
    audit,
    auth,
    files,
    forms,
    ml,
    notifications,
    organizations,
    responses,
    security_settings,
    sessions,
    users,
)
from app.api.routes.conditional_logic import router as conditional_logic_router
from app.api.routes.form_locking import router as form_locking_router
from app.api.routes.form_templates import router as form_templates_router
from app.api.routes.form_validation import router as form_validation_router
from app.api.routes.form_versioning import router as form_versioning_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.permission_groups import router as permission_groups_router
from app.api.routes.public import router as public_router
from app.api.routes.rbac import router as rbac_router
from app.api.routes.search import router as search_router
from app.core.config import settings
from app.core.database import close_db_pool, init_db_pool
from app.core.logging_config import get_logger, setup_logging
from app.core.responses import error_response
from app.utils.spaces import ensure_bucket_exists

# Setup logging
setup_logging()
logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        # Note: Adjust this based on your frontend needs
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none'"
        )

        # Strict Transport Security (HSTS) - only in production with HTTPS
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), camera=(self), microphone=(self), payment=()"
        )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown."""
    # Startup
    logger.info("Starting SDIGdata backend...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(
        f"Storage configured: {settings.SPACES_BUCKET} at {settings.SPACES_ENDPOINT}"
    )
    print(
        f"ℹ Storage configured: {settings.SPACES_BUCKET} at {settings.SPACES_ENDPOINT}"
    )

    # Initialize async database pool (skip in test environment)
    if settings.ENVIRONMENT != "test":
        await init_db_pool(settings)

    # Ensure MinIO bucket exists and is publicly accessible
    try:
        ensure_bucket_exists()
        print(f"✓ MinIO bucket ready: {settings.SPACES_BUCKET}")
    except Exception as e:
        logger.warning(f"Could not initialize storage bucket: {e}")
        print(f"⚠ Could not initialize storage bucket: {e}")

    yield

    # Shutdown
    if settings.ENVIRONMENT != "test":
        await close_db_pool()
    logger.info("Shutting down SDIGdata backend...")
    print("Shutting down SDIGdata backend...")


# Create FastAPI app
app = FastAPI(
    title="SDIGdata Backend",
    description="""
    **SDIGdata Backend** - AI-Ready Data Collection System for Metropolitan Assemblies

    Features:
    - Form creation and management with branding
    - Agent assignment and role-based access
    - Response collection (text, GPS, media)
    - File uploads via DigitalOcean Spaces / MinIO
    - Automated ML data quality scoring
    - ML-ready data exports (GeoJSON, JSON, JSONL, CSV)
    - Geospatial ML capabilities
    - Data versioning and lineage tracking
    - Privacy and consent framework
    - JWT authentication

    ## Authentication

    Most endpoints require authentication. Include the JWT token in the Authorization header:

    ```
    Authorization: Bearer <your_jwt_token>
    ```

    ## Roles

    - **admin**: Can create organizations, forms, assign agents, export data, and access ML endpoints
    - **agent**: Can view assigned forms and submit responses

    ## ML/AI Features

    - Automatic quality scoring on all responses (completeness, GPS accuracy, photo quality)
    - High-quality training dataset exports via /ml/training-data
    - GeoJSON spatial data exports for geospatial ML
    - Quality statistics and analytics via /ml/quality-stats
    - Bulk exports optimized for ML pipelines

    ## API Versioning

    This API supports versioning. Use versioned endpoints for stability:

    - `/v1/*` - Version 1 (current stable)
    - `/*` - Latest version (may change)

    Example:
    ```
    GET /v1/forms
    GET /forms  # Same as latest version
    ```
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add security headers middleware FIRST (before CORS)
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware
if settings.ENVIRONMENT == "development":
    # More permissive CORS for development
    print("🔧 CORS: Development mode - allowing all origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins in development
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
else:
    # Strict CORS for production
    print(f"🔒 CORS: Production mode - allowed origins: {settings.cors_origins_list}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "User-Agent",
        ],
        expose_headers=["*"],
    )


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with standardized error responses."""
    from app.core.responses import error_response_dict

    # If the detail is already a dict (from our error_response), use it directly
    if isinstance(exc.detail, dict):
        return error_response_dict(exc.detail, exc.status_code)
    else:
        return error_response_dict(
            {"success": False, "message": exc.detail, "data": None, "errors": None},
            exc.status_code,
        )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    from app.core.responses import error_response_dict

    errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors[field] = error["msg"]

    return error_response_dict(
        {
            "success": False,
            "message": "Validation failed",
            "data": None,
            "errors": errors,
        },
        422,
    )


@app.exception_handler(asyncpg.exceptions.PostgresError)
async def database_exception_handler(
    request: Request, exc: asyncpg.exceptions.PostgresError
):
    """Handle database errors."""
    from app.core.responses import error_response_dict

    logger.error(f"Database error: {exc}", exc_info=True)
    return error_response_dict(
        {
            "success": False,
            "message": "Database error occurred",
            "data": None,
            "errors": None,
        },
        500,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    from app.core.responses import error_response_dict

    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return error_response_dict(
        {
            "success": False,
            "message": "An unexpected error occurred",
            "data": None,
            "errors": None,
        },
        500,
    )


# Create versioned API router
v1_router = APIRouter(prefix="/v1")

# Include all routers under v1
v1_router.include_router(auth.router)
v1_router.include_router(users.router)
v1_router.include_router(organizations.router)
v1_router.include_router(forms.router)
v1_router.include_router(responses.router)
v1_router.include_router(files.router)
v1_router.include_router(notifications.router)
v1_router.include_router(analytics.router)
v1_router.include_router(ml.router)
v1_router.include_router(search_router)
v1_router.include_router(metrics_router)
v1_router.include_router(form_templates_router)
v1_router.include_router(conditional_logic_router)
v1_router.include_router(form_versioning_router)
v1_router.include_router(form_validation_router)
v1_router.include_router(form_locking_router)
v1_router.include_router(rbac_router)
v1_router.include_router(audit.router)
v1_router.include_router(sessions.router)
v1_router.include_router(api_keys.router)
v1_router.include_router(security_settings.router)
v1_router.include_router(permission_groups_router)
if public_router:
    v1_router.include_router(public_router)

# Include versioned router
app.include_router(v1_router)

# Also include routers at root level for backward compatibility (latest version)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(organizations.router)
app.include_router(forms.router)
app.include_router(responses.router)
app.include_router(files.router)
app.include_router(notifications.router)
app.include_router(analytics.router)
app.include_router(ml.router)
app.include_router(search_router)
app.include_router(metrics_router)
app.include_router(form_templates_router)
app.include_router(conditional_logic_router)
app.include_router(form_versioning_router)
app.include_router(form_validation_router)
app.include_router(form_locking_router)
app.include_router(rbac_router)
app.include_router(audit.router)
app.include_router(sessions.router)
app.include_router(api_keys.router)
app.include_router(security_settings.router)
app.include_router(permission_groups_router)
if public_router:
    app.include_router(public_router)


@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint for monitoring and load balancers.

    Checks:
    - API service status
    - Database connectivity
    - Connection pool health
    - Storage (MinIO) connectivity

    Returns 200 if all healthy, 503 if any component is down.
    """
    import time

    from app.core.database import _pool
    from app.core.responses import success_response
    from app.utils.spaces import get_s3_client

    health_status = {"status": "healthy", "timestamp": time.time(), "checks": {}}

    all_healthy = True

    # Check API
    health_status["checks"]["api"] = {"status": "healthy", "message": "API is running"}

    # Check database
    try:
        from app.core.config import get_settings

        current_settings = get_settings()

        # Try to create a direct connection for health check
        import asyncpg

        conn = await asyncpg.connect(dsn=current_settings.DATABASE_URL)
        await conn.fetchval("SELECT 1")
        await conn.close()

        # Also check pool if available
        pool_info = {}
        if _pool:
            pool_size = _pool.get_size()
            pool_max = _pool.get_max_size()
            pool_idle = _pool.get_idle_size()
            pool_info = {
                "size": pool_size,
                "max": pool_max,
                "idle": pool_idle,
                "active": pool_size - pool_idle,
            }

        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database is accessible",
            "pool": pool_info,
        }
    except Exception as e:
        all_healthy = False
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database check failed: {e!s}",
        }

    # Check storage (MinIO/S3)
    try:
        from app.core.config import get_settings

        current_settings = get_settings()
        s3_client = get_s3_client()
        # Try to list buckets to verify connectivity
        s3_client.list_buckets()

        health_status["checks"]["storage"] = {
            "status": "healthy",
            "message": "Storage is accessible",
            "endpoint": current_settings.SPACES_ENDPOINT,
            "bucket": current_settings.SPACES_BUCKET,
        }
    except Exception as e:
        # Storage failure is not critical - mark as degraded but don't fail health check
        health_status["checks"]["storage"] = {
            "status": "degraded",
            "message": f"Storage check warning: {e!s}",
        }
        # Note: We don't set all_healthy = False for storage issues
        # as the API can still function without it

    # Set overall status
    if not all_healthy:
        health_status["status"] = "unhealthy"
        return error_response(
            message="Health check failed", data=health_status, status_code=503
        )

    return success_response(data=health_status)


@app.get("/cors-test")
async def cors_test():
    """CORS test endpoint."""
    from app.core.responses import success_response

    return success_response(
        data={
            "message": "CORS is working!",
            "allowed_origins": settings.cors_origins_list
            if settings.ENVIRONMENT != "development"
            else ["*"],
            "environment": settings.ENVIRONMENT,
        }
    )
