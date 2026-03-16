# Memory-Aware Agent Design Guide

*AgentForge Starter Kit — Phase 3*

---

## Overview

Adding long-term memory to agents is not just a feature addition — it fundamentally changes how agents behave. A memory-aware agent has context that persists across sessions, making it more useful but also less predictable.

This guide covers what changes when you add memory, how to maintain predictability, and how to test memory-aware agents effectively.

---

## What Changes With Memory

### System Prompt Becomes Dynamic

Without memory, the system prompt is a static string defined once at agent creation. With memory, the prompt is assembled per-request by appending relevant memories:

```python
# Static (Pattern 1)
agent = Agent(system_prompt="You are a research assistant...")

# Dynamic (Memory-aware)
memory_context = await get_relevant_context(store, question, user_id)
system_prompt = f"{BASE_PROMPT}\n\n{memory_context}"
agent = Agent(system_prompt=system_prompt, ...)
```

This means the agent must be created fresh per-call rather than as a module-level singleton. This is an intentional design trade-off documented in `src/agent/memory_agent.py`.

### Agent Behavior Is No Longer Stateless

The same question may produce different answers for different users because each user has a different memory corpus. User A who previously discussed Python tutorials will get a different response than User B who discussed machine learning.

This is the core value of memory — but it means you cannot predict agent output from the input alone. You must also know the user's memory state.

### Token Usage Increases

Every request now includes memory context in the system prompt. With 5 retrieved memories averaging 50 tokens each, that adds ~250 tokens per request. At scale, this has cost implications:

- **Budget accordingly**: Memory context adds tokens to every prompt.
- **Limit memory count**: The `limit` parameter in `get_relevant_context()` controls how many memories are injected (default: 5).
- **Monitor via Langfuse**: The `memory_context_length` trace metadata tracks the exact token overhead per request.

### Response Quality Can Vary

Irrelevant memories can confuse the agent. If the memory search returns tangentially related content, the agent may incorporate it incorrectly. This is why memory is appended as supplementary context, not as authoritative instructions.

---

## Predictability Guidelines

### 1. Make Memory Injection Explicit

Memory context is always visible in Langfuse traces. The `run_memory_agent()` function logs:

- `has_memory` (bool) — whether any memories were injected
- `memory_context_length` (int) — character count of injected context
- `user_id` — which user's memories were retrieved

This makes it possible to debug why an agent gave a particular response.

### 2. Limit Memory Count

Retrieve 5-10 memories maximum per request. More memories increase token usage and the risk of injecting irrelevant context:

```python
context = await get_relevant_context(store, query, user_id, limit=5)
```

The default limit of 5 balances relevance with cost.

### 3. Log Memory Usage in Langfuse

Every memory agent call includes trace metadata:

```python
trace = lf.trace(
    name="memory_agent_run",
    metadata={
        "memory_context_length": len(memory_context),
        "has_memory": bool(memory_context),
    },
)
```

Use Langfuse dashboards to monitor memory usage patterns and identify when memory context degrades response quality.

### 4. Provide Memory Reset

Users should be able to clear their memories for debugging or privacy. The `BaseMemoryStore.get_all()` and `BaseMemoryStore.delete()` methods support this. A future admin endpoint or CLI command can expose this capability.

### 5. Memory Supplements, Never Overrides

The core system prompt is always present. Memory context is appended after it:

```python
system_prompt = f"{_BASE_SYSTEM_PROMPT}\n\n{memory_context}"
```

The agent's core behavior and guidelines are defined in `_BASE_SYSTEM_PROMPT`. Memories provide additional context but cannot override the base instructions.

---

## Memory Patterns

### User Preference Learning

Store stated preferences and retrieve them for future interactions:

- "I prefer Python tutorials over JavaScript"
- "I'm interested in channels about machine learning"

The agent can use these to prioritize relevant content in responses.

### Cross-Session Context

Remember previous discussion topics so users don't have to repeat context:

- "Last time you asked about deploying FastAPI apps"
- "You were researching async patterns in Python"

### Behavioral Pattern Recognition

Track recurring questions or interests over time. If a user consistently asks about a specific channel or topic, the agent can proactively surface related content.

### Anti-Pattern: Memory as Database

Do not use memory to store facts that belong in the database. Memories are for conversational context and user preferences — not structured data. Video metadata belongs in `youtube_videos`, not in the memory store.

---

## Testing Memory-Aware Agents

### Test With Empty Memory (New User)

The agent must work normally without any memory context. A new user with no history should get the same quality of response as the Pattern 1 agent:

```python
async def test_run_memory_agent_works_with_empty_memory():
    mock_store.search = AsyncMock(return_value=[])
    result = await run_memory_agent(question, user_id, pool, mock_store)
    assert result.answer  # Agent still produces a valid response
```

### Test With Populated Memory (Returning User)

Verify the agent incorporates relevant memories. Check that the system prompt passed to the Agent constructor includes the memory context:

```python
async def test_run_memory_agent_injects_memory_context():
    # Verify Agent() is called with a system_prompt containing memory text
    assert "previous conversations" in captured_system_prompt
```

### Test Memory Relevance

Verify the right memories are retrieved for a given query. This is primarily a test of the memory store's search function, but end-to-end tests should confirm that the agent receives relevant context.

### Test Memory Accumulation

Monitor whether performance degrades as a user's memory corpus grows. With vector search (Mem0 + pgvector), retrieval should remain fast regardless of corpus size, but the quality of retrieved memories may shift.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_ENABLED` | `true` | Enable/disable the memory layer entirely |
| `MEMORY_MODEL` | `gpt-4o-mini` | LLM used by Mem0 for memory extraction |

When `MEMORY_ENABLED=false`:
- `app.state.memory` is `None`
- `POST /api/ask/memory` returns **503 Service Unavailable**
- All other endpoints work normally

---

## API Reference

### POST /api/ask/memory

Submit a question to the memory-aware agent. Requires `MEMORY_ENABLED=true`.

**Request:**
```json
{
  "question": "What videos have been posted recently?",
  "user_id": "user-123"
}
```

**Response (200):**
```json
{
  "answer": "Based on the recent uploads and your previous interest in Python tutorials...",
  "sources": [
    {"title": "Advanced Python Patterns", "video_id": "abc123", "url": "https://youtube.com/watch?v=abc123"}
  ],
  "confidence": 0.85
}
```

**Error Responses:**
- **422** — Invalid request body (empty question or missing user_id)
- **503** — Memory is not enabled (`MEMORY_ENABLED=false`)
- **500** — Agent failed to process the request
