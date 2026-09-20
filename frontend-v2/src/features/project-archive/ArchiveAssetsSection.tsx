import { Link } from 'react-router-dom'
import type { AchievementItem, IssueItem } from '../../types'
import { formatArchiveDate } from './projectArchiveViewModel'

export function ArchiveAssetsSection({
  projectId,
  achievements,
  issues,
  achievementError,
  issueError,
}: {
  projectId: number
  achievements: AchievementItem[]
  issues: IssueItem[]
  achievementError?: string
  issueError?: string
}) {
  return (
    <section id="archive-assets" className="archive-section">
      <div className="archive-section-title-row">
        <div><span className="archive-section-eyebrow">ASSETS & ISSUES</span><h2>成果与问题</h2></div>
      </div>
      <div className="archive-two-column archive-assets-grid">
        <article className="archive-card archive-asset-card">
          <div className="archive-card-heading archive-card-heading--compact">
            <div><span className="archive-card-kicker">DELIVERABLES</span><h3>项目成果</h3></div>
            <span className="archive-card-count">{achievements.length}</span>
          </div>
          {achievementError ? <div className="archive-module-error">{achievementError}</div> : (
            <div className="archive-table-scroll">
              <table className="archive-table">
                <thead><tr><th>成果名称</th><th>类型</th><th>负责人</th><th>版本</th><th>状态</th><th>时间</th></tr></thead>
                <tbody>
                  {achievements.length === 0 ? <tr><td colSpan={6}><div className="archive-empty archive-empty--asset">暂无成果记录</div></td></tr> : achievements.map((item) => (
                    <tr key={item.id}>
                      <td className="archive-table__primary"><Link to={`/work/achievements?projectId=${projectId}`}>{item.name || `成果 #${item.id}`}</Link></td>
                      <td>{item.achievement_type || '未分类'}</td><td>{item.owner || '未记录'}</td><td>{item.version || '—'}</td>
                      <td><span className="archive-table-status">{item.status || '未记录'}</span></td><td>{formatArchiveDate(item.confirmed_at || item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
        <article className="archive-card archive-asset-card">
          <div className="archive-card-heading archive-card-heading--compact">
            <div><span className="archive-card-kicker">ISSUES</span><h3>问题记录</h3></div>
            <span className="archive-card-count">{issues.length}</span>
          </div>
          {issueError ? <div className="archive-module-error">{issueError}</div> : (
            <div className="archive-table-scroll">
              <table className="archive-table">
                <thead><tr><th>问题描述</th><th>类型</th><th>负责人</th><th>最终状态</th><th>解决结果</th></tr></thead>
                <tbody>
                  {issues.length === 0 ? <tr><td colSpan={5}><div className="archive-empty archive-empty--asset">暂无问题记录</div></td></tr> : issues.map((item) => (
                    <tr key={item.id}>
                      <td className="archive-table__primary"><Link to={`/work/issues?projectId=${projectId}`}>{item.description || `问题 #${item.id}`}</Link></td>
                      <td>{item.issue_type || '未分类'}</td><td>{item.owner || '未记录'}</td>
                      <td><span className="archive-table-status">{item.status || '未记录'}</span></td><td>{item.resolution || item.handler_reply || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </div>
    </section>
  )
}
