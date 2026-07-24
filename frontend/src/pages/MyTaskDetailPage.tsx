import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { fetchSubtaskDetail, type SubTaskDetail } from '../api/subtasks'
import { getMyTaskProgressText, getMyTaskStatusTone, normalizeMyTaskStatus, parseMyTaskPlanTime } from '../features/my-tasks/myTasksViewModel'
import '../features/my-tasks/myTasks.css'

type LoopItem = {
  title: string
  status: string
  time: string
  submit: string
  result: string
  outcomes: string[]
  issues: string[]
}

function fallback(value: unknown, empty = '暂无记录'): string {
  const text = String(value ?? '').trim()
  return text || empty
}

function formatDateTime(value?: string | null): string {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getProgress(status?: string | null): number {
  const normalized = normalizeMyTaskStatus(status)
  if (normalized === '已完成') return 100
  if (normalized === '进行中') return 75
  if (normalized === '延期') return 55
  if (normalized === '暂缓') return 40
  return 0
}

function buildLoopItems(detail: SubTaskDetail): LoopItem[] {
  const achievements = detail.related_achievements?.map((item) => fallback(item.name, '未命名成果')) ?? []
  const issues = detail.related_issues?.map((item) => fallback(item.description, '未命名问题')) ?? []
  const submission = detail.source_submission
  const currentStatus = normalizeMyTaskStatus(detail.status)

  if (submission) {
    const submitText = [
      fallback(submission.summary || submission.title),
      ...(submission.completed_items?.filter(Boolean) ?? []),
    ].join('\n')
    return [{
      title: '闭环 01',
      status: currentStatus,
      time: formatDateTime(submission.created_at),
      submit: submitText,
      result: getMyTaskProgressText(detail.notes),
      outcomes: achievements,
      issues,
    }]
  }

  return [{
    title: '闭环 01',
    status: currentStatus,
    time: formatDateTime(detail.updated_at || detail.created_at || null),
    submit: fallback(detail.completion_criteria, '尚未记录提交内容'),
    result: getMyTaskProgressText(detail.notes),
    outcomes: achievements,
    issues,
  }]
}

export function MyTaskDetailPage() {
  const navigate = useNavigate()
  const { taskId: taskIdParam } = useParams()
  const [searchParams] = useSearchParams()
  const taskId = Number(taskIdParam)
  const projectId = searchParams.get('projectId') || ''
  const [detail, setDetail] = useState<SubTaskDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    if (!Number.isInteger(taskId)) {
      setError('任务编号无效')
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    fetchSubtaskDetail(taskId)
      .then((data) => { if (!cancelled) setDetail(data) })
      .catch(() => { if (!cancelled) setError('任务详情加载失败，请稍后重试') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [taskId])

  const plan = useMemo(() => parseMyTaskPlanTime(detail?.plan_time), [detail?.plan_time])
  const loops = useMemo(() => (detail ? buildLoopItems(detail) : []), [detail])
  const progress = getProgress(detail?.status)
  const status = normalizeMyTaskStatus(detail?.status)
  const statusTone = getMyTaskStatusTone(detail?.status)
  const projectName = fallback(detail?.parent_task?.special_project, '未关联项目')
  const workstreamName = fallback(detail?.parent_task?.key_task, '未关联重点工作')
  const deadline = plan.end || plan.display || '未设置'
  const submitUrl = `/work/submit?${new URLSearchParams({ ...(projectId ? { projectId } : {}), subtaskId: String(taskId) }).toString()}`

  return (
    <div className="my-task-detail-page">
      <header className="my-tasks-header my-task-detail-header">
        <div>
          <nav className="my-task-detail-breadcrumb" aria-label="任务路径">
            <button type="button" onClick={() => navigate('/member/tasks')}>我的任务</button>
            <span>/</span>
            <span>{projectName}</span>
            <span>/</span>
            <span>{workstreamName}</span>
          </nav>
          <h1>{detail?.title || '任务详情'}</h1>
        </div>
        <div className="my-task-detail-header-actions">
          <button type="button" onClick={() => navigate('/member/tasks')}>返回列表</button>
          <button type="button" className="is-primary" onClick={() => navigate(submitUrl)} disabled={!Number.isInteger(taskId)}>提交更新</button>
        </div>
      </header>

      <main className="my-task-detail-content">
        {loading && <div className="my-task-state"><span className="my-task-state-icon is-spinning" aria-hidden="true">↻</span><h2>正在加载任务详情</h2><p>正在读取关键任务、闭环记录和关联成果问题。</p></div>}
        {!loading && error && <div className="my-task-state is-error"><span className="my-task-state-icon" aria-hidden="true">!</span><h2>加载失败</h2><p>{error}</p><button type="button" onClick={() => navigate('/member/tasks')}>返回列表</button></div>}
        {!loading && detail && (
          <div className="my-task-detail-layout">
            <section className="my-task-detail-main">
              <article className="my-task-progress-card">
                <div>
                  <span>整体完成率</span>
                  <strong>{progress}%</strong>
                  <em className={`my-task-status my-task-status--${statusTone}`}>{status}</em>
                </div>
                <div className="my-task-progress-bar"><i style={{ width: `${progress}%` }} /></div>
              </article>

              <section className="my-task-loop-panel">
                <div className="my-task-section-title">
                  <h2>闭环过程线</h2>
                  <span>按一次闭环归档</span>
                </div>
                <div className="my-task-loop-timeline">
                  {loops.map((item, index) => (
                    <article className="my-task-loop-card" key={`${item.title}-${index}`}>
                      <div className="my-task-loop-marker"><span>{index + 1}</span></div>
                      <div className="my-task-loop-body">
                        <div className="my-task-loop-head">
                          <div>
                            <strong>{item.title}</strong>
                            <em className={`my-task-status my-task-status--${statusTone}`}>{item.status}</em>
                          </div>
                          <time>{item.time}</time>
                        </div>
                        <dl className="my-task-loop-fields">
                          <div>
                            <dt>提交内容</dt>
                            <dd>{item.submit}</dd>
                          </div>
                          <div>
                            <dt>处理结果</dt>
                            <dd>{item.result}</dd>
                          </div>
                          <div>
                            <dt>关联成果/问题</dt>
                            <dd>
                              <span>成果：{item.outcomes.length ? item.outcomes.join('、') : '暂无'}</span>
                              <span>问题：{item.issues.length ? item.issues.join('、') : '暂无'}</span>
                            </dd>
                          </div>
                        </dl>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </section>

            <aside className="my-task-detail-side">
              <section className="my-task-side-card my-task-structure-card">
                <h2>任务结构</h2>
                <div className="my-task-structure-chain" aria-label="项目到关键任务的三层结构">
                  <article className="my-task-structure-node">
                    <span className="my-task-structure-index">01</span>
                    <div>
                      <span>项目</span>
                      <strong>{projectName}</strong>
                    </div>
                  </article>
                  <article className="my-task-structure-node">
                    <span className="my-task-structure-index">02</span>
                    <div>
                      <span>重点工作</span>
                      <strong>{workstreamName}</strong>
                    </div>
                  </article>
                  <article className="my-task-structure-node">
                    <span className="my-task-structure-index">03</span>
                    <div>
                      <span>关键任务</span>
                      <strong>{detail.title}</strong>
                    </div>
                  </article>
                </div>
                <div className="my-task-structure-deadline">
                  <span>截止日期</span>
                  <strong>{deadline}</strong>
                </div>
              </section>

              <section className="my-task-side-card my-task-assets-card">
                <h2>成果</h2>
                {detail.related_achievements?.length ? detail.related_achievements.map((item) => (
                  <article key={item.id}>
                    <strong>{fallback(item.name, '未命名成果')}</strong>
                    <span>{fallback(item.achievement_type, '未分类')} · {fallback(item.status, '未标记状态')}</span>
                  </article>
                )) : <p>暂无关联成果</p>}
              </section>

              <section className="my-task-side-card my-task-issues-card">
                <h2>问题</h2>
                {detail.related_issues?.length ? detail.related_issues.map((item) => (
                  <article key={item.id}>
                    <strong>{fallback(item.description, '未命名问题')}</strong>
                    <span>{fallback(item.priority, '未标记优先级')} · {fallback(item.status, '未标记状态')}</span>
                  </article>
                )) : <p>暂无关联问题</p>}
              </section>
            </aside>
          </div>
        )}
      </main>
    </div>
  )
}
