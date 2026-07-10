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
    <div className="detail-drawer-overlay" onClick={onClose}>
      <aside
        className="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title ?? '详情'}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="detail-drawer-head">
          <h2 className="detail-drawer-title">{title ?? '详情'}</h2>
          <button type="button" className="detail-drawer-close" aria-label="关闭详情" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="detail-drawer-body">{children}</div>
      </aside>
    </div>
  )
}
