# Feature: Phase 2 — LangGraph Multi-Agent Orchestration

The following plan should be complete, but validate documentation and codebase patterns before
implementing. Pay special attention to LangGraph's state-merging behaviour and the Langfuse v2
child-span API.

> **⚠ Pre-implementation verification required** — Before writing any code, run:
> ```bash
> uv run python -c "import langgraph; print(langgraph.__version__)"
> ```
> Then confirm two LangGraph-specific behaviours against the installed version's docs:
> 1. **Pydantic BaseModel state**: does the installed version support it natively, or must you
>    use TypedDict? (The plan is written for native Pydantic support, available in v0.2+.)
> 2. **Non-serializable deps in state**: the plan uses `Field(exclude=True)` to carry the
>    `asyncpg.Pool` in state without checkpointing. If you hit serialization errors, use the
>    **closure alternative** documented in the NOTES section instead.

---

## Feature Description

Add LangGraph as Pattern 2 — multi-agent orchestration for workflows where routing depends on
the output of a previous step. After this phase, AgentForge ships two complete patterns:

- **Pattern 1** (Phase 1, unchanged): Single Pydantic AI agent with tools. Implicit orchestration
  via tool-calling loop.
- **Pattern 2** (Phase 2): LangGraph coordinating multiple Pydantic AI agents with conditional
  edges, stateful routing, and a single cross-agent Langfuse trace.

The reference example is a three-node **research → analysis → synthesis** pipeline built on top
of the existing YouTube data.

---

## User Story

As a developer using AgentForge,
I want a working multi-agent orchestration example with conditional routing and cross-agent tracing,
So that I can adapt it to my own multi-step, stateful workflows without starting from scratch.

---

## Problem Statement

Pattern 1 (single agent + tools) is the right choice when "what happens next?" has a fixed answer.
When routing depends on previous output — retry if quality is too low, skip synthesis if research
found nothing — a single agent loop becomes unreadable. Developers currently have no reference for
this more complex pattern.

## Solution Statement

Integrate LangGraph as a graph runtime that coordinates three Pydantic AI agents. Each agent
node runs identically to a standalone Pydantic AI agent. LangGraph handles state passing,
conditional routing, and parallel-ready structure. A single Langfuse trace with per-node child
spans provides full observability across the entire workflow.

---

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `src/orchestration/` (new), `src/agent/` (new sub-agents), `src/api/` (new route), `tests/` (new test files)
**Dependencies**: `langgraph>=0.2.0` (new), existing `pydantic-ai`, `langfuse>=2.0.0`

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `src/agent/agent.py` (lines 39–128) — The definitive pattern for creating a Pydantic AI agent,
  injecting deps, and wrapping a call in a Langfuse trace. Every sub-agent in Phase 2 follows this
  exact structure. The `run_agent()` function is the template for `run_workflow()`.
- `src/agent/models.py` — `AgentResponse` and `Source` models. `Source` is reused in workflow
  responses. `AgentResponse` is the model to mirror for sub-agent output types.
- `src/agent/tools.py` — The three existing tools (`query_recent_videos`, `search_videos_by_query`,
  `get_channel_statistics`). ResearchAgent reuses these tools directly. Do NOT duplicate them.
- `src/observability/tracing.py` — `get_client()` returns `Langfuse | None`. The `flush()` helper.
  Trace creation pattern: `lf.trace(name=..., input=...)`, `trace.generation(...)`.
- `src/api/routes.py` — Route pattern to mirror for `POST /api/research`. Thin: validate,
  delegate to runner function, shape response. No business logic.
- `src/api/schemas.py` — How to import `Source` from `src.agent.models` and define request/response
  schemas. `ResearchRequest` and `WorkflowResponse` follow the same structure.
- `tests/test_agent.py` — Full test pattern for mocking `agent.run`, `get_langfuse`, and building
  mock result objects. Mirror this for orchestration tests.
- `tests/test_api.py` — Route test pattern: mock the runner function, assert status + response shape.
- `tests/test_collector.py` (lines 20–78) — AST-based boundary verification tests. Must add a new
  boundary test for `src/orchestration/`.
- `tests/conftest.py` — The `client` fixture pattern. The `mock_pool` fixture used in every test.
- `pyproject.toml` — Where to add `langgraph` dependency.

### New Files to Create

- `src/orchestration/__init__.py`
- `src/orchestration/state.py` — `WorkflowState` Pydantic model
- `src/orchestration/nodes.py` — Three async node functions wrapping sub-agents
- `src/orchestration/graph.py` — Graph definition + `run_workflow()` public entry point
- `src/agent/research_agent.py` — Pydantic AI agent: DB queries → `ResearchOutput`
- `src/agent/analysis_agent.py` — Pydantic AI agent: evaluate research → `AnalysisOutput`
- `src/agent/synthesis_agent.py` — Pydantic AI agent: combine → `AgentResponse`
- `tests/test_orchestration.py` — Workflow execution, conditional routing, state management tests
- `tests/test_cross_agent_tracing.py` — Langfuse span hierarchy tests
- `docs/pattern-decision-guide.md` — When to use Pattern 1 vs Pattern 2 vs plain Python

### Files to Modify

- `pyproject.toml` — Add `langgraph>=0.2.0`
- `src/api/routes.py` — Add `POST /api/research` route
- `src/api/schemas.py` — Add `ResearchRequest`, `WorkflowResponse`
- `tests/test_collector.py` — Add boundary test for `src/orchestration/`

### Relevant Documentation

