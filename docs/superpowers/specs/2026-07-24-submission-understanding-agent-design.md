# Submission Understanding Agent Design

## Goal

Turn a user's complete work-report submission into task-level progress drafts by
combining the user's permitted task context with semantic understanding of the
whole submission.

## Decision

The model receives only the candidate tasks already resolved from the authenticated
user's project permissions. It must first decide how many real work items are in
the whole submission, then emit one report per task rather than one report per
sentence. Each report contains verbatim evidence fragments plus rewritten,
business-ready progress fields.

## Safety Boundary

The model may select only a `subtask_id` in the supplied candidate context.
Every evidence fragment must be a verbatim substring of the source submission.
The server validates those constraints but does not overwrite valid business
summaries with the original wording. Ambiguous ownership remains in the AI
confirmation flow.

## Behaviour

- Completion, plans, risks, and achievements for one task are emitted in a
  single task card, even when expressed in different clauses.
- Multiple mixed work items become multiple cards when their activity or output
  maps to different permitted tasks.
- The agent may rewrite field values into clear business language, provided the
  meaning is supported by the evidence.
- A single permitted candidate is selected for relevant reported work unless
  the model explicitly identifies it as unrelated.
