# Project-init invalid-draft failover

## Goal

When a model successfully returns a response for project-init analysis but that
response cannot satisfy the project-init draft contract, treat that attempt as
recoverable and try the next configured model.  A valid fallback response must
complete the run normally.

## Scope

This applies only to the `project.init.analysis` text-draft path.  It does not
change fallback semantics for meeting analysis, task extraction, ASR, or the
vision path.

## Design

The project-init agent will validate the model response before accepting the
model invocation as successful.  A response that cannot be parsed into the
strict draft envelope is reported to the shared capability invocation loop as
a retryable invalid-response failure.  The loop then records that model attempt
as failed and invokes the next eligible model in the existing policy order.

The output accepted from the selected model continues through the existing
evidence repair, source-traceability checks, merging, and review-only result
pipeline.  Existing local structured-spreadsheet fallbacks remain unchanged.

## Observability and failure behavior

Each rejected response receives a sanitized invalid-response error code in the
AI invocation log.  The succeeding fallback attempt is logged with
`fallback_used=true`.  If no configured model returns a valid envelope, the
existing safe project-init analysis failure state and UI message are preserved.

## Tests

Add a focused test using two configured project-init chat models: the first
returns a schema-invalid `evidence` value and the second returns a valid draft.
The test asserts a completed draft plus one failed primary invocation and one
successful fallback invocation.  Existing tests cover the unchanged all-failed
behavior.
