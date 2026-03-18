# Evaluation Guide

*AgentForge — Running and Interpreting Ragas Evaluations*

---

## Prerequisites

Before running an evaluation you need:

1. **Langfuse configured and running** with agent traces from real usage. Phases 1 and 2 must have been used with Langfuse enabled (see `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in `.env`).
2. **`OPENAI_API_KEY` set** — Ragas uses an LLM as a judge to compute metrics.
3. **`EVAL_MODEL` set** in `.env` (defaults to `gpt-4o`). This is the model Ragas uses for evaluation — it is separate from your agent's model.
4. **At least ~20 traces** in Langfuse for meaningful scores. Fewer traces produce high-variance results.

Check your trace count by opening Langfuse at `http://localhost:3001` → Traces.

---

## Running Your First Evaluation

```bash
# Run with a small dataset first
uv run python scripts/evaluate.py --limit 20 --trace-name agent_run

# Expected output:
# Evaluation Report — 2026-03-16T...
# Dataset size: 18 samples        (some traces may be skipped if missing input/output)
#   context_precision: 0.712
#   faithfulness: 0.841
#   response_relevancy: 0.788
```

The `--trace-name` flag filters traces by name. Use `agent_run` for single-agent interactions or `multi-agent-workflow` for the research pipeline. Omit it to evaluate all traces.

The `--limit` flag controls how many traces to fetch from Langfuse. Start small (20) to verify the pipeline works, then increase for production evaluations.

---

## Exporting Dataset for Offline Use

```bash
uv run python scripts/export_dataset.py --limit 50 --output eval_data.json
```

The exported JSON contains an array of samples:

```json
[
  {
    "question": "What videos has this channel posted about Python?",
    "answer": "The channel has posted 3 Python tutorials...",
    "contexts": ["Video: Python Tutorial (1M views)...", "..."],
    "reference": null
  }
]
```

The `reference` field (ground truth) will be `null` for all samples unless manually annotated. See "Adding Ground Truth" below.

---

## Saving Results to Database

```bash
uv run python scripts/evaluate.py --limit 50 --save-to-db
```

Results are stored in the `evaluation_runs` table for historical tracking. Query them directly:

```sql
SELECT ran_at, dataset_size, results
FROM evaluation_runs
ORDER BY ran_at DESC
LIMIT 10;
```

Each row contains the full metric scores as JSONB, along with metadata about which model was used and how many samples were evaluated.

---

## When Scores Are Meaningful

- **Need ≥ 20 samples** for stable scores. Below 20, individual outliers dominate the average.
- **Use the same trace filter** each time for comparable results. Mixing `agent_run` and `multi-agent-workflow` traces in one evaluation muddies the signal.
- **Scores vary by model.** Always note which `EVAL_MODEL` was used. GPT-4o and GPT-4o-mini produce different judge scores for the same data.
- **Track over time.** A single evaluation is a snapshot. The value comes from tracking scores across releases and model changes.

---

## Acting on Low Scores

### Low Faithfulness (< 0.8)

The agent is generating answers that go beyond what the retrieved context supports — it is hallucinating.

**Actions:**
- Tighten the system prompt: add "Only answer based on data returned by your tools. If the data is insufficient, say so."
- Check if tool responses are being truncated — the agent may not be receiving full context.
- Review whether the agent is being asked questions outside its data domain.

### Low Response Relevancy (< 0.7)

The agent's answers do not address the actual question asked — they are tangential or off-topic.

**Actions:**
- Improve tool descriptions so the LLM selects the correct tool for the question type.
- Check if the system prompt is too broad — a focused prompt produces more relevant answers.
- Consider adding a clarification step when the question is ambiguous.

### Low Context Precision (< 0.6)

The search tools are returning irrelevant documents — the retrieved contexts do not relate to the question.

**Actions:**
- Review the full-text search queries in `src/db/queries.py` — `plainto_tsquery` may be too loose for your data.
- Consider adding a semantic similarity filter (pgvector cosine distance) as a second pass.
- Reduce the search limit to surface only the highest-relevance results.

### Low Context Recall (< 0.7, requires ground truth)

The search is missing relevant context that exists in the database.

**Actions:**
- Increase the search limit in tool calls to retrieve more candidates.
- Improve query expansion — the user's phrasing may not match the stored text.
- Check whether relevant data is actually in the database (collection may be incomplete).

---

## Adding Ground Truth for Supervised Metrics

Context Recall requires `reference` (ground truth) annotations. To add them:

1. Export a dataset:
   ```bash
   uv run python scripts/export_dataset.py --limit 50 --output eval_data.json
   ```

2. Open `eval_data.json` and fill in the `reference` field for each sample with the ideal answer:
   ```json
   {
     "question": "What videos has this channel posted about Python?",
     "answer": "The channel has posted 3 Python tutorials...",
     "contexts": ["..."],
     "reference": "The channel has 5 Python videos: Tutorial 1, Tutorial 2, ..."
   }
   ```

3. Re-run evaluation with the annotated dataset. The pipeline automatically enables Context Recall when `reference` fields are present.

Ground truth annotation is manual and time-consuming. Start with 20-30 samples for the most common question types, then expand as needed.
