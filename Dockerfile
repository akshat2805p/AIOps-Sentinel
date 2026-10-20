# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies (build tools, libpq for postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements first for caching
COPY backend/requirements.txt /app/backend_requirements.txt
COPY ml/requirements.txt /app/ml_requirements.txt

RUN pip install --no-cache-dir -r /app/backend_requirements.txt && \
    pip install --no-cache-dir -r /app/ml_requirements.txt

# Copy project files
COPY . /app

# Ensure non-root user for security
RUN adduser --disabled-password --gecos "" sentineluser && \
    chown -R sentineluser:sentineluser /app
USER sentineluser

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8080"]
