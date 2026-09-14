# Project Init AI Response Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make project-init AI extraction recover from valid-but-noncanonical model output, retry once with a targeted repair prompt, use configured fallback models, and expose the exact failure mode before deterministic fallback.

**Architecture:** Keep the existing evidence-bound Pydantic contract as the final authority. Add a focused response-normalization module before validation, move project-init recovery orchestration into an AI-service method that returns validated chat results or structured failure details, and persist only sanitized recovery metadata in the existing project-init result metadata. Update the owner-submit panel to distinguish AI success, repaired AI success, schema failure, and transport failure.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Pydantic, pytest, React, TypeScript, Vitest.

---

## Scope and file map

Files to create:

- `bowei_ai_dashboard/app/services/project_init_ai_response.py` — JSON extraction, approved field aliases, safe defaults, validation diagnostics, and repair-prompt construction.
- `bowei_ai_dashboard/tests/test_project_init_ai_response.py` — pure response normalization and diagnostic tests.

Files to modify:

- `bowei_ai_dashboard/app/ai/contracts.py` — carry ephemeral validation details between the AI service and project-init pipeline without persisting raw model output.
- `bowei_ai_dashboard/app/ai/service.py` — add project-init recovery invocation while preserving existing behavior for other capabilities.
- `bowei_ai_dashboard/app/services/project_init_ai_pipeline.py` — use the response recovery service and keep evidence validation strict.
- `bowei_ai_dashboard/app/services/project_init_analysis.py` — add sanitized recovery fields to `result_metadata` and map final processing mode accurately.
- `bowei_ai_dashboard/app/services/project_init_ai_agent.py` — re-export response helpers for existing compatibility imports.
- `bowei_ai_dashboard/tests/test_project_init_ai_agent.py` — test AI draft recovery and fallback behavior through the existing facade.
- `bowei_ai_dashboard/tests/test_project_init_analysis.py` — test persisted recovery metadata and final mode.
- `bowei_ai_dashboard/app/routers/ai_config.py` — add a project-init capability probe distinct from the existing `ping` test.
- `bowei_ai_dashboard/app/schemas.py` — add the typed request/response schema for the capability probe if the router currently uses untyped dictionaries.
- `frontend/src/api/projectInitAi.ts` — type and decode recovery metadata fields.
- `frontend/src/features/settings/OwnerSubmitAiPanel.tsx` — render precise mode and failure messages.
- `frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx` — verify the new notices and retry state.
- `frontend/src/features/settings/AIConfigurationSection.tsx` — expose project-init capability status beside model connectivity when the settings UI already renders capability diagnostics.
- `frontend/src/features/settings/AIConfigurationSection.test.tsx` — test the separate connectivity and project-init capability states.

No database migration is planned. Existing `ai_invocation_logs.error_code` records the sanitized attempt error, while `project_init_analysis_runs.result_json` already carries `result_metadata` and will receive the new bounded fields.

## Task 1: Add failing focused tests for response recovery

**Files:**

- Create: `bowei_ai_dashboard/tests/test_project_init_ai_response.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`

- [ ] **Step 1: Add one focused test for JSON extraction and approved aliases**

Add one test covering Markdown 包裹、可选字段补全和 `deadline` 到 `plan_end` 的兼容映射：

