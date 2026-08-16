import type { KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { formatDateTime } from './workspaceFormat'

export function KeyTaskContextCard({ workspace }: { workspace: KeyTaskWorkspace }) {
  const { project, workstream, key_task: keyTask } = workspace
  return <aside className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="所属关系和管理上下文"><h2 className="border-l-4 border-blue-600 pl-3 text-lg font-semibold text-slate-900">所属关系</h2><ol className="mt-4 space-y-4 border-l border-slate-200 pl-5 text-sm"><li><p className="text-slate-400">项目</p><p className="font-semibold text-slate-800">{project?.name || '—'}</p></li><li><p className="text-slate-400">重点工作</p><p className="font-semibold text-slate-800">{workstream?.name || '—'}</p></li><li><p className="text-slate-400">关键任务</p><p className="font-semibold text-slate-800">{keyTask.title}</p></li></ol><dl className="mt-5 space-y-3 border-t border-slate-200 pt-4 text-sm"><div><dt className="text-slate-400">完成定义 / 预期结果</dt><dd className="mt-1 whitespace-pre-wrap text-slate-700">{keyTask.completion_definition || '未填写'}</dd></div><div><dt className="text-slate-400">创建来源</dt><dd className="mt-1 text-slate-700">{keyTask.source_type || '—'}</dd></div><div><dt className="text-slate-400">创建时间</dt><dd className="mt-1 text-slate-700">{formatDateTime(keyTask.created_at)}</dd></div></dl></aside>
}
