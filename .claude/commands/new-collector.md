---
description: "Scaffold a new data collector with all required integration points"
argument-hint: <collector-name> [data-source-description]
---

# Create a New Collector

## Step 1: Gather Requirements

The collector name is provided in: $ARGUMENTS

If no name was provided, ask the user the following questions before proceeding. If a name was provided but details are missing, ask only the questions that aren't already answered.

**Required inputs:**

1. **Collector name** — a short snake_case name for the data source (e.g., `rss_feed`, `github_issues`, `slack_messages`)
2. **Data source description** — what external API or service does this collector pull from?
3. **Authentication** — does the data source require an API key, OAuth token, or no auth?
4. **Data shape** — what fields/data does each collected item contain? (e.g., title, body, url, timestamp, author)
5. **Collection strategy** — how should items be fetched? (e.g., paginated list, single endpoint, poll for changes)
6. **Scheduling interval** — how often should the collector run? (default: 60 minutes)

**Optional inputs (use sensible defaults if not provided):**

7. **New dependencies** — any Python packages needed to interact with the data source?
8. **Needs a new database table?** — or can data fit into an existing table? (default: new table)
9. **Embedding support** — should collected items have a `vector(1536)` embedding column for RAG? (default: yes)

## Step 2: Read Existing Patterns

Before writing any code, read these files to understand the established patterns:

1. `src/collector/base.py` — the BaseCollector interface
2. `src/collector/web_scraper.py` — minimal collector reference implementation
3. `src/collector/youtube.py` — full-featured collector reference
4. `src/collector/models.py` — collector-layer transfer models
5. `src/collector/scheduler.py` — how collectors are registered
6. `src/config.py` — how config variables are declared
7. `src/db/queries.py` — query function patterns and database models
8. `src/db/migrations/versions/0002_scraped_pages.py` — migration pattern

Also read `CLAUDE.md` for project conventions (docstrings, type hints, naming, architectural boundaries).

## Step 3: Add Configuration

Add new environment variables to `src/config.py` under a new commented section:

- API key variable (if auth is required): `{UPPER_NAME}_API_KEY`
- Interval variable: `{UPPER_NAME}_INTERVAL_MINUTES` with default from user input or 60

Add the same variables with descriptions to `.env.example`.

## Step 4: Create Database Migration (if new table needed)

Create a new migration file in `src/db/migrations/versions/` following the existing numbering pattern (`0005_...`). Check the latest migration number first.

The migration should:
- Use `op.execute()` with raw SQL (matching the existing pattern)
- Include `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- Include a unique natural key column (e.g., `url`, `item_id`)
- Include `embedding vector(1536)` if embedding support was requested
- Include a timestamp column (e.g., `collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`)
- Include an `upgrade()` and `downgrade()` function
- Add appropriate indexes

## Step 5: Add Query Functions

Add to `src/db/queries.py`:

1. **A Pydantic model** for the database record (e.g., `RssFeedRecord(BaseModel)`)
2. **An upsert function** — `async def upsert_{item}(pool: Pool, ...) -> None`
3. **A read function** — `async def get_{items}(pool: Pool, ...) -> list[{Record}]`
4. **Any additional query functions** needed by the collector's strategy (e.g., `item_exists()`, `search_{items}()`)

All functions must:
- Accept `Pool` as the first argument
- Return typed Pydantic models (never raw rows)
- Use parameterized queries (`$1`, `$2`) — never f-strings for SQL

## Step 6: Add Collector Transfer Models (if needed)

If the collector needs intermediate data models (between API response and database), add them to `src/collector/models.py`. Follow the `VideoMetadata` pattern — Pydantic models with type hints and optional fields using `str | None` syntax.

## Step 7: Create the Collector Module

Create `src/collector/{collector_name}.py` with:

- **Module docstring** describing the data source, collection strategy, and layer membership
- **Class** extending `BaseCollector` with:
  - `__init__(self, pool: Pool, ...)` — accept pool and any config (API keys, URLs, etc.)
  - `async def collect(self) -> int` — the main collection cycle
  - Private helper methods for fetching, transforming, and storing data
- **Error handling** — log errors but don't abort the cycle; individual item failures are caught and logged
- **Logging** — use `logging.getLogger(__name__)` with structured `extra={}` context

**Architectural rules (enforced — never violate):**
- NEVER import `pydantic_ai`, `langfuse`, or any LLM dependency
- Use `asyncio.to_thread()` to wrap synchronous API clients
- All database access goes through `src.db.queries` — no raw SQL in the collector
- Return the count of items upserted from `collect()`

## Step 8: Register in Scheduler

Update `src/collector/scheduler.py`:

1. Import the new collector class and its config variables
2. In `start_scheduler()`, conditionally instantiate and register:
   - Gate on the API key or a feature flag (e.g., `if {UPPER_NAME}_API_KEY:`)
   - Use `IntervalTrigger(minutes=...)` with the config interval
   - Give the schedule a unique `id` string (e.g., `"{collector_name}"`)
   - Log the registration with interval metadata

## Step 9: Add Dependencies (if needed)

If new Python packages are required:
1. Run `uv add {package}` to add them to `pyproject.toml`
2. Run `uv sync` to update the lock file

## Step 10: Create Tests

Create `tests/test_{collector_name}.py` with:

1. **Boundary test** — verify the collector module does not import `pydantic_ai` or `langfuse`
2. **Unit tests** — test the collector with mocked external API calls
3. **Error handling test** — verify that a single item failure doesn't abort the cycle

Follow existing test patterns in `tests/` and use pytest-asyncio for async tests.

## Step 11: Validate

Run the full validation suite:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Fix any issues before reporting completion.

## Step 12: Report

Provide a summary of what was created:

- **Files created/modified** — list each with a one-line description
- **Environment variables added** — list with defaults
- **Database table** — name and key columns
- **Scheduler registration** — interval and gate condition
- **Next steps** — remind the user to:
  1. Set the new environment variables in `.env`
  2. Run the database migration: `uv run alembic upgrade head`
  3. Restart the application to pick up the new collector
