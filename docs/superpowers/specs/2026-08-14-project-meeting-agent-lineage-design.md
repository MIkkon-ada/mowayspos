# Project meeting Agent: fact, baseline, delta, and lineage design

## Scope

Evolve the existing project-meeting document Agent without replacing it.  The
existing Word upload, frozen `ProjectMeetingRun.snapshot_json`, read-only
Agent tools, `MeetingChangeSet` / `MeetingChangeProposal`, owner review, and
manual writeback remain in place.

The new design makes four concepts explicit:

```text
Meeting Word -> Meeting Fact -> Project Match -> Project Delta -> Proposed Change
```

They are distinct data sources and must never be presented as one another.

## Data-source rules

1. The uploaded Word is the only source for facts newly said, confirmed, or
   changed in this meeting.  Each meeting fact has one or more exact Word
   evidence spans.
2. The frozen project snapshot is the official pre-meeting baseline.  It may
   prove an existing project value and may help matching, but it cannot supply
   a missing current-meeting fact.
3. An inference or delta is a reasoned comparison of a meeting fact and the
   frozen baseline.  It cannot itself create a new value that can be written
   to the project database.
4. A proposed change is review-only.  Every value it would write must have a
   field-level source: `meeting_fact`, `project_baseline`, or `human_edit`.
   An inferred value is never a write source.
5. Formal project data is changed only after owner approval and revalidation.

## Agent contract

The existing Agent remains a bounded single Agent.  Its final schema retains
the current meeting presentation fields (`meeting_info`, `summary`, agenda,
decisions, completions, next steps, risks, and open questions) and adds an
analysis layer:

```json
{
  "meeting": {},
  "meeting_facts": [],
  "project_matches": [],
  "project_deltas": [],
  "proposed_changes": [],
  "unmatched_items": [],
  "needs_confirmation": []
}
```

Every analysis-layer item uses a stable ID.  IDs are generated/validated as
unique within the result: `F...`, `M...`, `D...`, and `C...`.  A match cites a
fact; a delta cites its fact and an optional valid match; a proposed change
cites a fact and delta, and cites a match whenever it targets an existing
project node.

Existing display fields continue to use Word evidence and are serialized in
the existing result shape, so old meeting records remain readable.
The analysis layer augments rather than replaces those display fields.

## Snapshot tools

Tools stay read-only and snapshot-scoped.  Tool calls require the active
`project_id`; no live project database query is introduced during analysis.

`search_plan_nodes` accepts `fact_id` plus a focused query and returns a
candidate set with explicit target type, title, parent hierarchy, status,
assignee, and execution-schedule summaries.  Other tools can return detailed
snapshot nodes, recent progress, and prior approved meetings only after a
focused query.  Historical meetings remain continuity context, not current
meeting facts.

## Validation and normalization

Normalization treats the model output as untrusted.

- Meeting facts require valid continuous Word evidence.
- Project matches require a known fact, a target contained in the frozen
  snapshot, and project evidence that actually exists on that snapshot node.
- Deltas require a known fact and either a known match or an explicit
  `UNMATCHED` / `AMBIGUOUS` state.  Delta reasoning is retained as analysis,
  not promoted to a writable value.
- Proposed changes require a complete upstream lineage, a snapshot-bounded
  target, an allowed execution-schedule operation, `requires_confirmation`,
  and field-level provenance for every proposed field.
- Proposed values with no source, an invalid source ID, or an inferred-only
  source are blocked.

When a proposed field inherits a baseline value, its lineage records
`source_type: project_baseline`, the exact `source_object` and `source_field`,
and `usage: inherit`.  Only an explicitly allowed inherited field can use this
path; it is never represented as a value newly agreed in the meeting.

The existing generic legacy normalizer is retained for old meeting flows.

## Persistence and compatibility

`ProjectMeetingRun.result_json` and `MeetingChangeSet.result_json` retain the
full normalized analysis package.  `MeetingChangeProposal` gains a
`lineage_json` column containing fact/match/delta/change IDs, evidence,
baseline context, inference reasoning, and field-level provenance.

No separate MeetingFact, Match, Delta, or ProposedChange database tables are
introduced.  Records without `lineage_json` are legacy proposals: they remain
readable and use their existing validation/writeback behavior.

## Owner review and writeback

The review payload exposes the chain needed for lightweight display:

```text
meeting fact -> matched project node -> baseline -> delta reasoning -> proposed edit
```

The owner keeps the current choices: select approved changes, return the
meeting with a reason, or leave a proposal unapplied.  The review surface adds
an expandable trace; it does not become a new workflow.

Before a selected proposal writes, the server revalidates its lineage and
snapshot boundary.  An UPDATE must target the exact snapshot object and its
stored `before` baseline must still equal the live target.  A CREATE must
target a parent contained in the snapshot; the parent must still be valid and
unchanged in the fields that govern creation, and an equivalent live child
must not already exist.  If either operation becomes stale or conflicts, the
proposal is marked `conflict` / `stale` and the write is refused.  No silent
overwrite or duplicate creation is allowed.

## Test acceptance

Tests cover Word-fact isolation, snapshot-backed matching, cross-source delta
reasoning, ambiguous matching, target boundary rejection, stable lineage,
field provenance, stale-target writeback refusal, no AI direct write, and
legacy result readability.
