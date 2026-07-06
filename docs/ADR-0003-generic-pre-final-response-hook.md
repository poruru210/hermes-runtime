# ADR-0003: Generic Pre-Final-Response Hook

## Status

Superseded.

## Previous Decision

This ADR previously proposed a local Hermes core patch that exposed a generic
`pre_final_response` plugin hook.

## Superseding Decision

The current deployment does not patch Hermes core and does not register
`pre_final_response`. Advisor Gate uses official Hermes plugin surfaces only:

- `pre_tool_call`
- `post_tool_call`
- `subagent_start`
- `subagent_stop`
- `pre_verify`
- `transform_llm_output`

## Consequence

Advisor Gate supports coding-turn verification continuation through
`pre_verify` and final-response soft blocking through `transform_llm_output`.
It does not claim a universal pre-delivery repair loop for every final response
unless Hermes upstream adds an official hook later.
