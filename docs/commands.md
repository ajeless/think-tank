# Command Notes

These notes document the intent behind commands as they are introduced. The command surface is still early, so this file should capture both current syntax and unsettled naming questions.

## Principles

- Product command examples use `think ...`.
- From a source checkout, developers can run the same command as `uv run think ...`.
- `uv run think ...` is a development runner, not the product command surface.
- Commands should express user intent before internal implementation.
- Work commands must be non-interactive: required input arrives through arguments and flags.
- Setup commands may use interactive prompts because the user explicitly asked to configure or initialize something.
- The CLI is an adapter over engine behavior, not the owner of product logic.

## Reserved Syntax

These command shapes are either implemented or reserved as current direction, not permanent API:

| Command shape | Intent |
|---|---|
| `think setup` | Tool-level onboarding, credentials guidance, and first-run setup. |
| `think config ...` | Tool-level preferences, not project work. |
| `think new <path> --name <name>` | Create a local idea project/workspace. Implemented. |
| `think ask ...` | Run a non-interactive ideation/work command. |
| `think elaborate ...` | Capture a definition, example, clarification, or related note. |
| `think synthesize ...` | Consolidate agent outputs into durable state or summaries. |
| `think review ...` | Inspect stale, unresolved, or questionable project state. |
| `think visualize ...` | Generate or refresh rich artifacts such as diagrams or charts. |

## Current Command

### `think new <path> --name <name>`

Intent: create a local Think Tank project directory containing an initial `state.json`, transcript folder, notes folder, and artifact folders.

Why it exists: before agents can do useful work, Think Tank needs a durable local place for project state, transcripts, notes, and generated artifacts.

Current status: implemented.

Why this name: `think new` avoids making `project` a top-level namespace before the domain model has earned it, and it avoids `init`, which sounds like tool or current-directory setup.

## Nouns Under Evaluation

The current code uses `project` inside `state.json`, while user-facing language still uses project, workspace, and idea project. That is deliberate. We have not yet learned whether the durable unit should be named primarily as a project, workspace, idea, or something else.

Until that settles, prefer command names that do not require a premature namespace. Keep `think new` as the blessed creation command unless project-management commands become numerous enough to justify a namespace.
