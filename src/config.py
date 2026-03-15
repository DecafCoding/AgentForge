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

# Providers supported in Phase 1. Extend this set as new providers are added.
# The string must match Pydantic AI's provider prefix (e.g. "openai", "groq").
SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"openai", "groq"})

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


def get_model_string() -> str:
    """Return the model identifier Pydantic AI expects for the configured provider.

    Returns:
        A provider-prefixed model string (e.g. ``"openai:gpt-4o"`` or
        ``"groq:llama-3.1-70b-versatile"``).
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

    _required_keys: dict[str, str] = {
        "openai": OPENAI_API_KEY,
        "groq": GROQ_API_KEY,
    }
    key = _required_keys.get(MODEL_PROVIDER, "")
    if not key:
        logger.warning(
            "No API key found for provider '%s'. "
            "Set %s in your environment.",
            MODEL_PROVIDER,
            f"{'OPENAI_API_KEY' if MODEL_PROVIDER == 'openai' else 'GROQ_API_KEY'}",
        )
