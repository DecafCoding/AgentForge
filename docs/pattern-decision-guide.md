# Pattern Decision Guide

AgentForge ships three patterns for orchestrating agent logic. This guide explains when to use each one, with concrete decision criteria and code examples from the codebase.

---

## Quick Decision Flowchart

```
Is there more than one agent?
│
├── No  ─────────────────────────────────────────────────────► Pattern 1
│         (Pydantic AI agent with tools)
│
└── Yes
    │
    Does "what happens next?" depend on the output of a previous step?
    │
    ├── No  (fixed linear sequence) ─────────────────────────► Plain Python
    │         (sequential await calls)
    │
    └── Yes (conditional routing, retry logic, branching) ──► Pattern 2
              (LangGraph + Pydantic AI)
```

**The practical test:** Describe your workflow out loud. If you find yourself saying "if the result is X then do Y, otherwise do Z" — that's Pattern 2. If every step always runs in the same order — plain Python or Pattern 1.

---

## Pattern 1 — Single Agent with Tools (Pydantic AI)

### When to use

- You have **one agent** with **multiple tools**
- The agent decides which tools to call based on the user's question (implicit orchestration)
- "What happens next?" always has the same answer regardless of tool results
- You want the **lowest operational overhead**

### Reference implementation

`src/agent/agent.py` — the YouTube research agent that calls `query_recent_videos`, `search_videos_by_query`, and `get_channel_statistics` based on what the user asks.

### Code pattern

```python
from pydantic_ai import Agent
from src.agent.models import AgentResponse
from src.config import get_model_string

agent: Agent[Pool, AgentResponse] = Agent(
    model=get_model_string(),
    deps_type=Pool,
    output_type=AgentResponse,
    defer_model_check=True,
    system_prompt="You are a YouTube research assistant...",
    tools=[query_recent_videos, search_videos_by_query, get_channel_statistics],
)

async def run_agent(question: str, pool: Pool) -> AgentResponse:
    result = await agent.run(question, deps=pool)
    return result.output
```

### Strengths

- Simple to implement, test, and debug
- No graph infrastructure overhead
- Pydantic AI handles the tool-calling loop automatically
- A single Langfuse trace captures the full interaction

### Limitations

- Cannot conditionally route to different agents based on intermediate results
- No built-in retry logic for quality thresholds
- Parallel execution of independent sub-tasks requires manual `asyncio.gather()`

---

## Pattern 2 — Multi-Agent Orchestration (LangGraph + Pydantic AI)

### When to use

- You have **multiple agents** that each handle a distinct phase of work
- Routing between phases **depends on the output of the previous phase** (quality score below threshold → retry, confidence high enough → proceed, etc.)
- You need **parallel branches** — for example, running a fact-checker alongside a summariser and merging both results
- You need **stateful coordination** — data produced by one agent is consumed by another in a typed, validated way

### Reference implementation

`src/orchestration/` — the three-node research → analysis → synthesis pipeline:

1. **Research node** (`research_agent.py`) — queries the database, returns findings
2. **Analysis node** (`analysis_agent.py`) — evaluates research quality, assigns `quality_score`
3. **Synthesis node** (`synthesis_agent.py`) — combines both into a final answer

The `should_continue` function routes after analysis: if `quality_score < 0.3`, retry research (up to `max_retries` times); otherwise proceed to synthesis.

### Code pattern

```python
# State flows between nodes as a typed Pydantic model
class WorkflowState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    query: str
    pool: Any = Field(exclude=True)  # runtime dep, not serialised
    research_output: ResearchOutput | None = None
    analysis_output: AnalysisOutput | None = None
    final_answer: str | None = None
    steps_completed: int = 0

# Each node receives the full state, returns a dict of partial updates
async def research_node(state: WorkflowState) -> dict:
    result = await research_agent.run(state.query, deps=state.pool)
    return {"research_output": ..., "steps_completed": state.steps_completed + 1}

# Conditional routing is a plain synchronous function
def should_continue(state: WorkflowState) -> str:
    if state.analysis_output.quality_score < 0.3:
        return "retry" if state.steps_completed < state.max_retries else "end"
    return "continue"

# Graph assembly
workflow = StateGraph(WorkflowState)
workflow.add_node("research", research_node)
workflow.add_node("analysis", analysis_node)
workflow.add_node("synthesis", synthesis_node)
workflow.add_edge(START, "research")
workflow.add_edge("research", "analysis")
workflow.add_conditional_edges("analysis", should_continue,
    {"continue": "synthesis", "retry": "research", "end": END})
workflow.add_edge("synthesis", END)
graph = workflow.compile()
```

