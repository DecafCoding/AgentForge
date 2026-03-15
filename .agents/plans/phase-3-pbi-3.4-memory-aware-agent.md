# PBI 3.4 — Memory-Aware Agent Patterns

The following plan should be complete, but validate documentation and codebase patterns before implementing.

## Feature Description

Deliver the reference memory-aware agent implementation and documentation on how agent design changes with long-term memory. This PBI wires together the memory layer (PBI 3.1) and optionally web search (PBI 3.3) into a working agent with an API endpoint. It also produces `docs/memory-aware-agents.md` covering predictability guidelines and testing patterns.

## User Story

As a Python developer building AI agents
I want a reference implementation of a memory-aware agent and guidelines for using memory predictably
So that I can add memory to my own agents without introducing unpredictable behavior

## Feature Metadata

**Feature Type**: New Capability + Documentation
**Estimated Complexity**: Medium
**Primary Systems Affected**: `src/agent/`, `src/api/`, `docs/`
**Dependencies**: PBI 3.1 (Mem0 integration) must be complete. PBI 3.3 (Brave Search) is optional.
**Branch**: `feat/pbi-3.4-memory-aware-agent` (from `main`, after PBI 3.1 merged)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING!

- `CLAUDE.md` — Coding conventions, boundary rules. READ FIRST.
- `docs/Phase3.md` (lines 370-441) — PBI 3.4 specification: memory agent, docs requirements
- `src/agent/agent.py` (lines 1-129) — Pattern 1 agent + `run_agent()` with Langfuse tracing. MIRROR THIS.
- `src/agent/models.py` (lines 1-35) — `AgentResponse`, `Source` models reused here
- `src/agent/tools.py` (lines 1-94+) — Existing tools; `web_search` if PBI 3.3 is merged
- `src/agent/research_agent.py` (lines 1-59) — Standalone agent definition pattern
- `src/memory/store.py` — `BaseMemoryStore` ABC (from PBI 3.1)
- `src/memory/helpers.py` — `get_relevant_context()`, `store_interaction()` (from PBI 3.1)
- `src/observability/tracing.py` (lines 1-62) — Langfuse client pattern
- `src/config.py` — `get_model_string()`, `MODEL_PROVIDER`, `MODEL_NAME`, `MEMORY_ENABLED`
- `src/api/routes.py` (lines 1-94) — Thin route pattern
- `src/api/schemas.py` (lines 1-53) — API schema pattern
- `src/api/main.py` — `app.state.memory` (from PBI 3.1)
- `tests/test_agent.py` (lines 1-214) — Agent mock patterns
- `tests/test_api.py` (lines 1-127) — API test patterns
- `tests/conftest.py` — `mock_pool`, `mock_memory_store`, `client` fixtures
- `docs/pattern-decision-guide.md` — Existing docs style reference

### New Files to Create

- `src/agent/memory_agent.py` — Memory-aware agent implementation
- `docs/memory-aware-agents.md` — Design changes, predictability, testing guide
- `tests/test_memory_agent.py` — Memory agent tests

### Files to Modify

- `src/api/schemas.py` — Add `MemoryAskRequest`, `MemoryAskResponse`
- `src/api/routes.py` — Add `POST /api/ask/memory` route

### Patterns to Follow

**Agent + Tracing Pattern** (from `src/agent/agent.py:65-129`):
```python
async def run_agent(question: str, pool: Pool) -> AgentResponse:
    lf = get_langfuse()
    if lf is None:
        result = await agent.run(question, deps=pool)
        return result.output
    trace = lf.trace(name="agent_run", input={"question": question}, ...)
    generation = trace.generation(name="...", model=..., input=question)
    try:
        result = await agent.run(question, deps=pool)
        generation.end(output=..., usage=...)
        return result.output
    except ...:
        generation.end(level="ERROR", ...)
        raise
    finally:
        lf.flush()
```

**Route Pattern** (from `src/api/routes.py`):
```python
@router.post("/api/ask", response_model=AskResponse, tags=["agent"])
async def ask(request: Request, body: AskRequest) -> AskResponse:
    pool = request.app.state.pool
    try:
        response = await run_agent(body.question, pool)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="...") from exc
    return AskResponse(answer=response.answer, sources=response.sources)
```

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `src/agent/memory_agent.py` — Memory-aware agent

