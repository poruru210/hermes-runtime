# Research Notes

## Phase 0 Scope

This phase investigated official Hermes Agent docs and current source for the
baseline delegation topology only. Hermes core was not modified, no fork was
created, and Advisor Gate implementation was not started.

## Sources Inspected

- Official docs:
  - https://hermes-agent.nousresearch.com/docs/user-guide/configuration
  - https://hermes-agent.nousresearch.com/docs/integrations/providers
  - https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
  - https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers
  - https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord
  - https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
  - https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
  - https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin
  - https://hermes-agent.nousresearch.com/docs/api/model-catalog.json
- Current source clone:
  - repo: https://github.com/NousResearch/hermes-agent
  - commit: beaa1a08e6abf2fb8efff0b05da8857bef21ce1f
  - inspected in a local clone outside committed sources

## Confirmed

- Main model config uses `model.provider` and `model.default`; docs also say
  `model.model` is accepted as an alias, but source canonicalizes to
  `model.default`.
- `openai-codex` is a verified provider key.
- `gpt-5.5` is in `hermes_cli/codex_models.py::DEFAULT_CODEX_MODELS`.
- `agent.reasoning_effort` is a verified key. Documented values are `none`,
  `minimal`, `low`, `medium`, `high`, and `xhigh`.
- `delegate_task` supports child model/provider override through
  `delegation.provider` and `delegation.model`.
- `delegation.reasoning_effort` is implemented and overrides the parent
  reasoning config for child agents when valid.
- `delegation.max_concurrent_children`, `delegation.max_spawn_depth`,
  `delegation.orchestrator_enabled`, and `delegation.child_timeout_seconds`
  are verified source keys.
- `role` for `delegate_task` is verified with enum values `leaf` and
  `orchestrator`.
- Leaf children cannot further delegate by default. Orchestrator children retain
  `delegate_task` only when enabled and within `max_spawn_depth`.
- `/agents` exists, with `/tasks` documented as an alias in the delegation docs.
  Source also exposes `tools.delegate_tool.list_active_subagents()`.
- `fallback_providers` is the current top-level fallback config shape.
- `zai` is a verified provider key, and `glm-4.7` appears in the current source
  model list for that provider.
- `auxiliary.compression.provider/model` is the verified compression routing
  shape. `provider: main` is valid for auxiliary tasks only.
- OpenRouter `provider_routing` is opt-in. Omitting it keeps this baseline from
  using explicit smart/provider routing preferences.
- Discord config has top-level `discord.*` behavioral settings. Token and
  authorization values belong in `.env`, not in this repo.

## Runtime Checks Required

- Confirm the authenticated `openai-codex` account can actually use `gpt-5.5`.
- Confirm the authenticated `openai-codex` account can actually use
  `gpt-5.3-codex-spark`. Source says Spark is a Codex OAuth research-preview
  model and may require the right entitlement.
- Confirm `zai` + `glm-4.7` works for the target `GLM_API_KEY`, because the
  provider can expose account/endpoint-specific model availability.
- Confirm Discord thread behavior against the actual server/channel permissions.
- Confirm the TUI/CLI/gateway surface used for the smoke test exposes `/agents`
  or `/tasks` as expected.

## Unresolved Or Deliberately Deferred

- The exact Discord "current thread" UX should be validated in a real Discord
  channel. Source/docs confirm auto-thread and forum thread behavior, but the
  requested topology image was not available as a machine-readable artifact in
  this workspace.
- `display.platforms.discord.cleanup_progress` was not confirmed. The example
  config and docs mention cleanup progress primarily for Telegram, so this
  baseline does not set it for Discord.
- No live Hermes runtime validation was run from this workspace. Commands are
  documented in `docs/hermes-baseline-topology.md`.

## Phase 2-6 Advisor Gate Notes

Additional official docs/source inspected:

- Hermes official plugin LLM access docs
- Hermes Agent source: `hermes_cli/plugins.py`
- Hermes Agent source: `agent/plugin_llm.py`
- Hermes Agent source: `agent/turn_finalizer.py`
- Hermes Agent source: `agent/conversation_loop.py`
- Hermes Agent source: `tools/delegate_tool.py`
- Hermes Agent source: `hermes_cli/hooks.py`

Confirmed:

- General plugins can register tools with `ctx.register_tool()`.
- General plugins can register hooks with `ctx.register_hook()`.
- `ctx.llm.complete_structured()` is official plugin LLM access.
- Plugin LLM provider/model overrides are fail-closed and gated by
  `plugins.entries.<plugin_id>.llm.*`.
- `subagent_start` and `subagent_stop` are valid plugin hooks.
- `pre_verify` can return a `continue` directive for code-edited turns.
- `transform_llm_output` can replace final text before delivery.

Advisor Gate stays inside those confirmed surfaces. A generic local
`pre_final_response` hook was considered and then superseded by the current
no-core decision because it is not an official hook at the pinned Hermes commit.

Still unresolved until live runtime validation:

- Whether the target account can use the preferred Advisor model.
- Whether `advisor-gate` loads cleanly in the target Hermes install.
- Whether Discord gateway permissions allow the full orchestration smoke test.

## Guardrails

- Do not add Advisor-specific policy to Hermes core.
- Do not create a Hermes fork.
- Do not commit secrets.
- Do not implement unverified APIs.
- Do not make Advisor execute tools.
