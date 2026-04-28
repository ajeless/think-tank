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

The installed CLI entrypoint is assembled in `think_tank.cli`, but command groups may live in focused CLI modules. Root work commands stay in the root CLI module for now; config command groups live beside it in dedicated modules so interactive setup flows can grow without turning the entrypoint into a behavior owner. Top-level `think init` is a setup adapter: the CLI owns prompts and terminal formatting, while `think_tank.setup` owns the config orchestration.

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

Config files may record explicit user-authored defaults under `[defaults]`. Defaults are setup-owned preferences, not product-invented choices. Work commands may use a recorded default only when their command contract explicitly says they do. Until then, commands such as `think ask` must keep requiring explicit command input or an explicit model profile flag.

Setup commands may guide users through provider detection and configuration. Top-level `think init` is the first guided setup flow: it detects implemented ready auth paths, lets the user select the paths to record, may show planned official paths as disabled guidance, writes non-secret auth metadata, and may record model profiles and explicit defaults. Work commands must stay non-interactive and must not prompt for credentials mid-run.

Subscription account sign-in is provider-specific and only acceptable through an official supported auth path. The tool must not implement unsupported subscription-token workarounds, and it must not silently fall back from subscription auth to API billing. Any validation that could spend money or hit external provider rate limits must be opt-in.

Claude Code subscription auth is a separate integration candidate, not a replacement credential for the direct Anthropic API provider. The direct `anthropic:<model>` path remains Anthropic API access through `api_key_env`. A future Claude Code path must be modeled as a product-specific integration or adapter with its own command contract, auth detection, validation, transcript shape, and limitations.

Provider failures are product errors, not Python tracebacks. The CLI should surface concise messages for missing credentials, quota failures, authentication failures, and provider SDK issues without leaking secret values.

`think config validate` is the explicit real-provider diagnostic boundary. It belongs in setup/config space, not work-command behavior. Validation may spend provider quota or hit external rate limits, so it is opt-in and never runs as part of `doctor`, `init`, or `ask` by default. The engine owns the validation behavior and returns structured status data; the CLI only formats that status and chooses the process exit code.

Validation must use the same no-middleman rules as model calls:

- Require an explicit provider and `provider:model` value.
- Do not choose fallback models or fallback auth methods.
- Do not store credentials or write provider secrets to config.
- Do not write transcripts or mutate project state.
- Use fake clients in tests so test runs never depend on provider APIs or network access.

Ollama is local-provider validation rather than credential validation. The validator checks local server availability using `OLLAMA_API_URL` or the default `http://localhost:11434`, then verifies that the requested model appears in the local model registry.

Provider metadata is owned by the provider registry layer, not by CLI command code or config file mutation code. Engine behavior and config behavior may both depend on the packaged provider registry, but the registry should stay focused on supported provider names, auth method metadata, implementation status, official-path status, and environment-based readiness detection. Packaged provider specs use explicit auth method records as their only auth shape.

User config file concerns are separate from provider metadata. Config storage helpers own default config path resolution, TOML loading errors, text writing, and TOML string escaping. Shared config helpers own TOML table validation and rendering. Higher-level config behavior is split by product concern: auth records, model profiles, and explicit defaults each have their own module. `think_tank.config` remains a compatibility facade for CLI and external imports; it should not regain behavior ownership.

### Config Layering Direction

Think Tank currently writes user-level config to `~/.config/think-tank/config.toml` by default, or to an explicit `--config <path>`. This is enough for early setup, but project-specific model choices will likely need their own layer once projects have more durable agent and workflow preferences.

The likely long-term shape is:

- User config stores machine-local preferences: provider auth metadata, global model profiles, and global explicit defaults.
- Project config stores project-local preferences: project model profiles, project defaults, and future agent or workflow selections.
- Command inputs win over project config, and project config wins over user config.
- If no command input or configured value supplies a required model, work commands still fail clearly instead of inventing a provider, model, auth method, or fallback.

Provider auth metadata should remain primarily user-level because credentials are user-machine state, not project state. Project config may reference profile names or explicit `provider:model` strings, but it must not store provider secrets. Both config layers follow the same no-secret rule: API keys, bearer tokens, refresh tokens, subscription tokens, browser cookies, and provider session dumps stay out of Think Tank config and project state.

### Auth Model Direction

Provider auth is explicit configuration, not an implicit rescue path. Think Tank may help a user discover, inspect, enable, disable, or validate auth methods, but it must not invent a billing path or silently escalate from one user-supplied auth method to another.

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
- Capability commands inspect known provider auth methods and print implementation/readiness metadata, not secret values.
- Add/init commands may prompt because they are setup commands.
- Setup commands may help the user select an implemented ready auth method, model profiles, or explicit defaults, but those choices must be visible user-authored configuration.
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