- **IMPLEMENT**:
  ```python
  """
  Memory-aware agent — reference implementation.

  Demonstrates how agent design changes with long-term memory: the system
  prompt becomes dynamic (injected with relevant memories from previous
  sessions), and each interaction is stored for future retrieval. Reuses
  the existing tools and AgentResponse model for consistency with Pattern 1.

  The agent is created fresh per-call because the system prompt varies
  with the user's memory context. This is intentional and differs from
  Pattern 1/2 where agents are module-level singletons.

  This module belongs to the Agent layer and must not import apscheduler,
  httpx, or any collector dependency.
  """

  import logging

  from asyncpg import Pool
  from pydantic_ai import Agent

  from src.agent.models import AgentResponse
  from src.agent.tools import (
      get_channel_statistics,
      query_recent_videos,
      search_videos_by_query,
  )
  from src.config import MODEL_NAME, MODEL_PROVIDER, get_model_string
  from src.memory.helpers import get_relevant_context, store_interaction
  from src.memory.store import BaseMemoryStore
  from src.observability.tracing import get_client as get_langfuse

  logger = logging.getLogger(__name__)

  _BASE_SYSTEM_PROMPT = (
      "You are a YouTube content research assistant with memory. "
      "You remember previous conversations and can reference them.\n\n"
      "Guidelines:\n"
      "- Use your tools to look up data before answering. "
      "Do not guess or make up information.\n"
      "- Cite every video you reference in the sources field.\n"
      "- If the database has no relevant data, say so clearly.\n"
      "- Use the memory context below (if present) to provide "
      "continuity across sessions.\n"
      "- Set confidence to reflect how well the data supports your answer."
  )
  ```

  **Tools list**: Include `query_recent_videos`, `search_videos_by_query`, `get_channel_statistics`. If PBI 3.3 is merged, also include `web_search` from `src.agent.tools`. Check if `web_search` exists in tools.py and include conditionally:
  ```python
  _TOOLS = [query_recent_videos, search_videos_by_query, get_channel_statistics]
  try:
      from src.agent.tools import web_search
      _TOOLS.append(web_search)
  except ImportError:
      pass
  ```

  **Main function:**
  ```python
  async def run_memory_agent(
      question: str,
      user_id: str,
      pool: Pool,
      memory_store: BaseMemoryStore,
  ) -> AgentResponse:
      """Run a memory-aware agent that injects context from previous sessions.

      Creates a parent Langfuse trace spanning the full interaction. Memory
      retrieval and storage are logged as metadata in the trace. The agent
      is created fresh per-call because the system prompt is dynamic.

      Args:
          question: The user's natural-language question.
          user_id: User identifier for scoping memory context.
          pool: asyncpg connection pool for database tools.
          memory_store: Memory store for retrieving and storing memories.

      Returns:
          Structured AgentResponse with answer, sources, and confidence.
      """
      # 1. Retrieve relevant memories
      memory_context = await get_relevant_context(memory_store, question, user_id)

      # 2. Build dynamic system prompt
      if memory_context:
          system_prompt = f"{_BASE_SYSTEM_PROMPT}\n\n{memory_context}"
      else:
          system_prompt = _BASE_SYSTEM_PROMPT

      # 3. Create agent with memory-augmented prompt
      agent: Agent[Pool, AgentResponse] = Agent(
          model=get_model_string(),
          deps_type=Pool,
          output_type=AgentResponse,
          defer_model_check=True,
          system_prompt=system_prompt,
          tools=_TOOLS,
      )

      # 4. Run with Langfuse tracing
      lf = get_langfuse()

      if lf is None:
          result = await agent.run(question, deps=pool)
          await store_interaction(memory_store, question, result.output.answer, user_id)
          return result.output

      trace = lf.trace(
          name="memory_agent_run",
          input={"question": question, "user_id": user_id},
          metadata={
              "provider": MODEL_PROVIDER,
              "model": MODEL_NAME,
              "memory_context_length": len(memory_context),
              "has_memory": bool(memory_context),
          },
      )
      generation = trace.generation(
          name="memory_aware_agent",
          model=f"{MODEL_PROVIDER}/{MODEL_NAME}",
          input=question,
      )

      try:
          result = await agent.run(question, deps=pool)
          usage = result.usage()

          generation.end(
              output=result.output.model_dump(),
              usage={
                  "input": usage.request_tokens or 0,
                  "output": usage.response_tokens or 0,
                  "total": usage.total_tokens or 0,
                  "unit": "TOKENS",
              },
          )
          trace.update(output={"answer": result.output.answer})

          # 5. Store this interaction (fire-and-forget — don't block on failure)
          await store_interaction(memory_store, question, result.output.answer, user_id)

          logger.info(
              "Memory agent run complete",
              extra={
                  "user_id": user_id,
                  "tokens_total": usage.total_tokens,
                  "has_memory": bool(memory_context),
                  "confidence": result.output.confidence,
              },
          )
          return result.output

      except Exception as exc:
          generation.end(level="ERROR", status_message=str(exc))
          trace.update(level="ERROR", status_message=str(exc))
          logger.error("Memory agent run failed", extra={"error": str(exc)})
          raise

      finally:
          lf.flush()
  ```

