"""
Ragas evaluation pipeline.

Wraps Ragas aevaluate() for async use. Returns a flat dict of
metric name → float score suitable for storage and display.

This module belongs to the Evaluation layer.
"""

import logging

from ragas import EvaluationDataset, aevaluate

from src.config import EVAL_MODEL, OPENAI_API_KEY
from src.evaluation.metrics import DEFAULT_METRICS, SUPERVISED_METRICS

logger = logging.getLogger(__name__)


async def run_evaluation(
    dataset: EvaluationDataset,
    metrics: list | None = None,
) -> dict[str, float]:
    """Run Ragas evaluation on a dataset of agent interactions.

    Uses aevaluate() (truly async) rather than evaluate() (sync + nest_asyncio)
    to avoid event loop conflicts in an async application.

    Args:
        dataset: Ragas EvaluationDataset built from real agent interactions.
        metrics: Metric list to compute. Defaults to DEFAULT_METRICS. Adds
                 SUPERVISED_METRICS automatically when reference is present
                 in the samples.

    Returns:
        Dict mapping metric name to average score across the dataset.
        Returns empty dict if dataset is empty.
    """
    if len(dataset) == 0:
        logger.warning("Empty evaluation dataset — returning zero scores")
        return {}

    if metrics is None:
        has_reference = any(s.reference is not None for s in dataset.samples)
        metrics = (
            DEFAULT_METRICS + SUPERVISED_METRICS if has_reference else DEFAULT_METRICS
        )

    logger.info(
        "Running evaluation",
        extra={
            "samples": len(dataset),
            "metrics": [getattr(m, "name", str(m)) for m in metrics],
        },
    )

    # Wrap the configured model as a Ragas-compatible LLM judge.
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    llm = LangchainLLMWrapper(ChatOpenAI(model=EVAL_MODEL, api_key=OPENAI_API_KEY))

    result = await aevaluate(dataset=dataset, metrics=metrics, llm=llm)
    scores: dict[str, float] = result.to_pandas().mean().to_dict()

    logger.info("Evaluation complete", extra={"scores": scores})
    return scores
