# Think Tank

Think Tank is a local-first idea workspace where a human and multiple AI agents develop ideas into durable, searchable, versioned artifacts.

This repository is being bootstrapped incrementally. The first slice establishes the Python package, CLI entrypoint, and test harness only.

## Current CLI

Create a local workspace:

```bash
uv run tt project init ./my-idea --name "My Idea"
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
