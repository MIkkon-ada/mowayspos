# Project Standard Display Design

## Goal

Keep the work-progress table view consistent with the execution-detail view: show the project-level standard entry point only when the selected project has a non-empty `objectives` value.

## Scope

- Preserve each key work item's existing `completion_standard` display and modal.
- Do not change project data, API contracts, database schema, or migration files.
- Do not aggregate key-work standards into a project-level standard.

## Behavior

`PlanTableViewV2` computes whether the selected project has a trimmed non-empty `objectives` value. When true, it renders the top-level project-standard button that opens `ProjectStandardModal`. When false, it renders no project-standard button. The create-key-work button remains unchanged.

## Verification

The frontend structure test will assert that the button rendering is guarded by the same project-objectives condition used by `ProjectStandardModal`. The full frontend test suite and production build must pass.
