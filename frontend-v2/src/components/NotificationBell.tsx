import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import {
  fetchNotifications,
  fetchUnreadCount,
  markAllRead,
  markRead,
  type NotificationItem,
} from '../api/notifications'
import { fmtShort } from '../utils/time'
export function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [loading, setLoading] = useState(false)
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0 })
  const [toast, setToast] = useState<NotificationItem | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const prevUnread = useRef<number | null>(null)
  const navigate = useNavigate()
  const btnRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // 轮询未读数，新消息到来时弹出 toast
  useEffect(() => {
    function poll() {
      fetchUnreadCount()
        .then((r) => {
          const next = r.count
          setUnread(next)
          if (prevUnread.current !== null && next > prevUnread.current) {
            // 有新通知，拉最新一条展示
            fetchNotifications()
              .then((list) => {
                const newest = list.find((n) => !n.is_read)
                if (newest) showToast(newest)
              })
              .catch(() => {})
          }
          prevUnread.current = next
        })
        .catch(() => {})
    }

    poll()
    const id = setInterval(poll, 8_000)
    return () => clearInterval(id)
  }, [])

  function showToast(item: NotificationItem) {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToast(item)
    toastTimer.current = setTimeout(() => setToast(null), 5_000)
  }

  function dismissToast() {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToast(null)
  }

  function handleToastClick(item: NotificationItem) {
    dismissToast()
    markRead(item.id).catch(() => {})
    setUnread((prev) => Math.max(0, prev - 1))
    if (item.link) navigate(item.link)
  }

  // 点击面板外部关闭
  useEffect(() => {
    if (!open) return
    function onOutside(e: MouseEvent) {
      if (
        panelRef.current && !panelRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [open])

  function handleToggle() {
    const next = !open
    setOpen(next)
    if (next && btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect()
      setPanelPos({ top: rect.top, left: rect.right + 12 })
      setLoading(true)
      fetchNotifications()
        .then((data) => {
          setItems(data)
          setLoading(false)
        })
        .catch(() => setLoading(false))
    }
  }

  function handleClickItem(item: NotificationItem) {
    if (!item.is_read) {
      markRead(item.id).catch(() => {})
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, is_read: true } : i)))
      setUnread((prev) => Math.max(0, prev - 1))
    }
    if (item.link) navigate(item.link)
    setOpen(false)
  }

  function handleMarkAll() {
    markAllRead().catch(() => {})
    setItems((prev) => prev.map((i) => ({ ...i, is_read: true })))
    setUnread(0)
  }

  const notificationCenterPath = '/home/notifications'

  return (
    <div className="relative">
      <button
        ref={btnRef}
        type="button"
        onClick={handleToggle}
        title="通知"
        className="relative flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-white/10"
        style={{ color: unread > 0 ? '#38BDF8' : '#64748B' }}
      >
        <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unread > 0 && (
          <span
            className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold text-white"
            style={{ background: '#EF4444', lineHeight: 1 }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && createPortal(
        <div
          ref={panelRef}
          className="fixed z-[9999] w-80 overflow-hidden rounded-2xl border bg-white shadow-2xl"
          style={{ borderColor: '#E9EFF6', top: panelPos.top, left: panelPos.left }}
        >
          <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: '#E9EFF6' }}>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-800">通知</span>
              {unread > 0 && (
                <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-bold text-white">{unread}</span>
              )}
            </div>
            {unread > 0 && (
              <button type="button" onClick={handleMarkAll} className="text-xs font-semibold text-blue-500 hover:text-blue-700">
                全部已读
              </button>
            )}
          </div>

          <div className="max-h-[440px] overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-10">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
              </div>
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
                <svg width="28" height="28" fill="none" stroke="#CBD5E1" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                <p className="text-xs text-slate-400">暂无通知</p>
              </div>
            ) : (
              items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleClickItem(item)}
                  className={`flex w-full items-start gap-3 border-b px-4 py-3 text-left transition-colors ${
                    item.is_read ? 'hover:bg-slate-50' : 'bg-blue-50/70 hover:bg-blue-100/70'
                  }`}
                  style={{ borderColor: '#F1F5F9' }}
                >
                  <div
                    className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full"
                    style={{ background: item.is_read ? 'transparent' : '#2563EB' }}
                  />
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm leading-5 ${item.is_read ? 'text-slate-500' : 'font-semibold text-slate-800'}`}>
                      {item.title}
                    </p>
                    {item.body && (
                      <p className="mt-0.5 line-clamp-2 text-xs leading-4 text-slate-400">{item.body}</p>
                    )}
                    <p className="mt-1 text-[11px] text-slate-300">{fmtShort(item.created_at)}</p>
                  </div>
                </button>
              ))
            )}
          </div>
          {notificationCenterPath && (
            <div className="border-t border-slate-100 px-4 py-3">
              <button
                type="button"
                onClick={() => navigate(notificationCenterPath)}
                className="w-full rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                查看全部通知
              </button>
            </div>
          )}
        </div>,
        document.body,
      )}

      {toast && createPortal(
        <div
          role="alert"
          onClick={() => handleToastClick(toast)}
          style={{
            position: 'fixed',
            bottom: 28,
            right: 28,
            zIndex: 99999,
            width: 320,
            background: '#fff',
            border: '1px solid #E2E8F0',
            borderRadius: 14,
            boxShadow: '0 8px 32px rgba(15,23,42,0.14)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 12,
            padding: '14px 16px',
            cursor: toast.link ? 'pointer' : 'default',
            animation: 'slideUp .25s ease',
          }}
        >
          <style>{`@keyframes slideUp{from{transform:translateY(16px);opacity:0}to{transform:translateY(0);opacity:1}}`}</style>
          <div style={{ width: 34, height: 34, borderRadius: 9, background: '#EFF6FF', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="16" height="16" fill="none" stroke="#2563EB" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: 13, fontWeight: 600, color: '#1E293B', lineHeight: '1.4', marginBottom: 2 }}>{toast.title}</p>
            {toast.body && (
              <p style={{ fontSize: 12, color: '#64748B', lineHeight: '1.4', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as const }}>
                {toast.body}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); dismissToast() }}
            style={{ flexShrink: 0, background: 'none', border: 'none', cursor: 'pointer', color: '#94A3B8', padding: 2, lineHeight: 1 }}
          >
            <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>,
        document.body,
      )}
    </div>
  )
}
