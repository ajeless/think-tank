# Command Notes

These notes document the intent behind commands as they are introduced. The command surface is still early, so this file should capture both current syntax and unsettled naming questions.

## Principles

- Product command examples use `think ...`.
- From a source checkout, developers can run the same command as `uv run think ...`.
- `uv run think ...` is a development runner, not the product command surface.
- Commands should express user intent before internal implementation.
- Work commands must be non-interactive: required input arrives through arguments and flags.
- Work commands that call models must get provider/model choice from explicit command input, user config, or user/project-supplied agent configuration. They must fail clearly if no model is supplied.
- Setup commands may use interactive prompts because the user explicitly asked to configure or initialize something.
- The CLI is an adapter over engine behavior, not the owner of product logic.

## Reserved Syntax

These command shapes are either implemented or reserved as current direction, not permanent API:

| Command shape | Intent |
|---|---|
| `think setup` | Tool-level onboarding, credentials guidance, and first-run setup. |
| `think config doctor` | Detect provider credentials from the environment without printing secret values. Implemented. |
| `think config init` | Write non-secret provider configuration from detected credentials. Implemented. |
| `think config validate --provider <name> --model <provider:model>` | Explicitly validate real provider access for one selected model. Implemented. |
| `think new <path> --name <name>` | Create a local idea project/workspace. Implemented. |
| `think ask "<prompt>" --project <path> --model <provider:model>` | Run a single non-interactive model interaction and record its transcript. Implemented. |
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

### `think config doctor`

Intent: show which supported provider credential paths are visible to Think Tank without exposing secret values.

Why it exists: provider onboarding needs a fast, safe diagnostic before real model calls. Users should know whether the process can see their credentials before a work command fails at provider runtime.

Current status: implemented.

Current behavior:

- Detects provider environment variable names for OpenAI, Anthropic, Google Vertex AI, Ollama, OpenRouter, and Groq.
- Reports missing required environment variable names.
- Prints env var names only, never env var values.
- Supports `--json` for machine-readable output.
- Does not make provider API calls.

### `think config init`

Intent: write non-secret user-level provider configuration from detected credentials.

Why it exists: setup commands may be guided and interactive, while work commands must remain scriptable and non-interactive.

Current status: implemented.

Current behavior:

- Detects currently ready providers.
- Prompts the user to enable detected providers, unless `--yes` is passed.
- Writes `~/.config/think-tank/config.toml` by default, or `--config <path>`.
- Stores provider names, auth kinds, and detected env var names.
- Does not store API keys, bearer tokens, subscription tokens, or default models.

### `think config validate --provider <name> --model <provider:model>`

Intent: explicitly verify that Think Tank can reach one real provider/model path.

Why it exists: `doctor` only checks whether required credential names are visible. A separate validation command lets the user choose when to spend provider quota, exercise remote authentication, or contact a local Ollama server.

Current status: implemented.

Current behavior:

- Requires both `--provider <name>` and `--model <provider:model>`.
- Requires the model provider prefix to match `--provider`.
- Sends a tiny validation prompt to remote providers only after required credentials are present.
- Reports success, missing credentials, auth failure, quota/rate limit, provider SDK/config issues, and generic provider failure.
- Checks Ollama server availability through `OLLAMA_API_URL` or `http://localhost:11434` and verifies the requested model is installed.
- Does not write transcripts, mutate project state, choose fallback models, store secrets, or run as part of `doctor` or `init`.

### `think ask "<prompt>" --project <path> --model <provider:model>`

Intent: run one model interaction using the current project state as context and record the interaction in the project transcripts.

Why it exists: Think Tank needs the smallest useful work-command path before adding multi-agent fanout, synthesis, state mutation, configuration, or git automation.

Current status: implemented.

Current behavior:

- Loads `<path>/state.json` as read-only context.
- Requires an explicit `--model <provider:model>` value.
- Calls the model client once.
- Prints the model response.
- Appends one JSONL row to `<path>/transcripts/ask.jsonl`.

Packaged providers:

- `openai:<model>`
- `anthropic:<model>`
- `google:<model>`
- `ollama:<model>`
- `openrouter:<model>`
- `groq:<model>`

`openrouter:<model>` and `groq:<model>` are Think Tank adapter conventions for those providers' OpenAI-compatible APIs. The installed aisuite version does not expose first-class providers for those routes.

Current non-goals:

- No default provider or model.
- No fallback provider or model.
- No multi-agent fanout.
- No synthesis.
- No state mutation.
- No git auto-commit.

## Nouns Under Evaluation

The current code uses `project` inside `state.json`, while user-facing language still uses project, workspace, and idea project. That is deliberate. We have not yet learned whether the durable unit should be named primarily as a project, workspace, idea, or something else.

Until that settles, prefer command names that do not require a premature namespace. Keep `think new` as the blessed creation command unless project-management commands become numerous enough to justify a namespace.