- [LangGraph Python Docs — StateGraph](https://langchain-ai.github.io/langgraph/reference/graphs/#langgraph.graph.StateGraph)
  - State definition, add_node, add_edge, add_conditional_edges, compile, ainvoke
- [LangGraph — How to use Pydantic models as state](https://langchain-ai.github.io/langgraph/how-tos/state-model/)
  - Pydantic BaseModel state vs TypedDict, model_config requirements
- [LangGraph — Conceptual guide: nodes](https://langchain-ai.github.io/langgraph/concepts/low_level/#nodes)
  - Node functions receive full state, return dict of updates to merge
- [Langfuse Python SDK v2](https://langfuse.com/docs/sdk/python)
  - `lf.trace()`, `trace.span()`, `lf.span(trace_id=...)`, span `.end()`

---

## Patterns to Follow

### Pydantic AI Agent Pattern (mirror exactly)

From `src/agent/agent.py:39-61`:
```python
agent: Agent[Pool, AgentResponse] = Agent(
    model=get_model_string(),
    deps_type=Pool,
    result_type=AgentResponse,
    system_prompt="...",
    tools=[tool_a, tool_b],
)
```
Each sub-agent follows this same structure with its own `result_type` and `system_prompt`.

### Tool Pattern (mirror exactly)

From `src/agent/tools.py:22-42`:
```python
async def my_tool(ctx: RunContext[Pool], param: str) -> ReturnType:
    """Docstring written FOR THE LLM — describes when to call this tool."""
    return await queries.some_query(ctx.deps, param)
```
ResearchAgent reuses existing tools by importing them from `src.agent.tools`.

### Langfuse Trace Pattern (mirror from `run_agent()`)

From `src/agent/agent.py:64-128`:
```python
lf = get_langfuse()
if lf is None:
    # run without tracing
    ...
trace = lf.trace(name="...", input={...}, metadata={...})
generation = trace.generation(name="...", model="...", input=...)
try:
    result = await agent.run(...)
    generation.end(output=..., usage={...})
    trace.update(output={...})
    return result.data
except Exception as exc:
    generation.end(level="ERROR", status_message=str(exc))
    trace.update(level="ERROR", status_message=str(exc))
    raise
finally:
    lf.flush()
```
`run_workflow()` creates the parent trace. Nodes create child spans using `trace.span()`.

### API Route Pattern (mirror from `ask` route)

From `src/api/routes.py:27-51`:
```python
@router.post("/api/research", response_model=WorkflowResponse, tags=["orchestration"])
async def research(request: Request, body: ResearchRequest) -> WorkflowResponse:
    pool = request.app.state.pool
    try:
        response = await run_workflow(body.query, pool)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Workflow failed.") from exc
    return WorkflowResponse(...)
```

### Naming Conventions

- Module docstrings on every file (see `src/agent/agent.py` header)
- Class docstrings describing responsibility and layer
- Google-style docstrings when args/returns are non-obvious
- `_private` prefix for internal helpers
- Constants: `UPPER_SNAKE_CASE`
- All imports absolute (`from src.agent.tools import ...`, never `from .tools import ...`)

### Logging Pattern (mirror from existing modules)

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Workflow complete", extra={"steps": state.steps_completed})
```

---

## CRITICAL IMPLEMENTATION NOTES

### LangGraph State with Pydantic BaseModel

LangGraph ≥ 0.2 supports Pydantic `BaseModel` as state. Key rules:

1. Add `model_config = ConfigDict(arbitrary_types_allowed=True)` to `WorkflowState` because
   `asyncpg.Pool` is not a standard Pydantic type.
2. Node functions receive the full state model instance, return a **dict of partial updates**.
   LangGraph merges via `state.model_copy(update=returned_dict)`.
3. Invoke with the model instance directly:
   ```python
   initial_state = WorkflowState(query=query, pool=pool, ...)
   result = await compiled_graph.ainvoke(initial_state)
   ```
   Do NOT call `.model_dump()` — that drops the Pool (excluded field) and loses the reference.
4. No checkpointing is used in Phase 2 — this avoids all serialization concerns for the Pool.

### Langfuse Child Spans

Pass `trace_id: str | None = None` in `WorkflowState`. Set it from the parent trace in
`run_workflow()` before invoking the graph. Each node creates a child span:
```python
lf = get_langfuse()
if lf and state.trace_id:
    span = lf.span(name="research_node", trace_id=state.trace_id)
    # ... agent.run() ...
    span.end(output=..., usage=...)
```
The `span.end()` call is in a `finally` block to ensure it always fires.

### Conditional Routing (should_continue)

`should_continue` is a plain synchronous function — LangGraph conditional edge functions must be
synchronous. It reads `state.quality_score` and returns a string key matching the routing map:
```python
def should_continue(state: WorkflowState) -> str:
    if state.quality_score is not None and state.quality_score < 0.3:
        return "retry" if state.steps_completed < 3 else "end"
    return "continue"
```

### Boundary Rule for src/orchestration/

`src/orchestration/` IS allowed to import `pydantic_ai` and `langfuse` (it orchestrates agents).
It must NOT import `apscheduler` or `httpx`. Add a boundary test to `test_collector.py` to verify.

---

## IMPLEMENTATION PLAN

### Phase 1: Dependency + Branch Setup

Add `langgraph` to `pyproject.toml` and sync the lockfile. Create the feature branch.

### Phase 2: State Model

Define `WorkflowState` and the three sub-agent output models. This is pure data — no logic.

### Phase 3: Sub-Agents

Implement `research_agent.py`, `analysis_agent.py`, `synthesis_agent.py`. Each is a standalone
Pydantic AI agent mirroring the existing `agent.py` pattern.

### Phase 4: Graph Nodes + Routing

Implement `nodes.py` wrapping each agent with state-update logic and Langfuse child spans.
Implement the `should_continue` routing function.

### Phase 5: Graph Definition + Runner

Assemble the graph in `graph.py` and implement `run_workflow()` with the parent Langfuse trace.

### Phase 6: API Integration

Add `POST /api/research` route and request/response schemas.

### Phase 7: Tests

Comprehensive tests for workflow, routing, tracing, and the new API route. Boundary test update.

### Phase 8: Documentation

`docs/pattern-decision-guide.md` covering all three patterns.

---

## STEP-BY-STEP TASKS

### TASK 1: Branch + Dependency

**UPDATE `pyproject.toml`**
- **ADD** `"langgraph>=0.2.0",` to the `dependencies` list, after the `langfuse` entry
- **PATTERN**: Follow existing pinning style — `>=major.minor.0`
- **VALIDATE**: `uv sync && uv run python -c "import langgraph; print(langgraph.__version__)"`

**SETUP git branch:**
```bash
git checkout main
git pull origin main
git checkout -b feat/phase-2-langgraph
git push -u origin feat/phase-2-langgraph
```

---

### TASK 2: CREATE `src/orchestration/__init__.py`

```python
"""
Multi-agent orchestration layer.

Contains the LangGraph workflow graph, state model, and node functions.
This layer coordinates multiple Pydantic AI agents but does not contain
agent logic itself. Allowed imports: pydantic_ai, langfuse, src.agent,
src.db, src.config, src.observability. Forbidden: apscheduler, httpx.
"""
```

**VALIDATE**: `python -c "from src.orchestration import __init__"` — file exists, no errors.

---

### TASK 3: CREATE `src/orchestration/state.py`

```python
"""
Graph state model for the multi-agent workflow.

WorkflowState flows between LangGraph nodes. Each node receives the full
state and returns a dict of fields to update. The asyncpg Pool is carried
as a non-serialised dependency (arbitrary_types_allowed=True). This module
belongs to the Orchestration layer.
"""

from asyncpg import Pool
from pydantic import BaseModel, ConfigDict, Field


class ResearchOutput(BaseModel):
    """Structured output from the research agent node."""

    findings: list[str]
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class AnalysisOutput(BaseModel):
    """Structured output from the analysis agent node."""

    assessment: str
    gaps: list[str]
    quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Quality score driving conditional routing (< 0.3 triggers retry).",
    )
    confidence: float = Field(ge=0.0, le=1.0)


class WorkflowState(BaseModel):
    """State that flows through the multi-agent workflow graph.

    Passed between LangGraph nodes. Non-serialisable fields (pool) use
    Field(exclude=True) and are carried in-memory only — checkpointing
    is not used in Phase 2, so serialisation of pool is never attempted.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input
    query: str

    # Runtime dependency — injected by run_workflow(), not serialised
    pool: Pool = Field(exclude=True)

    # Observability — parent trace ID for Langfuse child spans
    trace_id: str | None = None

    # Research phase output
    research_output: ResearchOutput | None = None

    # Analysis phase output
    analysis_output: AnalysisOutput | None = None

    # Synthesis phase output (reuses AgentResponse from agent layer)
    final_answer: str | None = None
    final_sources: list[str] | None = None
    final_confidence: float | None = None

    # Workflow metadata
    steps_completed: int = 0
    max_retries: int = 3
```

**IMPORTS**: `from asyncpg import Pool`, `from pydantic import BaseModel, ConfigDict, Field`
**VALIDATE**: `uv run python -c "from src.orchestration.state import WorkflowState; print('ok')"`

---

### TASK 4: CREATE `src/agent/research_agent.py`

```python
"""
Research agent — data gathering node.

Queries the YouTube video database and gathers raw findings for the
orchestration workflow. Used as the first node in the LangGraph
multi-agent pipeline. This module belongs to the Agent layer and
must not import apscheduler, httpx, or any collector dependency.
"""

import logging

from asyncpg import Pool
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.agent.tools import get_channel_statistics, query_recent_videos, search_videos_by_query
from src.config import MODEL_NAME, MODEL_PROVIDER, get_model_string

logger = logging.getLogger(__name__)


class ResearchAgentOutput(BaseModel):
    """Structured output from the research agent.

    findings: Key facts found in the database relevant to the query.
    sources: Video IDs or titles that support the findings.
    confidence: Self-assessed confidence that findings are complete.
    """

    findings: list[str]
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


research_agent: Agent[Pool, ResearchAgentOutput] = Agent(
    model=get_model_string(),
    deps_type=Pool,
    result_type=ResearchAgentOutput,
    system_prompt=(
        "You are a research agent. Your job is to query the YouTube video database "
        "and gather all relevant information for the given query.\n\n"
        "Guidelines:\n"
        "- Use your tools to retrieve data. Do not guess or invent findings.\n"
        "- List concrete findings (facts, titles, dates, counts) from the database.\n"
        "- List the video IDs or titles you retrieved data from in 'sources'.\n"
        "- If the database has no relevant data, set findings to an empty list "
        "and confidence to 0.1.\n"
        "- Set confidence based on how complete the gathered data is: "
        "1.0 for comprehensive data, 0.5 for partial, 0.1 for minimal."
    ),
    tools=[query_recent_videos, search_videos_by_query, get_channel_statistics],
)
```

**IMPORTS**: `from asyncpg import Pool`, `from pydantic_ai import Agent`, `from src.agent.tools import ...`, `from src.config import get_model_string`
**GOTCHA**: Import tools from `src.agent.tools`, NOT from `src.db.queries` directly. Tools handle the `RunContext` wrapping.
**VALIDATE**: `uv run python -c "from src.agent.research_agent import research_agent; print('ok')"`

---

### TASK 5: CREATE `src/agent/analysis_agent.py`

```python
"""
Analysis agent — quality evaluation node.

Evaluates the quality of research output and identifies gaps. Its
quality_score drives conditional routing in the LangGraph workflow:
scores below 0.3 trigger a research retry. This module belongs to
the Agent layer and must not import apscheduler, httpx, or any
collector dependency.
"""

import logging

from asyncpg import Pool
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.config import get_model_string

logger = logging.getLogger(__name__)


class AnalysisAgentOutput(BaseModel):
    """Structured output from the analysis agent.

    assessment: Prose evaluation of the research quality.
    gaps: Topics the research did not cover but should have.
    quality_score: Numeric quality rating driving conditional routing.
    confidence: Self-assessed confidence in this analysis.
    """

    assessment: str
    gaps: list[str]
    quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Quality of the research: 1.0 = complete, 0.3 = needs retry.",
    )
    confidence: float = Field(ge=0.0, le=1.0)


analysis_agent: Agent[Pool, AnalysisAgentOutput] = Agent(
    model=get_model_string(),
    deps_type=Pool,
    result_type=AnalysisAgentOutput,
    system_prompt=(
        "You are a quality analysis agent. You evaluate research findings and "
        "determine whether they are sufficient to answer the original query.\n\n"
        "Guidelines:\n"
        "- Assess whether the findings address the query completely.\n"
        "- List any gaps: important aspects of the query that are not covered.\n"
        "- Set quality_score: 0.8–1.0 if findings are comprehensive, "
        "0.4–0.8 if partial but workable, 0.0–0.3 if insufficient (retry needed).\n"
        "- Set confidence based on how certain you are of your assessment."
    ),
    tools=[],  # Analysis agent reasons on provided text, no DB tools needed
)
```

**GOTCHA**: Analysis agent has NO tools — it reasons purely on the research text passed in its prompt.
**VALIDATE**: `uv run python -c "from src.agent.analysis_agent import analysis_agent; print('ok')"`

---

### TASK 6: CREATE `src/agent/synthesis_agent.py`

```python
"""
Synthesis agent — final answer node.

Combines research findings and analysis into a structured final answer
with cited sources. Produces the output returned to the API caller.
This module belongs to the Agent layer and must not import apscheduler,
httpx, or any collector dependency.
"""

import logging

from asyncpg import Pool
from pydantic_ai import Agent

from src.agent.models import AgentResponse
from src.config import get_model_string

logger = logging.getLogger(__name__)


synthesis_agent: Agent[Pool, AgentResponse] = Agent(
    model=get_model_string(),
    deps_type=Pool,
    result_type=AgentResponse,
    system_prompt=(
        "You are a synthesis agent. You combine research findings and quality "
        "analysis into a clear, well-cited final answer.\n\n"
        "Guidelines:\n"
        "- Write a direct, informative answer to the original query.\n"
        "- Populate 'sources' with every video title and ID referenced in your answer.\n"
        "- Set confidence to reflect how well the available data supports the answer.\n"
        "- Do not repeat gaps or analysis meta-commentary — the answer should read "
        "naturally without internal workflow details."
    ),
    tools=[],  # Synthesis reasons on provided research + analysis, no DB tools needed
)
```

**NOTE**: Synthesis reuses `AgentResponse` from `src.agent.models` — same type as Pattern 1 output.
This means both patterns return the same shape to the API, which makes the `/api/research` response
schema consistent with `/api/ask`.
**VALIDATE**: `uv run python -c "from src.agent.synthesis_agent import synthesis_agent; print('ok')"`

---

### TASK 7: CREATE `src/orchestration/nodes.py`

```python
"""
LangGraph node functions for the multi-agent workflow.

Each function wraps a Pydantic AI agent call, updates WorkflowState,
and records a Langfuse child span. Nodes return a dict of state field
updates — LangGraph merges these into the existing state via
state.model_copy(update=returned_dict).

This module belongs to the Orchestration layer. Allowed imports:
pydantic_ai, langfuse, src.agent.*, src.observability. Forbidden:
apscheduler, httpx.
"""

import logging

from src.agent.analysis_agent import analysis_agent
from src.agent.research_agent import research_agent
from src.agent.synthesis_agent import synthesis_agent
from src.observability.tracing import get_client as get_langfuse
from src.orchestration.state import AnalysisOutput, ResearchOutput, WorkflowState

logger = logging.getLogger(__name__)


async def research_node(state: WorkflowState) -> dict:
    """Run the research agent and return research findings as a state update.

    First node in the workflow. Queries the video database and gathers raw
    findings to pass to the analysis node.
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

        logger.info(
            "research_node complete",
            extra={"findings": len(result.data.findings), "confidence": result.data.confidence},
        )

        if span:
            span.end(
                output=result.data.model_dump(),
                usage={
                    "input": usage.request_tokens or 0,
                    "output": usage.response_tokens or 0,
                    "total": usage.total_tokens or 0,
                    "unit": "TOKENS",
                },
            )

        return {
            "research_output": ResearchOutput(
                findings=result.data.findings,
                sources=result.data.sources,
                confidence=result.data.confidence,
            ),
            "steps_completed": state.steps_completed + 1,
        }

    except Exception as exc:
        if span:
            span.end(level="ERROR", status_message=str(exc))
        logger.error("research_node failed", extra={"error": str(exc)})
        raise


async def analysis_node(state: WorkflowState) -> dict:
    """Run the analysis agent on research output and return quality assessment.

    Second node in the workflow. Evaluates research completeness and assigns
    a quality_score that drives conditional routing.
    """
    logger.info("analysis_node start")
    lf = get_langfuse()

    span = None
    if lf and state.trace_id:
        span = lf.span(
            name="analysis_node",
            trace_id=state.trace_id,
            input={"research_findings": state.research_output.findings if state.research_output else []},
        )

    research_text = (
        "\n".join(state.research_output.findings) if state.research_output else "No research available."
    )
    prompt = (
        f"Original query: {state.query}\n\n"
        f"Research findings:\n{research_text}\n\n"
        "Evaluate whether these findings are sufficient to answer the query."
    )

    try:
        result = await analysis_agent.run(prompt, deps=state.pool)
        usage = result.usage()

        logger.info(
            "analysis_node complete",
            extra={"quality_score": result.data.quality_score, "gaps": len(result.data.gaps)},
        )

        if span:
            span.end(
                output=result.data.model_dump(),
                usage={
                    "input": usage.request_tokens or 0,
                    "output": usage.response_tokens or 0,
                    "total": usage.total_tokens or 0,
                    "unit": "TOKENS",
                },
            )

        return {
            "analysis_output": AnalysisOutput(
                assessment=result.data.assessment,
                gaps=result.data.gaps,
                quality_score=result.data.quality_score,
                confidence=result.data.confidence,
            ),
        }

    except Exception as exc:
        if span:
            span.end(level="ERROR", status_message=str(exc))
        logger.error("analysis_node failed", extra={"error": str(exc)})
        raise


async def synthesis_node(state: WorkflowState) -> dict:
    """Run the synthesis agent to produce the final structured answer.

    Third (terminal) node. Combines research and analysis into a well-cited
    final answer returned to the API caller.
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
        "\n".join(state.research_output.findings) if state.research_output else "No research."
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

        logger.info(
            "synthesis_node complete",
            extra={"sources": len(result.data.sources), "confidence": result.data.confidence},
        )

        if span:
            span.end(
                output=result.data.model_dump(),
                usage={
                    "input": usage.request_tokens or 0,
                    "output": usage.response_tokens or 0,
                    "total": usage.total_tokens or 0,
                    "unit": "TOKENS",
                },
            )

        return {
            "final_answer": result.data.answer,
            "final_sources": [s.video_id for s in result.data.sources],
            "final_confidence": result.data.confidence,
        }

    except Exception as exc:
        if span:
            span.end(level="ERROR", status_message=str(exc))
        logger.error("synthesis_node failed", extra={"error": str(exc)})
        raise


def should_continue(state: WorkflowState) -> str:
    """Conditional edge: decide routing after analysis.

    Returns one of:
    - "continue" — quality is sufficient, proceed to synthesis
    - "retry"    — quality too low, repeat research (up to max_retries)
    - "end"      — quality too low and max retries exhausted, terminate

    Args:
        state: Current workflow state carrying quality_score and step counts.

    Returns:
        Routing key matching an entry in the conditional edges map.
    """
    if state.analysis_output is None:
        return "continue"

    if state.analysis_output.quality_score < 0.3:
        if state.steps_completed < state.max_retries:
            logger.info(
                "Analysis quality below threshold — retrying research",
                extra={"quality_score": state.analysis_output.quality_score, "steps": state.steps_completed},
            )
            return "retry"
        logger.warning(
            "Max retries reached with low quality — terminating",
            extra={"steps": state.steps_completed},
        )
        return "end"

    return "continue"
```

**GOTCHA**: `should_continue` must be a synchronous function — LangGraph conditional edge
functions cannot be async.
**VALIDATE**: `uv run python -c "from src.orchestration.nodes import research_node, should_continue; print('ok')"`

---

### TASK 8: CREATE `src/orchestration/graph.py`

```python
"""
LangGraph workflow graph definition and public runner.

Assembles the three-node research → analysis → synthesis pipeline.
Exposes run_workflow() as the single entry point used by the API layer —
it creates the parent Langfuse trace, injects the trace_id into state,
and invokes the compiled graph.

This module belongs to the Orchestration layer. The API layer may import
from here; this module must not import from src.api.
"""

import logging

from asyncpg import Pool
from langgraph.graph import END, START, StateGraph

from src.agent.models import AgentResponse, Source
from src.config import MODEL_NAME, MODEL_PROVIDER
from src.observability.tracing import get_client as get_langfuse
from src.orchestration.nodes import analysis_node, research_node, should_continue, synthesis_node
from src.orchestration.state import WorkflowState

logger = logging.getLogger(__name__)


def _build_graph() -> object:
    """Build and compile the multi-agent workflow graph.

    Returns:
        A compiled LangGraph StateGraph ready for async invocation.
    """
    workflow: StateGraph = StateGraph(WorkflowState)

    # Register nodes
    workflow.add_node("research", research_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("synthesis", synthesis_node)

    # Define entry point and fixed edges
    workflow.add_edge(START, "research")
    workflow.add_edge("research", "analysis")

    # Conditional routing after analysis
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


# Module-level compiled graph — built once at import time
_graph = _build_graph()


async def run_workflow(query: str, pool: Pool) -> AgentResponse:
    """Run the multi-agent research workflow and return a structured answer.

    Creates a parent Langfuse trace spanning the full workflow. Each node
    records a child span. If Langfuse is not configured, runs without tracing.

    Args:
        query: The user's natural-language research query.
        pool: asyncpg connection pool injected into each agent node.

    Returns:
        AgentResponse with the synthesised answer, sources, and confidence.
        Returns a default "no data" response if the workflow terminates early
        (quality too low, max retries reached).
    """
    lf = get_langfuse()
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
        final_state: WorkflowState = await _graph.ainvoke(initial_state)

        result = AgentResponse(
            answer=final_state.final_answer or "Research did not produce sufficient findings.",
            sources=[
                Source(
                    title=vid,
                    video_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}",
                )
                for vid in (final_state.final_sources or [])
            ],
            confidence=final_state.final_confidence or 0.1,
        )

        if lf and trace_id:
            lf.trace(id=trace_id).update(
                output={"answer": result.answer},
                metadata={"steps_completed": final_state.steps_completed},
            )

        logger.info(
            "Workflow complete",
            extra={
                "steps": final_state.steps_completed,
                "confidence": result.confidence,
                "sources": len(result.sources),
            },
        )
        return result

    except Exception as exc:
        if lf and trace_id:
            lf.trace(id=trace_id).update(level="ERROR", status_message=str(exc))
        logger.error("Workflow failed", extra={"error": str(exc)})
        raise

    finally:
        if lf:
            lf.flush()
```

**GOTCHA**: `_graph.ainvoke(initial_state)` passes the `WorkflowState` model instance directly.
Do NOT call `.model_dump()` — the `pool` field has `exclude=True` and would be lost.

**GOTCHA**: `final_state` returned by `ainvoke` is a `WorkflowState` instance (LangGraph returns
the same type you passed in). Access fields directly: `final_state.final_answer`.

**GOTCHA**: `lf.trace(id=trace_id).update(...)` is the Langfuse v2 pattern for updating an
existing trace by ID. If this API is not available in your Langfuse version, store the `trace`
object in a local variable before the `ainvoke` call and call `trace.update(...)` in the finally block.

**VALIDATE**: `uv run python -c "from src.orchestration.graph import run_workflow; print('ok')"`

---

### TASK 9: UPDATE `src/api/schemas.py`

Add `ResearchRequest` and `WorkflowResponse` after the existing `HealthResponse` class:

```python
class ResearchRequest(BaseModel):
    """Request body for POST /api/research."""

    query: str = Field(
        min_length=1,
        description="The natural-language research query to run through the multi-agent workflow.",
    )


class WorkflowResponse(BaseModel):
    """Response body for POST /api/research."""

    answer: str
    sources: list[Source]
    confidence: float
```

**IMPORTS**: `Source` is already imported from `src.agent.models`. No new imports needed.
**VALIDATE**: `uv run python -c "from src.api.schemas import ResearchRequest, WorkflowResponse; print('ok')"`

---

### TASK 10: UPDATE `src/api/routes.py`

Add the new route. Append after the existing `ask` route:

```python
from src.orchestration.graph import run_workflow
from src.api.schemas import AskRequest, AskResponse, HealthResponse, ResearchRequest, WorkflowResponse
```

And add the route handler:

```python
@router.post("/api/research", response_model=WorkflowResponse, tags=["orchestration"])
async def research(request: Request, body: ResearchRequest) -> WorkflowResponse:
    """Submit a query to the multi-agent research workflow.

    Runs a three-node LangGraph pipeline (research → analysis → synthesis)
    and returns a structured, source-cited answer. The full workflow is
    traced as a single Langfuse trace with per-node child spans.

    Args:
        request: FastAPI request object (used to access app.state.pool).
        body: Validated request body containing the research query.

    Returns:
        Structured response with the synthesised answer and cited sources.
    """
    pool = request.app.state.pool
    logger.info("Received research query", extra={"query": body.query[:120]})

    try:
        response = await run_workflow(body.query, pool)
    except Exception as exc:
        logger.error("Workflow failed to process query", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Workflow failed to process the request.") from exc

    return WorkflowResponse(
        answer=response.answer,
        sources=response.sources,
        confidence=response.confidence,
    )
```

**IMPORTS to add at top of routes.py**:
```python
from src.orchestration.graph import run_workflow
from src.api.schemas import AskRequest, AskResponse, HealthResponse, ResearchRequest, WorkflowResponse
```
(Replace the existing schemas import line.)

**VALIDATE**: `uv run python -c "from src.api.routes import router; print('ok')"`

---

### TASK 11: UPDATE `tests/test_collector.py`

Add a new boundary test after `test_agent_has_no_scheduler_or_http_imports`:

```python
def test_orchestration_has_no_scheduler_or_http_imports():
    """Verify src/orchestration/ contains no apscheduler or httpx imports."""
    forbidden = {"apscheduler", "httpx"}
    violations: list[str] = []

    orchestration_dir = pathlib.Path("src/orchestration")
    for py_file in sorted(orchestration_dir.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for pkg in forbidden:
                        if alias.name == pkg or alias.name.startswith(f"{pkg}."):
                            violations.append(
                                f"{py_file}:{node.lineno}: import {alias.name}"
                            )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for pkg in forbidden:
                    if module == pkg or module.startswith(f"{pkg}."):
                        violations.append(
                            f"{py_file}:{node.lineno}: from {module} import ..."
                        )

    assert not violations, (
        "Orchestration module imports forbidden dependencies (boundary violation):\n"
        + "\n".join(violations)
    )
```

**VALIDATE**: `uv run pytest tests/test_collector.py::test_orchestration_has_no_scheduler_or_http_imports -v`

---

### TASK 12: CREATE `tests/test_orchestration.py`

```python
"""
Orchestration module tests.

Covers WorkflowState model validation, conditional routing logic, and
the run_workflow() runner. No real LLM calls or database connections
are made — agents and the pool are mocked throughout.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.orchestration.state import AnalysisOutput, ResearchOutput, WorkflowState


# ---------------------------------------------------------------------------
# WorkflowState validation
# ---------------------------------------------------------------------------


def test_workflow_state_requires_query(mock_pool):
    """WorkflowState requires a non-empty query and a pool."""
    state = WorkflowState(query="test query", pool=mock_pool)
    assert state.query == "test query"
    assert state.steps_completed == 0


def test_workflow_state_pool_excluded_from_serialisation(mock_pool):
    """Pool must not appear in model_dump() output."""
    state = WorkflowState(query="q", pool=mock_pool)
    dumped = state.model_dump()
    assert "pool" not in dumped


def test_research_output_rejects_invalid_confidence():
    """ResearchOutput must reject confidence outside 0–1."""
    with pytest.raises(ValidationError):
        ResearchOutput(findings=[], sources=[], confidence=1.5)


def test_analysis_output_quality_score_range():
    """AnalysisOutput must reject quality_score outside 0–1."""
    with pytest.raises(ValidationError):
        AnalysisOutput(assessment="ok", gaps=[], quality_score=-0.1, confidence=0.9)


# ---------------------------------------------------------------------------
# should_continue conditional routing
# ---------------------------------------------------------------------------


def test_should_continue_returns_continue_when_quality_high(mock_pool):
    """should_continue returns 'continue' when quality_score >= 0.3."""
    from src.orchestration.nodes import should_continue

    state = WorkflowState(
        query="q",
        pool=mock_pool,
        analysis_output=AnalysisOutput(
            assessment="good", gaps=[], quality_score=0.8, confidence=0.9
        ),
        steps_completed=1,
    )
    assert should_continue(state) == "continue"


def test_should_continue_returns_retry_when_quality_low_and_steps_under_limit(mock_pool):
    """should_continue returns 'retry' when quality < 0.3 and steps < max_retries."""
    from src.orchestration.nodes import should_continue

    state = WorkflowState(
        query="q",
        pool=mock_pool,
        analysis_output=AnalysisOutput(
            assessment="poor", gaps=["x"], quality_score=0.2, confidence=0.5
        ),
        steps_completed=1,
        max_retries=3,
    )
    assert should_continue(state) == "retry"


def test_should_continue_returns_end_when_quality_low_and_max_retries_reached(mock_pool):
    """should_continue returns 'end' when quality < 0.3 and steps >= max_retries."""
    from src.orchestration.nodes import should_continue

    state = WorkflowState(
        query="q",
        pool=mock_pool,
        analysis_output=AnalysisOutput(
            assessment="poor", gaps=["x"], quality_score=0.2, confidence=0.5
        ),
        steps_completed=3,
        max_retries=3,
    )
    assert should_continue(state) == "end"


def test_should_continue_returns_continue_when_no_analysis(mock_pool):
    """should_continue defaults to 'continue' when analysis_output is None."""
    from src.orchestration.nodes import should_continue

    state = WorkflowState(query="q", pool=mock_pool)
    assert should_continue(state) == "continue"


# ---------------------------------------------------------------------------
# run_workflow — no tracing
# ---------------------------------------------------------------------------


async def test_run_workflow_returns_agent_response_when_tracing_disabled(mock_pool):
    """run_workflow() returns AgentResponse when Langfuse is not configured."""
    from src.agent.models import AgentResponse, Source

    expected_state = WorkflowState(
        query="test query",
        pool=mock_pool,
        final_answer="Synthesised answer.",
        final_sources=["vid1"],
        final_confidence=0.85,
        steps_completed=2,
    )

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(return_value=expected_state),
        ),
    ):
        from src.orchestration.graph import run_workflow

        result = await run_workflow("test query", mock_pool)

    assert result.answer == "Synthesised answer."
    assert result.confidence == 0.85
    assert len(result.sources) == 1


async def test_run_workflow_returns_default_response_on_early_termination(mock_pool):
    """run_workflow() returns a default low-confidence response when workflow ends early."""
    early_termination_state = WorkflowState(
        query="q",
        pool=mock_pool,
        final_answer=None,
        final_sources=None,
        final_confidence=None,
        steps_completed=3,
    )

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(return_value=early_termination_state),
        ),
    ):
        from src.orchestration.graph import run_workflow

        result = await run_workflow("q", mock_pool)

    assert result.confidence == 0.1
    assert "sufficient" in result.answer.lower()


