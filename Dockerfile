FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml ./

# Install dependencies (without dev for production)
RUN uv sync --no-dev

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 8000

# Start server (migrations handled separately)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
