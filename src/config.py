"""
Application configuration.

Loads all environment variables via python-dotenv and exposes them as
typed module-level constants. All other modules import from here — no
module should call os.getenv directly. This module belongs to the
Configuration layer and has no local application imports.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# LLM Provider
# ---------------------------------------------------------------------------

# Supported providers. The string must match Pydantic AI's provider prefix.
SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"openai", "groq", "ollama"})

MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "openai")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/agentforge",
)

# ---------------------------------------------------------------------------
# Langfuse (Observability)
# ---------------------------------------------------------------------------
LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "http://localhost:3001")
LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")

# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
COLLECTION_INTERVAL_MINUTES: int = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "60"))

# ---------------------------------------------------------------------------
# Memory (Phase 3)
# ---------------------------------------------------------------------------
MEMORY_ENABLED: bool = os.getenv("MEMORY_ENABLED", "true").lower() == "true"
MEMORY_MODEL: str = os.getenv("MEMORY_MODEL", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Web Scraping (Phase 3)
# ---------------------------------------------------------------------------
SCRAPE_URLS: list[str] = [
    u.strip() for u in os.getenv("SCRAPE_URLS", "").split(",") if u.strip()
]
SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "360"))

# ---------------------------------------------------------------------------
# Web Search (Phase 3)
# ---------------------------------------------------------------------------
BRAVE_SEARCH_API_KEY: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
BRAVE_SEARCH_ENABLED: bool = os.getenv("BRAVE_SEARCH_ENABLED", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Ollama (Phase 4)
# ---------------------------------------------------------------------------
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Pydantic AI's OllamaProvider reads OLLAMA_BASE_URL from the environment.
# Mirror OLLAMA_HOST so developers only configure one variable.
if MODEL_PROVIDER == "ollama" and not os.getenv("OLLAMA_BASE_URL"):
    os.environ["OLLAMA_BASE_URL"] = OLLAMA_HOST

# ---------------------------------------------------------------------------
# Search Provider (Phase 4)
# ---------------------------------------------------------------------------
SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "brave")

# ---------------------------------------------------------------------------
# SearXNG (Phase 4)
# ---------------------------------------------------------------------------
SEARXNG_HOST: str = os.getenv("SEARXNG_HOST", "http://localhost:8080")

# ---------------------------------------------------------------------------
# Caching (Phase 4)
# ---------------------------------------------------------------------------
CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "false").lower() == "true"
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Evaluation (Phase 5)
# ---------------------------------------------------------------------------
EVAL_MODEL: str = os.getenv("EVAL_MODEL", "gpt-4o")
EVAL_DATASET_LIMIT: int = int(os.getenv("EVAL_DATASET_LIMIT", "100"))

# ---------------------------------------------------------------------------
# MCP Server (Phase 5)
# ---------------------------------------------------------------------------
MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "stdio")
MCP_PORT: int = int(os.getenv("MCP_PORT", "8001"))

# ---------------------------------------------------------------------------
# Frontend & Deployment (Phase 6)
# ---------------------------------------------------------------------------
CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
DOMAIN: str = os.getenv("DOMAIN", "localhost")


def get_model_string() -> str:
    """Return the model identifier Pydantic AI expects for the configured provider.

    Returns:
        A provider-prefixed model string (e.g. ``"openai:gpt-4o"``,
        ``"groq:llama-3.1-70b-versatile"``, or ``"ollama:llama3.1:8b"``).
    """
    return f"{MODEL_PROVIDER}:{MODEL_NAME}"


def validate_provider_config() -> None:
    """Log warnings for common provider misconfiguration at startup.

    Does not raise — a missing key will surface as an authentication error
    on the first agent call, which produces a clearer message than a startup
    crash. This function just surfaces the problem earlier via logging.
    """
    import logging

    logger = logging.getLogger(__name__)

    if MODEL_PROVIDER not in SUPPORTED_PROVIDERS:
        logger.warning(
            "MODEL_PROVIDER '%s' is not in the supported set %s. "
            "Pydantic AI may raise at runtime if the provider string is unrecognised.",
            MODEL_PROVIDER,
            sorted(SUPPORTED_PROVIDERS),
        )

    # Ollama does not require an API key — only check cloud providers.
    _required_keys: dict[str, str] = {
        "openai": OPENAI_API_KEY,
        "groq": GROQ_API_KEY,
    }
    if MODEL_PROVIDER in _required_keys:
        key = _required_keys[MODEL_PROVIDER]
        if not key:
            env_var = "OPENAI_API_KEY" if MODEL_PROVIDER == "openai" else "GROQ_API_KEY"
            logger.warning(
                "No API key found for provider '%s'. Set %s in your environment.",
                MODEL_PROVIDER,
                env_var,
            )
