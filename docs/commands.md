# Command Notes

These notes document the intent behind commands as they are introduced. The command surface is still early, so this file should capture both current syntax and unsettled naming questions.

## Principles

- Product command examples use `think ...`.
- From a source checkout, developers can run the same command as `uv run think ...`.
- `uv run think ...` is a development runner, not the product command surface.
- Commands should express user intent before internal implementation.
- Work commands must be non-interactive: required input arrives through arguments and flags.
- Work commands that call models must get provider/model choice from explicit command input, user config, or user/project-supplied agent configuration. They must fail clearly if no model is supplied.
- Future project config should override user config, but command arguments and flags remain the most explicit source of command input.
- Setup commands may use interactive prompts because the user explicitly asked to configure or initialize something.
- The CLI is an adapter over engine behavior, not the owner of product logic.

## Reserved Syntax

These command shapes are either implemented or reserved as current direction, not permanent API:

| Command shape | Intent |
|---|---|
| `think setup` | Tool-level onboarding, credentials guidance, and first-run setup. |
| `think init` | Guided setup session for selecting auth methods, model profiles, and explicit user-authored defaults. Implemented. |
| `think config doctor` | Detect provider credentials from the environment without printing secret values. Implemented. |
| `think config init` | Write non-secret provider configuration from detected credentials. Implemented. |
| `think config validate --provider <name> --model <provider:model>` | Explicitly validate real provider access for one selected model. Implemented. |
| `think config auth doctor` | Inspect configured/detected auth paths without printing secret values. Implemented. |
| `think config auth methods` | List known provider auth method capabilities without printing secret values. Implemented. |
| `think config auth add <provider>` | Add or enable a provider auth path through setup-only guidance. Implemented. |
| `think config auth list` | List enabled provider auth metadata without secrets. Implemented. |
| `think config auth remove <provider>` | Remove or disable a provider auth path from Think Tank config. Implemented. |
| `think config model add <name> --model <provider:model>` | Store a named non-secret model profile. Implemented. |
| `think config model list` | List named model profiles. Implemented. |
| `think config model remove <name>` | Remove a named model profile. Implemented. |
| `think config defaults set --model-profile <name>` | Record an explicit user-authored default model profile. Implemented. |
| `think config defaults list` | List explicit user-authored defaults. Implemented. |
| `think config defaults remove model-profile` | Remove the default model profile. Implemented. |
| `think new <path> --name <name>` | Create a local idea project/workspace. Implemented. |
| `think ask "<prompt>" --project <path> --model <provider:model>` | Run a single non-interactive model interaction and record its transcript. Implemented. |
| `think ask "<prompt>" --project <path> --model-profile <name>` | Run a single non-interactive model interaction using a named model profile. Implemented. |
| `think elaborate ...` | Capture a definition, example, clarification, or related note. |
| `think synthesize ...` | Consolidate agent outputs into durable state or summaries. |
| `think review ...` | Inspect stale, unresolved, or questionable project state. |
| `think visualize ...` | Generate or refresh rich artifacts such as diagrams or charts. |

## Command Details

### `think init`

Intent: run an interactive CLI setup session that helps the user configure Think Tank deliberately. It is distinct from `think new`, which creates a local idea workspace.

Why it exists: first-run setup crosses several config concerns: provider auth metadata, model profiles, and explicit defaults. A top-level guided command lets the user make those choices in one place while keeping work commands scriptable.

Where it is going: `think init` should become the guided surface for implemented provider auth paths such as API-key env vars, local providers, and service-account credentials. Subscription and product-account integrations are deferred and must not be offered as near-term provider auth.

Why it is different from hidden defaults: the user is making visible choices during a setup command. Persisting those choices is not the same as Think Tank silently choosing a provider, model, auth method, billing path, or fallback at work-command runtime.

Current status: implemented.

Current behavior:

- `think init` may prompt because setup commands may be interactive.
- Detects implemented ready provider auth paths from the current environment.
- Lets the user select which implemented ready auth paths to record.
- Writes `~/.config/think-tank/config.toml` by default, or `--config <path>`.
- Stores provider names, auth kinds, env var names, and auth method records only.
- Does not store API keys, bearer tokens, refresh tokens, subscription tokens, browser cookies, provider session dumps, or provider secret values.
- May prompt for named model profiles from user-entered `provider:model` strings.
- May set one explicit default model profile after profile setup, selected from existing and newly created profiles.
- Does not validate provider credentials, call provider APIs, or hit the network.
- Does not make `think ask` or any other work command use defaults automatically.

