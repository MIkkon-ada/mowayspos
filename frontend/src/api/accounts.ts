import { apiGet, apiPatch, apiPost } from './client'

export type AccountItem = {
  id: number
  username: string
  person_id: number | null
  person_name: string
  status: 'active' | 'disabled'
  is_tech_admin: boolean
  must_change_password: boolean
  last_login_at?: string | null
  last_password_changed_at?: string | null
  failed_login_count: number
  created_at?: string
  updated_at?: string
}

export type AccountCreatePayload = {
  username: string
  password: string
  person_id?: number | null
  is_tech_admin?: boolean
  must_change_password?: boolean
}

export function fetchAccounts(): Promise<AccountItem[]> {
  return apiGet<AccountItem[]>('/api/accounts')
}

export function createAccount(payload: AccountCreatePayload): Promise<AccountItem> {
  return apiPost<AccountItem>('/api/accounts', payload)
}

export function resetAccountPassword(id: number, password: string): Promise<{ ok: boolean }> {
  return apiPost<{ ok: boolean }>(`/api/accounts/${id}/reset-password`, { password })
}

export function updateAccountStatus(id: number, status: AccountItem['status']): Promise<AccountItem> {
  return apiPatch<AccountItem>(`/api/accounts/${id}/status`, { status })
}

export function changeMyPassword(oldPassword: string, newPassword: string): Promise<{ ok: boolean }> {
  return apiPost<{ ok: boolean }>('/api/auth/change-password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
