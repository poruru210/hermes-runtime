# Hermes Plugin Contract For Advisor Gate

## Sources Inspected

- Hermes official plugin guide
- Hermes official plugins feature docs
- Hermes official hooks feature docs
- Hermes official plugin LLM access docs
- Hermes Agent source: `hermes_cli/plugins.py`
- Hermes Agent source: `agent/plugin_llm.py`
- Hermes Agent source: `agent/turn_finalizer.py`
- Hermes Agent source: `agent/conversation_loop.py`
- Hermes Agent source: `tools/delegate_tool.py`
- Hermes Agent source: `hermes_cli/hooks.py`

## Confirmed Surfaces

| Capability | Status | Evidence | Advisor use |
|---|---:|---|---|
| General plugin manifest | verified | docs require `plugin.yaml` and `__init__.py` | `plugin/advisor-gate` |
| Tool registration | verified | `PluginContext.register_tool` | `advisor_audit` |
| Hook registration | verified | `PluginContext.register_hook` | lifecycle receipts and soft gate |
| Structured LLM call | verified | `ctx.llm.complete_structured` / `agent.plugin_llm.PluginLlm` | review-only audit |
| Plugin LLM trust gate | verified | `plugins.entries.<id>.llm.*` docs/source | provider/model override is opt-in |
| `subagent_start` | verified | `VALID_HOOKS`, `tools/delegate_tool.py` | spawn receipts |
| `subagent_stop` | verified | `VALID_HOOKS`, `tools/delegate_tool.py` | completion receipts |
| `pre_tool_call` | verified | `VALID_HOOKS`, `get_pre_tool_call_directive` | A1/A2 pre-action gate |
| `post_tool_call` | verified | hooks docs and synthetic payload | evidence receipts |
| `pre_verify` | verified | `get_pre_verify_continue_message`, conversation loop | coding-turn continuation |
| `transform_llm_output` | verified | `agent/turn_finalizer.py` | final soft gate |

## Hook Semantics

`subagent_start` and `subagent_stop` are observer hooks. Return values are not
used by Hermes core.

`pre_tool_call` can return a directive before a tool runs. Advisor Gate uses the
official hook to block configured action tools until A1 passes and to block
configured assignment tools such as `kanban_create`, `kanban_link`,
`kanban_unblock`, and compatibility `delegate_task` until A2 passes. It also
records `advisor_audit` / `advisor_resolution_gate` invocation context so the
subsequent tool receipt can carry `turn_id`, `tool_call_id`, and
`api_request_id` even when the registry handler itself receives only
`session_id` / `task_id`. When Hermes provides a `turn_id`, A1/A2 receipts must
have the same `call_context.turn_id`; stale receipts from earlier turns are not
accepted.

`post_tool_call` is observer-only for policy purposes, so Advisor Gate writes
evidence metadata and redacts obvious secret-like keys.

`pre_verify` can return:

```json
{"action": "continue", "message": "..."}
```

Hermes accepts this as a nudge to keep a coding turn going, bounded by
`agent.max_verify_nudges`.

`transform_llm_output` can return a non-empty string to replace the final
response. First non-empty string wins. This is a soft gate because it changes
delivery text after the model has finished, but it does not itself create a
repair loop.

## LLM Access

`ctx.llm.complete_structured()` is the supported plugin LLM lane. It uses
host-owned auth and provider resolution. Provider/model overrides are denied by
default unless configured under `plugins.entries.advisor-gate.llm`.

The default Advisor config leaves `advisor_gate.provider` and
`advisor_gate.model` empty so the plugin follows the active Hermes model. If the
desired model is unavailable, this is the preferred fallback.

## Config Behavior

Official plugin config uses:

```yaml
plugins:
  enabled:
    - advisor-gate
  entries:
    advisor-gate:
      llm:
        allow_provider_override: false
        allow_model_override: false
```

`advisor_gate.*` is this plugin's private config block, read by the plugin via
Hermes `load_config()`. Implemented keys are:

```yaml
advisor_gate:
  enabled: true
  provider: ""
  model: ""
  max_input_chars: 64000
  receipt_path: "~/.hermes/advisor/receipts.jsonl"
  pre_action_gate:
    require_a1_before_action: true
    require_a2_before_assignment: true
    gate_unclassified_tools_before_a1: true
    a1_action_tool_names:
      - apply_patch
      - delegate_task
      - edit_file
      - execute_code
      - kanban_block
      - kanban_comment
      - kanban_complete
      - kanban_create
      - kanban_link
      - kanban_unblock
      - patch
      - send_message
      - terminal
      - write_file
    a2_assignment_tool_names:
      - delegate_task
      - kanban_create
      - kanban_link
      - kanban_unblock
    a1_exempt_tool_names:
      - advisor_audit
      - advisor_resolution_gate
      - browser_snapshot
      - find_files
      - list_files
      - read_file
      - search_files
      - view
      - web_extract
      - web_search
    a1_exempt_tool_prefixes: []
  soft_gate:
    require_a3_exception: true
    require_a3_final: true
    require_resolution_gate: true
    gate_subagents: false
    defer_while_subagents_active: true
```

The Advisor call uses `ctx.llm.complete_structured()` and does not expose tool
execution to the Advisor.

## Not Confirmed / Not Implemented

| Item | Status | Reason |
|---|---:|---|
| `delegate_task(advisor=true)` | not supported | no official API found |
| `pre_final_response` hook | not supported at pinned commit | not registered; no core patch is required |
| blocking all final responses before generation | not supported | `transform_llm_output` runs after generation |
| non-coding repair loop via `pre_verify` | not supported | `pre_verify` is scoped to code-edited turns |
| Advisor executing tools | intentionally not supported | violates Advisor role |

## Runtime Contract

Advisor Gate registers two tools:

- `advisor_audit`: review-only Advisor LLM audit.
- `advisor_resolution_gate`: Commander-owned resolution receipt for accepted,
  resolved, deferred, or rejected findings.

Configured action tools and unclassified tools are allowed only when the latest
current-turn A1 receipt passes. Configured assignment tools are allowed only
when both the latest current-turn A1 and A2 receipts pass. The initial runtime
profile uses Kanban assignment tools; `delegate_task` remains only as a
compatibility target.

Before verification/final delivery in coding turns, Advisor Gate asks Hermes to
continue only when:

- every observed exceptional tool result after the latest A3-Exception receipt
  has a later passing A3-Exception audit,
- the latest A3-Final receipt passes and was written after the latest relevant
  tool/subagent/exception event,
- the receipt's `FinalPayload.final_answer_draft` exactly matches the current
  final draft,
- a `ResolutionGate` receipt after that A3-Final audit has
  `commander_decision: continue`, and
- `open_findings` is empty.

Outside coding-turn verification, `transform_llm_output` remains a fallback
soft gate that can replace unsafe delivery text with an Advisor gate message.
