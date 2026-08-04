import { apiGet, apiPut } from './client'

export type LLMProviderConfig = {
  provider: string
  display_name: string
  default_base_url: string
  default_model: string
  api_key_set: boolean
  base_url: string
  model: string
  enabled: boolean
}

export type LLMConfigPayload = {
  api_key?: string
  base_url?: string
  model?: string
  enabled: boolean
}

export type LLMDefaultProvider = { provider: string }

export function getLLMConfigs(): Promise<LLMProviderConfig[]> {
  return apiGet<LLMProviderConfig[]>('/api/llm-config')
}

export function saveLLMConfig(provider: string, payload: LLMConfigPayload): Promise<{ ok: boolean }> {
  return apiPut<{ ok: boolean }>(`/api/llm-config/${provider}`, payload)
}

export function getLLMDefaultProvider(): Promise<LLMDefaultProvider> {
  return apiGet<LLMDefaultProvider>('/api/llm-config/default-provider')
}

export function saveLLMDefaultProvider(provider: string): Promise<{ ok: boolean; provider: string }> {
  return apiPut<{ ok: boolean; provider: string }>('/api/llm-config/default-provider', { provider })
}
