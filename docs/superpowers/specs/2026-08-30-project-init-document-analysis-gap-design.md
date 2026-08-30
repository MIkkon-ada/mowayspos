# Project-Initialization Document Analysis Gap Design

## Goal

Make project-initialization analysis reliable for both ordinary and complex
documents without treating a text-only model as if it had understood the
original spreadsheet layout. The system must retain the raw input, identify
when a spreadsheet's layout is too complex for text extraction alone, route
only to capabilities the configured model genuinely supports, and leave a
traceable review signal when automatic understanding is uncertain.

## Current Gaps

1. Project-init attachment storage defaults to `/app/data/project-init-attachments`.
   That is a container path, so the local Windows runtime can retain an
   attachment database record while the physical source file cannot later be
   reopened for retry, download, or a file-capable model.
2. The current `project.init.analysis` capability is a text chat capability.
   `.xlsx` data is converted into `SourceChunk` text before model invocation;
   there is no contract for a provider to receive an original file.
3. Analysis has no explicit complexity assessment. A heavily merged, hidden,
   sparse, or multi-sheet workbook looks like any other parsed text input, so
   the current flow cannot distinguish a safe text route from a layout-risky
   route.
4. Reviewers cannot see whether a result came from structured text, genuine
   file understanding, or a safe fallback.

## Design

### 1. Durable attachment root

Create one shared `project_init_attachment_root()` setting. If
`PROJECT_INIT_ATTACHMENT_ROOT` is set, use its resolved absolute path. If it
is absent, use `<backend-root>/data/project-init-attachments`, not `/app/...`.
The upload router, downloader, cleanup flow, project deletion cleanup, and
background analysis worker use this single resolver. Existing missing files
remain unavailable and are reported honestly; the change guarantees durable
retention for every future upload.

### 2. Spreadsheet complexity profile

For `.xlsx` uploads, inspect the workbook read-only after existing archive and
size validation. Produce a bounded, serializable profile:

- visible/hidden worksheet counts;
- non-empty cell count;
- merged-range count;
- formula-cell count;
- count of rows with sparse or repeated headings; and
- `layout_risk` of `low`, `medium`, or `high` plus named reasons.

High risk is triggered by signals that text extraction cannot faithfully
represent: many merged ranges, hidden structure, multiple non-empty sheets,
or a table whose populated rows do not share a stable header. The profile does
not store cell values, source text, or model output.

### 3. Truthful route selection

Introduce a pure route selector with these results:

```text
text_structured
file_understanding
text_with_review
```

- A low-risk workbook uses `text_structured` and the existing parser + AI
  workflow.
- A high-risk workbook uses `file_understanding` only if a configured document
  capability explicitly declares support for `.xlsx` input.
- If no such capability is configured, high-risk workbooks use
  `text_with_review`: existing parsing remains available, but the result gets
  a `layout_review_required` warning. It never claims original-layout
  understanding.

`deepseek-v4-flash` and `deepseek-v4-pro` are eligible only for the text
route. They are never selected for `file_understanding` because their official
API contract does not accept raw Excel files.

### 4. File-understanding capability boundary

Add a document model capability separate from chat and ASR. Its adapter
receives `Path`, original filename, MIME type, and a structured extraction
instruction; it returns only a text JSON envelope. The model configuration
must explicitly include `supported_input_extensions`, and the router only
chooses it for an extension it declares. Configuration without a provider or
credential leaves the capability unavailable, not silently routed to chat.

The first supported provider integration will be selected from a model/API
that documents raw `.xlsx` file input. It must upload only the retained
attachment, enforce the existing 25 MiB limit, omit raw prompts/responses and
file IDs from database logs, and clean temporary provider references when the
provider supports deletion.

### 5. Snapshot and review visibility

The immutable analysis snapshot records an attachment's metadata, complexity
profile, selected route, selected model capability, and fallback reason. The
run result exposes a safe `analysis_route`, `layout_risk`, and
`review_required` signal. It does not expose API keys, source cell values,
unvalidated model output, or remote file identifiers.

## Data Flow

```text
Upload raw file to durable root
        ↓
Validate type/archive and profile workbook complexity
        ↓
Create immutable run snapshot with route decision
        ↓
low risk → existing parser + text AI
high risk + document capability → original file model
high risk + no document capability → parser + visible review requirement
        ↓
Evidence validation, person reconciliation, reviewer confirmation
```

## Safety and Non-goals

- No existing attachment is deleted or migrated automatically.
- No API key is added to source code, output, or logs.
- No complex workbook is silently downgraded while being labeled as
  file-understood.
- The first increment supplies durable storage, profiling, route decision,
  snapshot metadata, and review signals. A live raw-file provider requires a
  separately configured provider credential and is only enabled after its
  adapter contract and integration tests are in place.

## Verification

Tests will prove that:

1. absent environment configuration resolves to the local durable root;
2. upload, download, cleanup, and worker resolve the same root;
3. low- and high-risk workbooks produce deterministic profiles without
   recording source values;
4. high-risk workbooks cannot choose a text-only model as a file route;
5. a missing document capability produces `text_with_review` plus a review
   signal; and
6. snapshots preserve route/profile metadata while retaining existing draft
   generation behavior for normal workbooks.
