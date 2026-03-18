"""Export agent interactions from Langfuse to a JSON file for offline evaluation.

Usage:
    uv run python scripts/export_dataset.py
    uv run python scripts/export_dataset.py --limit 50 --trace-name agent_run
    uv run python scripts/export_dataset.py --output eval_data.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Export evaluation dataset to JSON."""
    parser = argparse.ArgumentParser(
        description="Export agent interactions from Langfuse for offline evaluation"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of traces to export (default: 100)",
    )
    parser.add_argument(
        "--trace-name",
        type=str,
        default=None,
        help="Filter by trace name (e.g., 'agent_run')",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="eval_dataset.json",
        help="Output JSON file path (default: eval_dataset.json)",
    )
    args = parser.parse_args()

    from src.evaluation.dataset import create_dataset_from_langfuse

    dataset = create_dataset_from_langfuse(
        limit=args.limit,
        trace_name=args.trace_name,
    )

    if len(dataset) == 0:
        logger.warning(
            "No samples found — check Langfuse configuration and trace filters"
        )
        sys.exit(1)

    output_path = Path(args.output)
    records = [
        {
            "user_input": s.user_input,
            "response": s.response,
            "retrieved_contexts": s.retrieved_contexts,
            "reference": s.reference,
        }
        for s in dataset.samples
    ]

    output_path.write_text(json.dumps(records, indent=2, default=str))
    logger.info("Exported %d samples to %s", len(records), output_path)


if __name__ == "__main__":
    main()
