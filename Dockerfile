# =============================================================================
# Stage 1: Builder — install dependencies with uv
# =============================================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Copy dependency manifest and install deps before source code.
# This layer is cached as long as pyproject.toml doesn't change.
COPY pyproject.toml ./

# Install dependencies only (not the project itself) so the source
# copy below doesn't bust the dependency cache layer.
RUN uv sync --no-dev --no-install-project

# Copy source and install the project into the same venv.
COPY src/ src/
RUN uv sync --no-dev

# =============================================================================
# Stage 2: Runtime — slim image with only what is needed to run the app
# =============================================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Pull the fully installed virtual environment from the builder.
COPY --from=builder /app/.venv /app/.venv

# Copy application source.
COPY src/ src/

# Prepend the venv to PATH so all uv-installed binaries are available.
ENV PATH="/app/.venv/bin:$PATH"

# Crawl4AI requires Playwright browsers for web scraping.
# Install system deps and browsers. The || true prevents build failure
# in minimal environments where browsers cannot be installed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*
RUN crawl4ai-setup || true

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