```python
def test_normalize_wrapped_json_aliases_and_defaults():
    raw = "```json\n{\"project_profile\": {\"name\": \"示例\", \"evidence\": [{\"file_name\": \"a.xlsx\", \"location\": \"Sheet1!A1\"}]}, \"tasks\": [{\"title\": \"任务一\", \"subtasks\": [{\"title\": \"子任务一\"}]}]}\n```"

    payload, diagnostics = normalize_project_init_response(raw)

    assert diagnostics == []
    assert payload["project_profile"]["name"] == "示例"
    assert payload["tasks"][0]["plan_start"] == ""
    assert payload["tasks"][0]["subtasks"][0]["assignee_name"] == ""
    assert payload["tasks"][0]["plan_end"] == "2026-09-30"
```

- [ ] **Step 2: Add one test for safe diagnostics**

Cover one malformed/schema-invalid response with a missing subtask and a forbidden source field. Assert that diagnostics contain only bounded paths and error types; assert that the raw response text and any secret-like string are absent from the diagnostic payload.

- [ ] **Step 3: Run the new tests before implementation**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_project_init_ai_response.py -q
```

Expected: FAIL because the response module and recovery functions do not exist yet.

- [ ] **Step 4: Commit only the test files**

```powershell
git add -- bowei_ai_dashboard/tests/test_project_init_ai_response.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py
git commit -m "test: define project init ai response recovery"
```

## Task 2: Implement the response normalizer and diagnostics

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_init_ai_response.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_ai_response.py`

- [ ] **Step 1: Define the bounded diagnostic types**

Implement a frozen diagnostic value with these fields and limits:

```python
@dataclass(frozen=True)
class DraftResponseDiagnostic:
    code: str
    paths: tuple[dict[str, str], ...] = ()
    normalized: bool = False
```

Allowed codes are `json_missing_or_multiple`, `json_malformed`, `schema_invalid`, `evidence_invalid`, and `empty_result`. Never include raw response text in this type.

- [ ] **Step 2: Implement `normalize_project_init_response`**

Give it this public signature:

```python
def normalize_project_init_response(raw: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    ...
```

It must extract one JSON object, remove only an outer Markdown code fence or surrounding explanation, map the approved aliases `deadline`, `startDate`, and `endDate`, fill optional string/list fields with contract defaults, and return bounded validation diagnostics. It must not generate titles, people, dates, evidence, or IDs.

- [ ] **Step 3: Implement `build_repair_prompt`**

Use this signature:

```python
def build_project_init_repair_prompt(
    original_prompt: str,
    diagnostics: list[dict[str, str]],
) -> str:
    ...
```

The prompt must request exactly one JSON object, list the failing paths, preserve the original task/person/date/evidence facts, and tell the model to use an empty string when a source field is genuinely absent. Do not put API credentials or hidden server configuration into the prompt.

- [ ] **Step 4: Re-export compatibility helpers**

Re-export the new public functions from `project_init_ai_agent.py` so existing imports remain stable. Keep `_classify_raw_draft_envelope` as a compatibility wrapper over the new diagnostic classifier.

- [ ] **Step 5: Run pure response tests**

```powershell
python -m pytest tests/test_project_init_ai_response.py tests/test_project_init_ai_agent.py -q
```

Expected: PASS for normalization tests and the existing classifier tests.

- [ ] **Step 6: Commit the response layer**

```powershell
git add -- bowei_ai_dashboard/app/services/project_init_ai_response.py bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_ai_response.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py
git commit -m "feat: normalize project init ai responses"
```

## Task 3: Add AI-service recovery invocation

**Files:**

- Modify: `bowei_ai_dashboard/app/ai/contracts.py`
- Modify: `bowei_ai_dashboard/app/ai/service.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`

- [ ] **Step 1: Add an ephemeral validation error type**

Define a subclass of `AIUpstreamError` that carries `validation_code`, bounded `diagnostics`, and the last raw response only in memory. Its string representation and persisted error code must contain only the safe code. The raw response must never be inserted into `AIInvocationLog` or exception text.

- [ ] **Step 2: Add `invoke_project_init_chat`**

Implement this method on `AIService`:

```python
def invoke_project_init_chat(
    self,
    prompt: str,
    context: AIInvocationContext | None,
    *,
    validator: Callable[[str], tuple[bool, list[dict[str, str]]]],
    repair_prompt_factory: Callable[[list[dict[str, str]]], str],
) -> ChatResult:
    ...
```

The method must:

1. Load the enabled `project.init.analysis` policy and candidates using the existing `_candidates` method.
2. Invoke each candidate at most once with JSON response format.
3. Validate the raw text without discarding it in memory.
4. On validation failure, invoke one repair prompt for the same model and validate it once.
5. On success, return `ChatResult` and a successful invocation log.
6. On retryable transport or validation failure, commit a sanitized failed log and continue to the next configured candidate.
7. Raise the final safe AI error only after candidates are exhausted.

The method must preserve existing `invoke_chat` semantics for meeting analysis, task extraction, speech, and task-plan proposal.

- [ ] **Step 3: Add recovery tests with fake adapters**

Add four focused cases: primary valid; primary invalid then repair valid; primary invalid then fallback valid; all candidates invalid and deterministic fallback. Assert attempt order, `fallback_used`, safe error codes, and absence of raw model content in the database log.

- [ ] **Step 4: Run AI-service tests**

```powershell
python -m pytest tests/test_project_init_ai_agent.py -q
```

Expected: PASS, including the new recovery cases.

- [ ] **Step 5: Commit the service recovery layer**

```powershell
git add -- bowei_ai_dashboard/app/ai/contracts.py bowei_ai_dashboard/app/ai/service.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py
git commit -m "feat: recover project init ai responses"
```

## Task 4: Integrate recovery into project-init processing

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_init_ai_pipeline.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_analysis.py`

- [ ] **Step 1: Replace direct validated invocation in the pipeline**

Change the project-init caller to use `AIService.invoke_project_init_chat`, passing the existing `_context_prompt`, the new response normalizer/validator, and a repair prompt factory that reuses the current batch prompt. Keep `_validate_batch_sources` and `_repair_batch_evidence` after AI recovery; response recovery must not bypass evidence checks.

- [ ] **Step 2: Preserve deterministic fallback as the final branch**

Only return `structured-spreadsheet-fallback` after the primary model and configured fallback models have exhausted their original and repair attempts. Keep `provider="local-rule"`, `model_name="structured-spreadsheet-fallback"`, and `processing_mode="deterministic_fallback"` for the final fallback result.

- [ ] **Step 3: Add sanitized recovery metadata**

Extend the result metadata produced by `_result_metadata` with:

```python
{
    "ai_recovery_attempted": bool,
    "ai_recovery_succeeded": bool,
    "ai_failure_stage": "" | "transport" | "json" | "schema" | "evidence",
    "ai_failure_code": "",
}
```

Use empty strings and `False` for historical runs where no recovery metadata exists. Never persist raw prompts or responses.

- [ ] **Step 4: Add worker tests**

Extend `test_project_init_analysis.py` with two focused assertions:

- repaired AI output stores `processing_mode="ai"` and `ai_recovery_succeeded=True`;
- schema failure after all attempts stores `processing_mode="deterministic_fallback"`, `ai_failure_code="schema_invalid"`, and no raw response.

- [ ] **Step 5: Run backend project-init tests**

```powershell
python -m pytest tests/test_project_init_ai_response.py tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py -q
```

Expected: PASS with no changes to project apply/writeback behavior.

- [ ] **Step 6: Commit pipeline integration**

```powershell
git add -- bowei_ai_dashboard/app/services/project_init_ai_pipeline.py bowei_ai_dashboard/app/services/project_init_analysis.py bowei_ai_dashboard/tests/test_project_init_analysis.py
git commit -m "feat: integrate project init ai recovery metadata"
```

## Task 5: Configure and probe the project-init AI capability

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/ai_config.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/tests/test_ai_config_api.py`

- [ ] **Step 1: Add a project-init capability probe contract**

Add an endpoint or explicit mode to the existing model test that sends a minimal project-init sample through the same JSON response format and response validator. Return:

```json
{
  "ok": true,
  "connection_ok": true,
  "project_init_output_ok": true,
  "code": "",
  "message": "项目立项结构输出正常"
}
```

For a connection-only success, set `connection_ok=true` and `project_init_output_ok=false` only when the capability probe was requested and failed.

- [ ] **Step 2: Add one route test to the existing AI config API test module**

Use a fake adapter in `tests/test_ai_config_api.py` to verify the new capability probe validates the project-init envelope. The legacy `ping` behavior remains covered by its existing test.

- [ ] **Step 3: Validate current model settings without exposing credentials**

Run a read-only local probe against model id 1 using the configured credential through the backend service. Do not print or persist the key. Record the model name, response code, and sanitized validation result only.

- [ ] **Step 4: Commit capability probe changes**

```powershell
git add -- bowei_ai_dashboard/app/routers/ai_config.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/tests/test_ai_config_api.py
git commit -m "feat: probe project init ai capability"
```

## Task 6: Configure a verified fallback model policy

**Files:**

- Modify: `bowei_ai_dashboard/app/ai/repository.py` only if policy validation needs a recovery-specific setting.
- Modify: `frontend/src/features/settings/AIConfigurationSection.tsx` if the UI needs to show the fallback model.
- Modify: `frontend/src/features/settings/AIConfigurationSection.test.tsx`.
- Test: backend AI policy tests already covering `AICapabilityPolicy`.

- [ ] **Step 1: Do not hard-code a provider or secret**

Use the existing policy API to set a fallback model only after that model passes the project-init capability probe. The policy must keep the primary model first and cap `max_attempts` at the number of configured candidates.

- [ ] **Step 2: Reject an unverified fallback in the UI**

Show the fallback model’s capability status and prevent saving a project-init policy that references a disabled, wrong-type, credential-less, or unprobed model. Keep credentials encrypted and never include them in status responses.

- [ ] **Step 3: Manually verify policy save behavior**

Verify through the existing local settings flow that an enabled project-init policy with one valid primary and one valid fallback saves, while a fallback with missing credential or failed capability probe is rejected with a safe Chinese error message.

- [ ] **Step 4: Commit policy/UI changes**

```powershell
git add -- bowei_ai_dashboard/app/ai/repository.py frontend/src/features/settings/AIConfigurationSection.tsx frontend/src/features/settings/AIConfigurationSection.test.tsx
git commit -m "feat: validate project init ai fallback policy"
```

## Task 7: Update owner-submit API types and notices

**Files:**

- Modify: `frontend/src/api/projectInitAi.ts`
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx`

- [ ] **Step 1: Add typed recovery metadata**

Decode these optional fields from `run.result_metadata` with safe defaults:

```ts
type AiRecoveryMetadata = {
  ai_recovery_attempted?: boolean
  ai_recovery_succeeded?: boolean
  ai_failure_stage?: '' | 'transport' | 'json' | 'schema' | 'evidence'
  ai_failure_code?: string
}
```

- [ ] **Step 2: Replace the generic fallback notice**

Implement this decision table in `analysisModeNotice`:

```ts
if (mode === 'ai' && recovered) return 'AI 已参与分析，系统已自动整理返回格式，请重点核对关键字段。'
if (mode === 'ai') return 'AI 已参与分析，结果仅供核对，确认后再写入。'
if (failureStage === 'schema' || failureCode === 'schema_invalid') {
  return 'AI 已返回结果，但结构校验未通过，已切换为规则提取，请重点核对关键字段。'
}
if (failureStage === 'transport') {
  return 'AI 服务暂时不可用，已切换为规则提取，请稍后重试 AI 分析。'
}
if (mode === 'deterministic_fallback') return '本次使用规则提取，请重点核对关键字段。'
return ''
```

- [ ] **Step 3: Add a compact analysis-details line**

Show model, attempt path, recovery status, and sanitized failure code in the existing model usage summary. Do not render raw AI output.

- [ ] **Step 4: Test all notice branches**

Add tests for AI success, repaired AI success, schema fallback, transport fallback, and historical fallback with missing metadata.

- [ ] **Step 5: Run the two focused frontend tests and build**

From `frontend`:

```powershell
npm run test:unit -- src/features/settings/OwnerSubmitAiPanel.retry.test.tsx src/features/settings/AIConfigurationSection.test.tsx
npm run build
```

Expected: PASS with TypeScript compilation and no changed API contract failures.

- [ ] **Step 6: Commit frontend recovery notices**

```powershell
git add -- frontend/src/api/projectInitAi.ts frontend/src/features/settings/OwnerSubmitAiPanel.tsx frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx frontend/src/features/settings/AIConfigurationSection.tsx frontend/src/features/settings/AIConfigurationSection.test.tsx
git commit -m "feat: explain project init ai recovery status"
```

## Task 8: Run full verification and real-file acceptance

**Files:**

- Modify only if verification finds a regression in the files listed above.
- Test: existing backend and frontend suites.

- [ ] **Step 1: Run focused backend suite**

```powershell
python -m pytest tests/test_project_init_ai_response.py tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py -q
```

Expected: PASS.

- [ ] **Step 2: Do not run the full backend suite in this pass**

The focused suite from Step 1 is the backend verification boundary for this fix. Existing unrelated backend tests are not rerun unless a focused change exposes a regression.

- [ ] **Step 3: Run the required frontend build only**

```powershell
npm run build
```

Expected: PASS.

- [ ] **Step 4: Re-run the provided Excel file through the local UI**

Upload `第三阶段五项工作的简要方案_v0.2.xlsx` through the normal project-init import flow. Confirm the backend run metadata and UI notice agree:

- AI success or repaired AI success: provider is not `local-rule` and the notice says AI participated.
- Final fallback: provider is `local-rule`, failure code is visible as a safe reason, and the notice explicitly says rule extraction.

- [ ] **Step 5: Inspect the database for secret leakage**

Run a read-only query over the new invocation and run metadata, checking that API keys, full prompts, and full raw model responses are absent.

- [ ] **Step 6: Perform final diff review**

```powershell
git diff HEAD~8 --stat
git status --short
```

Confirm only the intended implementation files and tests are included in the implementation commits; preserve the user’s unrelated worktree changes.

- [ ] **Step 7: Commit the verification record if needed**

If a project verification note is added, commit only that note with:

```powershell
git add -- docs/superpowers/acceptance/2026-09-14-project-init-ai-response-recovery.md
git commit -m "docs: record project init ai recovery verification"
```

## Completion criteria

The implementation is complete only when all of the following are true:

- A valid AI response with harmless formatting differences reaches the AI preview.
- A recoverable schema failure performs exactly one repair attempt per model.
- A verified fallback model is used before deterministic extraction.
- Evidence validation remains strict and source-bound.
- The UI distinguishes connection failure from schema failure.
- Existing rule fallback and preview-only behavior are covered by the focused project-init tests; apply/writeback and permission tests are not rerun in this pass.
- The provided Excel file has been run through the normal local import flow and its final processing mode matches backend metadata.
