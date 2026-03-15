"""
Research agent — data gathering node for the multi-agent workflow.

Queries the YouTube video database and gathers raw findings. Used as
the first node in the LangGraph research pipeline. Reuses the existing
agent tools from src.agent.tools — no SQL or HTTP calls directly.

This module belongs to the Agent layer and must not import apscheduler,
httpx, or any collector dependency.
"""

import logging

from asyncpg import Pool
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.agent.tools import (
    get_channel_statistics,
    query_recent_videos,
    search_videos_by_query,
)
from src.config import get_model_string

logger = logging.getLogger(__name__)


class ResearchAgentOutput(BaseModel):
    """Structured output from the research agent.

    findings: Key facts retrieved from the database relevant to the query.
    sources: Video IDs or titles that support the findings.
    confidence: Self-assessed confidence that findings are complete (0-1).
    """

    findings: list[str]
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


research_agent: Agent[Pool, ResearchAgentOutput] = Agent(
    model=get_model_string(),
    deps_type=Pool,
    output_type=ResearchAgentOutput,
    defer_model_check=True,
    system_prompt=(
        "You are a research agent. Your job is to query the YouTube video database "
        "and gather all relevant information for the given query.\n\n"
        "Guidelines:\n"
        "- Use your tools to retrieve data. Do not guess or invent findings.\n"
        "- List concrete findings (facts, titles, dates, counts) in 'findings'.\n"
        "- List the video IDs or titles you used as evidence in 'sources'.\n"
        "- If the database has no relevant data, set findings to an empty list "
        "and confidence to 0.1.\n"
        "- Set confidence based on how complete the data is: "
        "1.0 for comprehensive, 0.5 for partial, 0.1 for minimal or none."
    ),
    tools=[query_recent_videos, search_videos_by_query, get_channel_statistics],
)
