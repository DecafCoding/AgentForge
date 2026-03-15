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

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
