# ADR-0002: No Core Fork

## Decision

Hermes Agent remains an upstream dependency pinned in `upstream.lock`. We do
not create a long-lived fork.

The current deployment also avoids local core patches. Advisor Gate uses only
official Hermes plugin surfaces.

## Why Not Fork

The requirement is best represented as layered pieces:

- official Hermes config for delegation topology
- Advisor plugin for audits, receipts, FinalPayload, and ResolutionGate
- official Hermes plugin hooks for pre-action gating, verification gating, and
  final-response soft blocking

## Upstream Pin

Current inspected upstream:

- repo: `https://github.com/NousResearch/hermes-agent`
- branch: `main`
- commit: `beaa1a08e6abf2fb8efff0b05da8857bef21ce1f`

## Patch Queue

Do not keep local Hermes core changes in this repository or on the target Pi.
If upstream later adds a suitable official hook, adopt it through normal Hermes
updates rather than a private patch queue.

Potential future extension points must remain generic and upstreamable; they
must not hard-code Advisor phases or receipt paths into Hermes core.
