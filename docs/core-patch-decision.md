# Core Patch Decision

## Decision

Do not patch Hermes core for Advisor Gate.

Advisor Gate must use only official Hermes plugin surfaces in the current
deployment. The implementation is therefore a baseline Hermes config plus a
private plugin, skill, and receipt store.

## Evidence

Official Hermes source/docs confirm the surfaces needed for the supported
Advisor Gate scope:

- `ctx.register_tool`
- `ctx.register_hook`
- `ctx.llm.complete_structured`
- `subagent_start`
- `subagent_stop`
- `pre_tool_call`
- `post_tool_call`
- `pre_verify`
- `transform_llm_output`

`pre_final_response` is not an official hook at the pinned Hermes commit and is
not registered by this plugin.

## Consequence

Advisor Gate can enforce:

- same-turn A1 before configured action tools and unclassified tools,
- same-turn A2 before delegation,
- observed exception review before verification,
- A3_FINAL freshness and ResolutionGate checks before coding-turn verification,
- final-response soft blocking through `transform_llm_output`.

Advisor Gate cannot guarantee a universal pre-delivery repair loop for every
non-coding final response unless Hermes upstream adds an official hook for that
purpose later.
