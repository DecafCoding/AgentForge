"""
Multi-agent orchestration layer.

Contains the LangGraph workflow graph, state model, and node functions that
coordinate multiple Pydantic AI agents. This layer orchestrates agents but
does not implement agent reasoning itself.

Allowed imports: pydantic_ai, langfuse, src.agent, src.db, src.config,
src.observability.
Forbidden imports: apscheduler, httpx.

This module belongs to the Agent Layer (same level) and sits above the
Data Layer (src/db) in the dependency hierarchy.
"""
