"""
Agent-layer data models.

Pydantic models shared between the agent, its tools, and the API layer.
Defining them here keeps the API schema decoupled from internal tool
implementation details. This module belongs to the Agent Layer.
"""

from pydantic import BaseModel, Field


class Source(BaseModel):
    """A cited source returned with an agent answer."""

    title: str
    video_id: str
    url: str


class AgentResponse(BaseModel):
    """Structured output returned by the YouTube research agent.

    The agent populates ``sources`` from the tool results it used to
    construct the answer. ``confidence`` is a self-assessed score the
    model assigns based on how well the available data supports the answer.
    """

    answer: str
    sources: list[Source]
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model's self-assessed confidence in the answer (0–1).",
    )
