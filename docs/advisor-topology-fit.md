# Advisor Fit Against Baseline Topology

## Source Images

Two primary design images define the target:

1. Baseline Hermes topology:
   Discord Gateway / current thread -> Level 0 Main Agent -> Level 1 Worker or
   Orchestrator -> Level 2 leaf workers. The baseline uses official Hermes
   delegation, max concurrent children, max spawn depth, delegation model
   routing, auxiliary compression, and fallback configuration.
2. Advisor overlay:
   Advisor is a review-only lane that audits the Commander's plan, delegation,
   exceptions, and final report. Advisor does not execute tools and does not own
   final responsibility; Commander remains the actor and final decision maker.

## Key Interpretation

The Advisor overlay is not a replacement for Hermes delegation. It is a side
channel over the existing Commander/Worker topology:

```text
Commander -> Worker(s) -> Commander
Commander -> advisor_audit(packet) -> AdvisorResult/finding(s) -> Commander
```

That means a plugin is a good fit for observation, audit calls, receipts, and
Advisor policy. The official `pre_tool_call` hook is enough to enforce A1/A2
before configured action tools and `delegate_task`. The current implementation
uses only official Hermes plugin surfaces: `pre_tool_call`, `post_tool_call`,
`subagent_*`, `pre_verify`, and `transform_llm_output`.

## Fit Matrix

| Requirement from images | Current status | Evidence / implementation | Plugin-only fit |
|---|---:|---|---:|
| Baseline Level 0/1/2 topology | specified for target validation | `docs/hermes-baseline-topology.md`; baseline config documents `delegation.max_spawn_depth: 2`, `max_concurrent_children: 3` | yes, via official Hermes config |
| Main model `openai-codex/gpt-5.5` | configured in baseline example | validate with `hermes doctor` in the target install | yes |
| Worker model override | configured conservatively | baseline example documents override; target installs may inherit the active model | yes, via official Hermes config |
| Advisor is review-only | implemented | `advisor_audit` uses `ctx.llm.complete_structured()` and exposes no tools | yes |
| A1/A2/A3-E/A3-F phase vocabulary | implemented | `AdvisorPhase` schema | yes |
| Structured verdicts PASS/CHANGES_REQUIRED/BLOCK | implemented | `AdvisorResult` schema and policy mapping | yes |
| Findings include id/severity/category/message/action/check/quote | implemented | `Finding` schema | yes |
| Receipt store for Advisor and hook evidence | implemented as JSONL | `ReceiptStore`, `subagent_start`, `subagent_stop`, `post_tool_call` | yes |
| Final missing/failing audit returns to Commander before delivery | implemented for coding-turn verification | official `pre_verify` hook asks Hermes to continue | partial |
| Final missing/failing audit blocks delivered final text as fallback | implemented | `transform_llm_output` remains a last-resort soft block | partial |
| Defer final gate while background subagent is active | implemented | `active_child_sessions`, `defer_while_subagents_active` | yes |
| Commander must call A1 before plan execution | enforced for current turn | official `pre_tool_call` hook blocks mutating/executing/delegating/unclassified tools until a same-turn A1 passes | yes |
| Commander must call A2 after delegation design | enforced before delegation | official `pre_tool_call` hook blocks `delegate_task` until a same-turn A2 passes | yes |
| Commander must call A3-E after observed failures | enforced before final | `post_tool_call` marks exceptional tool results; final gates require a later passing A3_EXCEPTION | yes |
| Commander must call A3-F before every verified coding final | enforced at verification gate | `pre_verify` asks for A3_FINAL; `transform_llm_output` blocks if still missing/failing | partial |
| A3-F audit must match the final draft and latest events | implemented | final gate compares current final text to `FinalPayload.final_answer_draft` and requires A3_FINAL after the latest tool/subagent/exception event | yes |
| CHANGES_REQUIRED returns to Commander for repair | implemented for coding-turn verification | `pre_verify` continues the same loop with Advisor findings | partial |
| Findings must be accepted/resolved/deferred/rejected by Commander | implemented for final gate | `advisor_resolution_gate` and `ResolutionGate` schema | yes |
| Worker review can be requested by Advisor | implemented as Commander-owned finding flow | Advisor findings can require Worker review; Commander resolves via normal delegation and records the decision in `advisor_resolution_gate` | yes |
| Final improvement proposals | partially implemented | `AdvisorResult.final_improvement` carries 0/1 proposal; adoption remains Commander-owned | partial |
| Final payload schema is enforced | implemented for A3_FINAL | `FinalPayload` validation rejects malformed final packets before Advisor LLM call | yes |
| Advisor report/receipt retained | implemented as JSONL sidecar | `ReceiptStore` keeps Advisor reports and hook evidence without writing private Hermes session internals | yes |
| Hidden prompt/API keys/memory not leaked | partially implemented | packet redaction by key name; no full content classifier | partial |

## What Plugin MVP Actually Guarantees

The current plugin can guarantee:

- Hermes loads `advisor-gate` through official plugin discovery.
- `advisor_audit` exists as a normal Hermes tool.
- Advisor LLM calls use host-owned Hermes plugin LLM access.
- Advisor itself does not execute tools.
- Advisor outputs are structured and validated.
- Receipts are written for Advisor calls and observed subagent/tool events.
- `A3_FINAL` packets use the required FinalPayload shape.
- Configured mutating/executing/delegating tools and unclassified tools are
  blocked until same-turn A1 passes.
- `delegate_task` is blocked until both same-turn A1 and same-turn A2 pass.
- Observed tool/runtime failures require a later passing A3-Exception audit
  before final delivery.
- A3-Final must be later than the latest relevant tool/subagent/exception event.
- Coding-turn verification re-enters the Commander loop when the current final
  draft lacks a passing matching A3-Final audit.
- Commander resolution is recorded through `advisor_resolution_gate`.
- A final response can still be replaced with a gate message when A3-Final or
  ResolutionGate is missing.

The current plugin cannot guarantee:

- The Commander always calls Advisor at each phase.
- Perfect automatic classification of arbitrary future tool semantics. Unknown
  tools fail closed by default unless configured as exact read-only/exempt names
  or explicit site-local prefixes.
- A Worker review is automatically spawned by Advisor. That is intentionally
  Commander-owned because Advisor is review-only.
- The full flow is saved into Hermes' first-class session metadata.

## Design Implication

The instruction design is valid as a layered architecture when scoped to
official Hermes plugin surfaces. The correct implementation split is:

1. Official Hermes config keeps the baseline topology.
2. Advisor plugin provides the audit tool, structured result, sidecar receipts,
   official `pre_tool_call` A1/A2 gate, `pre_verify` verification gate, and
   soft final gate.
3. Hermes core remains unmodified.
4. Commander prompt/skill still improves packet quality and workflow timing,
   but A1/A2 hard stops live in the plugin hook rather than in prompt text.

## Candidate Next Step

The next meaningful improvements are:

- broaden `a1_action_tool_names` when new Hermes action tools are enabled,
- add Worker-review enforcement if Hermes exposes a first-class review hook,
- include richer subagent/tool receipts in A3-F packets.

Verification gating, `ResolutionGate`, and pre-action A1/A2 enforcement are now
structurally implemented.
