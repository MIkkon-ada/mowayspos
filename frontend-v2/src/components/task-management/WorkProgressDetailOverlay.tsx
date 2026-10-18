import { useLayoutEffect, useRef, type ReactNode } from 'react'

export function WorkProgressDetailOverlay({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  const dialogRef = useRef<HTMLElement | null>(null)

  useLayoutEffect(() => {
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    dialogRef.current?.focus({ preventScroll: true })
    return () => {
      if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true })
    }
  }, [])

  return <div className="wp-detail-overlay">
    <button type="button" className="wp-detail-backdrop" aria-label="关闭关键任务详情" onClick={onClose} />
    <aside ref={dialogRef} tabIndex={-1} className="wp-detail-panel" role="dialog" aria-modal="true" aria-label="关键任务执行详情">
      {children}
    </aside>
  </div>
}
