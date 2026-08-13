# OwnerSubmitModal Workbench Sizing Design

**Goal:** Make the owner-submit modal size itself to its content until it reaches a viewport-safe maximum, while retaining the existing header, main content, footer, and every business interaction.

## Scope

- Change only the workbench shell dimensions and its scrolling contract in `frontend/src/features/settings/OwnerSubmitModal.tsx`.
- Keep the existing overlay padding as the single source of horizontal safe spacing.
- Keep Header and Footer as non-scrolling flex children; Main is the only scrolling region when the content reaches the maximum height.

## Chosen layout

Use the simple, stable outer-padding approach:

- Overlay: retain `p-4 sm:p-5`.
- Shell: `w-full max-w-[1400px]`, `min-h-[640px]`, `max-h-[calc(100vh-48px)]`, `flex flex-col overflow-hidden`.
- Remove `h-[94vh]` completely.
- Main: retain `min-h-0 flex-1 overflow-x-hidden overflow-y-auto`.

`min-h-[640px]` is deliberately below the originally suggested 660px: it preserves a credible workbench footprint while avoiding the forced near-fullscreen canvas with the one-task scenario. With normal and large content, flex layout lets the shell grow naturally until the viewport-safe maximum; Main then scrolls within the shell.

## Non-goals

No project-summary, task-card, table, color, typography, picker, AI, audit, submit, data, API, backend, database, or expansion-state edits.

## Acceptance

- One-task content produces a mid-sized shell rather than a 94vh shell.
- Three-task content grows naturally.
- Six-to-eight tasks reaches `calc(100vh - 48px)` and only Main scrolls.
- At 1440x900, 1600x900, and 1920x1080, the viewport has visible outer spacing and no page-level horizontal scrolling.