async def test_run_workflow_propagates_exception(mock_pool):
    """run_workflow() re-raises exceptions from the graph."""
    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(side_effect=RuntimeError("graph error")),
        ),
        pytest.raises(RuntimeError, match="graph error"),
    ):
        from src.orchestration.graph import run_workflow

        await run_workflow("q", mock_pool)
```

**VALIDATE**: `uv run pytest tests/test_orchestration.py -v`

---

### TASK 13: CREATE `tests/test_cross_agent_tracing.py`

```python
"""
Cross-agent tracing tests.

Verifies that run_workflow() creates a parent Langfuse trace and that
node functions create child spans. No real LLM or Langfuse calls are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestration.state import WorkflowState


async def test_run_workflow_creates_langfuse_trace_on_success(mock_pool):
    """run_workflow() creates a parent Langfuse trace when keys are configured."""
    final_state = WorkflowState(
        query="q",
        pool=mock_pool,
        final_answer="answer",
        final_sources=[],
        final_confidence=0.9,
        steps_completed=2,
    )

    mock_trace = MagicMock()
    mock_trace.id = "trace-123"

    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=mock_lf),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(return_value=final_state),
        ),
    ):
        from src.orchestration.graph import run_workflow

        result = await run_workflow("q", mock_pool)

    mock_lf.trace.assert_called_once()
    mock_lf.flush.assert_called_once()
    assert result.answer == "answer"


async def test_run_workflow_marks_trace_error_on_failure(mock_pool):
    """run_workflow() marks the Langfuse trace as ERROR when the graph raises."""
    mock_trace = MagicMock()
    mock_trace.id = "trace-err"

    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=mock_lf),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(side_effect=RuntimeError("graph failure")),
        ),
        pytest.raises(RuntimeError),
    ):
        from src.orchestration.graph import run_workflow
        import pytest

        await run_workflow("q", mock_pool)

    mock_lf.flush.assert_called_once()


async def test_research_node_creates_child_span(mock_pool):
    """research_node creates a Langfuse child span when trace_id is set."""
    from src.agent.research_agent import ResearchAgentOutput

    mock_result = MagicMock()
    mock_result.data = ResearchAgentOutput(findings=["fact"], sources=["vid1"], confidence=0.9)
    mock_result.usage.return_value = MagicMock(request_tokens=50, response_tokens=20, total_tokens=70)

    mock_span = MagicMock()
    mock_lf = MagicMock()
    mock_lf.span.return_value = mock_span

    state = WorkflowState(query="q", pool=mock_pool, trace_id="trace-abc")

    with (
        patch("src.orchestration.nodes.get_langfuse", return_value=mock_lf),
        patch("src.orchestration.nodes.research_agent.run", AsyncMock(return_value=mock_result)),
    ):
        from src.orchestration.nodes import research_node

        updates = await research_node(state)

    mock_lf.span.assert_called_once_with(
        name="research_node", trace_id="trace-abc", input={"query": "q"}
    )
    mock_span.end.assert_called_once()
    assert updates["research_output"].findings == ["fact"]
```

**VALIDATE**: `uv run pytest tests/test_cross_agent_tracing.py -v`

---

### TASK 14: CREATE `docs/pattern-decision-guide.md`

Create this file with content covering:

1. **Quick decision flowchart** (as ASCII or markdown):
   - 1 agent? → Pattern 1
   - Fixed linear sequence? → Plain Python
   - Conditional routing or state-dependent branching? → Pattern 2

2. **Pattern 1 — Single Agent with Tools** (Pydantic AI)
   - When to use, reference to `src/agent/agent.py`, code snippet, strengths/limits

3. **Pattern 2 — Multi-Agent Orchestration** (LangGraph + Pydantic AI)
   - When to use, reference to `src/orchestration/`, code snippet, strengths/limits

4. **Plain Python Orchestration**
   - When to use, code snippet, strengths/limits

5. **Migration signals** — signs you've outgrown plain Python or Pattern 1

The file should be thorough enough for a developer unfamiliar with the codebase to make the
right pattern choice for their use case.

**VALIDATE**: File exists at `docs/pattern-decision-guide.md` and is non-empty.

---

## TESTING STRATEGY

### Unit Tests

**`tests/test_orchestration.py`** (Task 12):
- `WorkflowState` model validation (pool excluded from dump, confidence ranges)
- `should_continue` routing: all three branches (continue/retry/end), edge case (no analysis)
- `run_workflow()`: success path, early termination, exception propagation
- Mock: `_graph.ainvoke`, `get_langfuse` — no real LLM or DB

**`tests/test_cross_agent_tracing.py`** (Task 13):
- Parent trace created and flushed by `run_workflow()`
- Trace marked ERROR on failure
- Individual node child span creation
- Mock: Langfuse client, agent.run — no real observability or LLM

### Integration Tests

All existing Phase 1 tests must still pass (`uv run pytest tests/ -v`).

The new `POST /api/research` route should be tested in `test_api.py` by extending the file
(or adding a separate `test_orchestration_api.py`) following the exact same pattern as the
existing `ask` route tests in `test_api.py` — mock `run_workflow`, assert status + response shape.

### Edge Cases

- Workflow with no analysis output (early termination path)
- `should_continue` at exactly `max_retries` boundary
- `run_workflow()` when `Langfuse` client is `None` (tracing disabled)
- Node failure propagates and triggers trace error update
- `WorkflowState.pool` not present in `model_dump()` output
- `research_node` called when `trace_id` is `None` (no span created, no crash)

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
uv run ruff check .
uv run ruff format --check .
```

**Expected**: exit code 0, zero errors.

### Level 2: Imports Sanity

```bash
uv run python -c "from src.orchestration.graph import run_workflow; print('ok')"
uv run python -c "from src.orchestration.nodes import research_node, analysis_node, synthesis_node, should_continue; print('ok')"
uv run python -c "from src.agent.research_agent import research_agent; from src.agent.analysis_agent import analysis_agent; from src.agent.synthesis_agent import synthesis_agent; print('ok')"
uv run python -c "from src.api.routes import router; print('ok')"
```

### Level 3: Boundary Tests

```bash
uv run pytest tests/test_collector.py -v
```

All three boundary tests must pass:
- `test_collector_has_no_llm_imports`
- `test_agent_has_no_scheduler_or_http_imports`
- `test_orchestration_has_no_scheduler_or_http_imports`

### Level 4: New Unit Tests

```bash
uv run pytest tests/test_orchestration.py tests/test_cross_agent_tracing.py -v --tb=short
```

### Level 5: Full Test Suite

```bash
uv run pytest tests/ -v --tb=short
```

All pre-existing Phase 1 tests must still pass. Zero regressions.

---

## ACCEPTANCE CRITERIA

- [ ] `langgraph>=0.2.0` in `pyproject.toml`, resolves via `uv sync`
- [ ] `src/orchestration/` module exists with `state.py`, `nodes.py`, `graph.py`, `__init__.py`
- [ ] Three sub-agents in `src/agent/`: `research_agent.py`, `analysis_agent.py`, `synthesis_agent.py`
- [ ] `POST /api/research` route returns a structured `WorkflowResponse` (answer, sources, confidence)
- [ ] Multi-agent workflow runs end-to-end with at least 3 Pydantic AI agents as nodes
- [ ] Conditional edge: `should_continue` routes to retry/continue/end based on `quality_score`
- [ ] `WorkflowState.pool` is excluded from serialisation (`model_dump()` does not contain "pool")
- [ ] Single Langfuse parent trace created per workflow run with per-node child spans
- [ ] Tracing gracefully no-ops when Langfuse keys are not configured
- [ ] All boundary tests pass (collector, agent, orchestration)
- [ ] All new tests pass (`test_orchestration.py`, `test_cross_agent_tracing.py`)
- [ ] All Phase 1 tests still pass — zero regressions
- [ ] `ruff check .` and `ruff format --check .` pass with zero errors
- [ ] `docs/pattern-decision-guide.md` exists covering all three patterns with decision criteria

---

## COMPLETION CHECKLIST

- [ ] TASK 1: `langgraph` added to `pyproject.toml`, `uv sync` clean, feature branch created
- [ ] TASK 2: `src/orchestration/__init__.py` created
- [ ] TASK 3: `src/orchestration/state.py` created, imports validate
- [ ] TASK 4: `src/agent/research_agent.py` created, imports validate
- [ ] TASK 5: `src/agent/analysis_agent.py` created, imports validate
- [ ] TASK 6: `src/agent/synthesis_agent.py` created, imports validate
- [ ] TASK 7: `src/orchestration/nodes.py` created, imports validate
- [ ] TASK 8: `src/orchestration/graph.py` created, imports validate
- [ ] TASK 9: `src/api/schemas.py` updated with `ResearchRequest`, `WorkflowResponse`
- [ ] TASK 10: `src/api/routes.py` updated with `POST /api/research`
- [ ] TASK 11: `tests/test_collector.py` updated with orchestration boundary test
- [ ] TASK 12: `tests/test_orchestration.py` created, passes
- [ ] TASK 13: `tests/test_cross_agent_tracing.py` created, passes
- [ ] TASK 14: `docs/pattern-decision-guide.md` created
- [ ] Level 1 validation: ruff passes
- [ ] Level 2 validation: all import checks pass
- [ ] Level 3 validation: all boundary tests pass
- [ ] Level 4 validation: new tests pass
- [ ] Level 5 validation: full suite passes, zero regressions
- [ ] All acceptance criteria met

---

## NOTES

### Closure alternative for pool injection (if Field(exclude=True) causes issues)

If `asyncpg.Pool` in state causes serialization errors with your LangGraph version, use this
closure pattern instead. Remove `pool` from `WorkflowState` entirely and inject it via factory:

```python
# In src/orchestration/graph.py

def _build_graph(pool: Pool) -> object:
    """Build graph with pool captured in node closures — no pool in state."""

    async def research_node(state: WorkflowState) -> dict:
        result = await research_agent.run(state.query, deps=pool)
        ...

    async def analysis_node(state: WorkflowState) -> dict:
        result = await analysis_agent.run(prompt, deps=pool)
        ...

    async def synthesis_node(state: WorkflowState) -> dict:
        result = await synthesis_agent.run(prompt, deps=pool)
        ...

    workflow = StateGraph(WorkflowState)
    workflow.add_node("research", research_node)
    ...
    return workflow.compile()


async def run_workflow(query: str, pool: Pool) -> AgentResponse:
    graph = _build_graph(pool)   # graph built per call (or cache per pool instance)
    initial_state = WorkflowState(query=query, trace_id=trace_id)
    final_state = await graph.ainvoke(initial_state)
    ...
```

With this approach `WorkflowState` has no `pool` field — it's purely serializable. The tradeoff
is that the graph is built per-request rather than once at module level (acceptable overhead;
`compile()` is fast). This is the canonical LangGraph pattern for runtime dependencies.

---

### Why `ainvoke` receives the model instance, not a dict

LangGraph's `ainvoke` accepts either a dict or the state type. Passing the `WorkflowState`
instance directly preserves the `pool` field in memory even though it's excluded from
`model_dump()`. Calling `.model_dump()` before `ainvoke` would silently drop the pool and cause
`AttributeError` inside every node.

### Why synthesis reuses `AgentResponse`

Pattern consistency: both `/api/ask` (Pattern 1) and `/api/research` (Pattern 2) return the same
shape. This means the frontend (Phase 6) can use a single response component for both endpoints,
and developers can see clearly that the underlying data contract is the same regardless of pattern.

### LangGraph version and Pydantic BaseModel state

LangGraph ≥ 0.2.0 natively supports Pydantic `BaseModel` as state. If you encounter issues with
state merging (LangGraph expecting a TypedDict), the fallback is to define `WorkflowState` as a
`TypedDict` and move the sub-models to a separate file. The Pydantic approach is preferred because
it provides field validation and is consistent with the rest of the codebase.

### Langfuse trace update pattern

Store the `trace` object before `ainvoke` and update it afterwards — do NOT reconstruct it by ID.
The `lf.trace(id=trace_id)` form is not guaranteed in all Langfuse v2 SDK versions:

```python
# CORRECT
trace = lf.trace(name="multi-agent-workflow", input={"query": query}, ...)
trace_id = trace.id
final_state = await _graph.ainvoke(initial_state)
trace.update(output={"answer": final_state.final_answer})   # use stored trace object

# AVOID (not guaranteed)
lf.trace(id=trace_id).update(...)
```

Update the `graph.py` Task 8 implementation to store `trace` as a local variable above the
`try` block so it's accessible in both the success path and the `except` block.

### Boundary test for src/orchestration/

`src/orchestration/` is allowed to import `pydantic_ai` and `langfuse` (it orchestrates agents).
The boundary test verifies only that `apscheduler` and `httpx` are absent. Do not add `pydantic_ai`
to the forbidden list for the orchestration boundary test.
