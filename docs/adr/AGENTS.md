# Decision Records (`docs/dr/`)

## Intent

This directory holds **Architectural Decision Records (ADRs)** — short notes capturing non-trivial choices about this repo: what was decided, why, and what follows.

An ADR is warranted whenever a choice is non-obvious enough that future-me (or an agent) would otherwise have to reverse-engineer the reasoning.

## Writing a record

1. Copy the template below into a new file named `NNN-kebab-slug.md`, where `NNN` is the next zero-padded number in sequence (`001`, `002`, …). Never reuse a number.
2. Fill every heading. Keep it tight — a DR is a note, not an essay. Aim for 30 lines per file. This may be exceeded if the decision is complex enough to need more considered explanaition. 

### Template

```markdown
# DR-NNN: <Sentence-case title>

**Status:** Proposed
**Date:** DD/MM/YYYY

## Context
The situation and the forces at play — what made this a decision.

## Decision
What was chosen.

## Considered
alternatives explored with one-liner for why they were discarded. 

## Consequences
What follows — trade-offs accepted, things to watch, follow-ups.
```

## Status lifecycle

`Proposed` → `Accepted` → `Superseded by DR-NNN`  (or `Rejected`)

The **Status** / **Date** header is the only part of a record edited after the fact.
The body is a snapshot: if a decision changes, don't rewrite history — set the old
record's status to `Superseded by DR-NNN` and write the new one.