Explicit defaults are different from hidden defaults. A setup flow may offer to write a user-selected default model profile or auth preference to config. Work commands may then use that recorded configuration only when the command contract says they can. Think Tank must still never invent a default model, choose a billing path, or retry through a fallback path that the user did not configure.

Unsupported auth paths are out of scope until the provider documents them for third-party tools. Browser-cookie scraping, private subscription-token reuse, or undocumented app-token extraction would violate the no-middleman and no-surprise-billing principles even if technically possible.

Provider config supports multiple auth method records per provider. The current flat `auth_kind` and `env_vars` fields remain the selected/current method and keep existing config readable. New writes also include an `auth_methods` collection under each provider so setup flows can add implemented official OAuth, service-account, local-server, or subscription-supported methods without treating them as fallback paths. Existing flat provider metadata is still accepted and is normalized in engine results.

`think config auth methods` lists known provider auth method capabilities, including implementation status, official-path status, readiness, selectability, env var names, and notes. It is diagnostic only: it does not read or write config, validate credentials with provider APIs, or print secret values.

`think config auth add` may select among multiple ready auth methods when a provider has more than one implemented method. `--yes` remains deterministic and uses the provider's current primary implemented method. Subscription/OAuth-style methods must not be listed as selectable until they are backed by an official supported provider path.

### Official Subscription Auth Roadmap

Reducing live-testing API cost is a real product goal. `think init` should eventually be the guided setup surface for any official provider-supported subscription, OAuth, local, or cloud auth path that Think Tank can use without becoming a credential middleman.

The implementation gate is strict: an auth path is selectable only after the provider documents it for the kind of client Think Tank is building, and after Think Tank has an implementation that stores no provider secrets in TOML or project state. Browser-cookie scraping, undocumented app-token reuse, private subscription-token extraction, or replaying another app's session files remain out of scope.

Official does not always mean general-purpose. Some providers document subscription-backed auth for a specific first-party coding product, while separately documenting API usage and billing for general API clients. Think Tank should treat those as candidate product-specific integrations, not as proof that the same subscription can be used for arbitrary `provider:model` calls.

Near-term roadmap:

- Track provider-supported auth methods in the provider registry even before all are implemented, and make only implemented ready methods selectable.
- Let `think init` explain when a provider has a promising official path that is not implemented yet by showing it as disabled guidance.
- Prefer local or subscription-backed official paths for live testing when available, then direct API keys, then aggregators only when explicitly selected.
- Add fallback policy only as visible user-authored config, never as automatic recovery.
- Keep `think config validate` as the opt-in boundary for any check that may call a provider or spend credits.

Current research snapshot, as of April 28, 2026:

| Provider/product | Official lower-cost or subscription-relevant path | Think Tank status |
|---|---|---|
| OpenAI API | API docs document API-key bearer auth; OpenAI Help says ChatGPT and API billing are separate. | Keep `api_key_env` for general OpenAI API calls. Do not treat ChatGPT Plus/Pro as generic API auth. |
| OpenAI Codex | OpenAI Help documents ChatGPT sign-in for Codex CLI/IDE/app and says Codex is included with ChatGPT plans. | Candidate separate Codex integration, not a drop-in OpenAI API provider path. Needs design before implementation. |
| Anthropic API | Anthropic API docs require `x-api-key`; Anthropic Help says paid Claude.ai plans do not include API Console usage. | Keep `api_key_env` for direct Anthropic API calls. Do not treat Claude Pro/Max as generic API auth. |
| Claude Code | Anthropic/Claude Code docs document Claude.ai subscription OAuth credentials for Claude Code. | Candidate Claude Code or Claude Code SDK integration, not a drop-in Messages API auth path. Needs design before implementation. |
| Google Gemini / Vertex AI | Google documents API keys, OAuth, and Application Default Credentials. | Prioritize official env/ADC support before inventing any Google-specific secret storage. Cost still belongs to the user's Google project. |
| Ollama | Local server auth needs no provider account or API key. | Already supported as `local_server`; safest path for cost-free live testing. |
| OpenRouter | Docs document bearer API keys and account credit limits. | Keep explicit `api_key_env`; useful for budgets/limits but not subscription auth. |
| Groq | Docs document bearer API keys through OpenAI-compatible endpoints. | Keep explicit `api_key_env`; no subscription path currently documented for Think Tank. |

### Claude Code Subscription Auth Design Direction