Rules to preserve:

- Work commands must remain non-interactive.
- Any default written by setup must be explicit user-authored config, not an invented product default.
- Subscription and product-account auth must not be represented as generic API provider auth.
- ChatGPT/Codex and Claude/Claude Code subscription flows are deferred and must not be offered by setup/config commands.
- Fallback between auth methods or providers must remain explicit user-authored policy, never automatic recovery.

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

- Detects provider environment variable names for OpenAI, Anthropic, Gemini, Google Vertex AI, Ollama, OpenRouter, and Groq.
- Human-readable output reports ready providers and partially configured providers.
- Human-readable output does not warn about entirely unconfigured providers.
- JSON output reports all packaged providers, including missing required environment variable names.
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

### `think config auth ...`

Intent: manage provider auth metadata without storing provider secrets.

Why it exists: `config init` is a first-pass setup command. As auth support grows to include multiple API-key, service-account, local-server methods and explicit fallback policies, auth needs a focused namespace.

Current status: implemented for environment and local-server auth metadata. `auth methods`, `auth doctor`, `auth add`, `auth list`, and `auth remove` are implemented.

Reserved commands:

| Command | Intent |
|---|---|
| `think config auth doctor` | Show detected and configured auth paths without printing secret values. Implemented. |
| `think config auth methods` | Show known packaged auth method capabilities without printing secret values. Implemented. |
| `think config auth add <provider>` | Add or enable an auth path for a provider. May prompt because it is a setup command. Implemented. |
| `think config auth list` | Show enabled provider auth metadata, including auth kind and env var names, without secret values. Implemented. |
| `think config auth remove <provider>` | Remove or disable a provider auth path from Think Tank config. Implemented. |

Current `auth add` behavior:

- Reads and rewrites `~/.config/think-tank/config.toml` by default, or `--config <path>`.
- Creates the config file if it does not already exist.
- Requires the provider to be in the packaged provider set.
- Requires required environment variables to be visible for API-key or service-account providers before recording metadata.
- Supports Ollama/local-server metadata without requiring a secret.
- In interactive mode, prompts for auth method selection when a provider has more than one implemented ready method.
- Does not allow unimplemented auth methods to be selected or written.
- Records provider name, selected auth kind, detected env var names, and an auth method record for the selected/current method only.
- Supports `--yes` for non-interactive setup/test use; `--yes` uses the provider's current primary implemented method and does not select fallback methods.
- Does not store API keys, bearer tokens, refresh tokens, subscription tokens, browser cookies, provider session dumps, or default models.

Future behavior:

- `auth add` may prompt interactively for setup choices beyond the current confirmation and method-selection prompts.
- `auth add` may record additional non-secret preferences.
- `auth list` should make any user-authored fallback policy visible if fallback policies are added later.
- No command may silently fall back from direct provider credentials to aggregator credentials.

Current `auth methods` behavior:

- Does not require the config file to exist and does not read or write config.
- Lists all packaged providers by default, or one provider with `--provider <name>`.
- Reports every packaged auth method with implementation status, official-path status, readiness, selectability, required env var names, detected env var names, missing env var names, and provider notes.
- Currently exposes implemented API-key, local-server, and service-account paths only.
- Supports `--json` for machine-readable output.
- Does not print secret values.
- Does not call provider APIs or validate credentials.

Deferred product integration note:

- `anthropic` auth methods describe the direct Anthropic API path, currently `api_key_env`.
- Claude Code subscription OAuth is deferred and must not be represented as a generic Anthropic API provider auth method.
- ChatGPT/Codex and Claude/Claude Code product auth must not be offered by `think config auth add` or `think config auth methods` unless that whole product-integration scope is reopened later.
- Product tokens, browser cookies, OAuth tokens, and credential files are secrets and must not be written to Think Tank config.

Current `auth doctor` behavior:

- Reads `~/.config/think-tank/config.toml` by default, or `--config <path>`.
- Does not require the config file to exist.
- Combines configured provider auth metadata with current environment detection.
- Reports configured status, detected status, readiness, configured env var names, detected env var names, missing env var names, and provider notes.
- Supports `--json` for machine-readable output.
- JSON output includes configured auth method records for future multi-method setup flows.
- Does not print secret values.
- Does not call provider APIs.

