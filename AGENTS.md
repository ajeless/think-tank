# AGENTS.md

Treat this AGENTS.md as a living document that itself will change over time.

## What Think Tank is

A local-first idea workspace where a human and multiple AI agents develop ideas into durable, searchable, versioned artifacts. The core product is an engine generating structured, editable project state, from interaction with the user and with other agents. So claims, questions, evidence, disagreements, decisions, assumptions, artifacts, and changes over time. A CLI tool for ideation with multiple LLMs is built in parallel with the engine. Beyond that, hold the design loosely.

## Inspiration for and Direction on Think Tank

- Inspiration: https://github.com/ajeless/deliberation-room
- Direction: https://github.com/ajeless/docs/tree/main/think_tank

Study these thoroughly to understand the problem space and the design thinking.

!IMPORTANT!: Think Tank is its own product.  Treat the inspiration and direction as important guidance, not gospel.

## How to read the docs

Start with this AGENTS.md. Then read local docs that are relevant to the work:

- `docs/architecture.md` — active architecture notes and engine/CLI boundaries.
- `docs/commands.md` — active command intent, reserved syntax, and naming questions.

Then read the external docs at:

- Inspiration: https://github.com/ajeless/deliberation-room
- Direction: https://github.com/ajeless/docs/tree/main/think_tank

When touching a new area or revisiting a design decision, check the external inspiration/direction docs for prior thinking. Do not treat them as binding. Use them as source material. When external guidance becomes active for this codebase, copy or adapt it into local docs so future work can rely on this repo as the source of truth.

The docs repo describes a mature version of Think Tank that is *not* what we are building first. Read it for principles and direction, not as a build spec. Borrow specific patterns when they fit the current slice, not preemptively. Implementation details in the docs are provisional unless I say otherwise.

If a referenced document doesn't exist, ask before creating it.

## Stack

The project's stack is decided. Don't propose alternatives during the bootstrap session unless something specific blocks one of these choices. The full reasoning for each choice lives in the docs repo at `stack-decisions.md`.

| Layer | Choice |
|---|---|
| Engine language | Python (3.12+) |
| Toolchain | `uv` |
| Provider abstraction | `aisuite` |
| Concurrency | `asyncio` |
| CLI framework | `typer` |
| Terminal output | `rich` |
| Interactive prompts | `questionary` |
| Test framework | `pytest` + `pytest-asyncio` |
| Storage | JSON + JSONL files, git for versioning |

What's deferred (do not pull these in until they're explicitly needed):

- HTTP API framework (FastAPI is the eventual choice, not now)
- Database (SQLite or otherwise — premature)
- Vector search libraries
- Any frontend or UI framework
- Logging frameworks beyond standard library

## Toolchain

This project uses Python with `uv` for environment and dependency management. The toolchain rules below are literal.

**Always use:**
- `uv add <package>` to add a dependency
- `uv add --dev <package>` to add a dev dependency
- `uv remove <package>` to remove a dependency
- `uv run python <script>` to run a Python script
- `uv run pytest` to run tests
- `uv run <command>` to run any other command in the project's environment
- `uv sync` to sync the environment to `uv.lock`

**Never use:**
- `pip install` or `pip` for anything
- `python <script>` or `python3 <script>` directly (always prefix with `uv run`)
- `python -m pip ...`
- Manual `venv`/`virtualenv` creation
- `poetry`, `pipenv`, `conda`, or any other Python environment tool

**Why:** `uv` manages the project's virtual environment, lock file, and Python version automatically. Running `python` directly bypasses the project environment and uses whatever Python is on `$PATH`, which is rarely what we want. Running `pip install` mutates the environment outside `uv.lock`, which makes builds non-reproducible.

If you find yourself wanting to run a tool that doesn't fit the patterns above, ask before reaching for the older toolchain.

## Design principles

These are non-negotiable principles that apply across all code in this project. Add new principles here only when one earns its place.

### No opinions imposed on the user