### Key LangGraph rules

- Node functions receive the full `WorkflowState` and return a **dict** (partial state update)
- `graph.ainvoke(state)` returns a **dict**, not a model instance — access with `result['field_name']`
- Conditional edge functions **must be synchronous**
- The compiled graph is built once at module level — it does not embed the pool; the pool is in state

### Cross-agent observability

A single Langfuse parent trace spans the entire workflow. Each node creates a child span:

```
Trace: "multi-agent-workflow"
├── Span: "research_node"   (findings count, tokens, latency)
├── Span: "analysis_node"   (quality_score, gaps, tokens, latency)
└── Span: "synthesis_node"  (source count, confidence, tokens, latency)
```

Pass the `trace_id` through `WorkflowState` and create child spans in each node via `lf.span(name=..., trace_id=state.trace_id)`.

### Strengths

- Explicit, testable routing logic
- State is typed and validated at every transition
- Conditional edges are readable and auditable
- Parallel branches supported natively via `workflow.add_node` + converging edges
- Single cross-workflow Langfuse trace with per-agent detail

### Limitations

- More moving parts than Pattern 1 — more files, more concepts
- State management requires careful design (which fields are optional, what defaults to None)
- `ainvoke` returns a dict not a model — a minor ergonomic friction point
- Debugging requires tracing through node execution order, not a single call stack

---

## Plain Python Orchestration

### When to use

- Multiple agents, **fixed linear sequence** — every step always runs in the same order
- No conditional branching ("if quality is low, retry" → that's Pattern 2)
- You want maximum simplicity and readability

### Code pattern

```python
async def run_pipeline(query: str, pool: Pool) -> AgentResponse:
    # Step 1 always runs
    research = await research_agent.run(query, deps=pool)

    # Step 2 always runs, consumes step 1 output
    analysis = await analysis_agent.run(
        f"Analyse: {research.output.findings}", deps=pool
    )

    # Step 3 always runs
    synthesis = await synthesis_agent.run(
        f"Synthesise: {research.output.findings} | {analysis.output.assessment}",
        deps=pool,
    )
    return synthesis.output
```

### Strengths

- Simplest possible code — readable top-to-bottom
- No framework overhead, no state model required
- Easy to add logging and error handling inline

### Limitations

- No conditional routing — "if this then that" requires adding if/else around agent calls
- If/else grows into unreadable nesting quickly (the signal to move to Pattern 2)
- No built-in retry or parallel execution

---

## Migration Signals

### Plain Python → Pattern 2

You've outgrown plain Python when you start adding:

- `if result.quality < threshold: await research_agent.run(...) again` (retry logic)
- `if result.type == "A": await agent_a.run(...) else: await agent_b.run(...)` (conditional routing)
- `results = await asyncio.gather(agent_a.run(...), agent_b.run(...))` (parallel branches you then need to join with conditional logic)

When your coordination code grows beyond 3–5 lines of conditionals, extract it into a LangGraph graph.

### Pattern 1 → Pattern 2

You've outgrown a single agent when:

- The single agent's system prompt has grown to describe multiple distinct "modes" it switches between
- Tool calls depend on the results of previous tool calls in complex, stateful ways
- You want separate observability, retry budgets, or model choices per phase

---

## Summary Table

| | Pattern 1 | Pattern 2 | Plain Python |
|---|---|---|---|
| **Agents** | 1 | 2+ | 2+ |
| **Routing** | Implicit (tool-calling loop) | Conditional (explicit edges) | Fixed linear sequence |
| **State** | In agent context | Typed Pydantic model | Local variables |
| **Observability** | Single trace | Cross-workflow trace + spans | Manual |
| **Complexity** | Low | Medium | Lowest |
| **Files** | 1 agent + tools | 3+ agents + graph + state + nodes | Inline functions |
| **Use when** | One agent, any number of tools | Multi-step with conditional logic | Fixed linear multi-agent |
