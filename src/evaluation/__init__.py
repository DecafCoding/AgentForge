"""
Agent quality evaluation layer.

Provides Ragas evaluation pipelines for measuring agent output quality
against real interactions logged in Langfuse. This layer imports from
src.config and src.db.queries only — no agent or collector imports.
"""
