# ADR-0001: Plugin First

## Decision

Advisor Gate starts as a Hermes plugin, skill, and receipt-store extension. It
does not modify Hermes core and does not add `delegate_task(advisor=true)`.

Status update: this remains the current decision. ADR-0003 was superseded and
no Hermes core hook patch is applied in the current deployment.

## Context

Official Hermes docs/source confirm enough plugin surface for an MVP:

- `ctx.register_tool()` for `advisor_audit`
- `ctx.register_hook()` for lifecycle hooks
- `ctx.llm.complete_structured()` for host-owned structured LLM calls
- `transform_llm_output` for final-response soft gating
- `pre_verify` for code-edit continuation nudges
- `subagent_start` and `subagent_stop` for delegation receipts

This covers review-only Advisor behavior without creating a fork.

## Consequences

- Advisor enforcement is soft at first.
- Plugin failures degrade to `CHANGES_REQUIRED` receipts.
- Hard guarantees are limited by the official hook semantics.
- Operators can enable/disable the plugin through normal Hermes plugin config.

## Core Patch Trigger

Consider a core patch only if integration evidence proves that plugin/hook
surfaces cannot meet the required gate behavior, for example if final audit
results must re-enter the same agent loop for repair and no official hook can do
that.
