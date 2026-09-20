import { useEffect, useState } from 'react'
import { fetchSubtaskDetail, type SubTaskDetail } from '../../api/subtasks'
import type { MyTaskRow } from './myTasksViewModel'

type Props = {
  row: MyTaskRow | null
  onClose: () => void
  onOpenProject: (row: MyTaskRow) => void
  onOpenSubmit: (row: MyTaskRow) => void
}

export function MyTaskDetailDrawer({ row, onClose, onOpenProject, onOpenSubmit }: Props) {
  const [detail, setDetail] = useState<SubTaskDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)

  useEffect(() => {
    if (!row) return
    let cancelled = false
    setDetail(null)
    setError('')
    setLoading(true)
    fetchSubtaskDetail(row.id)
      .then((result) => { if (!cancelled) setDetail(result) })
      .catch(() => { if (!cancelled) setError('任务详情加载失败，请稍后重试') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [row, retryVersion])

  useEffect(() => {
    if (!row) return
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [row, onClose])

  if (!row) return null

  return (
    <div className="my-task-drawer-layer" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <aside className="my-task-drawer" role="dialog" aria-modal="true" aria-labelledby="my-task-detail-title">
        <header className="my-task-drawer-header">
          <div><p>任务详情</p><h2 id="my-task-detail-title" aria-label={row.title} title={row.title}>{row.title}</h2></div>
          <button type="button" aria-label="关闭任务详情" onClick={onClose}><span aria-hidden="true">×</span></button>
        </header>

        <div className="my-task-drawer-body">
          <section className="my-task-detail-overview">
            <div><span>所属项目</span><strong>{row.projectName}</strong></div>
            <div><span>重点工作</span><strong>{row.workstreamName}</strong></div>
            <div><span>当前状态</span><strong className={`my-task-status my-task-status--${row.statusTone}`}>{row.status}</strong></div>
            <div>
              <span>计划时间</span>
              <strong className="my-task-detail-plan">
                {row.planStart && row.planEnd ? <>
                  <span>{row.planStart}</span>
                  <span>～</span>
                  <span>{row.planEnd}</span>
                </> : <span>{row.planTime || '未填写'}</span>}
              </strong>
            </div>
          </section>

          <section className="my-task-detail-section">
            <h3>完成标准</h3>
            <p>{row.completionCriteria || '暂未填写完成标准'}</p>
          </section>
          <section className="my-task-detail-section">
            <h3>当前进展</h3>
            <p className="my-task-pre-wrap">{row.progressText}</p>
          </section>

          {loading && <div className="my-task-detail-loading"><span className="is-spinning" aria-hidden="true">↻</span>正在加载任务详情…</div>}
          {error && (
            <div className="my-task-detail-error"><span aria-hidden="true">!</span><span>{error}</span><button type="button" onClick={() => setRetryVersion((value) => value + 1)}>重试</button></div>
          )}
          {detail?.source_submission && (
            <section className="my-task-detail-section">
              <h3>来源汇报</h3>
              <dl className="my-task-source">
                <div><dt>标题</dt><dd>{detail.source_submission.title || '未命名汇报'}</dd></div>
                <div><dt>提交人</dt><dd>{detail.source_submission.submitter || '未记录'}</dd></div>
                <div><dt>摘要</dt><dd>{detail.source_submission.summary || '未记录'}</dd></div>
              </dl>
              {detail.source_submission.transcript_text && <p className="my-task-transcript">{detail.source_submission.transcript_text}</p>}
            </section>
          )}
          {detail && (
            <section className="my-task-detail-assets">
              <div>
                <h3>关联成果 <span>{detail.related_achievements?.length ?? 0}</span></h3>
                {detail.related_achievements?.length ? detail.related_achievements.map((item) => (
                  <article key={item.id}><strong>{item.name}</strong><span>{item.achievement_type || item.status}</span></article>
                )) : <p>暂无关联成果</p>}
              </div>
              <div>
                <h3>关联问题 <span>{detail.related_issues?.length ?? 0}</span></h3>
                {detail.related_issues?.length ? detail.related_issues.map((item) => (
                  <article key={item.id}><strong>{item.description}</strong><span>{item.priority || item.status}</span></article>
                )) : <p>暂无关联问题</p>}
              </div>
            </section>
          )}
        </div>

        <footer className="my-task-drawer-footer">
          <button type="button" onClick={() => onOpenProject(row)} disabled={row.projectId === null}><span aria-hidden="true">↗</span>查看工作推进</button>
          <button type="button" className="is-primary" onClick={() => onOpenSubmit(row)} disabled={row.projectId === null}><span aria-hidden="true">▤</span>提交工作汇报</button>
        </footer>
      </aside>
    </div>
  )
}
