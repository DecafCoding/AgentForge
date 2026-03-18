---
description: Execute a development plan with task tracking
argument-hint: [plan-file-path]
---

# Execute Development Plan

## Step 1: Read the Plan

Read the plan file specified in: $ARGUMENTS

The plan file will contain:
- A list of tasks to implement
- References to existing codebase components and integration points
- Context about where to look in the codebase for implementation

## Step 2: Create All Tasks

Before writing any code, create a task for each item in the plan using `TaskCreate`:
- Use an imperative subject (e.g., "Add CORS middleware to FastAPI app")
- Include the plan's acceptance criteria and context in the description
- Set `addBlockedBy` on tasks that depend on earlier ones

Create ALL tasks upfront so the full scope is visible before implementation starts.

## Step 3: Codebase Analysis

Before implementing anything:
1. Read all files referenced in the plan's context section
2. Use Grep and Glob to understand existing patterns and find similar implementations
3. Verify your understanding of integration points before touching code

## Step 4: Implementation Cycle

Work through tasks in order (lowest ID first). For each task:

**4.1 Start** — Set the task to `in_progress` with `TaskUpdate` before writing any code.

**4.2 Implement** — Make all necessary changes. Follow existing patterns, conventions, and the project's `CLAUDE.md`.

**4.3 Validate** — Run the task's validation command (linter, type check, or test) before moving on. Fix failures before proceeding — do not mark a task complete if its validation fails.

**4.4 Complete** — Set the task to `completed` with `TaskUpdate` only after validation passes.

Only one task should be `in_progress` at a time.

## Step 5: Final Validation

After all tasks are complete, run the full validation suite specified in the plan (typically lint → tests → build). If anything fails, reopen the relevant task (`in_progress`), fix it, and re-validate.

## Step 6: Final Report

Provide a summary covering:
- Tasks completed
- Validation results
- Any deviations from the plan and why
- Ready for `/commit`
