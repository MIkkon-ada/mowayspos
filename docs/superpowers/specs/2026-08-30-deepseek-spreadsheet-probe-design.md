# DeepSeek Spreadsheet Understanding Probe Design

## Goal

Provide a standalone, opt-in diagnostic that compares two DeepSeek-compatible
ways of understanding an uploaded Excel work-progress sheet without changing
the project-init import flow, its saved draft, model policy, or stored
credentials:

1. **Probe A (text-structure)** sends a cited, loss-aware representation of
   the workbook to `deepseek-v4-flash` and `deepseek-v4-pro`.
2. **Probe B (visual-layout)** sends rendered worksheet images and the same
   cited representation to `deepseek-v4-flash-vision-exp`.

The probe will report whether each model can reconstruct the requested
three-level hierarchy and per-key-task fields, especially collaborator names
that may be embedded in non-standard columns or prose. It is a diagnostic
tool, not a production parser replacement.

## Constraints and Evidence

- The existing DeepSeek adapter is OpenAI-chat compatible and only accepts a
  text prompt. It reads a configured encrypted credential internally.
- The local configuration has an enabled `deepseek-v4-pro` model and a usable
  encrypted DeepSeek credential. There is no separately configured
  `deepseek-v4-flash` model. Probe A may therefore use the configured model
  only as an in-memory credential source, never persist a new model, and send
  the official target name per invocation.
- DeepSeek's Files API documents image-only upload formats. `deepseek-v4-flash`
  and `deepseek-v4-pro` therefore cannot receive an `.xlsx` attachment as a
  raw file. Probe A is intentionally a structured-text test. Probe B uses the
  documented experimental vision model with PNG sheet images; it is the
  closest supported test of layout comprehension, not raw Excel-file input.
- Existing production import code must remain untouched. Test results and
  prompts must not be saved to the application database; invocation logging is
  allowed only when it contains the existing safe metadata (model, status,
  duration, error category) and no source cells or key material.

## Interfaces

Add a command-line script:

```text
bowei_ai_dashboard/scripts/probe_deepseek_spreadsheet.py
```

Example invocation:

```text
python scripts/probe_deepseek_spreadsheet.py \
  --input C:\\path\\工作推进表.xlsx \
  --mode all \
  --output-dir tmp/deepseek-probe
```

The script has no API-key command-line argument, no configuration write mode,
and no implicit execution. It loads the project environment and database,
selects an enabled DeepSeek chat configuration with an encrypted credential,
and decrypts it inside the existing service boundary. It prints neither the
credential, Authorization headers, raw prompt, nor raw provider response.

The probe accepts:

- `--mode a`, `--mode b`, or `--mode all` (default `all`),
- `--input` for a local `.xlsx` file,
- `--output-dir` for local, gitignored evidence and summary artifacts,
- `--max-sheets` / `--max-cells` safety limits, and
- `--dry-run` to validate parsing, rendering availability, credential
  eligibility, and planned model calls without an external request.

## Workbook Representation

### Shared evidence map

The script uses the existing project workbook parser for the canonical textual
evidence, retaining `file_name`, sheet name, and cell-range location. It also
loads the workbook read-only to construct a compact map of:

- non-empty cells with A1 coordinates and displayed values;
- merged-cell ranges and their anchor values;
- hidden-sheet/row/column flags when available; and
- selected row/column headers.

Values are truncated per cell and globally bounded. The manifest records
counts and SHA-256 digests, not source contents, in the terminal summary.
Local output can retain the generated prompt/evidence only under the requested
output directory for user inspection; it is ignored by git and is never
inserted into application tables.

### Probe A: `v4-flash` then `v4-pro`

Each text model receives the same bounded source representation and a strict
JSON request. It must return:

```json
{
  "workstreams": [
    {
      "title": "专项 / 重点工作",
      "key_tasks": [
        {
          "title": "关键任务",
          "owner": "",
          "collaborators": [],
          "plan_start": "",
          "plan_end": "",
          "completion_standard": "",
          "note": "",
          "evidence": ["Sheet1!A2:F2"]
        }
      ]
    }
  ]
}
```

The prompt explicitly says that collaboration names found in fields such as
`协同成员`, `协助人`, `参与人`, or a note like `协助人：张三、李四` belong in
`collaborators`; the remaining note excludes that duplicate roster. Empty,
unknown, or ambiguous values must be reported in `note` rather than invented.
The script parses JSON strictly, checks all cited evidence locations against
the manifest, and reports each model as `succeeded`, `invalid_json`,
`invalid_schema`, `uncited_output`, `upstream_error`, or `skipped`.

`deepseek-v4-flash` is invoked using the configured DeepSeek endpoint and
credential but only an in-memory model-name override. `deepseek-v4-pro` uses
the same safe path. If the provider denies a model, the result is reported as
an expected per-model failure; no configuration is changed.

### Probe B: visual layout

Before this route, render selected sheets to PNG, preferring a locally
available office renderer so merged cells, column widths, wrapping, and
formatting resemble the source workbook. If that renderer is unavailable, the
probe reports `skipped: renderer_unavailable`; it must not silently replace a
visual test with the text route.

Upload only the generated PNGs through DeepSeek's documented file endpoint
with purpose `user_data`, then call `deepseek-v4-flash-vision-exp` with the
file IDs plus the compact evidence map. Images are treated as external source
data: the command prints the number and sizes only, and local temporary images
and file IDs are deleted/forgotten after the request where supported. The same
JSON contract and evidence checks as Probe A apply.

## Result Artifact

The output directory receives a single `summary.json` containing:

- run timestamp and local input digest;
- per-mode, per-model status and elapsed milliseconds;
- model-owned structured output only after schema/evidence validation;
- quality counters: workstreams, key tasks, owners, collaborator fields,
  date fields, completion standards, and uncited/ambiguous items; and
- a capability note distinguishing structured-text and visual-layout results.

It never contains a credential, request headers, provider file IDs, or raw
unvalidated response. A concise terminal table gives model, mode, status,
quality counters, and the path to the local summary.

## Test Strategy

Unit tests will use mocked adapters and temporary workbooks. They prove that:

1. the canonical text evidence carries cell and merge-range citations;
2. collaborator prose is requested and normalized without duplicating it in
   notes;
3. the configured credential is read only within the service boundary and is
   never included in output;
4. `v4-flash` and `v4-pro` target names are attempted independently without a
   database write;
5. invalid JSON, unsupported model, and unsupported cited locations yield safe
   result statuses; and
6. Probe B is explicitly skipped when PNG rendering or the vision capability
   is unavailable, rather than masquerading as Probe A.

An opt-in manual smoke run against the user's sample workbook will execute A
then B and preserve only the sanitized result artifact in `tmp/`.

## Non-goals

- Changing the production project-init model policy or import parser.
- Adding any API-key UI, plaintext key storage, or logging of source content.
- Claiming that rendered images are identical to direct `.xlsx` attachment
  support.
- Auto-creating people or modifying project members from diagnostic output.
