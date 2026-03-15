"""
Langfuse observability integration.

Initialises the Langfuse v2 client and exposes low-level tracing primitives.
Higher-level wrappers that combine the agent with tracing live in
src/agent/agent.py, since the agent layer is permitted to import from here
but not vice versa.

When LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY are not configured the
client is None and all tracing calls are no-ops — useful in local
development without a running Langfuse instance.
"""

import logging

from langfuse import Langfuse

from src.config import LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY

logger = logging.getLogger(__name__)

# Module-level singleton. None when Langfuse is not configured.
_client: Langfuse | None = None


def get_client() -> Langfuse | None:
    """Return the Langfuse client, initialising it on first call.

    Returns:
        A live Langfuse client, or None if keys are not configured.
    """
    global _client

    if _client is not None:
        return _client

    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        logger.warning(
            "Langfuse keys not configured — tracing disabled. "
            "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable."
        )
        return None

    _client = Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )
    logger.info("Langfuse client initialised", extra={"host": LANGFUSE_HOST})
    return _client


def flush() -> None:
    """Flush any buffered Langfuse events to the server.

    Call this after agent runs that are not already handled by
    run_agent() in src/agent/agent.py.
    """
    client = get_client()
    if client is not None:
        client.flush()
