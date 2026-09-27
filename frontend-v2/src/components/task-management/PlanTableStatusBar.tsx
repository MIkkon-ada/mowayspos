import { MAX_PLAN_TABLE_ZOOM, MIN_PLAN_TABLE_ZOOM } from './planTableViewModel'

type Props = {
  keyTaskCount: number
  emptyTaskCount: number
  zoomPercent: number
  onZoomChange: (value: number) => void
  onZoomOut: () => void
  onZoomIn: () => void
  onResetView: () => void
}

export function PlanTableStatusBar({
  keyTaskCount,
  emptyTaskCount,
  zoomPercent,
  onZoomChange,
  onZoomOut,
  onZoomIn,
  onResetView,
}: Props) {
  return (
    <div className="plan-table-status-bar">
      <div className="plan-table-status-bar__summary">
        <span>共 {keyTaskCount} 条关键任务</span>
        {emptyTaskCount > 0 && <span>{emptyTaskCount} 个重点工作暂无关键任务</span>}
      </div>
      <div className="plan-table-status-bar__zoom" aria-label="底部缩放控件">
        <button type="button" onClick={onZoomOut} aria-label="缩小表格">−</button>
        <input
          type="range"
          min={MIN_PLAN_TABLE_ZOOM}
          max={MAX_PLAN_TABLE_ZOOM}
          step={5}
          value={zoomPercent}
          onChange={(event) => onZoomChange(Number(event.target.value))}
          aria-label="表格缩放比例"
        />
        <button type="button" onClick={onZoomIn} aria-label="放大表格">＋</button>
        <span data-testid="plan-table-bottom-zoom">{zoomPercent}%</span>
        <button type="button" className="plan-table-status-bar__reset" onClick={onResetView} aria-label="重置视图">↺</button>
      </div>
    </div>
  )
}
