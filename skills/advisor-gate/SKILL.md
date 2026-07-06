# Advisor Gate

Use this skill when work must pass Hermes Advisor Gate before final delivery.

The Advisor is review-only. It must not execute tools, edit files, deploy,
or claim implementation work. Use the `advisor_audit` tool to audit packets.
Use `advisor_resolution_gate` to record the Commander's decision about Advisor
findings after A3-Final.

Run audits at these points:

- `A1_PLAN`: before implementation, with task, plan, constraints, and evidence.
- `A2_DELEGATION`: after delegation planning or subagent fanout decisions.
- `A3_EXCEPTION`: after tool, model, runtime, or subagent failures.
- `A3_FINAL`: before final response, with final draft, verification evidence,
  known unresolved items, receipts, and changed files.

For `A3_FINAL`, the packet must have this shape:

- `actions_taken`: list of evidence objects or summaries.
- `tests_or_checks`: list of command/test/log/check evidence objects or summaries.
- `known_unresolved`: list of unresolved items, also reflected in the final draft.
- `final_answer_draft`: the exact final answer draft to be audited.
- `flow_summary`: concise Plan/Delegation/Exception/Final flow summary.

Treat verdicts as follows:

- `PASS`: continue.
- `CHANGES_REQUIRED`: resolve findings or document unresolved items before final.
- `BLOCK`: stop until the blocking finding is resolved.

The plugin enforces A1/A2 before action:

- Configured mutating, executing, or dispatching tools are blocked until
  `A1_PLAN` passes for the current turn.
- `delegate_task` is blocked until both `A1_PLAN` and `A2_DELEGATION` pass for
  the current turn.
- If a tool/runtime failure is observed, final delivery is blocked until a
  later `A3_EXCEPTION` audit passes.
- `A3_FINAL` must be run after the latest relevant tool, subagent, or exception
  event; stale final audits are not accepted.
- If blocked, run the requested `advisor_audit` phase, address any findings,
  and retry the action only after the Advisor policy action is `continue`.

Before final delivery, call `advisor_resolution_gate`:

- Use `commander_decision="continue"` only when no open findings remain.
- Use `commander_decision="requires_resolution"` when findings remain open.
- Every Advisor finding must be marked `accepted`, `resolved`, `deferred`, or
  `rejected` with a reason and evidence.
- Do not hide unresolved or deferred findings; include them in `known_unresolved`
  and in the final answer.

Do not hide degraded Advisor behavior. If the audit cannot run or returns
invalid JSON, keep the degraded receipt and report it honestly.
