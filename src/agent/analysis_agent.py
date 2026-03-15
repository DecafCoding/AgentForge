"""
Analysis agent — quality evaluation node for the multi-agent workflow.

Evaluates the quality of research output and identifies gaps. Its
quality_score drives conditional routing in the LangGraph workflow:
scores below 0.3 trigger a research retry (up to max_retries times).

This module belongs to the Agent layer and must not import apscheduler,
httpx, or any collector dependency.
"""

import logging

from asyncpg import Pool
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.config import get_model_string

logger = logging.getLogger(__name__)


class AnalysisAgentOutput(BaseModel):
    """Structured output from the analysis agent.

    assessment: Prose evaluation of the research quality.
    gaps: Topics the research did not cover but should have.
    quality_score: Numeric quality rating (< 0.3 triggers a research retry).
    confidence: Self-assessed confidence in this analysis (0-1).
    """

    assessment: str
    gaps: list[str]
    quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Research quality: 1.0 = comprehensive, 0.3 = needs retry.",
    )
    confidence: float = Field(ge=0.0, le=1.0)


analysis_agent: Agent[Pool, AnalysisAgentOutput] = Agent(
    model=get_model_string(),
    deps_type=Pool,
    output_type=AnalysisAgentOutput,
    defer_model_check=True,
    system_prompt=(
        "You are a quality analysis agent. You evaluate research findings and "
        "determine whether they are sufficient to answer the original query.\n\n"
        "Guidelines:\n"
        "- Assess whether the findings address the query completely.\n"
        "- List any gaps: important aspects of the query not covered.\n"
        "- Set quality_score: 0.8-1.0 if findings are comprehensive, "
        "0.4-0.8 if partial but workable, 0.0-0.3 if insufficient (retry needed).\n"
        "- Set confidence based on how certain you are of your assessment."
    ),
    tools=[],
)
