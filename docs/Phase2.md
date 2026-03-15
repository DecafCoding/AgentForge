# Phase 2 — Multi-Agent Orchestration → v0.2

*AgentForge Starter Kit*

---

## Purpose of This Document

This document contains everything an AI or developer needs to build Phase 2 of AgentForge. It is self-contained. Phase 2 adds LangGraph as the multi-agent orchestration layer (Pattern 2), giving developers both architectural patterns with clear guidance on when to use each.

---

## Prerequisites (Phase 1 Complete)

Phase 2 assumes the following are already built and working from Phase 1:

- Project structure with `uv`, `ruff`, Docker Compose (bundled + shared profiles)
- Postgres 15 + pgvector with Alembic migrations
- Pydantic AI agent with tool registration and structured output (Pattern 1)
- FastAPI API layer with lifespan hook and APScheduler
- Langfuse observability wired into agent calls
- Collector/reasoning separation enforced by module structure
- OpenAI + Groq provider switching via env vars
- Reference YouTube monitor agent (collector + agent working end-to-end)
- Pytest skeleton and GitHub Actions CI

---

## What Phase 2 Delivers

LangGraph integrated as Pattern 2 — multi-agent orchestration with conditional routing, parallel execution, and stateful coordination. After this phase, the kit ships two complete patterns:

- **Pattern 1** (Phase 1): Single agent with tools — Pydantic AI alone
- **Pattern 2** (Phase 2): Multi-agent orchestration — LangGraph coordinating Pydantic AI agents

Developers get a clear decision guide for when to use each pattern, plus a working reference implementation for Pattern 2.

---

## Core Concepts

### When to Use Each Pattern

| Pattern | Tool | Use When |
|---------|------|----------|
| **Single agent with tools** | Pydantic AI | One agent, multiple tools, implicit orchestration via tool-calling loop. "What happens next?" always has the same answer regardless of previous output. |
| **Multi-agent orchestration** | LangGraph + Pydantic AI | Multiple agents, conditional routing, parallel branches, stateful coordination. "What happens next?" depends on what the previous step produced. |
| **Plain Python** | `await agent.run()` | Fixed linear sequence, no conditional branching. You can read the coordination logic top to bottom. |

**The practical test:** If you're asking "what happens next?" and the answer is always the same regardless of what the previous step produced, use plain Python or Pattern 1. If the answer depends on the output of the previous step — conditional edges, early termination, parallel branches with merge — that's where LangGraph earns its place.

### LangGraph's Role

LangGraph is a **graph runtime for orchestrating agents**, not an agent framework itself. It manages the workflow graph — nodes, edges, conditional routing, parallel execution, state checkpointing. Each node in the graph contains a Pydantic AI agent that handles its own reasoning. LangGraph does not replace Pydantic AI; it coordinates multiple Pydantic AI agents.

### State Management

Graph state is defined as Pydantic models. State flows between nodes through these models, which are serializable by default. This keeps the state contract explicit and type-safe.

---

## Technology Addition

| Layer | Tool | Role |
|-------|------|------|
| Multi-agent orchestration | `langgraph` | Graph-based coordination of Pydantic AI agents |

Add to `pyproject.toml`:
```toml
[project]
dependencies = [
    # ... existing Phase 1 deps ...
    "langgraph",
]
```

---

## Project Structure Changes

Add the following to the existing Phase 1 structure:

```
agentforge/
├── src/
│   ├── orchestration/              # NEW — LangGraph multi-agent workflows
│   │   ├── __init__.py
│   │   ├── graph.py                # Graph definition, node registration, edges
│   │   ├── state.py                # Pydantic models for graph state
│   │   └── nodes.py                # Node functions wrapping Pydantic AI agents
│   │
│   ├── agent/
│   │   ├── agent.py                # Existing Pattern 1 agent (unchanged)
│   │   ├── tools.py                # Existing tools (unchanged)
│   │   ├── research_agent.py       # NEW — Research agent for Pattern 2 example
│   │   ├── analysis_agent.py       # NEW — Analysis agent for Pattern 2 example
│   │   └── synthesis_agent.py      # NEW — Synthesis agent for Pattern 2 example
│   │
│   ├── api/
│   │   ├── routes.py               # MODIFIED — Add route for multi-agent workflow
│   │   └── schemas.py              # MODIFIED — Add request/response for workflow
│
├── docs/
│   └── pattern-decision-guide.md   # NEW — When to use Pattern 1 vs Pattern 2
│
└── tests/
    ├── test_orchestration.py       # NEW — Multi-agent workflow tests
    └── test_cross_agent_tracing.py # NEW — Langfuse span hierarchy tests
```

---

## Product Backlog Items (PBIs)

### PBI 2.1 — LangGraph Integration

**Description:** LangGraph dependency, graph setup pattern, Pydantic AI agents composing inside graph nodes.

**Done when:** A multi-agent workflow runs end-to-end. Each node is a standard Pydantic AI agent.

**Implementation details:**

**`src/orchestration/graph.py`** — Graph definition:
```python
from langgraph.graph import StateGraph, END
from src.orchestration.state import WorkflowState
from src.orchestration.nodes import research_node, analysis_node, synthesis_node, should_continue

def build_workflow() -> StateGraph:
    """Build and compile the multi-agent workflow graph."""
    workflow = StateGraph(WorkflowState)

    # Add nodes — each wraps a Pydantic AI agent
    workflow.add_node("research", research_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("synthesis", synthesis_node)

    # Define edges
    workflow.set_entry_point("research")
    workflow.add_edge("research", "analysis")
    workflow.add_conditional_edges(
        "analysis",
        should_continue,
        {
            "continue": "synthesis",
            "retry": "research",
            "end": END,
        }
    )
    workflow.add_edge("synthesis", END)

    return workflow.compile()
```

**`src/orchestration/nodes.py`** — Node functions:
```python
from src.orchestration.state import WorkflowState
from src.agent.research_agent import research_agent
from src.agent.analysis_agent import analysis_agent
from src.agent.synthesis_agent import synthesis_agent

async def research_node(state: WorkflowState) -> dict:
    """Run the research agent and update state."""
    result = await research_agent.run(state.query, deps=state.deps)
    return {"research_output": result.data, "steps_completed": state.steps_completed + 1}

async def analysis_node(state: WorkflowState) -> dict:
    """Run the analysis agent on research output."""
    result = await analysis_agent.run(
        f"Analyze: {state.research_output}",
        deps=state.deps,
    )
    return {"analysis_output": result.data, "quality_score": result.data.confidence}

async def synthesis_node(state: WorkflowState) -> dict:
    """Run the synthesis agent to produce final output."""
    result = await synthesis_agent.run(
        f"Synthesize research and analysis: {state.research_output} | {state.analysis_output}",
        deps=state.deps,
    )
    return {"final_output": result.data}

def should_continue(state: WorkflowState) -> str:
    """Conditional edge: decide next step based on analysis quality."""
    if state.quality_score and state.quality_score < 0.3:
        if state.steps_completed < 3:
            return "retry"
        return "end"
    return "continue"
```

**Key integration points:**
- Each node function receives the full `WorkflowState` and returns a dict of state updates
- Inside each node, a standard Pydantic AI agent runs with `agent.run()`
- The Pydantic AI agent inside a LangGraph node works identically to how it works standalone
- LangGraph handles the routing; Pydantic AI handles the reasoning

### PBI 2.2 — State Management

**Description:** Graph state defined as Pydantic models, state passing between nodes, serialization.

**Done when:** State flows correctly between agents. Pydantic models serialize/deserialize cleanly.

**Implementation details:**

