import type { KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { formatDateTime } from './workspaceFormat'

export function KeyTaskContextCard({ workspace }: { workspace: KeyTaskWorkspace }) {
  const { project, workstream, key_task: keyTask } = workspace
  return <aside className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="任务归属和背景信息">
    <h2 className="text-base font-bold text-slate-900">任务归属</h2>
    <ol className="mt-4 space-y-4 border-l border-slate-200 pl-4 text-sm">
      <li><p className="text-xs font-medium text-slate-500">项目</p><p className="mt-1 font-semibold leading-5 text-slate-800">{project?.name || '—'}</p></li>
      <li><p className="text-xs font-medium text-slate-500">重点工作</p><p className="mt-1 font-semibold leading-5 text-slate-800">{workstream?.name || '—'}</p></li>
      <li><p className="text-xs font-medium text-slate-500">关键任务</p><p className="mt-1 font-semibold leading-5 text-slate-800">{keyTask.title}</p></li>
    </ol>
    <dl className="mt-5 space-y-3 border-t border-slate-200 pt-4 text-xs">
      <div><dt className="text-slate-500">创建来源</dt><dd className="mt-1 text-slate-700">{keyTask.source_type || '—'}</dd></div>
      <div><dt className="text-slate-500">创建时间</dt><dd className="mt-1 text-slate-700">{formatDateTime(keyTask.created_at)}</dd></div>
    </dl>
  </aside>
}
