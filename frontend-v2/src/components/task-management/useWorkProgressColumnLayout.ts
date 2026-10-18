import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import type { PlanTableRow } from './planTableViewModel'
import {
  calculateWorkProgressWidths,
  clampWorkProgressWidth,
  readWorkProgressWidthOverrides,
  type WorkProgressColumnKey,
  type WorkProgressOptionalColumnKey,
  type WorkProgressWidthOverrides,
} from './workProgressColumnSizing'

const STORAGE_KEY = 'moways.workProgress.visibleColumnWidths.v1'

function readSavedWidths(): WorkProgressWidthOverrides {
  if (typeof window === 'undefined') return {}
  try {
    return readWorkProgressWidthOverrides(window.localStorage.getItem(STORAGE_KEY))
  } catch {
    return {}
  }
}

export function useWorkProgressColumnLayout(rows: PlanTableRow[], loading: boolean, projectId?: number, optionalColumns: readonly WorkProgressOptionalColumnKey[] = []) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const dragCleanup = useRef<(() => void) | null>(null)
  const [availableWidth, setAvailableWidth] = useState(0)
  const [overrides, setOverrides] = useState<WorkProgressWidthOverrides>(readSavedWidths)

  useLayoutEffect(() => {
    const container = scrollRef.current
    if (!container) return
    const updateWidth = () => setAvailableWidth(container.clientWidth)
    updateWidth()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(updateWidth) : null
    observer?.observe(container)
    window.addEventListener('resize', updateWidth)
    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', updateWidth)
    }
  }, [loading, projectId])

  useEffect(() => {
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides)) } catch { /* Browser storage may be unavailable. */ }
  }, [overrides])

  useEffect(() => () => dragCleanup.current?.(), [])

  const widths = useMemo(
    () => calculateWorkProgressWidths(rows, availableWidth, overrides, undefined, optionalColumns),
    [rows, availableWidth, overrides, optionalColumns],
  )

  const resetWidth = useCallback((key: WorkProgressColumnKey) => {
    setOverrides((current) => {
      const next = { ...current }
      delete next[key]
      return next
    })
  }, [])

  const changeWidth = useCallback((key: WorkProgressColumnKey, width: number) => {
    setOverrides((current) => ({ ...current, [key]: clampWorkProgressWidth(key, width) }))
  }, [])

  const startResize = useCallback((key: WorkProgressColumnKey, event: ReactPointerEvent<HTMLButtonElement>) => {
    event.preventDefault()
    event.stopPropagation()
    dragCleanup.current?.()
    const startX = event.clientX
    const startWidth = widths[key]
    const previousCursor = document.body.style.cursor
    const previousSelection = document.body.style.userSelect
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    const onMove = (moveEvent: PointerEvent) => changeWidth(key, startWidth + moveEvent.clientX - startX)
    const cleanup = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', cleanup)
      window.removeEventListener('pointercancel', cleanup)
      document.body.style.cursor = previousCursor
      document.body.style.userSelect = previousSelection
      dragCleanup.current = null
    }
    dragCleanup.current = cleanup
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', cleanup)
    window.addEventListener('pointercancel', cleanup)
  }, [changeWidth, widths])

  return { scrollRef, widths, startResize, changeWidth, resetWidth }
}
