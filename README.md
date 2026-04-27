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
