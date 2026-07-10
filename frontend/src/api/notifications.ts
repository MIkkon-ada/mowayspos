import { apiGet, apiPost } from './client'

export type NotificationItem = {
  id: number
  type: string
  title: string
  body: string
  link: string
  is_read: boolean
  created_at: string | null
  project_id: number | null
  project_name?: string | null
}

type FetchNotificationsOptions = {
  page?: number
  pageSize?: number
  isRead?: boolean
}

export function fetchNotifications(options: FetchNotificationsOptions = {}): Promise<NotificationItem[]> {
  const params = new URLSearchParams()
  params.set('page', String(options.page ?? 1))
  params.set('page_size', String(options.pageSize ?? 20))
  if (typeof options.isRead === 'boolean') {
    params.set('is_read', options.isRead ? 'true' : 'false')
  }
  return apiGet(`/api/notifications?${params.toString()}`)
}

export function fetchUnreadCount(): Promise<{ count: number }> {
  return apiGet('/api/notifications/count')
}

export function markRead(id: number): Promise<void> {
  return apiPost(`/api/notifications/${id}/read`, {})
}

export function markAllRead(): Promise<void> {
  return apiPost('/api/notifications/read-all', {})
}
