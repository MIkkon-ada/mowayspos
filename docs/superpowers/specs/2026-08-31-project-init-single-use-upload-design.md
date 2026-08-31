# Project-init single-use upload design

## Goal

Make AI document analysis a fresh, single-use upload flow: every new analysis requires the user to select and upload files again.

## User-visible behavior

- Opening the AI-from-file panel always shows the file picker and an inactive **开始分析** button.
- The panel does not load or display prior project-init attachments or the latest analysis run.
- A prior failed run therefore cannot automatically place the panel in an error state or hide the upload picker.
- After a run fails, completes, or partially completes, the user must use a reset action that clears the current queue and returns to the picker before another analysis. The next run uploads newly selected files and creates a new analysis run.
- Existing server-side attachments and analysis runs remain available for audit; the interactive panel does not reuse them.

## Architecture

Limit the change to `OwnerSubmitAiPanel`. Its initial-load effect retains no project-init history, initializes the panel as idle, and ignores `existingAttachments`. The retry and completed-preview actions reset local queue, attachment IDs, draft, run, and errors instead of calling the run retry endpoint or creating a run from stored attachment IDs.

No backend data is deleted and no API contract changes. The old attachment/list/latest/retry API functions may continue to support audit or other callers but are no longer used by this panel.

## Error handling

Upload errors remain attached only to files selected in the active session. A failed analysis reports its failure while the current run is visible; the recovery action clears it and requires a new file selection. The user is never shown an error merely because an old database record exists.

## Tests

The panel test will mock a failed historical run and historical attachment list, render the panel, then verify the picker remains visible, the failure message is absent, and the history APIs are not called. A second test will enter a terminal run state, invoke the fresh-analysis action, and verify the panel returns to the picker without calling the retry API or creating an analysis run from old attachment IDs.
