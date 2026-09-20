import { useCallback, useEffect, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import {
  clampPlanTableColumnWidth,
  getDefaultPlanTableWidths,
  normalizeStoredPlanTableWidths,
} from './planTableViewModel'
import { PLAN_TABLE_COLUMNS, type PlanTableColumnKey } from './planTableColumns'

export const PLAN_TABLE_COLUMN_WIDTHS_STORAGE_KEY = 'moways.workProgress.planColumnWidths'

function readStoredWidths(): Record<PlanTableColumnKey, number> {
  if (typeof window === 'undefined') return getDefaultPlanTableWidths()
  return normalizeStoredPlanTableWidths(window.localStorage.getItem(PLAN_TABLE_COLUMN_WIDTHS_STORAGE_KEY))
}

export function usePlanTableColumnLayout() {
  const [columnWidths, setColumnWidths] = useState<Record<PlanTableColumnKey, number>>(readStoredWidths)

  const getColumnWidth = useCallback((key: PlanTableColumnKey) => columnWidths[key], [columnWidths])

  const resetColumnWidths = useCallback(() => {
    setColumnWidths(getDefaultPlanTableWidths())
  }, [])

  const startResize = useCallback((key: PlanTableColumnKey, event: ReactPointerEvent<HTMLElement>) => {
    event.preventDefault()
    event.stopPropagation()
    const startX = event.clientX
    const startWidth = columnWidths[key]

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const nextWidth = clampPlanTableColumnWidth(key, startWidth + moveEvent.clientX - startX)
      setColumnWidths((current) => ({ ...current, [key]: nextWidth }))
    }
    const handlePointerUp = () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
  }, [columnWidths])

  useEffect(() => {
    window.localStorage.setItem(PLAN_TABLE_COLUMN_WIDTHS_STORAGE_KEY, JSON.stringify(columnWidths))
  }, [columnWidths])

  return {
    columnWidths,
    getColumnWidth,
    resetColumnWidths,
    startResize,
    columns: PLAN_TABLE_COLUMNS,
  }
}