- **GOTCHA**: Agent is created per-call (not module-level) because system_prompt is dynamic. Document this.
- **GOTCHA**: `store_interaction()` is called after the response — it never raises (caught internally), so it won't crash the response.
- **GOTCHA**: Memory context length is logged in Langfuse metadata for observability.
- **VALIDATE**: `uv run python -c "from src.agent.memory_agent import run_memory_agent; print('OK')"`

---

### Task 2: UPDATE `src/api/schemas.py` — Add memory endpoint schemas

- **IMPLEMENT**: Add after existing schemas:
  ```python
  class MemoryAskRequest(BaseModel):
      """Request body for POST /api/ask/memory."""

      question: str = Field(
          min_length=1,
          description="The question to ask the memory-aware agent.",
      )
      user_id: str = Field(
          min_length=1,
          description="User identifier for scoping memory context.",
      )


  class MemoryAskResponse(BaseModel):
      """Response body for POST /api/ask/memory."""

      answer: str
      sources: list[Source]
      confidence: float
  ```
- **PATTERN**: Mirror `AskRequest`/`AskResponse` at schemas.py:17-30
- **VALIDATE**: `uv run python -c "from src.api.schemas import MemoryAskRequest, MemoryAskResponse; print('OK')"`

---

### Task 3: UPDATE `src/api/routes.py` — Add memory-aware agent route

- **IMPLEMENT**: Add after existing routes:
  ```python
  from src.agent.memory_agent import run_memory_agent
  from src.api.schemas import MemoryAskRequest, MemoryAskResponse
  ```
  (Add to existing import blocks)

  ```python
  @router.post("/api/ask/memory", response_model=MemoryAskResponse, tags=["agent"])
  async def ask_with_memory(request: Request, body: MemoryAskRequest) -> MemoryAskResponse:
      """Submit a question to the memory-aware agent.

      Runs a Pydantic AI agent with memory context injected from previous
      sessions. Requires MEMORY_ENABLED=true. The interaction is stored
      as a new memory for future retrieval.

      Args:
          request: FastAPI request object (used to access app.state).
          body: Validated request body with question and user_id.

      Returns:
          Structured response with answer, sources, and confidence.
      """
      pool = request.app.state.pool
      memory_store = getattr(request.app.state, "memory", None)

      if memory_store is None:
          raise HTTPException(
              status_code=503,
              detail="Memory is not enabled. Set MEMORY_ENABLED=true to use this endpoint.",
          )

      logger.info(
          "Received memory-aware question",
          extra={"question": body.question[:120], "user_id": body.user_id},
      )

      try:
          response = await run_memory_agent(body.question, body.user_id, pool, memory_store)
      except Exception as exc:
          logger.error("Memory agent failed", extra={"error": str(exc)})
          raise HTTPException(
              status_code=500,
              detail="Memory agent failed to process the request.",
          ) from exc

      return MemoryAskResponse(
          answer=response.answer,
          sources=response.sources,
          confidence=response.confidence,
      )
  ```
