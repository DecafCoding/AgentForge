"""
Collector module tests.

Covers the architectural boundary guarantee (zero LLM imports), pure
utility functions, and behaviour under common edge cases. External APIs
(YouTube Data API, transcript API) are mocked — no network calls are made.
"""

import ast
import pathlib

# ---------------------------------------------------------------------------
# Architectural boundary
# ---------------------------------------------------------------------------


def test_collector_has_no_llm_imports():
    """Verify src/collector/ contains no pydantic_ai or langfuse imports."""
    forbidden = {"pydantic_ai", "langfuse"}
    violations: list[str] = []

    collector_dir = pathlib.Path("src/collector")
    for py_file in sorted(collector_dir.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for pkg in forbidden:
                        if alias.name == pkg or alias.name.startswith(f"{pkg}."):
                            violations.append(
                                f"{py_file}:{node.lineno}: import {alias.name}"
                            )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for pkg in forbidden:
                    if module == pkg or module.startswith(f"{pkg}."):
                        violations.append(
                            f"{py_file}:{node.lineno}: from {module} import ..."
                        )

    assert not violations, (
        "Collector module imports LLM dependencies (boundary violation):\n"
        + "\n".join(violations)
    )


def test_agent_has_no_scheduler_or_http_imports():
    """Verify src/agent/ contains no apscheduler or httpx imports."""
    forbidden = {"apscheduler", "httpx"}
    violations: list[str] = []

    agent_dir = pathlib.Path("src/agent")
    for py_file in sorted(agent_dir.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for pkg in forbidden:
                        if alias.name == pkg or alias.name.startswith(f"{pkg}."):
                            violations.append(
                                f"{py_file}:{node.lineno}: import {alias.name}"
                            )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for pkg in forbidden:
                    if module == pkg or module.startswith(f"{pkg}."):
                        violations.append(
                            f"{py_file}:{node.lineno}: from {module} import ..."
                        )

    assert not violations, (
        "Agent module imports forbidden dependencies (boundary violation):\n"
        + "\n".join(violations)
    )


def test_orchestration_has_no_scheduler_or_http_imports():
    """Verify src/orchestration/ contains no apscheduler or httpx imports."""
    forbidden = {"apscheduler", "httpx"}
    violations: list[str] = []

    orchestration_dir = pathlib.Path("src/orchestration")
    for py_file in sorted(orchestration_dir.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for pkg in forbidden:
                        if alias.name == pkg or alias.name.startswith(f"{pkg}."):
                            violations.append(
                                f"{py_file}:{node.lineno}: import {alias.name}"
                            )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for pkg in forbidden:
                    if module == pkg or module.startswith(f"{pkg}."):
                        violations.append(
                            f"{py_file}:{node.lineno}: from {module} import ..."
                        )

    assert not violations, (
        "Orchestration module imports forbidden dependencies (boundary violation):\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# _safe_int utility
# ---------------------------------------------------------------------------


def test_safe_int_converts_valid_string():
    from src.collector.youtube import _safe_int

    assert _safe_int("42") == 42


def test_safe_int_returns_none_for_none():
    from src.collector.youtube import _safe_int

    assert _safe_int(None) is None


def test_safe_int_returns_none_for_non_numeric_string():
    from src.collector.youtube import _safe_int

    assert _safe_int("not-a-number") is None


def test_safe_int_handles_zero():
    from src.collector.youtube import _safe_int

    assert _safe_int("0") == 0


# ---------------------------------------------------------------------------
# YouTubeCollector edge cases
# ---------------------------------------------------------------------------


async def test_collector_skips_when_api_key_is_empty(mock_pool):
    """Collector returns 0 and does not call the API when no key is set."""
    from src.collector.youtube import YouTubeCollector

    collector = YouTubeCollector(pool=mock_pool, api_key="")
    count = await collector.collect()

    assert count == 0
    mock_pool.fetch.assert_not_called()


async def test_collector_skips_when_no_channels_in_db(mock_pool):
    """Collector returns 0 without calling YouTube when no channels exist."""
    from src.collector.youtube import YouTubeCollector

    # mock_pool.fetch returns [] by default — no channel rows.
    collector = YouTubeCollector(pool=mock_pool, api_key="fake-key")
    count = await collector.collect()

    assert count == 0
