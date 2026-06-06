# Daily Workflow

## Objective

Use AI agent as an implementation accelerator without losing architectural control, code quality, or documentation consistency.

This workflow is designed for a local-first Python project with modular architecture and incremental evolution.

---

## Core Principles

* Small scope per session
* One clear objective at a time
* Architecture first, implementation second
* Review before accepting
* Tests are mandatory for behavior changes
* Documentation must stay aligned with code
* Do not let AI agent redefine the project implicitly

---

## Source of Truth

Before starting any task, AI agent must align with these files:

1. `AGENT.md`
2. relevant architecture docs under `docs/architecture/`
3. relevant skill files under `docs/ai/skills/`
4. the specific task file under `docs/ai/tasks/`

If these sources conflict, prefer:

1. actual code behavior
2. `AGENT.md`
3. architecture docs
4. task file

---

## Daily Workflow

### Step 1 — Define the session goal

Choose exactly one primary goal.

Examples:

* add `--local-only` to `stock_analyzer`
* integrate `smc` model
* improve `stock_data_manager` tests
* update README after CLI change

Do not combine unrelated goals in the same session.

---

### Step 2 — Load context

At the beginning of the session, tell AI agent to use:

* `AGENT.md`
* one or more relevant skill files
* one task file
* the current relevant code files

Typical prompt pattern:

> Use `AGENT.md`, `docs/ai/skills/add-feature.md`, and `docs/ai/tasks/stock-analyzer-local-only.md`. First summarize the current behavior from the code, then propose a minimal implementation plan, then make only the necessary changes.

---

### Step 3 — Ask for a plan before changes

Always require AI agent to first produce:

* current behavior summary
* intended change
* impacted files
* test plan
* documentation impact

Only after that should it modify code.

Recommended instruction:

> Do not change code yet. First explain the implementation plan, impacted files, assumptions, and tests to add.

---

### Step 4 — Implement in a controlled scope

Once the plan looks correct, ask AI agent to make only the scoped change.

Rules:

* no unrelated refactors
* no infra changes unless explicitly requested
* no architectural redesign unless explicitly requested
* preserve existing behavior outside the requested feature

Recommended instruction:

> Implement only this feature. Do not refactor unrelated modules. Keep the change minimal and explicit.

---

### Step 5 — Require tests

Any meaningful behavior change must include tests.

Minimum expectation:

* happy path
* failure path
* one regression path when relevant

Recommended instruction:

> Add behavior-oriented unit tests. Avoid network access. Mock only external boundaries.

---

### Step 6 — Require documentation update

If CLI, workflow, or module behavior changes:

* update README
* update examples
* update help text
* update architecture docs if behavior or boundaries changed

Recommended instruction:

> Update the relevant README and CLI help text to match the implemented behavior.

---

### Step 7 — Review the diff before accepting

Never accept changes blindly.

Review in this order:

#### A. Behavior

* Did the change do exactly what was requested?
* Did anything else change?

#### B. Architecture

* Did module boundaries remain clean?
* Was new coupling introduced?

#### C. Tests

* Do tests validate behavior or only trivial assertions?
* Are network and filesystem boundaries handled correctly?

#### D. Documentation

* Does the README reflect the actual implemented behavior?

---

### Step 8 — Commit in small units

Prefer separate commits for:

* code
* tests
* docs

Or at least one commit per coherent feature.

Good example:

* `feat(stock_analyzer): add local-only analysis mode`
* `test(stock_analyzer): add local-only CLI coverage`
* `docs(stock_analyzer): document local-only workflow`

---

## Standard Session Types

### 1. Feature Session

Use when adding new behavior.

Inputs:

* `AGENT.md`
* `docs/ai/skills/add-feature.md`
* task file

Expected outputs:

* code
* tests
* docs

---

### 2. Test Hardening Session

Use when improving confidence without changing behavior.

Inputs:

* `AGENT.md`
* `docs/ai/skills/write-tests.md`

Expected outputs:

* new or improved tests
* maybe small bug fixes only if directly exposed by tests

---

### 3. Documentation Session

Use when architecture or usage needs to be clarified.

Inputs:

* `AGENT.md`
* `docs/ai/skills/update-docs.md`
* relevant code files

Expected outputs:

* README updates
* architecture docs
* examples

---

### 4. Review Session

Use when AI agent already changed files and you want validation.

Inputs:

* `AGENT.md`
* `docs/ai/skills/code-review.md`
* changed files or diff

Expected outputs:

* risk assessment
* keep / fix / discard recommendations

---

## Standard Prompt Templates

### Template A — Start a feature session

> Use `AGENT.md`, `docs/ai/skills/add-feature.md`, and `docs/ai/tasks/<task-name>.md`. First inspect the current implementation and summarize the behavior. Then propose a minimal implementation plan, list impacted files, and list tests to add. Do not change code yet.

---

### Template B — Approve implementation

> Approved. Implement exactly that plan. Keep scope tight. Do not refactor unrelated code. Add tests and update README/help text where needed. At the end, summarize exactly what changed.

---

### Template C — Review generated changes

> Review the changes against `AGENT.md` and the relevant task/skill files. Identify risks, unintended behavior changes, weak tests, and documentation inconsistencies. Be specific.

---

### Template D — Documentation only

> Use `AGENT.md` and `docs/ai/skills/update-docs.md`. Update the documentation strictly to match the current implementation. Do not introduce future concepts unless explicitly marked as future.

---

## Rules for Safe AI agent Usage

Always do:

* ask for a plan first
* constrain scope tightly
* require tests
* require docs update when behavior changes
* review diff before accepting

Never do:

* ask for multiple unrelated features at once
* accept automatic refactors without review
* merge weak tests
* let docs drift from code
* let AI agent invent architecture changes silently

---

## Recommended Daily Cadence

### Morning

* choose one goal
* load context
* ask for plan

### Mid-session

* approve minimal implementation
* review tests and docs

### End of session

* review diff
* run tests
* commit in small unit
* update task status

---

## Suggested Task Status Tracking

Inside each task file, track:

* `Status: Planned`
* `Status: In Progress`
* `Status: Done`

And optionally:

* assumptions
* known limitations
* follow-up tasks

---

## Definition of Done

A task is done only when:

* code is implemented
* tests pass
* docs are updated
* behavior is reviewed
* scope remained controlled

---

## Current Recommended Usage For This Project

For the next feature, use:

* `AGENT.md`
* `docs/ai/skills/add-feature.md`
* `docs/ai/tasks/stock-analyzer-local-only.md`

Session flow:

1. ask AI agent to inspect current analyzer behavior
2. ask for minimal implementation plan
3. approve only the scoped change
4. require tests
5. require README/help update
6. review diff before accepting
