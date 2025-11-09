FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy all files (we need the full project structure for hatchling)
COPY . .

# Install dependencies with dev dependencies for testing
RUN uv sync

# Expose port
EXPOSE 8000

# Start server (migrations handled separately)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