The tool may default *between* user-supplied options (e.g., pick between configured credentials when multiple exist). The tool must not pick *on the user's behalf* (e.g., select a default model the user did not configure).

When the user hasn't supplied something the tool needs, fail with a clear error pointing at how to supply it. Do not invent helpful defaults to make the tool "easier to start with" — those are a form of middleman behavior the tool rejects.

The line: are we choosing between things the user supplied, or choosing for them? The first is fine. The second is not.

This applies to code, config, prompts, and error messages. If you're writing a default value, ask whether the user supplied the alternatives or whether you're inventing one. If the latter, fail explicitly instead.

### Setup commands may use interactive prompts; work commands must not

Commands fall into two categories with different rules:

**Setup commands** (`new`, `config init`, `config edit`, etc.) — commands the user runs explicitly to configure or initialize something. They may use interactive prompts, menus, validation flows. `questionary` is the right tool for selection menus here. Rich formatting (panels, colors, structured output) is fine.

**Work commands** (`ask`, future `synthesize`, future `visualize`, etc.) — commands that exercise the engine to do real work. They must accept all required input via arguments and flags. They must not prompt interactively. If required input is missing, fail with a clear error pointing at how to provide it. Output is plain text by default, structured (`--json` or similar) when requested.

"Interactive" here means *requiring user input mid-execution* — selection menus, free-text prompts, confirmation dialogs that block until the user responds. Pretty output is *not* interaction; it's display, and it's fine in any command. Rich's auto-detection of TTY vs. pipe means colorized terminal output becomes plain when piped, so work commands can be both pretty and scriptable simultaneously.

The reason for the asymmetry: work commands need to be scriptable, testable, and embeddable. Interactive prompts break all three. Setup commands are explicitly user-facing moments where guidance helps; work commands are the engine's interface to the world and must stay clean.

The engine itself never prompts, ever. Prompting is a CLI-layer concern, and only for setup commands.

## What to do first

1. Read this file completely.
2. Wait for me to give you a task. Do not start working until I do.
3. When given a task, write a short plan first. Wait for approval before writing code.

## Working autonomy during the bootstrap session

For structural decisions (project layout, file organization, naming): propose your choice with a one-sentence rationale, then proceed. I'll push back if I disagree.

For dependency choices: the stack above is fixed. If a new dependency is needed beyond what's listed there, propose it with rationale and wait for approval before adding it.

For destructive or non-reversible actions (deleting files, force-pushing, modifying anything outside the repo): always wait for approval.


## Tests

- Code coverage requirement.  Unit tests = 100%.  Integration tests aim for >= 90%. E2E tests aim for >= 80%. Integration and e2e tests coverage is a loose requirement.  Aim for it when it makes sense to do it.  But don't create tests for the sake of tests.
- For code or behavior changes, run tests before committing using `uv run pytest`. Include the test output (passing or failing) in the commit message body. If you cannot run tests in this environment, say so explicitly and do not commit.
- For docs-only changes, tests are not required. Say explicitly that tests were skipped because only documentation changed.


## Branching and Commits

Working branches.
- Never work in or commit directly to main. Open a working branch.
- Commit directly to the working branch, and push, no approval needed. 
- Create a PR and raise it in chat.


## Workflow and Definition of Done

- At the end of every slice/iteration do:
    1. Add to this section any rules/tasks discussed during the work that belong here.
    2. At this early stage, every slice includes a document audit. Review all .md files in the repo for alignment, consistency, redundancy, staleness. This includes AGENTS.md. Align/make consistent/de-duplicate/make-current the docs in the same task. If no changes were needed, say so explicitly
    3. If you encounter a situation where this file was silent and you had to guess, surface it at the end of the task and propose a rule. I'll decide whether to add it. Do not edit this file directly.
    4. Commit and push to the working branch, create a PR, and raise it in chat.

## When in doubt

Ask. The cost of a question is small. The cost of guessing wrong on a project's foundational session is large.
