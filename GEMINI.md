# SDIGdata Backend

## Project Overview

This project is the backend for SDIGdata, a data collection platform for Metropolitan Assemblies. It is a FastAPI application written in Python, designed to power both web dashboards and mobile clients.

**Key Technologies:**

*   **Framework:** FastAPI
*   **Database:** PostgreSQL
*   **Database Driver:** psycopg
*   **Migrations:** Yoyo
*   **Authentication:** JWT (python-jose) + bcrypt
*   **Storage:** DigitalOcean Spaces / MinIO (S3-compatible)
*   **Package Manager:** uv
*   **Deployment:** Docker + CapRover

**Architecture:**

The application follows a standard FastAPI project structure.

*   `app/main.py`: The main FastAPI application entry point.
*   `app/core/`: Core application logic, including configuration, database connection, and security.
*   `app/api/`: API routes for different resources (auth, organizations, forms, etc.).
*   `app/services/`: Database operations (raw SQL).
*   `app/utils/`: Utility functions, such as CSV export and S3 storage.
*   `migrations/`: Database migration scripts.

## Building and Running

### Docker (Recommended for Local Development)

1.  **Start services:**
    ```bash
    docker-compose up -d
    ```

2.  **View logs:**
    ```bash
    docker-compose logs -f api
    ```

The API will be available at `http://localhost:8000`.

### Local Development (Without Docker)

1.  **Install dependencies:**
    ```bash
    uv sync
    ```

2.  **Apply migrations:**
    ```bash
    uv run yoyo apply --database "postgresql://..." migrations
    ```

3.  **Start the development server:**
    ```bash
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```

### Testing

Run tests with the following command:

```bash
uv run pytest
```

## Development Conventions

*   **Package Management:** Dependencies are managed with `uv` and are listed in `pyproject.toml`.
*   **Database Migrations:** Database schema changes are handled by `yoyo-migrations`.
*   **Configuration:** Application settings are loaded from a `.env` file using `pydantic-settings`.
*   **Testing:** Tests are written with `pytest`.
