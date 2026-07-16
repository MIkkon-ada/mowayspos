import { useCallback, useEffect, useState } from 'react'
import type { RefObject } from 'react'
import {
  calculatePlanTableFitZoom,
  clampPlanTableZoom,
  DEFAULT_PLAN_TABLE_ZOOM,
  normalizeStoredPlanTableZoom,
  PLAN_TABLE_NATURAL_WIDTH,
  PLAN_TABLE_ZOOM_STEP,
} from './planTableViewModel'

export const PLAN_TABLE_ZOOM_STORAGE_KEY = 'moways.workProgress.planZoom'

function readStoredZoom(): number {
  if (typeof window === 'undefined') return DEFAULT_PLAN_TABLE_ZOOM
  return normalizeStoredPlanTableZoom(window.localStorage.getItem(PLAN_TABLE_ZOOM_STORAGE_KEY))
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tagName = target.tagName
  return tagName === 'INPUT'
    || tagName === 'SELECT'
    || tagName === 'TEXTAREA'
    || target.isContentEditable
}

export function usePlanTableZoom(workspaceRef: RefObject<HTMLDivElement | null>) {
  const [zoomPercent, setZoomPercentState] = useState(readStoredZoom)

  const setZoomPercent = useCallback((value: number) => {
    setZoomPercentState(clampPlanTableZoom(value))
  }, [])

  const zoomOut = useCallback(() => {
    setZoomPercentState((value) => clampPlanTableZoom(value - PLAN_TABLE_ZOOM_STEP))
  }, [])

  const zoomIn = useCallback(() => {
    setZoomPercentState((value) => clampPlanTableZoom(value + PLAN_TABLE_ZOOM_STEP))
  }, [])

  const fitWidth = useCallback(() => {
    const workspace = workspaceRef.current
    if (!workspace) return
    setZoomPercent(calculatePlanTableFitZoom(workspace.clientWidth, PLAN_TABLE_NATURAL_WIDTH))
    workspace.scrollTo({ left: 0, behavior: 'smooth' })
  }, [setZoomPercent, workspaceRef])

  const resetView = useCallback(() => {
    setZoomPercent(DEFAULT_PLAN_TABLE_ZOOM)
    workspaceRef.current?.scrollTo({ left: 0, top: 0 })
  }, [setZoomPercent, workspaceRef])

  useEffect(() => {
    window.localStorage.setItem(PLAN_TABLE_ZOOM_STORAGE_KEY, String(zoomPercent))
  }, [zoomPercent])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || isEditableTarget(event.target)) return
      if (event.key === '+' || event.key === '=') {
        event.preventDefault()
        zoomIn()
      } else if (event.key === '-' || event.key === '_') {
        event.preventDefault()
        zoomOut()
      } else if (event.key === '0') {
        event.preventDefault()
        resetView()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [resetView, zoomIn, zoomOut])

  return {
    zoomPercent,
    setZoomPercent,
    zoomIn,
    zoomOut,
    fitWidth,
    resetView,
  }
}
