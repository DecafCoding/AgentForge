"""
Evaluation pipeline tests.

Tests the evaluation module components using mocked Langfuse and Ragas
dependencies. No real LLM calls or Langfuse connections are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from ragas import EvaluationDataset
from ragas.dataset_schema import SingleTurnSample

# ---------------------------------------------------------------------------
# EvalSample model
# ---------------------------------------------------------------------------


def test_eval_sample_requires_question_and_answer():
    """EvalSample must have question and answer fields."""
    from src.evaluation.dataset import EvalSample

    sample = EvalSample(question="What is X?", answer="X is Y.", contexts=["X is Y."])
    assert sample.question == "What is X?"
    assert sample.ground_truth is None


# ---------------------------------------------------------------------------
# create_dataset_from_langfuse
# ---------------------------------------------------------------------------


def test_create_dataset_returns_empty_when_langfuse_not_configured():
    """Dataset creation returns empty EvaluationDataset when Langfuse is None."""
    with patch("src.observability.tracing.get_client", return_value=None):
        from src.evaluation.dataset import create_dataset_from_langfuse

        dataset = create_dataset_from_langfuse(limit=10)

    assert len(dataset) == 0


def test_create_dataset_skips_traces_with_missing_input():
    """Traces with empty question or answer are skipped."""
    mock_trace = MagicMock()
    mock_trace.id = "trace-1"
    mock_trace.input = {}
    mock_trace.output = {"answer": "Some answer"}

    mock_traces = MagicMock()
    mock_traces.data = [mock_trace]

    mock_lf = MagicMock()
    mock_lf.fetch_traces.return_value = mock_traces

    with patch("src.observability.tracing.get_client", return_value=mock_lf):
        from src.evaluation.dataset import create_dataset_from_langfuse

        dataset = create_dataset_from_langfuse(limit=10)

    assert len(dataset) == 0


def test_create_dataset_extracts_question_and_answer():
    """Valid traces produce one sample per trace with contexts from tool spans."""
    mock_obs = MagicMock()
    mock_obs.type = "TOOL"
    mock_obs.output = "retrieved context text"

    mock_observations = MagicMock()
    mock_observations.data = [mock_obs]

    mock_trace = MagicMock()
    mock_trace.id = "trace-1"
    mock_trace.input = {"question": "What is Python?"}
    mock_trace.output = {"answer": "Python is a programming language."}

    mock_traces = MagicMock()
    mock_traces.data = [mock_trace]

    mock_lf = MagicMock()
    mock_lf.fetch_traces.return_value = mock_traces
    mock_lf.fetch_observations.return_value = mock_observations

    with patch("src.observability.tracing.get_client", return_value=mock_lf):
        from src.evaluation.dataset import create_dataset_from_langfuse

        dataset = create_dataset_from_langfuse(limit=10)

    assert len(dataset) == 1
    assert dataset.samples[0].user_input == "What is Python?"
    assert dataset.samples[0].response == "Python is a programming language."
    assert "retrieved context text" in dataset.samples[0].retrieved_contexts


def test_create_dataset_defaults_contexts_to_empty_string_when_no_tools():
    """Traces with no tool spans get retrieved_contexts=[''] — never empty list."""
    mock_observations = MagicMock()
    mock_observations.data = []

    mock_trace = MagicMock()
    mock_trace.id = "trace-1"
    mock_trace.input = {"question": "Q?"}
    mock_trace.output = {"answer": "A."}

    mock_traces = MagicMock()
    mock_traces.data = [mock_trace]

    mock_lf = MagicMock()
    mock_lf.fetch_traces.return_value = mock_traces
    mock_lf.fetch_observations.return_value = mock_observations

    with patch("src.observability.tracing.get_client", return_value=mock_lf):
        from src.evaluation.dataset import create_dataset_from_langfuse

        dataset = create_dataset_from_langfuse(limit=10)

    assert dataset.samples[0].retrieved_contexts == [""]


# ---------------------------------------------------------------------------
# run_evaluation
# ---------------------------------------------------------------------------


async def test_run_evaluation_returns_empty_dict_for_empty_dataset():
    """run_evaluation() returns empty dict when dataset has no samples."""
    from src.evaluation.pipeline import run_evaluation

    empty_dataset = EvaluationDataset(samples=[])
    result = await run_evaluation(empty_dataset)
    assert result == {}


async def test_run_evaluation_calls_aevaluate_with_metrics_and_llm():
    """run_evaluation() calls aevaluate() with metrics and a wrapped LLM."""
    dataset = EvaluationDataset(
        samples=[
            SingleTurnSample(
                user_input="Q?",
                response="A.",
                retrieved_contexts=["context"],
            )
        ]
    )

    mock_df = MagicMock()
    mock_df.mean.return_value.to_dict.return_value = {"faithfulness": 0.9}
    mock_result = MagicMock()
    mock_result.to_pandas.return_value = mock_df

    with (
        patch(
            "src.evaluation.pipeline.aevaluate",
            AsyncMock(return_value=mock_result),
        ),
        patch("langchain_openai.ChatOpenAI"),
        patch("ragas.llms.LangchainLLMWrapper"),
    ):
        from src.evaluation.pipeline import run_evaluation

        scores = await run_evaluation(dataset)

    assert scores == {"faithfulness": 0.9}


# ---------------------------------------------------------------------------
# EvalReport
# ---------------------------------------------------------------------------


def test_eval_report_summary_includes_metric_scores():
    """EvalReport.summary() produces readable string with all metric scores."""
    from src.evaluation.reporter import EvalReport

    report = EvalReport(
        results={"faithfulness": 0.85, "response_relevancy": 0.92},
        dataset_size=50,
    )
    summary = report.summary()

    assert "50 samples" in summary
    assert "faithfulness: 0.850" in summary
    assert "response_relevancy: 0.920" in summary


def test_eval_report_summary_handles_empty_results():
    """EvalReport.summary() handles empty results without crashing."""
    from src.evaluation.reporter import EvalReport

    report = EvalReport(results={}, dataset_size=0)
    summary = report.summary()
    assert "No results" in summary


async def test_eval_report_save_to_db_delegates_to_upsert(mock_pool):
    """EvalReport.save_to_db() calls upsert_evaluation_run with correct args."""
    from src.evaluation.reporter import EvalReport

    report = EvalReport(results={"faithfulness": 0.8}, dataset_size=10)

    with patch("src.db.queries.upsert_evaluation_run", AsyncMock()) as mock_upsert:
        await report.save_to_db(mock_pool)

    mock_upsert.assert_called_once_with(
        pool=mock_pool,
        dataset_size=10,
        results={"faithfulness": 0.8},
        metadata={},
    )
