"""
Web search integration layer.

Provides async web search capabilities via external search APIs.
Supports Brave Search (cloud API) and SearXNG (self-hosted).
The active provider is selected via the SEARCH_PROVIDER config var.
This module is imported by agent tools — it must not import collector
or scheduler dependencies.
"""
