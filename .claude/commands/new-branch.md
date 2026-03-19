---
description: Switch to main, pull latest, and create a new branch
argument-hint: <branch-name>
---

# New Branch

## Step 1: Get the Branch Name

The branch name is provided in: $ARGUMENTS

If no branch name was provided, ask the user what to name the branch before proceeding.

## Step 2: Switch to Main and Pull

Run these sequentially:
1. `git checkout main`
2. `git pull`

Report the result — how many commits were pulled and a one-line summary of what came in.

## Step 3: Create and Switch to the New Branch

Run `git checkout -b <branch-name>` using the name from Step 1.

## Step 4: Report to User

Confirm:
- **Now on branch:** the new branch name
- **Based on:** main at the commit it was pulled to (show the short SHA and commit message)
