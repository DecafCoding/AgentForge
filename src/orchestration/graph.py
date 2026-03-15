"""
LangGraph workflow graph definition and public runner.

Assembles the three-node research → analysis → synthesis pipeline and
exposes run_workflow() as the single entry point used by the API layer.
run_workflow() creates the parent Langfuse trace, injects the trace_id
into WorkflowState for child spans, and invokes the compiled graph.

Important: graph.ainvoke() returns a dict, not a WorkflowState instance.
Access final fields with dict-style keys: result['final_answer'].

This module belongs to the Orchestration layer. The API layer may import
from here; this module must not import from src.api.
"""

import logging

from asyncpg import Pool
from langgraph.graph import END, START, StateGraph

from src.agent.models import AgentResponse, Source
from src.config import MODEL_NAME, MODEL_PROVIDER
from src.observability.tracing import get_client as get_langfuse
from src.orchestration.nodes import (
    analysis_node,
    research_node,
    should_continue,
    synthesis_node,
)
from src.orchestration.state import WorkflowState

logger = logging.getLogger(__name__)


def _build_graph() -> object:
    """Build and compile the multi-agent workflow graph.

    Returns:
        A compiled LangGraph StateGraph ready for async invocation.
    """
    workflow: StateGraph = StateGraph(WorkflowState)

    workflow.add_node("research", research_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("synthesis", synthesis_node)

    workflow.add_edge(START, "research")
    workflow.add_edge("research", "analysis")
    workflow.add_conditional_edges(
        "analysis",
        should_continue,
        {
            "continue": "synthesis",
            "retry": "research",
            "end": END,
        },
    )
    workflow.add_edge("synthesis", END)

    return workflow.compile()


# Compiled graph — built once at module import time.
# The Pool is NOT embedded in the graph; it is passed per-request via
# WorkflowState, so a single compiled graph instance is safe to reuse.
_graph = _build_graph()


async def run_workflow(query: str, pool: Pool) -> AgentResponse:
    """Run the multi-agent research workflow and return a structured answer.

    Creates a parent Langfuse trace spanning the full workflow. Each node
    records a child span under this trace. Gracefully no-ops if Langfuse
    is not configured.

    Args:
        query: The user's natural-language research query.
        pool: asyncpg connection pool injected into each agent node.

    Returns:
        AgentResponse with the synthesised answer, sources, and confidence.
        Returns a default low-confidence response if the workflow terminates
        early (quality too low, max retries reached).
    """
    lf = get_langfuse()
    trace = None
    trace_id: str | None = None

    if lf is not None:
        trace = lf.trace(
            name="multi-agent-workflow",
            input={"query": query},
            metadata={"provider": MODEL_PROVIDER, "model": MODEL_NAME},
        )
        trace_id = trace.id

    initial_state = WorkflowState(query=query, pool=pool, trace_id=trace_id)

    try:
        # ainvoke returns a dict of state field values, not a WorkflowState instance.
        final: dict = await _graph.ainvoke(initial_state)

        result = AgentResponse(
            answer=final.get("final_answer")
            or "Research did not produce sufficient findings.",
            sources=[
                Source(
                    title=vid,
                    video_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}",
                )
                for vid in (final.get("final_sources") or [])
            ],
            confidence=final.get("final_confidence") or 0.1,
        )

        if trace is not None:
            trace.update(
                output={"answer": result.answer},
                metadata={
                    "steps_completed": final.get("steps_completed", 0),
                },
            )

        logger.info(
            "Workflow complete",
            extra={
                "steps": final.get("steps_completed", 0),
                "confidence": result.confidence,
                "sources": len(result.sources),
            },
        )
        return result

    except Exception as exc:
        if trace is not None:
            trace.update(level="ERROR", status_message=str(exc))
        logger.error("Workflow failed", extra={"error": str(exc)})
        raise

    finally:
        if lf is not None:
            lf.flush()
