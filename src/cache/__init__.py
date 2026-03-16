"""
Caching layer.

Provides async caching via Redis/Valkey for measured performance
bottlenecks. Disabled by default (CACHE_ENABLED=false). The cache
is transparent — the system works identically without it, just slower.
This module must not import agent, collector, or LLM dependencies.
"""
