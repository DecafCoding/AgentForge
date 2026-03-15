"""
LangGraph node functions for the multi-agent workflow.

Each async function wraps a Pydantic AI agent call, updates WorkflowState,
and records a Langfuse child span. Nodes receive the full WorkflowState and
return a dict of partial updates — LangGraph merges these back into state.

The synchronous should_continue function drives conditional routing after
the analysis node based on quality_score.

This module belongs to the Orchestration layer. Allowed imports:
pydantic_ai, langfuse, src.agent.*, src.observability. Forbidden:
apscheduler, httpx.
"""

import logging

from src.agent.analysis_agent import AnalysisAgentOutput, analysis_agent
from src.agent.research_agent import ResearchAgentOutput, research_agent
from src.agent.synthesis_agent import synthesis_agent
from src.observability.tracing import get_client as get_langfuse
from src.orchestration.state import AnalysisOutput, ResearchOutput, WorkflowState

logger = logging.getLogger(__name__)


async def research_node(state: WorkflowState) -> dict:
    """Run the research agent and return findings as a state update.

    First node in the workflow. Queries the video database to gather raw
    findings. Returns a partial state dict with research_output and an
    incremented steps_completed.
    """
    logger.info("research_node start", extra={"query": state.query[:80]})
    lf = get_langfuse()

    span = None
    if lf and state.trace_id:
        span = lf.span(
            name="research_node",
            trace_id=state.trace_id,
            input={"query": state.query},
        )

    try:
        result = await research_agent.run(state.query, deps=state.pool)
        usage = result.usage()
        output: ResearchAgentOutput = result.output

        logger.info(
            "research_node complete",
            extra={"findings": len(output.findings), "confidence": output.confidence},
        )

        if span:
            span.end(
                output=output.model_dump(),
                usage={
                    "input": usage.request_tokens or 0,
                    "output": usage.response_tokens or 0,
                    "total": usage.total_tokens or 0,
                    "unit": "TOKENS",
                },
            )

        return {
            "research_output": ResearchOutput(
                findings=output.findings,
                sources=output.sources,
                confidence=output.confidence,
            ),
            "steps_completed": state.steps_completed + 1,
        }

    except Exception as exc:
        if span:
            span.end(level="ERROR", status_message=str(exc))
        logger.error("research_node failed", extra={"error": str(exc)})
        raise


async def analysis_node(state: WorkflowState) -> dict:
    """Evaluate research quality and return an analysis update.

    Second node in the workflow. Evaluates research completeness and assigns
    a quality_score that drives conditional routing via should_continue.
    """
    logger.info("analysis_node start")
    lf = get_langfuse()

    span = None
    if lf and state.trace_id:
        span = lf.span(
            name="analysis_node",
            trace_id=state.trace_id,
            input={
                "research_findings": state.research_output.findings
                if state.research_output
                else [],
            },
        )

    research_text = (
        "\n".join(state.research_output.findings)
        if state.research_output
        else "No research available."
    )
    prompt = (
        f"Original query: {state.query}\n\n"
        f"Research findings:\n{research_text}\n\n"
        "Evaluate whether these findings are sufficient to answer the query."
    )

    try:
        result = await analysis_agent.run(prompt, deps=state.pool)
        usage = result.usage()
        output: AnalysisAgentOutput = result.output

        logger.info(
            "analysis_node complete",
            extra={"quality_score": output.quality_score, "gaps": len(output.gaps)},
        )

        if span:
            span.end(
                output=output.model_dump(),
                usage={
                    "input": usage.request_tokens or 0,
                    "output": usage.response_tokens or 0,
                    "total": usage.total_tokens or 0,
                    "unit": "TOKENS",
                },
            )

        return {
            "analysis_output": AnalysisOutput(
                assessment=output.assessment,
                gaps=output.gaps,
                quality_score=output.quality_score,
                confidence=output.confidence,
            ),
        }

    except Exception as exc:
        if span:
            span.end(level="ERROR", status_message=str(exc))
        logger.error("analysis_node failed", extra={"error": str(exc)})
        raise


async def synthesis_node(state: WorkflowState) -> dict:
    """Synthesise research and analysis into the final structured answer.

    Terminal node. Combines research findings and analysis assessment into
    a well-cited AgentResponse that is returned to the API caller.
    """
    logger.info("synthesis_node start")
    lf = get_langfuse()

    span = None
    if lf and state.trace_id:
        span = lf.span(
            name="synthesis_node",
            trace_id=state.trace_id,
            input={"query": state.query},
        )

    research_text = (
        "\n".join(state.research_output.findings)
        if state.research_output
        else "No research available."
    )
    analysis_text = (
        state.analysis_output.assessment if state.analysis_output else "No analysis."
    )
    prompt = (
        f"Original query: {state.query}\n\n"
        f"Research findings:\n{research_text}\n\n"
        f"Analysis:\n{analysis_text}\n\n"
        "Synthesise a final answer with cited sources."
    )

    try:
        result = await synthesis_agent.run(prompt, deps=state.pool)
        usage = result.usage()
        output = result.output

        logger.info(
            "synthesis_node complete",
            extra={"sources": len(output.sources), "confidence": output.confidence},
        )

        if span:
            span.end(
                output=output.model_dump(),
                usage={
                    "input": usage.request_tokens or 0,
                    "output": usage.response_tokens or 0,
                    "total": usage.total_tokens or 0,
                    "unit": "TOKENS",
                },
            )

        return {
            "final_answer": output.answer,
            "final_sources": [s.video_id for s in output.sources],
            "final_confidence": output.confidence,
        }

    except Exception as exc:
        if span:
            span.end(level="ERROR", status_message=str(exc))
        logger.error("synthesis_node failed", extra={"error": str(exc)})
        raise


def should_continue(state: WorkflowState) -> str:
    """Decide routing after the analysis node based on quality_score.

    Returns one of:
    - "continue" — quality is sufficient, proceed to synthesis
    - "retry"    — quality too low, repeat research (up to max_retries)
    - "end"      — quality too low and max retries exhausted

    This function must be synchronous — LangGraph conditional edge
    functions cannot be async.

    Args:
        state: Current workflow state carrying analysis_output and step counts.

    Returns:
        Routing key matching an entry in the conditional edges map.
    """
    if state.analysis_output is None:
        return "continue"

    if state.analysis_output.quality_score < 0.3:
        if state.steps_completed < state.max_retries:
            logger.info(
                "Analysis quality below threshold — retrying research",
                extra={
                    "quality_score": state.analysis_output.quality_score,
                    "steps": state.steps_completed,
                },
            )
            return "retry"
        logger.warning(
            "Max retries reached with low quality — terminating",
            extra={"steps": state.steps_completed},
        )
        return "end"

    return "continue"
