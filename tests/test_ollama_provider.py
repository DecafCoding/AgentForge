"""
Ollama provider configuration tests.

Verifies that Ollama is a valid provider in config, that get_model_string()
produces correct model strings, and that validate_provider_config() does
not warn for Ollama (which needs no API key).
"""

import logging
from unittest.mock import patch


def test_ollama_is_supported_provider():
    """Ollama is in the SUPPORTED_PROVIDERS set."""
    from src.config import SUPPORTED_PROVIDERS

    assert "ollama" in SUPPORTED_PROVIDERS


def test_supported_providers_includes_all_three():
    """SUPPORTED_PROVIDERS includes openai, groq, and ollama."""
    from src.config import SUPPORTED_PROVIDERS

    assert SUPPORTED_PROVIDERS == frozenset({"openai", "groq", "ollama"})


def test_get_model_string_returns_ollama_prefix():
    """get_model_string() returns 'ollama:model' for Ollama provider."""
    with (
        patch("src.config.MODEL_PROVIDER", "ollama"),
        patch("src.config.MODEL_NAME", "llama3.1:8b"),
    ):
        from src.config import get_model_string

        result = get_model_string()

    assert result == "ollama:llama3.1:8b"


def test_validate_provider_config_no_warning_for_ollama(caplog):
    """validate_provider_config() does not warn about missing keys for Ollama."""
    with (
        patch("src.config.MODEL_PROVIDER", "ollama"),
        patch(
            "src.config.SUPPORTED_PROVIDERS",
            frozenset({"openai", "groq", "ollama"}),
        ),
    ):
        with caplog.at_level(logging.WARNING):
            from src.config import validate_provider_config

            validate_provider_config()

    key_warnings = [
        r for r in caplog.records if "API key" in r.message or "No API key" in r.message
    ]
    assert len(key_warnings) == 0


def test_validate_provider_config_warns_for_openai_without_key(caplog):
    """validate_provider_config() warns when OpenAI key is missing."""
    with (
        patch("src.config.MODEL_PROVIDER", "openai"),
        patch("src.config.OPENAI_API_KEY", ""),
        patch(
            "src.config.SUPPORTED_PROVIDERS",
            frozenset({"openai", "groq", "ollama"}),
        ),
    ):
        with caplog.at_level(logging.WARNING):
            from src.config import validate_provider_config

            validate_provider_config()

    key_warnings = [r for r in caplog.records if "No API key" in r.message]
    assert len(key_warnings) == 1
