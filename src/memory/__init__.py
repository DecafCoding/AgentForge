"""
Long-term memory layer.

Provides cross-session memory storage and retrieval backed by Mem0 with a
Postgres/pgvector vector store. The memory layer sits alongside the Agent
and Observability layers in the architecture — it may be imported by the
Agent and API layers but must not import from them.

Public API:
  - create_memory_client() — initialise the Mem0 AsyncMemory instance
  - Mem0MemoryStore — async memory store wrapping the Mem0 client
  - BaseMemoryStore — ABC for alternative memory backends
  - get_relevant_context() — retrieve memories formatted for agent prompts
  - store_interaction() — persist a question/answer pair as memory
"""
