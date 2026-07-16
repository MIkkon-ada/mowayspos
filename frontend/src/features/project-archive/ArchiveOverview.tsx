import { useState } from 'react'
import type { Project, ProjectCloseRequest, ProjectMember } from '../../types'
import type { ArchiveMetric } from './projectArchiveViewModel'
import { formatArchiveDate } from './projectArchiveViewModel'
import { getProjectRoleLabel } from '../../domain/roleLabels'

function DisplayLines({ value, empty }: { value?: string | null; empty: string }) {
  const text = value?.trim()
  if (!text) return <p className="archive-muted-copy">{empty}</p>
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  if (lines.length <= 1) return <p className="archive-body-copy">{text}</p>
  return <ul className="archive-simple-list">{lines.map((line, index) => <li key={`${index}-${line}`}>{line}</li>)}</ul>
}

export function ArchiveOverview({
  project,
  closeRequest,
  members,
  metrics,
  memberError,
}: {
  project: Project
  closeRequest: ProjectCloseRequest | null
  members: ProjectMember[]
  metrics: ArchiveMetric[]
  memberError?: string
}) {
  const [expanded, setExpanded] = useState(false)
  const visibleMembers = expanded ? members : members.slice(0, 6)
  const objectiveStatus = closeRequest?.objective_result?.includes('部分完成') ? '部分完成' : '已完成'

  return (
    <>
      <section id="archive-overview" className="archive-section archive-section--flush">
        <div className="archive-section-title-row">
          <div>
            <span className="archive-section-eyebrow">ARCHIVE OVERVIEW</span>
            <h2>档案总览</h2>
          </div>
          <span className="archive-readonly-pill">只读档案</span>
        </div>
        <div className="archive-metric-grid">
          {metrics.map((metric) => (
            <article className="archive-metric-card" key={metric.label}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <small>{metric.detail}</small>
            </article>
          ))}
        </div>
        <article className="archive-card archive-intro-card">
          <div className="archive-card-heading archive-card-heading--compact">
            <div><span className="archive-card-kicker">ABOUT</span><h3>项目简介</h3></div>
          </div>
          <DisplayLines value={project.description || project.background} empty="暂无项目简介" />
        </article>
      </section>

      <section id="archive-project-info" className="archive-section">
        <div className="archive-section-title-row">
          <div><span className="archive-section-eyebrow">PROJECT PROFILE</span><h2>项目基本信息</h2></div>
        </div>
        <div className="archive-two-column archive-two-column--balanced">
          <article className="archive-card archive-goal-card">
            <div className="archive-card-heading archive-card-heading--compact">
              <div><span className="archive-card-kicker">OBJECTIVES</span><h3>最终目标完成情况</h3></div>
              <span className={`archive-status-chip ${objectiveStatus === '部分完成' ? 'is-partial' : 'is-complete'}`}>{objectiveStatus}</span>
            </div>
            <div className="archive-goal-columns">
              <div>
                <h4>项目目标</h4>
                <DisplayLines value={project.objectives || project.expected_outcomes} empty="未记录项目目标" />
              </div>
              <div>
                <h4>结束时完成情况</h4>
                <DisplayLines value={closeRequest?.objective_result} empty="未记录目标完成情况" />
              </div>
            </div>
          </article>

          <article className="archive-card archive-members-card">
            <div className="archive-card-heading archive-card-heading--compact">
              <div><span className="archive-card-kicker">FINAL TEAM</span><h3>最终项目成员</h3></div>
              <span className="archive-card-count">{members.length}</span>
            </div>
            {memberError ? <div className="archive-module-error">{memberError}</div> : (
              <div className="archive-table-scroll">
                <table className="archive-table archive-table--members">
                  <thead><tr><th>姓名</th><th>角色</th><th>所属方/部门</th><th>参与时间</th></tr></thead>
                  <tbody>
                    {visibleMembers.length === 0 ? (
                      <tr><td colSpan={4}><div className="archive-empty">暂无成员记录</div></td></tr>
                    ) : visibleMembers.map((member) => (
                      <tr key={member.id}>
                        <td className="archive-table__primary">{member.person_name_snapshot || '未记录'}</td>
                        <td>{getProjectRoleLabel(member.role)}</td>
                        <td>我方</td>
                        <td>{formatArchiveDate(member.joined_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {members.length > 6 && (
              <button type="button" className="archive-text-link archive-print-hidden" onClick={() => setExpanded((value) => !value)}>
                {expanded ? '收起成员' : `查看全部（共 ${members.length} 人）`} <span>{expanded ? '⌃' : '⌄'}</span>
              </button>
            )}
          </article>
        </div>
      </section>
    </>
  )
}
