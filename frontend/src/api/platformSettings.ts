import { apiGet, apiPut } from './client'

export type PlatformSettingsData = {
  platform_name: string
  language: 'zh' | 'en'
  timezone: string
  theme_color: string
  logo_url: string | null
  notify_delay: boolean
  notify_ai: boolean
  notify_decision: boolean
  notify_weekly: boolean
  notify_channels: string[]
  confidence: number
  two_fa: boolean
  session_ttl: string
}

export function getPlatformSettings(): Promise<PlatformSettingsData> {
  return apiGet<PlatformSettingsData>('/api/platform-settings')
}

export function savePlatformSettings(data: Partial<PlatformSettingsData>): Promise<PlatformSettingsData> {
  return apiPut<PlatformSettingsData>('/api/platform-settings', data)
}
