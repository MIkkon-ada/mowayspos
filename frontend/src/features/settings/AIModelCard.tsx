import type { AIModel } from '../../api/aiConfig'

type Props = {
  model: AIModel
  busy?: boolean
  onEdit: (model: AIModel) => void
  onTest: (model: AIModel) => void
  onToggle: (model: AIModel) => void
}

function ModelTypeIcon({ type }: { type: AIModel['model_type'] }) {
  return type === 'asr' ? (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 1 0 6 0V6a3 3 0 0 0-3-3Z"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3m-3 0h6"/></svg>
  ) : (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M5 6.5A3.5 3.5 0 0 1 8.5 3h7A3.5 3.5 0 0 1 19 6.5v6a3.5 3.5 0 0 1-3.5 3.5H11l-4.5 4v-4A3.5 3.5 0 0 1 3 12.5v-6Z"/><path d="M8 9h8m-8 3h5"/></svg>
  )
}

export function AIModelCard({ model, busy, onEdit, onTest, onToggle }: Props) {
  const displayName = model.display_name.trim() || model.model_name
  const status = !model.enabled ? '已停用' : model.credential_configured ? '已配置' : '缺少 API Key'
  const statusClass = !model.enabled
    ? 'bg-slate-100 text-slate-500'
    : model.credential_configured
      ? 'bg-emerald-50 text-emerald-700'
      : 'bg-amber-50 text-amber-700'

  return (
    <article className="flex min-h-40 flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div>
        <div className="mb-5 flex items-start justify-between gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-sky-50 text-sky-700"><ModelTypeIcon type={model.model_type} /></span>
          <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusClass}`}>{status}</span>
        </div>
        <h3 className="truncate text-base font-bold text-slate-800">{displayName}</h3>
        <p className="mt-1 truncate text-xs text-slate-500">{model.provider} · {model.model_name}</p>
      </div>
      <div className="mt-5 flex items-center gap-4 border-t border-slate-100 pt-4 text-xs font-semibold">
        <button type="button" onClick={() => onEdit(model)} className="text-sky-700">编辑</button>
        {model.model_type === 'chat' && <button type="button" disabled={busy || !model.credential_configured || !model.enabled} onClick={() => onTest(model)} className="text-sky-700 disabled:text-slate-300">测试连接</button>}
        <button type="button" disabled={busy} onClick={() => onToggle(model)} className="ml-auto text-slate-600 disabled:text-slate-300">{model.enabled ? '停用' : '启用'}</button>
      </div>
    </article>
  )
}
