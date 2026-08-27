# DeepSeek Primary Project-Initialization Analysis Design

## Goal

Make DeepSeek the preferred chat model for project-initialization analysis, retain DashScope as a retryable fallback, and prevent harmless DeepSeek JSON variations from being rejected before a draft can be reviewed.

## Current Evidence

For project-initialization run 19, DashScope timed out after about 62 seconds. DeepSeek then returned a successful chat response after about 21 seconds. The response was valid JSON but failed strict draft validation because it included a redundant evidence `source_label`, used `null` for date fields, omitted required `subtasks`, and contained non-contract role labels. The prompt currently asks for `source_label` even though the `Evidence` schema forbids it.

## Model Policy

The active local `project.init.analysis` policy will use model 4 (`migrated-deepseek-chat`) as primary and model 2 (`migrated-dashscope-chat`) as its only fallback. It will allow two attempts. A new missing legacy policy created during migration will prefer DeepSeek when both migrated chat models are available, otherwise retain the existing deterministic first-available behavior.

## Output Contract

The extraction prompt will contain the exact allowed task, subtask, and evidence keys. It will require at least one subtask per task, require empty strings rather than `null` for optional string fields, and state that evidence uses only `attachment_id`, `file_name`, `location`, and `excerpt`. The prompt will no longer ask the model to emit `source_label`.

Before Pydantic validation, the server will normalize only presentation-equivalent values:

- Remove `source_label` from evidence objects because it is deterministically derived from `file_name` and `location`.
- Convert `null` to an empty string for optional string fields such as `plan_start` and `plan_end`.

The server will not invent subtasks, rewrite role labels into personnel assignments, accept unknown business fields, or relax evidence verification. A response that lacks a subtask or contains unsupported business data remains invalid and is safely rejected.

## Observability

When parsing or schema validation rejects a response, the background run will record a safe failure category such as `invalid_draft_schema` rather than only the generic public error. It will not persist model output, prompts, source text, secrets, or raw validation values. The UI may continue to show the generic public message while diagnostics remain safe for local operators.

## Tests

Tests will prove:

1. Prompt text and the `Evidence` schema no longer contradict each other.
2. Redundant evidence labels and null optional strings normalize successfully.
3. Missing subtasks and unknown business fields remain rejected.
4. Legacy policy generation chooses DeepSeek first when both migrated providers exist.
5. A recorded validation failure is categorized without storing raw response data.

