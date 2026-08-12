import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from './client'

export type AIModel = {
  id: number
  code: string
  display_name: string
  provider: string
  model_name: string
  model_type: 'chat' | 'asr'
  base_url: string
  config: Record<string, unknown>
  enabled: boolean
  source: string
  managed_by: string
  revision: number
  credential_configured: boolean
}

export type AIModelWrite = {
  code: string
  display_name: string
  provider: string
  model_name: string
  model_type: 'chat' | 'asr'
  base_url: string
  config: Record<string, unknown>
  enabled: boolean
  source: string
}

export type AICapabilityPolicy = {
  id: number
  capability_key: string
  primary_model_id: number | null
  fallback_model_ids: number[]
  timeout_seconds: number
  max_attempts: number
  policy_version: number
  enabled: boolean
}

export type AIPolicyWrite = Pick<
  AICapabilityPolicy,
  'primary_model_id' | 'fallback_model_ids' | 'timeout_seconds' | 'max_attempts' | 'enabled'
>

export function listAIModels(): Promise<AIModel[]> {
  return apiGet<AIModel[]>('/api/ai-config/models')
}

export function createAIModel(payload: AIModelWrite): Promise<AIModel> {
  return apiPost<AIModel>('/api/ai-config/models', payload)
}

export function updateAIModel(id: number, payload: Partial<AIModelWrite>): Promise<AIModel> {
  return apiPut<AIModel>(`/api/ai-config/models/${id}`, payload)
}

export function setAIModelEnabled(id: number, enabled: boolean): Promise<AIModel> {
  return apiPatch<AIModel>(`/api/ai-config/models/${id}/enabled`, { enabled })
}

export function replaceAIModelCredentials(id: number, apiKey: string): Promise<{ ok: boolean }> {
  return apiPut<{ ok: boolean }>(`/api/ai-config/models/${id}/credentials`, { api_key: apiKey })
}

export function clearAIModelCredential(id: number, field: 'api_key' | 'app_secret' = 'api_key'): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(`/api/ai-config/models/${id}/credentials/${field}`)
}

export function testAIModel(id: number, temporaryApiKey?: string): Promise<{ ok: boolean; message: string; code?: string }> {
  return apiPost<{ ok: boolean; message: string; code?: string }>(`/api/ai-config/models/${id}/test`, temporaryApiKey ? { temporary_api_key: temporaryApiKey } : {})
}

export function listAICapabilityPolicies(): Promise<AICapabilityPolicy[]> {
  return apiGet<AICapabilityPolicy[]>('/api/ai-config/policies')
}

export function saveAICapabilityPolicy(key: string, payload: AIPolicyWrite): Promise<AICapabilityPolicy> {
  return apiPut<AICapabilityPolicy>(`/api/ai-config/policies/${key}`, payload)
}
