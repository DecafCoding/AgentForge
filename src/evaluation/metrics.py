"""
Ragas metric definitions for agent evaluation.

Defines the default metric sets for unsupervised evaluation (no ground truth
required) and supervised evaluation (ground truth annotations available).
Import DEFAULT_METRICS or SUPERVISED_METRICS into the pipeline module.

This module belongs to the Evaluation layer.
"""

# ---------------------------------------------------------------------------
# Metric imports
#
# Ragas 0.4.x exposes pre-instantiated metric instances from ragas.metrics.
# The legacy import path is deprecated in favour of ragas.metrics.collections
# but both work. We use the stable top-level path for now.
# ---------------------------------------------------------------------------
from ragas.metrics import (
    _ResponseRelevancy as ResponseRelevancy,
)
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
)

response_relevancy = ResponseRelevancy()

# Metrics that work without ground_truth — use for automated evaluation.
DEFAULT_METRICS = [
    faithfulness,  # Is the answer supported by the retrieved context?
    response_relevancy,  # Is the answer relevant to the question?
    context_precision,  # Are the retrieved contexts ranked by relevance?
]

# Additional metrics that require ground_truth / reference annotations.
SUPERVISED_METRICS = [
    context_recall,  # Did we retrieve all context needed to answer?
]
