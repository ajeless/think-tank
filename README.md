# Think Tank

Think Tank is a local-first idea workspace where a human and multiple AI agents develop ideas into durable, searchable, versioned artifacts.

This repository is being bootstrapped incrementally. The current implementation provides the Python package, CLI entrypoint, test harness, local workspace creation, guided setup, provider credential diagnostics, explicit provider validation, named model profiles, and a minimal one-model `ask` path that records transcripts.

## Design Notes

- [Architecture notes](docs/architecture.md)
- [Command notes](docs/commands.md)

## Current CLI

Create a local workspace:

```bash
think new ./my-idea --name "My Idea"
```

Ask one explicitly selected model a question inside that workspace:

```bash
think ask "What should we evaluate first?" --project ./my-idea --model openai:gpt-4o
```

Or use a named model profile that you configured explicitly:

```bash
think config model add fast --model groq:llama-3.1-8b-instant
think ask "What should we evaluate first?" --project ./my-idea --model-profile fast
```

From a source checkout during development, run the installed command through `uv`:

```bash
uv run think new ./my-idea --name "My Idea"
uv run think ask "What should we evaluate first?" --project ./my-idea --model openai:gpt-4o
```

Check which provider credentials Think Tank can see:

```bash
think config doctor
```

Run guided setup for non-secret auth metadata, model profiles, and explicit defaults:

```bash
think init
```

Write non-secret provider configuration from detected credentials:

```bash
think config init
```

Inspect provider auth capabilities, then add, list, or remove non-secret provider auth metadata:

```bash
think config auth methods
think config auth doctor
think config auth add groq --yes
think config auth list
think config auth remove groq
```

Add, list, or remove named model profiles:

```bash
think config model add fast --model groq:llama-3.1-8b-instant
think config model list
think config model remove fast
```

Record, list, or remove explicit user-authored defaults:

```bash
think config defaults set --model-profile fast
think config defaults list
think config defaults remove model-profile
```

Explicitly validate real provider credentials and one selected model:

```bash
think config validate --provider openai --model openai:gpt-4o
```

The command creates:

```text
my-idea/
  state.json
  transcripts/
  notes/
  artifacts/
    diagrams/
    charts/
    mindmaps/
    flows/
    mocks/
    data/
```

`state.json` starts with `schema_version: 1`, user-supplied project metadata, and intentionally empty top-level collections for the project state.

`think ask` loads the project `state.json` as read-only context, calls the requested `provider:model`, prints the model response, and appends the raw interaction to `transcripts/ask.jsonl`. It does not synthesize, mutate project state, choose default models, run multiple agents, or commit to git.

`think init` is an interactive setup command. It detects implemented ready provider auth paths, lets the user select which ones to record, writes only non-secret auth metadata, and can prompt for named model profiles from user-entered `provider:model` strings. It can also record one explicit user-authored default after profile setup. Work commands do not use recorded defaults automatically yet, so `think ask` still requires `--model` or `--model-profile`.

`think config model add <name> --model <provider:model>` stores a user-named model profile in non-secret config. `think ask` can use that profile with `--model-profile <name>`. Model profiles are explicit user choices; Think Tank still does not store or choose a default model, and it does not create fallback policies.

`think config defaults set --model-profile <name>` records an explicit user-authored default model profile in non-secret config. Work commands do not use recorded defaults automatically yet; `think ask` still requires `--model` or `--model-profile`.

`think config validate` is an explicit opt-in diagnostic for real provider access. It may call provider APIs with a tiny validation prompt, so it is never run by `doctor`, `init`, or work commands by default. It reports success, missing credentials, authentication failures, quota or rate limits, provider SDK/configuration issues, and generic provider failures without printing secret values. For Ollama, it checks the local server and verifies that the requested model is installed. It does not write transcripts, mutate project state, choose fallback models, or store secrets.

Packaged model-provider support currently includes:

- OpenAI: `openai:<model>` with `OPENAI_API_KEY`.
- Anthropic: `anthropic:<model>` with `ANTHROPIC_API_KEY`.
- Gemini: `gemini:<model>` with `GEMINI_API_KEY` or `GOOGLE_API_KEY`.
- Google Vertex AI: `google:<model>` with Google/Vertex credentials supported by aisuite.
- Ollama: `ollama:<model>` with a local Ollama server, defaulting to `http://localhost:11434`.
- OpenRouter: `openrouter:<model>` with `OPENROUTER_API_KEY`, routed through OpenRouter's OpenAI-compatible API.
- Groq: `groq:<model>` with `GROQ_API_KEY`, routed through Groq's OpenAI-compatible API.

Think Tank does not store provider secrets. Provider credentials are read from environment variables, and config files store only non-secret metadata such as enabled provider names and detected env var names. Subscription and product-account sign-in are deferred; ChatGPT/Codex, Claude/Claude Code, browser-session reuse, and similar flows are not near-term provider auth paths.

The provider registry describes packaged auth methods and readiness without provider API calls. Packaged providers currently expose implemented API-key, local-server, and service-account paths only. Config writes accept only implemented ready paths and still store no secret values.

If subscription or product integrations are reconsidered later, they need a separate design pass before code. They must not be represented as direct `openai:<model>` or `anthropic:<model>` provider auth, and Think Tank must not read or store product credential files, browser cookies, OAuth tokens, or subscription tokens.

`think config auth add <provider>` creates or updates Think Tank's non-secret auth metadata for one known provider. In interactive mode it can ask the user to choose among implemented ready auth methods when a provider has more than one. It records the selected auth kind, detected env var names, and a non-secret auth method record only. It requires required env vars to be visible for API-key providers, supports local Ollama metadata without secrets, and can run non-interactively with `--yes`.

`think config auth remove <provider>` removes Think Tank's non-secret auth metadata only. It does not edit shell files, delete environment variables, change provider account settings, remove keychain entries, or delete local Ollama models.
