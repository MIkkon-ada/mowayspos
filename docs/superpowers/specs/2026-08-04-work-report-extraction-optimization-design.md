# Work Report Extraction Optimization Design

## Goal

Improve the personal work-report text-to-structure pipeline without changing
realtime ASR transport. The pipeline must produce reviewable, permission-safe
work cards from transcript text and must not invent facts.

## Scope

The change covers `POST /api/updates/extract`, the extractor service, and the
voice-update review UI. Meeting transcription and automatic submission remain
out of scope.

## Extraction contract

The LLM output remains JSON with summary, completed items, achievements, issues,
next steps, task reports, and key-task issues. The prompt must distinguish:

- completed work from plans;
- concrete deliverables from process descriptions;
- explicit blockers from ordinary progress or possible coordination;
- known facts from unknown fields, which stay empty;
- progress reports from genuinely new tasks.

Every task report may carry evidence text and a confidence value. Evidence is a
short quote or normalized span from the submitted transcript, never generated
facts.

## Deterministic validation

After LLM JSON parsing, the backend normalizes dates and status values, removes
duplicate items, validates field types and length limits, rejects unauthorized
task IDs, and marks malformed or low-confidence matches as `needs_confirmation`.
The original transcript remains available for human review; no automatic
submission is triggered by extraction.

## Task matching

The model may suggest a task description, but the backend remains authoritative
for IDs and permissions. It matches only against the user's authorized task
candidate pool. Ambiguous matches return candidates and a reason instead of
silently binding a task.

## Evaluation

Create a small immutable extraction corpus covering completed work, achievements,
issues, plans, multiple subtasks, dates, ASR typos, and empty fields. Each case
has a human-reviewed expected JSON. Regression tests validate JSON shape,
classification rules, task matching safety, and no-fabrication behavior. The
corpus is for local evaluation and contains no production secrets.

## UI behavior

The review cards show match status, confidence, evidence, and fields requiring
confirmation. User edits remain authoritative when the report is submitted.
