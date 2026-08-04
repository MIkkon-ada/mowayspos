# Persistent LLM Configuration Design

## Goal

Keep administrator-managed LLM configuration across image updates while making an explicit front-end selection take precedence over the application default.

## Storage and security

Production configuration is stored in the host-mounted `/data/mowayspos/env/llm_configs.json` file, exposed to the backend as `/app/llm_configs.json`. The file stores each provider's enabled state, base URL, model and API key. API keys are never returned by the API; the UI receives only an `api_key_set` flag.

The deployment configuration must mount this exact host file without copying an image-owned replacement over it. Environment variables remain an operator override for API key, base URL and model.

## Provider selection precedence

1. A provider explicitly selected by a supported page or request, if enabled and usable.
2. The administrator-selected `default_provider` stored in the persistent configuration, if enabled and usable.
3. The legacy `LLM_PROVIDER` environment variable, if usable.
4. The first enabled provider with credentials, using the stable provider declaration order.

Environment values override credentials and endpoint/model values for their provider, but do not erase the persisted administrator choice.

## Administrator experience

The LLM settings page shows one default-provider selector plus provider cards. Administrators can save an API key in production; the key field stays blank after reload and is represented as “configured”. Existing enabled provider/model settings remain unchanged when a masked or empty key is submitted.

## Failure handling

An unavailable selection is skipped rather than causing a global failure. Callers receive the existing no-credential behavior only after every configured fallback is exhausted. Invalid providers are rejected at the API boundary.

## Verification

Automated tests cover production persistence, masked-key retention, default-provider validation, selection precedence and unavailable-provider fallback. A production-compose contract test verifies the persistent volume mount. Browser verification confirms the settings page can select and retain the default provider without exposing credentials.