**`src/orchestration/state.py`:**
```python
from pydantic import BaseModel, Field
from typing import Any, Optional

class WorkflowState(BaseModel):
    """State that flows through the multi-agent workflow graph.

    LangGraph passes this between nodes. Each node receives the full state
    and returns a dict of updates to merge into state.
    """
    # Input
    query: str
    deps: Any = Field(exclude=True)  # Database pool, not serialized

    # Research phase output
    research_output: Optional[str] = None

    # Analysis phase output
    analysis_output: Optional[str] = None
    quality_score: Optional[float] = None

    # Synthesis phase output
    final_output: Optional[str] = None

    # Workflow metadata
    steps_completed: int = 0
    max_steps: int = 5
```

**State design rules:**
- State is always a Pydantic model — type-safe, serializable, validatable
- Non-serializable dependencies (like the database pool) use `Field(exclude=True)`
- Each node returns only the fields it updates, not the full state
- LangGraph merges the returned dict into the existing state

### PBI 2.3 — Cross-Agent Observability

**Description:** Langfuse traces that span the full multi-agent workflow with per-agent detail as child spans.

**Done when:** A single Langfuse trace shows the entire workflow with nested agent-level detail.

**Implementation details:**

The goal is a trace hierarchy like this in Langfuse:

```
Trace: "multi-agent-workflow" (total time, total cost)
├── Span: "research_node" (agent prompt, response, tokens, cost, latency)
├── Span: "analysis_node" (agent prompt, response, tokens, cost, latency)
└── Span: "synthesis_node" (agent prompt, response, tokens, cost, latency)
```

**Implementation approach:**
- Create a parent Langfuse trace at the start of the workflow
- Pass the trace context (trace ID) through the `WorkflowState` or as a dependency
- Each Pydantic AI agent call creates a child span under the parent trace
- Use Langfuse's `trace.span()` to create named spans for each node
- The parent trace aggregates total tokens, cost, and latency across all agents

```python
from langfuse import Langfuse

langfuse = Langfuse()

async def run_workflow(query: str, pool):
    trace = langfuse.trace(name="multi-agent-workflow", input={"query": query})

    # Pass trace to nodes via state or deps
    state = WorkflowState(query=query, deps=pool, trace_id=trace.id)
    result = await workflow.ainvoke(state)

    trace.update(output={"result": result.get("final_output")})
    return result
```

**Each node creates a child span:**
```python
async def research_node(state: WorkflowState) -> dict:
    span = langfuse.span(name="research_node", trace_id=state.trace_id)
    result = await research_agent.run(state.query, deps=state.deps)
    span.update(output=result.data, metadata={"tokens": result.usage})
    span.end()
    return {"research_output": result.data}
```

### PBI 2.4 — Pattern 2 Reference Example

**Description:** Working multi-agent example demonstrating conditional edges, parallel execution, and state-dependent routing.

**Done when:** Example is clear enough that a developer can adapt it to their own multi-agent problem.

**Implementation details:**

The reference example demonstrates a **research → analysis → synthesis** pipeline:

1. **Research Agent** — Queries the database and gathers relevant information about a topic
2. **Analysis Agent** — Evaluates the research quality and identifies gaps or patterns
3. **Synthesis Agent** — Combines research and analysis into a final structured response

**What the example demonstrates:**
- **Conditional edges:** If analysis quality score is below threshold, retry research (up to max_steps)
- **State-dependent routing:** The `should_continue` function reads `quality_score` from state to decide the next node
- **Pydantic model state:** All inter-agent data flows through typed `WorkflowState`
- **Cross-agent tracing:** Single Langfuse trace spans the entire workflow

**Each agent is a standalone Pydantic AI agent:**

```python
# src/agent/research_agent.py
from pydantic_ai import Agent
from pydantic import BaseModel

class ResearchOutput(BaseModel):
    findings: list[str]
    sources: list[str]
    confidence: float

research_agent = Agent(
    model=get_model_string(),
    system_prompt="You are a research agent. Query the database to find relevant information.",
    tools=[query_videos, search_videos],
    result_type=ResearchOutput,
)
```

