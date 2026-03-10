# =============================================================================
# Dive Service Management - Dockerfile
# Multi-stage build for Python 3.12 on ARM64 and x86-64
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build dependencies (includes compilers for mysqlclient)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime image (no compilers, smaller image)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Runtime dependencies for mysqlclient (shared library, no compiler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    libffi8 \
    curl \
    # -----------------------------------------------------------------------
    # WeasyPrint dependencies (OPTIONAL - uncomment for complex PDF layouts)
    # These add ~150MB to the image and are slow to install on ARM64.
    # For lightweight Pi deployments, leave commented and use fpdf2 only.
    # -----------------------------------------------------------------------
    # libpango-1.0-0 \
    # libpangocairo-1.0-0 \
    # libgdk-pixbuf2.0-0 \
    # libcairo2 \
    # libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p /app/uploads/logos /app/uploads/imports /app/uploads/exports \
             /app/uploads/attachments /app/logs /app/instance

# Create non-root user and set ownership
RUN useradd -m -r -s /bin/bash dsm \
    && chown -R dsm:dsm /app

USER dsm

EXPOSE 8080

# Health check: verify the /health endpoint responds
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run migrations and seed on startup, then start gunicorn
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "2", \
     "--threads", "4", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--timeout", "120", \
     "app:create_app()"]
