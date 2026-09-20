import { apiGet, apiPatch, apiPost, apiPut, apiDelete } from './client'

export type AccountItem = {
  id: number
  username: string
  person_id: number | null
  person_name: string
  status: 'active' | 'disabled'
  is_tech_admin: boolean
  must_change_password: boolean
  wecom_userid: string
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

export function updateAccount(id: number, payload: { username: string }): Promise<AccountItem> {
  return apiPatch<AccountItem>(`/api/accounts/${id}`, payload)
}

export function bindAccountWecom(id: number, wecomUserid: string): Promise<AccountItem> {
  return apiPut<AccountItem>(`/api/accounts/${id}/wecom`, { wecom_userid: wecomUserid })
}

export function unbindAccountWecom(id: number): Promise<AccountItem> {
  return apiDelete<AccountItem>(`/api/accounts/${id}/wecom`)
}

export type WecomUserItem = {
  wecom_userid: string
  wecom_name: string
  department_ids: number[]
  bound_account_id: number | null
  bound_username: string
  preselect_account_id: number | null
  preselect_username: string
}

export function fetchWecomUsers(): Promise<WecomUserItem[]> {
  return apiGet<WecomUserItem[]>('/api/accounts/wecom-users')
}

export type WecomBatchBindItem = {
  account_id: number
  wecom_userid: string
}

export function batchBindWecom(items: WecomBatchBindItem[]): Promise<AccountItem[]> {
  return apiPost<AccountItem[]>('/api/accounts/wecom-bind-batch', { items })
}

export type WecomDirectoryPreviewItem = {
  userid: string
  name: string
  department_ids: number[]
  department_path: string
  position: string
  matched_person_id: number | null
  matched_person_name: string
  match_type: 'exact' | 'name_suggestion' | 'new' | 'conflict'
  needs_confirmation: boolean
  current_department: string
  current_position_title: string
  department_source: 'wecom' | 'local'
  position_source: 'wecom' | 'local'
  wecom_department: string
  wecom_position_title: string
}

export type WecomDirectoryPreview = {
  items: WecomDirectoryPreviewItem[]
  summary: { total: number; exact: number; needs_confirmation: number; new: number; conflict: number }
}

export function fetchWecomDirectory(): Promise<WecomDirectoryPreview> {
  return apiGet<WecomDirectoryPreview>('/api/accounts/wecom-directory')
}

export type WecomDirectorySyncItem = {
  wecom_userid: string
  person_id?: number | null
  create_person?: boolean
}

export function syncWecomDirectory(items: WecomDirectorySyncItem[]): Promise<{ synced: number; items: Array<{ person_id: number; person_name: string; wecom_userid: string }> }> {
  return apiPost('/api/accounts/wecom-directory/sync', { items })
}

export type WecomDirectoryProvisionResult = {
  updated: number
  linked_by_name: number
  created_people: number
  created_accounts: number
  conflicts: Array<{ userid: string; name: string; reason: string }>
}

export function provisionWecomDirectoryAccounts(): Promise<WecomDirectoryProvisionResult> {
  return apiPost<WecomDirectoryProvisionResult>('/api/accounts/wecom-directory/provision-all', {})
}

export function changeMyPassword(oldPassword: string, newPassword: string): Promise<{ ok: boolean }> {
  return apiPost<{ ok: boolean }>('/api/auth/change-password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
