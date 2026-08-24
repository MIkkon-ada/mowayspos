# Key Task Workspace Scroll Design

## Goal

Allow every section of the shared key-task execution workspace to be reached by vertical scrolling when it is opened from the work-progress page.

## Root cause

`ProjectLayout` fixes the application frame to the viewport and hides overflow. `TaskManagementPage` preserves that constraint while the shared `KeyTaskExecutionWorkspace` renders a `min-h-full` main element without a scroll container. When workspace content exceeds the viewport, it is clipped instead of scrollable.

## Chosen design

The shared workspace main element becomes the single vertical scroll container when embedded in a constrained application frame. It receives flex sizing (`flex-1 min-h-0`) and `overflow-y-auto`; its existing responsive padding and mobile bottom-navigation clearance remain unchanged.

## Scope

- Change only `KeyTaskExecutionWorkspace.tsx`.
- Add a source-level regression assertion for the scroll-container contract.
- Verify at desktop and 375px mobile viewports that scrolling reaches content below the initial viewport.

## Out of scope

- No redesign of detail cards, data, actions, or page layout.
- No changes to the work-progress list views or application shell.