- **GOTCHA**: Use `getattr(request.app.state, "memory", None)` for safety — returns None if attribute doesn't exist.
- **GOTCHA**: Return 503 (Service Unavailable) when memory is disabled, not 400.
- **PATTERN**: Mirror `ask()` and `research()` routes exactly
- **VALIDATE**: `uv run python -c "from src.api.routes import router; print('OK')"`

---

### Task 4: CREATE `docs/memory-aware-agents.md` — Documentation

- **IMPLEMENT**: Comprehensive documentation following existing doc style from `docs/pattern-decision-guide.md`:

  ```markdown
  # Memory-Aware Agent Design Guide

  *AgentForge Starter Kit — Phase 3*

  ---

  ## Overview

  Adding long-term memory to agents is not just a feature addition — it fundamentally
  changes how agents behave. A memory-aware agent has context that persists across
  sessions, making it more useful but also less predictable.

  This guide covers what changes, how to maintain predictability, and how to test.

  ---

  ## What Changes With Memory

  ### System Prompt Becomes Dynamic
  [Explain: memories injected into system prompt, prompt varies per user]

  ### Agent Behavior Is No Longer Stateless
  [Explain: same question may produce different answers for different users]

  ### Token Usage Increases
  [Explain: memory context adds tokens to every prompt, cost implications]

  ### Response Quality Can Vary
  [Explain: irrelevant memories can confuse the agent]

  ---

  ## Predictability Guidelines

  ### 1. Make Memory Injection Explicit
  [Always visible in logs and Langfuse traces]

  ### 2. Limit Memory Count
  [5-10 memories max per request, configurable via limit parameter]

  ### 3. Log Memory Usage in Langfuse
  [memory_context_length, has_memory, user_id in trace metadata]

  ### 4. Provide Memory Reset
  [Users should be able to clear their memories for debugging]

  ### 5. Memory Supplements, Never Overrides
  [Core system prompt is always present; memory is appended]

  ---

  ## Memory Patterns

  ### User Preference Learning
  [Store stated preferences, retrieve for future interactions]

  ### Cross-Session Context
  [Remember previous discussion topics]

  ### Behavioral Pattern Recognition
  [Track recurring questions or interests]

  ### Anti-Pattern: Memory as Database
  [Don't use memory to store facts that belong in the database]

  ---

  ## Testing Memory-Aware Agents

  ### Test With Empty Memory (New User)
  [Agent should work normally without any memory context]

  ### Test With Populated Memory (Returning User)
  [Agent should incorporate relevant memories naturally]

  ### Test Memory Relevance
  [Verify the right memories are retrieved for a given query]

  ### Test Memory Accumulation
  [Does performance degrade as memory corpus grows?]

  ---

  ## Configuration

  | Variable | Default | Description |
  |----------|---------|-------------|
  | MEMORY_ENABLED | true | Enable/disable memory layer |
  | MEMORY_MODEL | gpt-4o-mini | LLM used by Mem0 for memory extraction |

  ---

  ## API Reference

  ### POST /api/ask/memory

  Request:
  ```json
  {
    "question": "What videos have been posted recently?",
    "user_id": "user-123"
  }
  ```

  Response:
  ```json
  {
    "answer": "Based on the recent uploads...",
    "sources": [...],
    "confidence": 0.85
  }
  ```

  Returns 503 when MEMORY_ENABLED=false.
  ```

- **Fill in all section content** with practical, specific guidance. Not placeholder text.
- **PATTERN**: Follow `docs/pattern-decision-guide.md` style — headers, tables, code examples
- **VALIDATE**: Visual review

---

### Task 5: CREATE `tests/test_memory_agent.py` — Memory agent tests

