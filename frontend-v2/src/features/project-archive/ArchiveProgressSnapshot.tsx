import type { ArchiveProgressRow } from './projectArchiveViewModel'

export function ArchiveProgressSnapshot({
  rows,
  distribution,
  error,
}: {
  rows: ArchiveProgressRow[]
  distribution: { completed: number; inProgress: number; incomplete: number; total: number }
  error?: string
}) {
  const total = distribution.total
  const completedPercent = total ? (distribution.completed / total) * 100 : 0
  const progressPercent = total ? (distribution.inProgress / total) * 100 : 0
  const ring = total
    ? `conic-gradient(#22C55E 0 ${completedPercent}%, #3B82F6 ${completedPercent}% ${completedPercent + progressPercent}%, #EF4444 ${completedPercent + progressPercent}% 100%)`
    : 'conic-gradient(#E2E8F0 0 100%)'
  return (
    <section id="archive-progress" className="archive-section">
      <div className="archive-section-title-row">
        <div><span className="archive-section-eyebrow">PROGRESS SNAPSHOT</span><h2>工作推进快照</h2></div>
        <span className="archive-section-note">最终状态</span>
      </div>
      <article className="archive-card archive-progress-card">
        {error ? <div className="archive-module-error">{error}</div> : (
          <div className="archive-progress-layout">
            <div className="archive-table-scroll">
              <table className="archive-table archive-progress-table">
                <thead><tr><th>重点工作</th><th>计划时间</th><th>关键任务</th><th>已完成</th><th>完成率</th><th>最终状态</th></tr></thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr><td colSpan={6}><div className="archive-empty archive-empty--progress">暂无工作推进记录</div></td></tr>
                  ) : rows.map((row) => (
                    <tr key={row.id}>
                      <td className="archive-table__primary">{row.name}</td>
                      <td>{row.planTime}</td>
                      <td>{row.total}</td>
                      <td>{row.completed}</td>
                      <td><strong className="archive-rate">{row.total ? `${row.completed} / ${row.total}` : '0 / 0'}</strong><small>{row.rate}</small></td>
                      <td><span className="archive-table-status">{row.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="archive-ring-panel">
              <h3>任务完成分布</h3>
              <div className="archive-ring" style={{ background: ring }}>
                <div className="archive-ring__center"><strong>{total ? `${Math.round(completedPercent)}%` : '—'}</strong><span>完成率</span></div>
              </div>
              <div className="archive-ring-legend">
                <span><i className="is-complete" />已完成 <strong>{distribution.completed}</strong></span>
                <span><i className="is-progress" />进行中 <strong>{distribution.inProgress}</strong></span>
                <span><i className="is-incomplete" />未完成 <strong>{distribution.incomplete}</strong></span>
              </div>
            </div>
          </div>
        )}
        <button type="button" className="archive-text-link archive-print-hidden" onClick={() => document.getElementById('archive-progress')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
          进入工作推进表快照详情 <span>›</span>
        </button>
      </article>
    </section>
  )
}