**API integration:**

Add a new route for the multi-agent workflow:

```python
# In src/api/routes.py
@router.post("/api/research", response_model=WorkflowResponse)
async def research(request: Request, body: ResearchRequest):
    result = await run_workflow(body.query, request.app.state.pool)
    return WorkflowResponse(...)
```

### PBI 2.5 — Pattern Decision Guide

**Description:** Documentation explaining Pattern 1 vs Pattern 2 vs plain Python orchestration with concrete decision criteria and examples.

**Done when:** Developer can read the guide and know which pattern to use for their use case.

**Implementation details:**

**`docs/pattern-decision-guide.md`** should cover:

**1. Quick Decision Flowchart:**
- How many agents? → If one → Pattern 1
- Is routing conditional on output? → If no → Plain Python
- Need parallel execution, conditional edges, or checkpointing? → Pattern 2

**2. Pattern 1 — Single Agent with Tools (Pydantic AI)**
- When to use: one agent, multiple tools, implicit orchestration
- Reference: YouTube monitor agent
- Code example showing agent setup with tools
- Strengths: simple, less overhead, easy to test
- Limitations: no conditional routing between agents

**3. Pattern 2 — Multi-Agent Orchestration (LangGraph + Pydantic AI)**
- When to use: multiple agents, conditional routing, parallel branches
- Reference: research/analysis/synthesis pipeline
- Code example showing graph, nodes, conditional edges
- Strengths: complex workflows, conditional logic, parallel execution
- Limitations: more complexity, harder to debug, state management overhead

**4. Plain Python Orchestration**
- When to use: fixed linear sequence, no conditional branching
- Code example: sequential `await agent.run()` calls
- Strengths: simplest to understand and debug
- Limitations: no conditional routing, no parallelism

**5. Migration Guide**
- How to upgrade from Plain Python → Pattern 2 when you outgrow it
- Signs that you need LangGraph (adding if/else around agent calls, manual retry logic, etc.)

---

## Acceptance Criteria (Phase 2 Complete)

All of these must be true (in addition to all Phase 1 criteria still passing):

1. `langgraph` is in `pyproject.toml` and resolves via `uv sync`
2. A multi-agent workflow runs end-to-end through LangGraph with at least 3 Pydantic AI agents as nodes
3. Each node contains a standard Pydantic AI agent that works identically to standalone usage
4. Graph state is defined as a Pydantic model and flows correctly between all nodes
5. Conditional edges work: the `should_continue` function routes based on state values
6. A single Langfuse trace shows the entire multi-agent workflow with per-agent child spans
7. The trace includes per-agent token count, cost, and latency
8. `POST /api/research` (or equivalent) triggers the multi-agent workflow and returns a structured response
9. The Pattern Decision Guide (`docs/pattern-decision-guide.md`) exists and covers all three patterns with examples
10. All existing Phase 1 tests still pass
11. New tests cover: workflow execution, conditional routing, state management, cross-agent tracing
12. The reference example is complete enough that a developer can adapt it to their own multi-agent problem

---

## What Is NOT in Phase 2

These remain deferred:

- **Long-term memory** (Mem0) → Phase 3
- **Web scraping** (Crawl4AI) → Phase 3
- **Web search** (Brave Search) → Phase 3
- **Local model serving** (Ollama, vLLM) → Phase 4
- **Caching** (Redis/Valkey) → Phase 4
- **Evaluation pipelines** (Ragas) → Phase 5
- **MCP server exposure** (FastMCP) → Phase 5
- **Frontend / UI** → Phase 6
- **Reverse proxy / HTTPS** (Caddy) → Phase 6
- **LangGraph checkpointing / persistence** — Only if needed by a real use case
- **LangGraph Studio integration** — Nice to have, not required

---

*This document is the complete specification for Phase 2 of AgentForge. It contains everything needed to add multi-agent orchestration without referencing external documents.*
