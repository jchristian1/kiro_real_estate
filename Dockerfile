# Multi-stage Dockerfile for the Lead Intake & Workflow Platform
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python runtime dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY gmail_lead_sync/ ./gmail_lead_sync/
COPY api/ ./api/
COPY migrations/ ./migrations/
COPY worker/ ./worker/
COPY scripts/ ./scripts/
COPY alembic.ini ./

# Create directory for database and static files
RUN mkdir -p /data /app/static

# Environment defaults (override at runtime via env_file or -e flags)
# DATABASE_URL is intentionally not set here — it must be supplied explicitly.
# Use postgresql://... for any multi-process deployment.
ENV STATIC_FILES_DIR=/app/static \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    LOG_LEVEL=INFO

EXPOSE 8000

# Entrypoint: run migrations then start server
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

COPY docker-worker-entrypoint.sh ./
RUN chmod +x docker-worker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