Current `auth list` behavior:

- Reads `~/.config/think-tank/config.toml` by default, or `--config <path>`.
- Prints enabled providers, selected auth kinds, and env var names.
- Supports `--json` for machine-readable output.
- JSON output includes `auth_methods` for future multi-method setup flows.
- Does not print or read secret values.

Current `auth remove` behavior:

- Reads and rewrites `~/.config/think-tank/config.toml` by default, or `--config <path>`.
- Removes the provider from `enabled_providers`.
- Removes Think Tank's `[providers.<provider>]` metadata table.
- Is idempotent when the provider is absent.
- Does not delete user-managed env files, shell config, keychain entries, provider account settings, or local Ollama models.

### `think config model ...`

Intent: manage user-named model profiles without creating default models or fallback policies.

Why it exists: full `provider:model` strings are useful for explicitness but tedious to repeat. Named profiles let users shorten repeated work-command invocations while preserving the rule that the model choice came from user-supplied configuration.

Current status: implemented.

Current behavior:

- `think config model add <name> --model <provider:model>` creates or updates a profile.
- `think config model list` prints configured profiles and supports `--json`.
- `think config model remove <name>` removes a profile and is idempotent when the profile is absent.
- Reads and rewrites `~/.config/think-tank/config.toml` by default, or `--config <path>`.
- Stores profile names and explicit `provider:model` strings only.
- Requires model strings to use a packaged provider prefix.
- Does not validate provider credentials, call provider APIs, store provider secrets, choose a default model, or create fallback policies.

### `think config defaults ...`

Intent: manage explicit user-authored preferences that setup flows can write without turning them into hidden product defaults.

Why it exists: guided setup needs a durable place to record choices the user intentionally made, such as a preferred model profile. Recording those choices is different from Think Tank inventing a provider, model, auth method, billing path, or fallback.

Current status: implemented for model profile defaults. `defaults set`, `defaults list`, and `defaults remove` are implemented.

Current behavior:

- `think config defaults set --model-profile <name>` records a default model profile.
- The named model profile must already exist in the same config file.
- `think config defaults list` prints configured defaults and supports `--json`.
- `think config defaults remove model-profile` removes the default model profile and is idempotent when absent.
- Removing a model profile also clears the default if that default pointed at the removed profile.
- Reads and rewrites `~/.config/think-tank/config.toml` by default, or `--config <path>`.
- Stores default profile names only, not raw model strings or provider secrets.
- Does not make `think ask` or any other work command use defaults automatically yet.
- Does not create fallback policies.

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
- Requires either an explicit `--model <provider:model>` value or a user-configured `--model-profile <name>`.
- Rejects commands that pass both `--model` and `--model-profile`.
- Resolves model profiles from `~/.config/think-tank/config.toml` by default, or `--config <path>`.
- Calls the model client once.
- Prints the model response.
- Appends one JSONL row to `<path>/transcripts/ask.jsonl`.

Packaged providers:

- `openai:<model>`
- `anthropic:<model>`
- `gemini:<model>`
- `google:<model>`
- `ollama:<model>`
- `openrouter:<model>`
- `groq:<model>`

`gemini:<model>` is the Gemini Developer API key path and uses `GEMINI_API_KEY` or `GOOGLE_API_KEY`. It does not require Vertex project or service-account credentials.

`google:<model>` is the Google Vertex AI path and uses Vertex-style credentials.

`openrouter:<model>` and `groq:<model>` are Think Tank adapter conventions for those providers' OpenAI-compatible APIs. The installed aisuite version does not expose first-class providers for those routes.

Current non-goals:

- No default provider or model.
- No fallback provider or model.
- No automatic model profile selection.
- No multi-agent fanout.
- No synthesis.
- No state mutation.
- No git auto-commit.

## Nouns Under Evaluation

The current code uses `project` inside `state.json`, while user-facing language still uses project, workspace, and idea project. That is deliberate. We have not yet learned whether the durable unit should be named primarily as a project, workspace, idea, or something else.

Until that settles, prefer command names that do not require a premature namespace. Keep `think new` as the blessed creation command unless project-management commands become numerous enough to justify a namespace.