- **IMPLEMENT**:
  ```python
  """
  Memory-aware agent tests.

  Covers run_memory_agent() with mocked LLM, memory store, and Langfuse.
  No real API calls or database connections are made.
  """

  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest
  ```

  **Tests:**

  - `test_run_memory_agent_returns_response_without_tracing`:
    - Mock `get_langfuse` → None
    - Mock agent.run → AgentResponse
    - Mock `get_relevant_context` → ""
    - Mock `store_interaction` → "mem-id"
    - Verify response returned correctly

  - `test_run_memory_agent_injects_memory_context`:
    - Mock `get_relevant_context` → "Relevant context..."
    - Capture the system_prompt passed to Agent() — verify it contains the memory context
    - Use `patch("src.agent.memory_agent.Agent")` to capture constructor args

  - `test_run_memory_agent_stores_interaction_after_response`:
    - Verify `store_interaction` called with question, answer, user_id

  - `test_run_memory_agent_creates_langfuse_trace_with_memory_metadata`:
    - Mock Langfuse client
    - Verify trace metadata includes `memory_context_length` and `has_memory`

  - `test_run_memory_agent_works_with_empty_memory`:
    - `get_relevant_context` returns ""
    - Agent still runs and returns response (new user experience)

  - `test_run_memory_agent_propagates_agent_exception`:
    - Agent.run raises RuntimeError
    - Verify it propagates, Langfuse trace marked ERROR

  **API route tests (in `tests/test_api.py` or here):**
  - `test_ask_memory_returns_503_when_memory_disabled`:
    ```python
    async def test_ask_memory_returns_503_when_memory_disabled(client):
        """POST /api/ask/memory returns 503 when app.state.memory is None."""
        response = await client.post(
            "/api/ask/memory",
            json={"question": "test", "user_id": "user-1"},
        )
        assert response.status_code == 503
    ```
  - `test_ask_memory_returns_answer_on_success` — Mock `run_memory_agent`
  - `test_ask_memory_rejects_empty_question` — 422 validation
  - `test_ask_memory_rejects_missing_user_id` — 422 validation

- **PATTERN**: Mirror `tests/test_agent.py` mock patterns
- **VALIDATE**: `uv run pytest tests/test_memory_agent.py -v`

---

### Task 6: RUN full validation

- **VALIDATE**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest tests/ -v --tb=short
  ```

---

## TESTING STRATEGY

### Unit Tests
- Mock Pydantic AI `Agent` class — no real LLM calls
- Mock `BaseMemoryStore` — no real Mem0 or Postgres
- Mock Langfuse — no real tracing
- Test agent creation, memory injection, interaction storage, error handling

### Integration Tests (API)
- Test `/api/ask/memory` with mocked agent and memory store
- Test 503 when memory disabled
- Test input validation

### Edge Cases
- Empty memory context (new user) → agent works normally
- Memory store raises during context retrieval → empty context, agent continues
- Memory store raises during interaction storage → response still returned
- Langfuse not configured → agent runs without tracing
- Agent raises exception → Langfuse trace marked ERROR, exception propagated

---

## ACCEPTANCE CRITERIA

- [ ] `run_memory_agent()` retrieves memories, injects into prompt, runs agent, stores interaction
- [ ] Agent is created per-call with dynamic system prompt (documented as intentional)
- [ ] Memory context logged in Langfuse trace metadata
- [ ] `POST /api/ask/memory` works end-to-end with question + user_id
- [ ] 503 returned when `MEMORY_ENABLED=false`
- [ ] `docs/memory-aware-agents.md` covers design changes, predictability, testing
- [ ] All existing tests still pass
- [ ] New tests cover: response, memory injection, storage, tracing, empty memory, errors, API

---

## NOTES

- **Dynamic agent creation**: The memory agent creates `Agent()` per-call because the system prompt varies with memory context. This is different from Pattern 1/2 singletons. Document clearly.
- **Depends on PBI 3.1**: This PBI requires the memory layer from 3.1. The `BaseMemoryStore`, `get_relevant_context()`, and `store_interaction()` must exist.
- **Optional PBI 3.3**: If Brave Search (PBI 3.3) is merged, the memory agent includes `web_search` in its tools. If not, it works with just the database tools.
- **store_interaction is fire-and-forget**: It catches all exceptions internally. Memory write failure never crashes the agent response.
