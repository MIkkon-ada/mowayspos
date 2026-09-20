import type { ProjectCloseRequest, ProjectCloseResidualItem } from '../../types'
import { formatArchiveDateTime } from './projectArchiveViewModel'

const closeStatus: Record<string, string> = { pending: '待审核', approved: '已批准', rejected: '已退回', cancelled: '已取消' }

function ReviewField({ title, value }: { title: string; value?: string | null }) {
  return <div className="archive-review-field"><span>{title}</span><p>{value?.trim() || '未记录'}</p></div>
}

function ResidualTable({ title, rows }: { title: string; rows?: ProjectCloseResidualItem[] }) {
  return (
    <div className="archive-residual-block">
      <h4>{title}</h4>
      <div className="archive-table-scroll">
        <table className="archive-table archive-residual-table">
          <thead><tr><th>事项</th><th>原因</th><th>负责人</th><th>交接对象</th><th>后续安排</th></tr></thead>
          <tbody>
            {!rows?.length ? <tr><td colSpan={5}><div className="archive-empty">无</div></td></tr> : rows.map((row, index) => (
              <tr key={`${title}-${index}`}><td className="archive-table__primary">{row.description || '未记录'}</td><td>{row.reason || '—'}</td><td>{row.owner || '—'}</td><td>{row.handover_to || '—'}</td><td>{row.follow_up_plan || row.expected_resolution || '—'}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function ArchiveCloseReviewSection({ latestApproved, requests, error }: { latestApproved: ProjectCloseRequest | null; requests: ProjectCloseRequest[]; error?: string }) {
  const sorted = [...requests].sort((a, b) => Date.parse(b.created_at ?? '') - Date.parse(a.created_at ?? ''))
  return (
    <>
      <section id="archive-close-review" className="archive-section">
        <div className="archive-section-title-row"><div><span className="archive-section-eyebrow">CLOSE REVIEW</span><h2>结束复盘</h2></div></div>
        <article className="archive-card archive-close-review-card">
          {error ? <div className="archive-module-error">{error}</div> : !latestApproved ? <div className="archive-empty archive-empty--review">暂无已批准的结束复盘</div> : (
            <>
              <div className="archive-review-grid">
                <ReviewField title="项目总结" value={latestApproved.summary} />
                <ReviewField title="目标完成情况" value={latestApproved.objective_result} />
                <ReviewField title="交接计划" value={latestApproved.handover_plan} />
                <ReviewField title="项目复盘" value={latestApproved.retrospective} />
              </div>
              <div className="archive-residual-grid">
                <ResidualTable title="未完成事项" rows={latestApproved.unfinished_items} />
                <ResidualTable title="剩余风险" rows={latestApproved.remaining_risks} />
              </div>
            </>
          )}
        </article>
      </section>

      <section id="archive-approvals" className="archive-section">
        <div className="archive-section-title-row"><div><span className="archive-section-eyebrow">APPROVAL HISTORY</span><h2>审批记录</h2></div><span className="archive-section-note">共 {requests.length} 条</span></div>
        <article className="archive-card">
          {error ? <div className="archive-module-error">{error}</div> : (
            <div className="archive-table-scroll">
              <table className="archive-table archive-approval-table">
                <thead><tr><th>申请编号</th><th>申请人</th><th>提交时间</th><th>审核人</th><th>审核时间</th><th>审核意见</th><th>状态</th></tr></thead>
                <tbody>
                  {sorted.length === 0 ? <tr><td colSpan={7}><div className="archive-empty archive-empty--approval">暂无审批记录</div></td></tr> : sorted.map((row) => (
                    <tr key={row.id}><td className="archive-table__primary">#{row.id}</td><td>{row.requester_name || '未记录'}</td><td>{formatArchiveDateTime(row.created_at)}</td><td>{row.reviewer_name || '—'}</td><td>{formatArchiveDateTime(row.reviewed_at || row.cancelled_at)}</td><td>{row.review_comment || '—'}</td><td><span className={`archive-approval-status is-${row.status}`}>{closeStatus[row.status] || row.status}</span></td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>
    </>
  )
}
