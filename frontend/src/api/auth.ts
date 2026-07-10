import { apiGet, apiPost } from './client'
import type { CurrentUser } from '../types'

export function login(
  username: string,
  password: string,
): Promise<{ ok: boolean; user: string; username: string; default_route?: string }> {
  return apiPost('/api/auth/login', { username, password })
}

export function logout(): Promise<{ ok: boolean }> {
  return apiPost('/api/auth/logout')
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiGet<CurrentUser>('/api/auth/me')
}
