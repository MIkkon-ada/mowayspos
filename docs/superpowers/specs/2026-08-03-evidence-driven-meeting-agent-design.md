# Evidence-Driven Meeting Agent Design

## Objective

Turn ordinary meeting analysis into a traceable, review-only Agent workflow.  The Agent may propose structured candidates, but it must never silently create meeting facts, project tasks, or task updates.

## Non-negotiable rules

1. `TranscriptSource` is the immutable ASR/manual original.  It is never overwritten.
2. A user correction creates a new `TranscriptRevision`; analyses identify both the original source and the exact revision used.
3. Every candidate must contain verifiable evidence against that revision.  An Agent-supplied quote, person, date, acceptance criterion, decision, or risk is not a fact merely because it is valid JSON.
4. Project members, plans, and tasks are frozen as an analysis-run context.  They may support matching and validation only; they cannot substitute for an assertion in the meeting transcript.
5. Metadata has one of four explicit origins: `user_input`, `transcript`, `system_context`, or `derived`.  Derived values retain the original expression and derivation inputs.
6. Relative dates use the meeting date in `Asia/Shanghai`, with ISO weeks Monday through Sunday.  Ambiguous expressions remain `needs_confirmation`; no year, owner, acceptance criterion, impact, probability, mitigation, decision, or risk may be invented.
7. Candidate types are disjoint: `action_item`, `decision`, `decision_request`, `risk`, and `progress`.  `blocked` candidates remain in the run audit but cannot be included in a saved meeting revision.
8. Saving a draft, submitting, publishing, or returning a meeting appends an immutable meeting revision.  The editable working copy is not a revision.
9. Formal confirmation writes only the selected meeting-minutes content.  Creating or changing project tasks remains a separate, explicit, human-triggered action.
10. All raw sources, analyses, evidence, reviews, and versions use existing project access controls and produce audit-log records when viewed or changed.

## Domain model

```text
Meeting (current/latest projection)
  ├─ MeetingTranscriptSource (one immutable original input)
  │   └─ MeetingTranscriptRevision (zero or more human corrections)
  ├─ MeetingAnalysisRun (one immutable context + provider execution)
  │   └─ MeetingAnalysisCandidate (one reviewable candidate per item/metadata field)
  └─ MeetingRevision (immutable saved snapshot, linked to source/revision/run)
```

`MeetingAnalysisRun` stores the provider/model/policy version, prompt hash, input hash, system time and timezone, member snapshot, plan/task snapshot, untrusted raw model response, normalized candidate package, and validation package.  `MeetingAnalysisCandidate` stores the Agent proposal, evidence, validation state, reviewer decision, human final value, and reviewer comment.

An evidence object always includes the source/revision identity, quote, character range, and source hash.  Audio segment identifiers and millisecond ranges are optional and are populated only when the ASR source supplies them.

## Agent and validation boundary

```text
Transcript revision + frozen context
        ↓
Extraction Agent (untrusted candidate JSON with evidence spans)
        ↓
Deterministic validator
  source-span/hash, metadata origin, member evidence, date resolution,
  candidate-type rules, task-ID membership, and no-invented-field checks
        ↓
Review workbench (accept / edit and accept / needs confirmation / ignore)
        ↓
Immutable meeting revision (human-selected content only)
```

The Agent is permitted to leave fields null.  It is not permitted to fill a missing value with a plausible value.  A missing explicit owner is not repaired with a task snapshot owner.  A snapshot completion standard can be shown as a linked reference, but is never represented as a meeting-confirmed criterion without transcript evidence.

## Date policy

- `明天`, `后天`, `本周五`, and `下周三` resolve only from the stored meeting date/timezone and retain the original expression.
- `下周` becomes an ISO-week range, not an arbitrary single deadline.
- Month/day expressions resolve only where the year is uniquely determined by explicit transcript context or the meeting-date policy; otherwise they remain the original expression with `needs_confirmation`.
- `尽快`, `近期`, `过几天`, `下一阶段`, `有时间的时候`, and `月底左右` are never converted to calendar values.

## Review and versioning

The review screen presents one candidate at a time with: Agent proposal, source evidence, validator state/messages, and final editable value.  It shows a complete save preview and revision diff before creating a version.  `MeetingRevision` stores the parent revision, source/revision/run IDs, raw agent and validation snapshots, human output, and human diff in addition to the legacy current-meeting projection fields.  Existing V0 legacy snapshots and V1+ user versions keep their established numbering.

