"""Run the Ragas evaluation pipeline against real agent interactions.

Fetches traces from Langfuse, runs Ragas evaluation, prints the report,
and optionally saves results to Postgres.

Usage:
    uv run python scripts/evaluate.py
    uv run python scripts/evaluate.py --limit 50 --trace-name agent_run
    uv run python scripts/evaluate.py --save-to-db
"""

import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run evaluation pipeline."""
    parser = argparse.ArgumentParser(description="Run Ragas agent evaluation pipeline")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--trace-name", type=str, default=None)
    parser.add_argument(
        "--save-to-db",
        action="store_true",
        help="Persist results to Postgres evaluation_runs table",
    )
    args = parser.parse_args()

    from src.evaluation.dataset import create_dataset_from_langfuse
    from src.evaluation.pipeline import run_evaluation
    from src.evaluation.reporter import EvalReport

    dataset = create_dataset_from_langfuse(
        limit=args.limit,
        trace_name=args.trace_name,
    )
    logger.info("Dataset size: %d samples", len(dataset))

    results = await run_evaluation(dataset)

    report = EvalReport(
        results=results,
        dataset_size=len(dataset),
        metadata={"trace_name": args.trace_name, "limit": args.limit},
    )
    print(report.summary())

    if args.save_to_db:
        from src.db.client import close_pool, create_pool

        pool = await create_pool()
        try:
            await report.save_to_db(pool)
            logger.info("Results saved to database")
        finally:
            await close_pool(pool)


if __name__ == "__main__":
    asyncio.run(main())
