"""
API request and response schemas.

Pydantic models that define the shape of HTTP requests and responses.
Kept separate from agent-layer models to allow the API contract to evolve
independently. Source is imported from src.agent.models — the shared type
that both the agent and API agree on — rather than duplicated here.
This module belongs to the Application Layer.
"""

from pydantic import BaseModel, Field

from src.agent.models import Source


class AskRequest(BaseModel):
    """Request body for POST /api/ask."""

    question: str = Field(
        min_length=1,
        description="The natural-language question to send to the agent.",
    )


class AskResponse(BaseModel):
    """Response body for POST /api/ask."""

    answer: str
    sources: list[Source]


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
