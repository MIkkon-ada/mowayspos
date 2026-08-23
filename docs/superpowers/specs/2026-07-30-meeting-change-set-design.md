# Meeting Change Set Design

## Goal

Replace the current two-pass meeting workflow with one Agent result that contains
both the meeting record and a reviewable change set for the work progress plan.
The Agent may propose changes to workstreams and subtasks, but it never writes
the plan directly.

## Scope

The feature applies to a project progress meeting after the user supplies a
meeting transcript or a transcription generated from an audio recording.

The Agent may propose these actions:

- Create a workstream.
- Update an existing workstream.
- Create a subtask under an existing workstream.
- Update an existing subtask.

Each proposal may change only the fields supported by its target:

- Workstream: title, owner, coordinator, collaborators, plan time, status,
  expected achievement, and completion standard.
- Subtask: title, assignee, plan time, completion criteria, status, and notes.

Meeting summaries, speaker reports, decision requests, and risk items remain
part of the saved meeting record. They do not automatically change the work
progress plan.

## Source Of Truth And Input

The analysis request receives the meeting transcript and a project ID. The
server builds an immutable plan snapshot before calling the Agent. The snapshot
contains the current workstreams and subtasks, including their IDs and fields
needed for comparison.

The transcript is the only source of meeting facts. The snapshot provides
identity, ownership, and validation context; it must not be used to invent an
unspoken meeting decision.

## Unified Agent Result

The response contains a meeting record and `change_set` items. A change item
uses this shape conceptually:

```json
{
  "action": "create_workstream | update_workstream | create_subtask | update_subtask",
  "target": {
    "project_id": 1,
    "workstream_id": 12,
    "subtask_id": 34
  },
  "before": {},
  "proposed": {},
  "evidence": ["verbatim transcript excerpt"],
  "reason": "why this proposal follows from the meeting",
  "confidence": 0.0,
  "validation": {
    "state": "ready | needs_review | blocked",
    "errors": []
  }
}
```

`before` is server-populated from the frozen snapshot. `proposed` contains
only the fields that are changing or that are required for a creation. Every
item requires at least one non-empty evidence excerpt and a reason.

## Validation And Safety

The server validates every item after the Agent response and before presenting
it for execution.

- Update proposals must reference an ID present in the frozen snapshot.
- A created subtask must reference an existing workstream in that snapshot.
- A created workstream must have a non-empty title.
- A created subtask must have a non-empty title and parent workstream.
- Items with unknown ownership, an ambiguous target, missing required fields,
  invalid IDs, or no evidence are `blocked` and cannot be selected for
  execution.
- `needs_review` items remain editable by a human but are not selected by
  default.
- All change items are unselected by default, including `ready` items.

The execution endpoint revalidates the selected items against the current
project state and the original frozen snapshot. It rejects any item the current
user is not authorized to change.

## Review Experience

The meeting review page shows the ordinary meeting record first. Below it, the
change set is grouped by workstream and presented as a diff:

- Action and target.
- Before values and proposed values.
- Evidence excerpts and Agent reasoning.
- Validation state and errors.
- A per-item checkbox that starts unchecked.

Blocked items display the information needed for a human to complete or correct
them, but have no executable checkbox. The user may edit a non-blocked proposal
before selecting it. The UI executes only the selected items after an explicit
confirmation action.

## Persistence And Audit

Saving the meeting persists the meeting record and the full change set, but does
not mutate the work plan. Executing selected items creates an audit record with
the meeting ID, change-set item ID, actor, timestamp, before values, proposed
values, and evidence. The resulting workstream or subtask keeps a reference to
the audit item so the plan can show why it changed.

The previous `generate-task-cards` second Agent call is removed from this flow.
It is the source of interpretation drift and is not needed once the meeting
analysis produces a typed change set.

## Out Of Scope

- Automatic execution without human review.
- Deletion of workstreams or subtasks from a meeting.
- Automatic creation of issues, achievements, or decisions from a change item.
- Changing unrelated project configuration or permissions.

## Acceptance Criteria

1. A single meeting analysis response contains both the meeting draft and a
   structured change set.
2. A meeting analysis does not modify workstreams or subtasks.
3. Every executable proposal has a valid target, required creation fields,
   evidence, and a reason.
4. Every proposal is unselected initially.
5. Only selected, valid, authorized proposals change the work progress plan.
6. Each executed change remains traceable to its meeting and evidence.
7. A meeting no longer invokes a second LLM call when pushing changes to the
   work progress plan.
