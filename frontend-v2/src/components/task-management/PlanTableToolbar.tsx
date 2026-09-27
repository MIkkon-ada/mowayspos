type Props = {
  zoomPercent: number
  onZoomOut: () => void
  onZoomIn: () => void
  onFitWidth: () => void
  onResetView: () => void
  onExport: () => void
  exportDisabled?: boolean
  exportLabel?: string
}

export function PlanTableToolbar({
  zoomPercent,
  onZoomOut,
  onZoomIn,
  onFitWidth,
  onResetView,
  onExport,
  exportDisabled = false,
  exportLabel = '导出 Excel',
}: Props) {
  return (
    <div className="plan-table-toolbar" aria-label="工作推进表视图工具栏">
      <div className="plan-table-toolbar__zoom" aria-label="顶部缩放控件">
        <button type="button" onClick={onZoomOut} aria-label="缩小表格">−</button>
        <span className="plan-table-toolbar__percent" data-testid="plan-table-top-zoom">{zoomPercent}%</span>
        <button type="button" onClick={onZoomIn} aria-label="放大表格">＋</button>
      </div>
      <button type="button" className="plan-table-toolbar__action" onClick={onFitWidth}>
        适合宽度
      </button>
      <button type="button" className="plan-table-toolbar__action" onClick={onResetView}>
        重置视图
      </button>
      <span className="plan-table-toolbar__spacer" />
      <button
        type="button"
        className="plan-table-toolbar__export"
        disabled={exportDisabled}
        onClick={onExport}
      >
        {exportLabel}
      </button>
    </div>
  )
}
