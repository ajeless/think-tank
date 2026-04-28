# Think Tank

Think Tank is a local-first idea workspace where a human and multiple AI agents develop ideas into durable, searchable, versioned artifacts.

This repository is being bootstrapped incrementally. The current slice provides the Python package, CLI entrypoint, test harness, initial local workspace creation, and a minimal one-model `ask` path that records transcripts.

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

From a source checkout during development, run the installed command through `uv`:

```bash
uv run think new ./my-idea --name "My Idea"
uv run think ask "What should we evaluate first?" --project ./my-idea --model openai:gpt-4o
```

Check which provider credentials Think Tank can see:

```bash
think config doctor
```

Write non-secret provider configuration from detected credentials:

```bash
think config init
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

Packaged model-provider support currently includes:

- OpenAI: `openai:<model>` with `OPENAI_API_KEY`.
- Anthropic: `anthropic:<model>` with `ANTHROPIC_API_KEY`.
- Google: `google:<model>` with Google/Vertex credentials supported by aisuite.
- Ollama: `ollama:<model>` with a local Ollama server, defaulting to `http://localhost:11434`.
- OpenRouter: `openrouter:<model>` with `OPENROUTER_API_KEY`, routed through OpenRouter's OpenAI-compatible API.

Think Tank does not store provider secrets. Provider credentials are read from environment variables, and config files store only non-secret metadata such as enabled provider names and detected env var names. Provider subscription sign-in is not implemented unless a provider exposes a supported auth path for third-party tools; Think Tank will not silently switch from subscription auth to API billing.
