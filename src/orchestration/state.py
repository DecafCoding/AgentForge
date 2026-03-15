"""
Graph state models for the multi-agent workflow.

WorkflowState flows between LangGraph nodes. Each node receives the full
state and returns a dict of fields to update — LangGraph merges these back
into the state. Non-serialisable dependencies (asyncpg Pool) are carried
via arbitrary_types_allowed and excluded from serialisation.

This module belongs to the Orchestration layer.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchOutput(BaseModel):
    """Structured output from the research agent node."""

    findings: list[str]
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class AnalysisOutput(BaseModel):
    """Structured output from the analysis agent node.

    quality_score drives conditional routing in the graph: values below
    0.3 trigger a research retry (up to max_retries times).
    """

    assessment: str
    gaps: list[str]
    quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Research quality rating. < 0.3 triggers retry.",
    )
    confidence: float = Field(ge=0.0, le=1.0)


class WorkflowState(BaseModel):
    """State that flows through the multi-agent research workflow graph.

    Passed between LangGraph nodes. Each node receives this model instance
    and returns a dict of partial updates. Non-serialisable fields (pool)
    use Field(exclude=True) and are carried in-memory only — LangGraph
    checkpointing is not used in Phase 2, so pool serialisation is never
    attempted.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input
    query: str

    # Runtime dependency — injected by run_workflow(), not serialised.
    # Typed as Any so test doubles (MagicMock) can be injected without
    # Pydantic raising an is_instance_of validation error.
    pool: Any = Field(exclude=True)

    # Observability — parent Langfuse trace ID for child spans
    trace_id: str | None = None

    # Research phase output
    research_output: ResearchOutput | None = None

    # Analysis phase output
    analysis_output: AnalysisOutput | None = None

    # Synthesis phase output
    final_answer: str | None = None
    final_sources: list[str] | None = None
    final_confidence: float | None = None

    # Workflow metadata
    steps_completed: int = 0
    max_retries: int = 3
