# syntax=docker/dockerfile:1

# ============================================================================
# Stage 1: Dependency builder with Astral uv
# ============================================================================
FROM python:3.11-slim-bookworm AS builder

# Copy uv binaries from official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation and copy mode for uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 1. Install dependencies first for maximum layer cache reuse
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# 2. Copy source and install project package into virtual environment
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ============================================================================
# Stage 2: Minimal, secure production runtime
# ============================================================================
FROM python:3.11-slim-bookworm AS runner

# Create non-root system group and user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy the compiled virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy runtime code, policy documents, fixtures, and versioned prompts
COPY src/ /app/src/
COPY data/ /app/data/
COPY prompts/ /app/prompts/
COPY pyproject.toml README.md /app/

# Set environment variables for virtual environment and unbuffered stdout/stderr
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

# Drop root privileges
USER appuser

# Expose HTTP port for API and Prometheus scraping
EXPOSE 8000

# Zero-dependency container health check using Python standard library
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)" || exit 1

# Start production ASGI server with uvicorn
CMD ["uvicorn", "runwise.service.app:app", "--host", "0.0.0.0", "--port", "8000"]
