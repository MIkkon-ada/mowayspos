# OwnerSubmitModal Screenshot-Reference Design

## Goal

Use the user-approved screenshot as the visual reference for `OwnerSubmitModal` while preserving every existing data binding, picker, AI, audit, submit, permission, and lifecycle behavior.

## Scope

- Keep the single-column workbench and the existing three-item project summary.
- Render the summary as a horizontal display-oriented strip: project name, project period, and completion criteria use understated dividers and text-first presentation.
- Make an expanded task header scan as one compact work item: number, title, status chip, objective, task count, derived date range, collapse, and more actions.
- Retain the current six-column task table and its `AssigneePicker` / `HelperPicker`; add only presentational drag, calendar, and delete icons using inline SVG.
- Keep collapsed tasks read-only and compact, adding derived date-range presentation when dates exist.
- Preserve the top add action and weak full-width continuation action.

## Explicit Non-Goals

- No API, backend, database, payload, permission, lifecycle, AI, audit, Picker, submit, or expansion-state behavior changes.
- No third-party icon dependency or new application state.
- No mock data or database changes for visual acceptance.

## Acceptance

- The structural test protects display-summary, status/task-count/date-range affordances and the six-column editable table.
- Real Modal acceptance with one expanded and two collapsed tasks at 1440px, 1600px, and 1920px has no page-level horizontal overflow.
- Expanded and collapsed layouts retain their existing click, Picker, AI and submit paths.
