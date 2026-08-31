# AI capability policy visibility design

## Goal

Let a technical administrator see and configure every supported AI capability even when no policy rows exist in the database.

## User-visible behavior

- The AI capability strategy section always shows `meeting.analysis`, `task.extraction`, `project.init.analysis`, and `speech.realtime`.
- A capability without a saved policy is visibly marked `未配置` and offers eligible enabled models for selection.
- Selecting a model and saving creates an enabled policy through the existing policy endpoint; the first selected model is the primary model and later selections are fallbacks.
- Existing saved policies retain their current timeout, attempt count, enabled state, model order, and model-type filtering.
- The page never automatically assigns or enables a model for any capability.

## Architecture

Define the supported capability metadata in the AI configuration UI and merge it with the API's saved policy list. Unsaved descriptors provide the default chat/ASR model type and conservative policy defaults only for the save request. The existing backend `PUT /api/ai-config/policies/{capability_key}` already validates models and creates a missing policy row, so no persistence contract changes are required.

## Error handling and tests

An empty policies response must render all four capability keys and expose `meeting.analysis` as unconfigured. Saving an unsaved `meeting.analysis` with an eligible selected model must send it as the primary model. Existing model-type filtering remains: chat capabilities exclude ASR models and `speech.realtime` excludes chat models.
