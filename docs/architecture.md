# Architecture Notes

These notes capture decisions that are active in this repository. They borrow useful direction from the earlier Think Tank planning docs, but this repo is now the working source of truth for implemented behavior.

## Engine First

Think Tank is a headless engine with a CLI as the first adapter. The CLI should stay thin: parse arguments, call engine functions, and format results. Product behavior belongs in the engine.

This matters because the CLI is not the final boundary of the product. Future API layers, UI clients, database-backed storage, or indexing services should be able to call the same engine behavior without inheriting terminal assumptions.

Engine functions should:

- Return structured data instead of printing.
- Avoid interactive prompts.
- Avoid reading environment variables unless passed explicit configuration.
- Avoid depending on Typer, Rich, or any other CLI-only concern.

CLI handlers should:

- Parse arguments and options.
- Call engine functions.
- Convert engine results or errors into terminal output and exit codes.

## Model Call Boundary

Model calls are engine behavior behind a testable client boundary. The engine owns loading project state, assembling the model messages, receiving structured response data from a model client, and writing durable transcript records. The CLI chooses no behavior beyond parsing command input and selecting the concrete client adapter.

Provider and model selection must not be hardcoded. Work commands that call models must get the model from one of these user-supplied sources:

- Explicit command input such as `--model <provider:model>`.
- Future user configuration.
- Future project or agent configuration.

If no model is supplied through one of those sources, the engine must fail with a clear error instead of picking a default provider, default model, fallback model, or "best" model on the user's behalf.

The current aisuite-backed client is intentionally thin. Unit tests should use a fake model client so test runs do not hit provider APIs or depend on network access.

The packaged provider set is intentionally limited to the providers in active early use: OpenAI, Anthropic, Google, Ollama, and OpenRouter. OpenAI, Anthropic, Google, and Ollama use aisuite provider support directly. OpenRouter is routed through OpenRouter's OpenAI-compatible API because the installed aisuite version does not expose a first-class OpenRouter provider.

## Provider Onboarding And Secrets

Think Tank detects provider credentials from the user's environment and may write non-secret configuration under `~/.config/think-tank/config.toml`. Config files may record enabled provider names, auth kinds, and env var names. They must not contain API keys, subscription tokens, bearer tokens, or project-local secrets.

Setup commands may guide users through provider detection and configuration. Work commands must stay non-interactive and must not prompt for credentials mid-run.

Subscription account sign-in is provider-specific and only acceptable through an official supported auth path. The tool must not implement unsupported subscription-token workarounds, and it must not silently fall back from subscription auth to API billing. Any validation that could spend money or hit external provider rate limits must be opt-in.

Provider failures are product errors, not Python tracebacks. The CLI should surface concise messages for missing credentials, quota failures, authentication failures, and provider SDK issues without leaking secret values.

`think config validate` is the explicit real-provider diagnostic boundary. It belongs in setup/config space, not work-command behavior. Validation may spend provider quota or hit external rate limits, so it is opt-in and never runs as part of `doctor`, `init`, or `ask` by default. The engine owns the validation behavior and returns structured status data; the CLI only formats that status and chooses the process exit code.

Validation must use the same no-middleman rules as model calls:

- Require an explicit provider and `provider:model` value.
- Do not choose fallback models or fallback auth methods.
- Do not store credentials or write provider secrets to config.
- Do not write transcripts or mutate project state.
- Use fake clients in tests so test runs never depend on provider APIs or network access.

Ollama is local-provider validation rather than credential validation. The validator checks local server availability using `OLLAMA_API_URL` or the default `http://localhost:11434`, then verifies that the requested model appears in the local model registry.

## Local-First Project State

A Think Tank project is a local directory containing durable state and artifacts. Today that state begins as JSON plus directories for transcripts, notes, and artifacts. Git remains the versioning layer.

The current layout is intentionally small and provisional. The engine may later gain richer storage, migrations, an API layer, or a database-backed query path, but the current filesystem layout gives us a concrete project spine without committing to a mature schema too early.

`transcripts/ask.jsonl` is the current append-only log for the minimal `think ask` path. Its row shape is provisional and records one model interaction per line. Do not infer a full session, round, or multi-agent transcript schema from it yet.

## Domain Model Discipline

The domain model is the vocabulary the system treats as real: nouns such as project, claim, question, decision, evidence, artifact, transcript, and summary; verbs such as ask, elaborate, synthesize, review, branch, and visualize.

These words are candidates, not all settled abstractions. Avoid creating heavy domain classes, schemas, or command namespaces before repeated real use proves they have earned their place.

`state.json` should carry a `schema_version` from the beginning. Schema evolution is expected.
