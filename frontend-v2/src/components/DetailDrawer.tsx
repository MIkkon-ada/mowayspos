import { useEffect } from 'react'
import type { ReactNode } from 'react'

type DetailDrawerProps = {
  open: boolean
  onClose: () => void
  title?: string
  children?: ReactNode
}

// 通用右侧详情抽屉：不依赖第三方 UI 库，移动端全屏展示。
// 仅用于只读详情查看，不承载任何主表写入能力。
export function DetailDrawer({ open, onClose, title, children }: DetailDrawerProps) {
  // ESC 关闭
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="detail-drawer-overlay fixed inset-0 z-50 flex justify-end bg-slate-900/30" onClick={onClose}>
      <aside
        className="detail-drawer flex h-full w-full max-w-[480px] flex-col bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label={title ?? '详情'}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="detail-drawer-head flex items-center justify-between border-b border-slate-200 px-6 py-5">
          <h2 className="detail-drawer-title text-lg font-semibold text-slate-900">{title ?? '详情'}</h2>
          <button type="button" className="detail-drawer-close rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="关闭详情" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="detail-drawer-body min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </aside>
    </div>
  )
}
