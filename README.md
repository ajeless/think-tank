# Think Tank

Think Tank is a local-first idea workspace where a human and multiple AI agents develop ideas into durable, searchable, versioned artifacts.

This repository is being bootstrapped incrementally. The current slice provides the Python package, CLI entrypoint, test harness, and initial local workspace creation.

## Design Notes

- [Architecture notes](docs/architecture.md)
- [Command notes](docs/commands.md)

## Current CLI

Create a local workspace:

```bash
think new ./my-idea --name "My Idea"
```

From a source checkout during development, run the installed command through `uv`:

```bash
uv run think new ./my-idea --name "My Idea"
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
