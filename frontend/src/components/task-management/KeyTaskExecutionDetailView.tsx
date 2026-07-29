import type { Project, TaskItem } from '../../types'
import type { SubTaskDetail } from '../../api/subtasks'

type Props = { project: Project | null; task: TaskItem | null; subTask: SubTaskDetail; onBack: () => void }
type ReportItem = NonNullable<SubTaskDetail['work_reports']>[number]

const toLines = (value?: string[] | string) => Array.isArray(value) ? value.filter(Boolean) : value ? [value] : []
const collaboratorOf = (notes?: string) => notes?.match(/协同人[：:]?([^\n]+)/)?.[1]?.trim() || ''
const dateText = (value?: string | null) => value ? value.replace('T', ' ').slice(0, 16) : '暂无汇报时间'

function ReportCell({ title, values }: { title: string; values: string[] }) {
  return <div className="min-w-0 border-b border-slate-100 px-4 py-3 even:border-l sm:border-b-0 sm:[&:nth-child(n+3)]:border-t">
    <h3 className="text-xs font-semibold text-slate-600">{title}</h3>
    <div className="mt-1.5 text-xs leading-5 text-slate-700">
      {values.length ? values.map((value, index) => <p key={`${value}-${index}`}>{value}</p>) : <span className="text-slate-400">暂无</span>}
    </div>
  </div>
}

function AchievementList({ subTask }: { subTask: SubTaskDetail }) {
  const achievements = subTask.related_achievements ?? []
  return <section className="rounded-xl border border-slate-200 bg-white p-4">
    <h2 className="text-sm font-semibold text-slate-800">相关成果{achievements.length ? `（${achievements.length}）` : ''}</h2>
    {achievements.length ? <div className="mt-3 space-y-2">
      {achievements.map((item) => <div key={item.id} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
        <p className="truncate text-xs font-medium text-slate-700">{item.name}</p>
        <p className="mt-1 text-[11px] text-slate-400">{item.achievement_type || '成果'} · {item.status || '进行中'}</p>
      </div>)}
    </div> : <p className="mt-3 text-xs text-slate-400">暂无关联成果</p>}
  </section>
}

export function KeyTaskExecutionDetailView({ project, task, subTask, onBack }: Props) {
  const reports: ReportItem[] = subTask.work_reports ?? []
  const hasReports = reports.length > 0
  const hasAchievements = (subTask.related_achievements?.length ?? 0) > 0
  const criteria = toLines(subTask.completion_criteria)
  const collaborator = collaboratorOf(subTask.notes)
  const latest = reports[0]

  return <main className="flex-1 overflow-y-auto bg-slate-50">
    <div className="mx-auto max-w-[1360px] px-6 py-5">
      <button type="button" onClick={onBack} className="text-xs font-medium text-slate-500 hover:text-blue-600">← 返回工作推进表</button>

      <section className="mt-3 rounded-xl border border-slate-200 bg-white px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">{subTask.title}</h1>
              <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">{subTask.status || '未开始'}</span>
            </div>
            <p className="mt-2 text-xs text-slate-500">所属重点工作：{task?.key_task || '—'}</p>
          </div>
          <span className="text-xs text-slate-400">所属项目：{project?.name || '—'}</span>
        </div>
        <div className="mt-4 grid border-t border-slate-100 pt-3 sm:grid-cols-2 xl:grid-cols-4">
          <Info title="负责人" value={subTask.assignee || '未指定'} />
          {collaborator && <Info title="协同人" value={collaborator} />}
          <Info title="当前状态" value={subTask.status || '未开始'} accent />
          <Info title="时间范围" value={subTask.plan_time || '未填写'} />
        </div>
      </section>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-4">
          {criteria.length > 0 && <section className="rounded-xl border border-slate-200 bg-white px-5 py-4">
            <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-semibold text-slate-800">任务评价标准</h2><span className="text-xs text-slate-400">按实际内容填写</span></div>
            <div className="mt-3 space-y-1.5 text-sm leading-6 text-slate-700">{criteria.map((item, index) => <p key={`${item}-${index}`}>• {item}</p>)}</div>
          </section>}

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between gap-3"><h2 className="text-base font-semibold text-slate-800">工作汇报记录</h2><span className="text-xs text-slate-400">共 {reports.length} 条</span></div>
            {hasReports ? <div className="mt-4 space-y-3">
              {reports.map((report) => <article key={report.id} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50 px-4 py-2.5">
                  <span className="text-xs font-semibold text-slate-700">{report.submitter || '—'}</span><time className="text-xs text-slate-400">{dateText(report.created_at)}</time>
                </header>
                <div className="grid sm:grid-cols-2">
                  <ReportCell title="已完成内容" values={toLines(report.completed_items)} />
                  <ReportCell title="下一步计划" values={toLines(report.next_steps)} />
                  <ReportCell title="问题" values={report.issues.map((item) => typeof item === 'string' ? item : item.description || '').filter(Boolean)} />
                  <ReportCell title="成果" values={report.achievements.map((item) => item.name || item.achievement_type || '').filter(Boolean)} />
                </div>
              </article>)}
            </div> : <div className="mt-4 rounded-lg border border-dashed border-slate-200 px-4 py-7 text-center"><p className="text-sm font-medium text-slate-600">暂无工作汇报</p><p className="mt-1 text-xs text-slate-400">提交第一条汇报后，这里会形成实际的任务推进记录。</p></div>}
          </section>
        </div>

        <aside className="space-y-4">
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-800">当前任务概览</h2>
            <dl className="mt-4 space-y-3 text-xs"><div><dt className="text-slate-400">当前状态</dt><dd className="mt-1 font-semibold text-blue-600">{subTask.status || '未开始'}</dd></div><div><dt className="text-slate-400">最新汇报时间</dt><dd className="mt-1 text-slate-700">{dateText(latest?.created_at)}</dd></div>{criteria.length > 0 && <div><dt className="text-slate-400">评价标准</dt><dd className="mt-1 leading-5 text-slate-700">已填写 {criteria.length} 条</dd></div>}</dl>
          </section>
          {hasAchievements && <AchievementList subTask={subTask} />}
        </aside>
      </div>
    </div>
  </main>
}

function Info({ title, value, accent = false }: { title: string; value: string; accent?: boolean }) {
  return <div className="min-w-0 border-b border-slate-100 px-4 py-3 last:border-b-0 sm:border-r sm:last:border-r-0 xl:border-b-0"><p className="text-xs text-slate-400">{title}</p><p className={`mt-1 truncate text-sm font-medium ${accent ? 'text-blue-600' : 'text-slate-800'}`}>{value}</p></div>
}
