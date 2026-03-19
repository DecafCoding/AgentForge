---
description: Commit staged changes and push to the current remote branch
---

# Commit and Push

## Step 1: Check What's Staged

Run `git diff --cached --stat` to see what is staged. If nothing is staged, stop and tell the user there is nothing to commit.

## Step 2: Review the Diff

Run `git diff --cached` to read the full staged diff. Use this to understand what changed and why.

## Step 3: Check Recent Commit Style

Run `git log --oneline -5` to see recent commit messages and match the project's conventional commit style.

## Step 4: Write the Commit Message

Draft a commit message following the conventional commit format used in this project:

```
<type>: <short summary>

<optional body — only if the change needs more explanation>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

Keep the subject line under 72 characters. Focus on *why*, not *what*.

## Step 5: Commit

Run `git commit -m` with the message via a heredoc to preserve formatting.

## Step 6: Push

Run `git push` to push the current branch to its remote tracking branch. If the branch has no upstream yet, use `git push -u origin <branch-name>`.

## Step 7: Report to User

Provide a concise summary covering:
- **Branch** pushed to
- **Files changed** (count + key files)
- **What changed** — a plain-English summary of the staged changes
- The **commit message** used
