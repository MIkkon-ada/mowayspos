# Unified task execution detail design

## Goal

Both the work-progress table and execution-progress view must open the same new key-task execution workspace when a user selects a key task.

## Scope

- Re-enable the execution-progress view tab in `TaskManagementPage`.
- Route selection from both `PlanTableViewV2` and `ExecutionProgressView` through the existing `openSubDetail` and `focusSubTask` flow.
- Show `KeyTaskExecutionDetailView`, which wraps the new shared `KeyTaskExecutionWorkspace`, after a key task is selected.
- Preserve the workspace back action so users return to the list and current view.

## Exclusions

- The table and execution-progress list layouts are not redesigned in this change.
- The shared workspace itself, its permissions, and its data API are not rewritten.
- The legacy side panel may remain for unrelated management selections, but key-task detail entries from these two views no longer use it.

## Data and access

The existing selection loads the key-task detail before rendering the workspace. The workspace continues to receive the selected key-task ID and resolved project ID, retaining its current data loading and permission behavior.

## Verification

- A structural regression test confirms the execution tab is enabled and selection switches to the shared detail workspace.
- At 375px, selection from the mobile table list opens the shared workspace with bottom-navigation spacing.
- Targeted tests and the production build pass.
