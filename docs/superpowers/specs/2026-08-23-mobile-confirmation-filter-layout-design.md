# Mobile confirmation filter layout design

## Goal

Make the Enterprise WeChat mobile confirmation header usable at 375px without truncating filters or introducing horizontal overflow.

## Considered approaches

1. Keep all controls in one horizontally scrollable row. This preserves every control but hides context and makes common filters hard to discover.
2. Wrap every control over several rows. This keeps them visible but pushes confirmation content too far below the fold.
3. Keep the project selector and a single filter trigger in the header; place submitter, status, and keyword search in an on-demand panel. This keeps the primary context visible while making all existing filters available. **Selected.**

## Mobile layout

- The header uses two rows below 800px: the title first, then the project selector and `筛选` trigger.
- The trigger opens a compact panel containing submitter, status, keyword search, and a reset action.
- Desktop retains the existing one-row header and controls at 800px and above.

## Data and interaction

- Existing filter state (`filterProject`, `filterSubmitter`, `filterStatus`, `search`) remains the source of truth.
- The mobile controls update the same state, so filtering results behave identically to desktop.
- The panel is closed after reset and can be dismissed without changing filters.

## Verification

- A regression test asserts the mobile-only header and filter trigger exist alongside the unchanged desktop controls.
- At 375px, the document width remains 375px and no header control is clipped.
- Targeted mobile tests and the production build pass.
