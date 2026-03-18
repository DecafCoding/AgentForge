"""
Evaluation dataset creation from Langfuse traces.

Extracts agent interactions (question → retrieved contexts → answer) from
Langfuse traces and converts them into a Ragas-compatible EvaluationDataset.
Each Langfuse trace becomes one SingleTurnSample.

This module belongs to the Evaluation layer.
"""

import logging

from pydantic import BaseModel
from ragas import EvaluationDataset
from ragas.dataset_schema import SingleTurnSample

logger = logging.getLogger(__name__)


class EvalSample(BaseModel):
    """Intermediate representation of one evaluation sample before Ragas conversion."""

    question: str
    answer: str
    contexts: list[str]
    ground_truth: str | None = None


def create_dataset_from_langfuse(
    limit: int = 100,
    trace_name: str | None = None,
) -> EvaluationDataset:
    """Extract agent interactions from Langfuse traces into a Ragas dataset.

    Fetches traces from Langfuse, extracts input/output, and collects context
    strings from tool call child spans. Returns an EvaluationDataset ready for
    aevaluate(). Returns an empty dataset if Langfuse is not configured.

    Args:
        limit: Maximum number of traces to include.
        trace_name: Optional filter for trace name (e.g., "agent_run").

    Returns:
        EvaluationDataset with one SingleTurnSample per valid Langfuse trace.
    """
    from src.observability.tracing import get_client

    lf = get_client()
    if lf is None:
        logger.warning("Langfuse not configured — returning empty evaluation dataset")
        return EvaluationDataset(samples=[])

    traces = lf.fetch_traces(name=trace_name, limit=limit)
    logger.info(
        "Fetched traces for evaluation",
        extra={"count": len(traces.data), "trace_name": trace_name},
    )

    samples = []
    for trace in traces.data:
        question = (trace.input or {}).get("question", "")
        answer = (trace.output or {}).get("answer", "")

        if not question or not answer:
            logger.debug(
                "Skipping trace with missing input/output",
                extra={"trace_id": trace.id},
            )
            continue

        # Extract context strings from tool call child spans.
        contexts: list[str] = []
        try:
            observations = lf.fetch_observations(trace_id=trace.id)
            for obs in observations.data:
                if obs.type == "TOOL" and obs.output:
                    contexts.append(str(obs.output))
        except Exception as exc:
            logger.warning(
                "Failed to fetch observations for trace",
                extra={"trace_id": trace.id, "error": str(exc)},
            )

        samples.append(
            SingleTurnSample(
                user_input=question,
                response=answer,
                # Ragas requires a non-empty list — default to [""] when no tool
                # contexts were captured so evaluation still runs.
                retrieved_contexts=contexts if contexts else [""],
            )
        )

    logger.info("Built evaluation dataset", extra={"samples": len(samples)})
    return EvaluationDataset(samples=samples)