This section records the first design boundary for Claude Code subscription-backed auth, verified against official docs on April 28, 2026.

Current facts:

- The Claude API is a REST API for programmatic access and requires a Claude Console account plus an API key. Direct API requests require the `x-api-key` header. A paid Claude subscription does not include Claude API or Console access.
- Claude Code is a separate Anthropic product and supports Claude Pro, Max, Team, and Enterprise subscription OAuth through Claude.ai login. It also supports Console auth, cloud-provider auth, `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `apiKeyHelper`, and `CLAUDE_CODE_OAUTH_TOKEN` with its own precedence rules.
- Claude Code can generate a long-lived OAuth token with `claude setup-token`; the token is printed for the user to place in `CLAUDE_CODE_OAUTH_TOKEN`. That token is a secret and must not be stored in Think Tank config or project state.
- Claude Code CLI has non-interactive print mode via `claude -p`, including JSON output options. This makes a future subprocess adapter plausible, but it would be a Claude Code integration with Claude Code behavior, not a direct Anthropic Messages API client.
- The Claude Agent SDK docs say third-party developers may not offer claude.ai login or rate limits for their products without prior approval and should use the documented API-key auth methods. That blocks a direct SDK-based subscription-login implementation unless Anthropic explicitly approves it for Think Tank's use case.

Design decision:

- Keep the current `anthropic` provider path as direct Anthropic API access through `api_key_env`.
- Do not represent Claude Code subscription OAuth as `anthropic:...` auth.
- Do not read, parse, copy, or reuse Claude Code's stored credential files.
- Do not store `CLAUDE_CODE_OAUTH_TOKEN`, bearer tokens, refresh tokens, browser cookies, or Claude Code credential dumps.
- Treat Claude Code as a future product-specific integration, likely a separate adapter surfaced explicitly by command/profile configuration after the model profile schema can distinguish generic `provider:model` API clients from tool/product adapters.
- Prefer a future implementation that shells out to the installed `claude` CLI in non-interactive print mode using user-managed Claude Code auth, with explicit user opt-in and clear transcript/cost semantics.
- Any future Claude Code integration must disable or tightly constrain editing/tool permissions unless the command is explicitly a code-agent workflow. It must not silently gain file-editing or shell-execution behavior inside a plain ideation command.

Open implementation questions:

- Whether Think Tank should add a new adapter namespace such as `claude_code` or a more general integration profile type instead of extending the current `provider:model` model profile grammar.
- Whether `think config auth methods` should keep listing Anthropic `subscription_official` as a planned path, or split it into a separate `think config integrations methods` surface once product integrations exist.
- Whether validation should call `claude auth status --json`, run a tiny `claude -p` request, or offer both as separate diagnostics with clear quota and behavior warnings.
- How to represent Claude Code output and usage metadata in transcripts without pretending it is the same row shape as direct model API calls.

Research source links for this snapshot:

- OpenAI API authentication: https://platform.openai.com/docs/api-reference/authentication
- OpenAI ChatGPT/API billing separation: https://help.openai.com/en/articles/9039756
- OpenAI Codex with ChatGPT plans: https://help.openai.com/en/articles/11369540-codex-in-chatgpt
- Anthropic API authentication: https://docs.anthropic.com/en/api/getting-started
- Anthropic Claude.ai/API billing separation: https://support.anthropic.com/en/articles/9876003
- Claude Code authentication: https://code.claude.com/docs/en/iam
- Claude Code CLI reference: https://code.claude.com/docs/en/cli-reference
- Claude Agent SDK overview: https://code.claude.com/docs/en/agent-sdk/overview
- Google Gemini OAuth: https://ai.google.dev/gemini-api/docs/oauth
- Google Vertex AI Application Default Credentials: https://cloud.google.com/vertex-ai/generative-ai/docs/start/gcp-auth
- OpenRouter API authentication: https://openrouter.ai/docs/api-reference/authentication
- Groq API docs: https://console.groq.com/docs/

### Provider Auth Matrix

This matrix captures current direction, not complete implementation.

| Provider | Current/future auth kinds | Notes |
|---|---|---|
| OpenAI | `api_key_env`; possible future Codex-specific subscription integration. | ChatGPT subscription access is separate from API billing. Codex subscription auth is product-specific and needs separate design. |
| Anthropic | `api_key_env`; possible future Claude Code-specific subscription integration. | Claude.ai paid plans do not include API Console usage. Claude Code subscription auth is product-specific and needs separate design. |
| Google / Gemini | `service_account_env`; future `api_key_env` for Gemini API path; possible official OAuth/ADC expansion. | Current Google path uses Vertex-style environment credentials. |
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
