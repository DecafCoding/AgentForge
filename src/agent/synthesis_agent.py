"""
Synthesis agent — final answer node for the multi-agent workflow.

Combines research findings and quality analysis into a structured final
answer with cited sources. Produces the AgentResponse returned to the
API caller. Reuses AgentResponse from src.agent.models for consistency
with Pattern 1 — both patterns return the same output shape.

This module belongs to the Agent layer and must not import apscheduler,
httpx, or any collector dependency.
"""

import logging

from asyncpg import Pool
from pydantic_ai import Agent

from src.agent.models import AgentResponse
from src.config import get_model_string

logger = logging.getLogger(__name__)


synthesis_agent: Agent[Pool, AgentResponse] = Agent(
    model=get_model_string(),
    deps_type=Pool,
    output_type=AgentResponse,
    defer_model_check=True,
    system_prompt=(
        "You are a synthesis agent. You combine research findings and quality "
        "analysis into a clear, well-cited final answer.\n\n"
        "Guidelines:\n"
        "- Write a direct, informative answer to the original query.\n"
        "- Populate 'sources' with every video title and ID referenced.\n"
        "- Set confidence to reflect how well the data supports the answer.\n"
        "- Do not include internal workflow details in the answer — write for "
        "the end user, not for the pipeline."
    ),
    tools=[],
)
