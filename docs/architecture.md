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
- User configuration such as a named model profile.
- Future project or agent configuration.

If no model is supplied through one of those sources, the engine must fail with a clear error instead of picking a default provider, default model, fallback model, or "best" model on the user's behalf.

Named model profiles are explicit user configuration, not defaults. A profile may shorten a command like `think ask ... --model-profile fast`, but Think Tank still must not select that profile automatically or fall back to another profile if the selected one fails.

The current aisuite-backed client is intentionally thin. Unit tests should use a fake model client so test runs do not hit provider APIs or depend on network access.

The packaged provider set is intentionally limited to the providers in active early use: OpenAI, Anthropic, Google, Ollama, OpenRouter, and Groq. OpenAI, Anthropic, Google, and Ollama use aisuite provider support directly. OpenRouter and Groq are routed through their OpenAI-compatible APIs because the installed aisuite version does not expose first-class providers for those routes.

## Provider Onboarding And Secrets

Think Tank detects provider credentials from the user's environment and may write non-secret configuration under `~/.config/think-tank/config.toml`. Config files may record enabled provider names, auth kinds, and env var names. They must not contain API keys, subscription tokens, bearer tokens, or project-local secrets.

Config files may also record named model profiles as explicit `provider:model` strings. Model profiles must not become implicit defaults, hidden fallback chains, or credential selectors.

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

### Auth Model Direction

Provider auth is explicit configuration, not an implicit rescue path. Think Tank may help a user discover, enable, disable, or validate auth methods, but it must not invent a billing path or silently escalate from one user-supplied auth method to another.

Auth method names should describe the mechanism, not the provider:

| Auth kind | Meaning | Secret storage rule |
|---|---|---|
| `api_key_env` | Provider API key read from a named environment variable. | Store env var names only. |
| `local_server` | Local service endpoint, such as Ollama. | Store optional endpoint env var names only. |
| `service_account_env` | Provider service account or application credentials discovered from environment variables. | Store env var names and non-secret metadata only. |
| `official_oauth` | Official OAuth/device flow intended for third-party API clients. | Store no bearer/refresh tokens until a secure storage decision is made. |
| `subscription_official` | Official provider-supported subscription auth for third-party tools, if one exists. | Store no subscription tokens in Think Tank config or project state. |

Future auth setup should keep this separation:

- Discovery commands inspect what is already present and print names, not values.
- Add/init commands may prompt because they are setup commands.
- Work commands never prompt and never ask the user to choose credentials mid-run.
- Validation commands remain explicit opt-in because they can call provider APIs.
- Config may record enabled provider names, auth kinds, env var names, and non-secret preference metadata.
- Config must not record API keys, bearer tokens, refresh tokens, subscription tokens, cookies, or provider session dumps.

Fallback rules are deliberately strict:

- If the configured auth method fails, report that failure.
- If another auth method is also configured, do not switch to it unless the user explicitly selected a fallback policy.
- Never fall back from subscription/OAuth-style auth to API-key billing silently.
- Never fall back from a direct provider key to an aggregator key silently.
- If fallback policies are added later, they must be user-authored config, visible in `config auth list`, and validated explicitly.

Unsupported auth paths are out of scope until the provider documents them for third-party tools. Browser-cookie scraping, private subscription-token reuse, or undocumented app-token extraction would violate the no-middleman and no-surprise-billing principles even if technically possible.

### Provider Auth Matrix

This matrix captures current direction, not complete implementation.

| Provider | Current/future auth kinds | Notes |
|---|---|---|
| OpenAI | `api_key_env`; future official OAuth only if documented for API clients. | ChatGPT subscription access is separate from API billing unless OpenAI exposes an official third-party path. |
| Anthropic | `api_key_env`; future official OAuth/subscription only if documented for third-party tools. | Claude subscription-token reuse is not an implemented path. |
| Google / Gemini | `service_account_env`; future `api_key_env` for Gemini API path; possible official OAuth if needed. | Current Google path uses Vertex-style environment credentials. |
| Ollama | `local_server`. | No provider subscription or remote billing path. |
| OpenRouter | `api_key_env`. | Aggregator account credits; do not silently fall back to or from direct provider keys. |
| Groq | `api_key_env`. | OpenAI-compatible API route with Groq account key. |
| Mistral | Future `api_key_env`. | Candidate provider. |
| xAI | Future `api_key_env`. | Candidate provider. |
| DeepSeek | Future `api_key_env`. | Candidate provider. |
| Cohere | Future `api_key_env`. | Candidate provider. |
| Perplexity | Future `api_key_env`. | Consumer Pro subscription should not be assumed to grant API access. |
| Together AI | Future `api_key_env`. | Candidate aggregator/provider. |
| Fireworks | Future `api_key_env`. | Candidate aggregator/provider. |
| Cerebras | Future `api_key_env`. | Candidate provider. |

## Local-First Project State

A Think Tank project is a local directory containing durable state and artifacts. Today that state begins as JSON plus directories for transcripts, notes, and artifacts. Git remains the versioning layer.

The current layout is intentionally small and provisional. The engine may later gain richer storage, migrations, an API layer, or a database-backed query path, but the current filesystem layout gives us a concrete project spine without committing to a mature schema too early.

`transcripts/ask.jsonl` is the current append-only log for the minimal `think ask` path. Its row shape is provisional and records one model interaction per line. Do not infer a full session, round, or multi-agent transcript schema from it yet.

## Domain Model Discipline

The domain model is the vocabulary the system treats as real: nouns such as project, claim, question, decision, evidence, artifact, transcript, and summary; verbs such as ask, elaborate, synthesize, review, branch, and visualize.

These words are candidates, not all settled abstractions. Avoid creating heavy domain classes, schemas, or command namespaces before repeated real use proves they have earned their place.

`state.json` should carry a `schema_version` from the beginning. Schema evolution is expected.
