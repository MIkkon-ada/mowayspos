import { useState } from 'react'
import { createKickoffRun } from '../../api/meetings'

export function KickoffAgentWorkspace({ projectId, onClose }: { projectId: number; onClose: () => void }) {
  const [transcript, setTranscript] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  async function submit() {
    setSaving(true)
    try { const run = await createKickoffRun(projectId, transcript); setMessage(`已创建启动会审核包 #${run.id}，等待企业教练审核`) }
    catch { setMessage('创建审核包失败，请稍后重试') }
    finally { setSaving(false) }
  }
  return <div className="rounded-2xl border bg-white p-6" data-project-id={projectId}>
    <h2 className="text-base font-bold text-slate-800">启动会确认 Agent</h2>
    <p className="mt-2 text-sm text-slate-500">Agent 将对照会前工作推进表生成待审核的启动会纪要与变更提案；未经企业教练审核不会写入执行版。</p>
    <textarea className="mt-4 min-h-40 w-full rounded-xl border p-3 text-sm" value={transcript} onChange={(event) => setTranscript(event.target.value)} placeholder="粘贴或录入启动会原文" />
    <div className="mt-4 flex gap-3">
      <button className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={!transcript.trim() || saving} onClick={submit}>{saving ? '提交中…' : '提交企业教练审核'}</button>
      <button className="rounded-xl border px-4 py-2 text-sm" onClick={onClose}>返回</button>
    </div>
    {message && <p className="mt-3 text-sm text-slate-600">{message}</p>}
  </div>
}
