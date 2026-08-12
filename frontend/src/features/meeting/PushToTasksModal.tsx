import { useEffect, useMemo, useState } from 'react'
import { apiPost } from '../../api/client'
import { createTask, fetchTasks } from '../../api/tasks'
import type { TaskItem } from '../../types'
import { ErrorBar } from './meetingShared'

type PushStep = 'review' | 'executing' | 'done'

type ActionItem = {
  id: string
  title: string
  owner: string
  dueDate: string
  source: string
  selected: boolean
  targetTaskId: string
  executing?: boolean
  done?: boolean
  error?: string
}

function firstValue(row: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = String(row[key] ?? '').trim()
    if (value) return value
  }
  return ''
}

function parseActionItems(raw: string): ActionItem[] {
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    return parsed.flatMap((entry, index) => {
      if (typeof entry === 'string') {
        const title = entry.trim()
        return title ? [{ id: `${index}-${title}`, title, owner: '', dueDate: '', source: '', selected: true, targetTaskId: '' }] : []
      }
      if (!entry || typeof entry !== 'object') return []

      const row = entry as Record<string, unknown>
      const title = firstValue(row, ['会议安排事项', '事项', '待办事项', 'task', 'title', 'content', 'name'])
      if (!title) return []
      return [{
        id: `${index}-${title}`,
        title,
        owner: firstValue(row, ['负责人', '责任人', 'owner', 'assignee']),
        dueDate: firstValue(row, ['完成时限', '完成时间', '截止日期', 'due_date', 'dueDate', 'plan_time']),
        source: firstValue(row, ['本周进展/说明', '说明', '备注', 'source', 'note']),
        selected: true,
        targetTaskId: '',
      }]
    })
  } catch {
    return []
  }
}

export function PushToTasksModal({
  projectId,
  taskListJson,
  onClose,
  onDone,
}: {
  projectId: number
  taskListJson: string
  onClose: () => void
  onDone: () => void
}) {
  const [step, setStep] = useState<PushStep>('review')
  const [items, setItems] = useState<ActionItem[]>(() => parseActionItems(taskListJson))
  const [workstreams, setWorkstreams] = useState<TaskItem[]>([])
  const [loadingWorkstreams, setLoadingWorkstreams] = useState(true)
  const [error, setError] = useState('')
  const [doneCount, setDoneCount] = useState(0)
  const [failCount, setFailCount] = useState(0)

  useEffect(() => {
    let active = true
    fetchTasks(projectId)
      .then((result) => { if (active) setWorkstreams(result) })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : String(reason)) })
      .finally(() => { if (active) setLoadingWorkstreams(false) })
    return () => { active = false }
  }, [projectId])

  const selectedItems = useMemo(() => items.filter((item) => item.selected), [items])
  const missingTargets = selectedItems.some((item) => !item.targetTaskId)

  function updateItem(id: string, patch: Partial<ActionItem>) {
    setItems((previous) => previous.map((item) => item.id === id ? { ...item, ...patch } : item))
  }

  async function handlePush() {
    if (!selectedItems.length || missingTargets) return
    setStep('executing')
    setError('')
    let succeeded = 0
    let failed = 0

    for (const selected of selectedItems) {
      updateItem(selected.id, { executing: true, error: '' })
      try {
        const note = selected.source ? `会议待办：${selected.source}` : '会议待办'
        if (selected.targetTaskId === '__new__') {
          await createTask({
            project_id: projectId,
            key_task: selected.title,
            owner: selected.owner,
            plan_time: selected.dueDate,
            status: '未开始',
            problem_note: note,
          })
        } else {
          await apiPost(`/api/tasks/${selected.targetTaskId}/subtasks`, {
            title: selected.title,
            assignee: selected.owner,
            plan_time: selected.dueDate,
            status: '未开始',
            notes: note,
          })
        }
        succeeded += 1
        updateItem(selected.id, { executing: false, done: true })
      } catch (reason: unknown) {
        failed += 1
        updateItem(selected.id, { executing: false, error: reason instanceof Error ? reason.message : String(reason) })
      }
      setDoneCount(succeeded)
      setFailCount(failed)
    }
    setStep('done')
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50" onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div className="flex max-h-[88vh] w-[760px] max-w-[calc(100vw-32px)] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <header className="flex items-start justify-between border-b border-slate-100 px-6 py-5">
          <div>
            <h2 className="text-base font-semibold text-slate-900">推送待办到工作推进</h2>
            <p className="mt-1 text-sm text-slate-500">选择已确认待办的归属重点工作；系统只创建任务，不再分析发言人或生成 AI 卡片。</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" aria-label="关闭">×</button>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          {!items.length ? (
            <div className="rounded-xl border border-dashed border-slate-200 py-12 text-center text-sm text-slate-400">无待办事项可推送</div>
          ) : (
            <div className="space-y-3">
              {items.map((item, index) => (
                <section key={item.id} className={`rounded-xl border p-4 ${item.done ? 'border-emerald-200 bg-emerald-50/50' : item.error ? 'border-red-200 bg-red-50/50' : 'border-slate-200'}`}>
                  <div className="flex gap-3">
                    <input aria-label={`选择待办 ${index + 1}`} type="checkbox" checked={item.selected} disabled={step !== 'review'} onChange={(event) => updateItem(item.id, { selected: event.target.checked })} className="mt-1 h-4 w-4 accent-sky-600" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-medium text-slate-800">{item.title}</p>
                        {item.done && <span className="text-xs font-medium text-emerald-600">已推送</span>}
                        {item.executing && <span className="text-xs text-sky-600">推送中…</span>}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500">
                        <span>负责人：{item.owner || '未填写'}</span>
                        <span>完成时间：{item.dueDate || '未填写'}</span>
                        {item.source && <span>说明：{item.source}</span>}
                      </div>
                      {step === 'review' && (
                        <label className="mt-4 block text-xs font-medium text-slate-600">
                          归属重点工作
                          <select value={item.targetTaskId} onChange={(event) => updateItem(item.id, { targetTaskId: event.target.value })} disabled={!item.selected || loadingWorkstreams} className="mt-1.5 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal text-slate-700 outline-none focus:border-sky-400 disabled:bg-slate-50">
                            <option value="">请选择</option>
                            <option value="__new__">新建重点工作</option>
                            {workstreams.map((workstream) => <option key={workstream.id} value={String(workstream.id)}>{workstream.key_task}</option>)}
                          </select>
                        </label>
                      )}
                      {item.error && <p className="mt-3 text-xs text-red-600">推送失败：{item.error}</p>}
                    </div>
                  </div>
                </section>
              ))}
            </div>
          )}
          {error && <div className="mt-4"><ErrorBar msg={error} /></div>}
        </main>

        <footer className="flex items-center justify-between border-t border-slate-100 px-6 py-4">
          <button onClick={onClose} className="rounded-lg px-3 py-2 text-sm text-slate-500 hover:bg-slate-100">{step === 'done' ? '关闭' : '取消'}</button>
          {step === 'review' && <button onClick={() => void handlePush()} disabled={!selectedItems.length || missingTargets || loadingWorkstreams} className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40">推送 {selectedItems.length} 项待办</button>}
          {step === 'done' && <button onClick={onDone} className="rounded-lg bg-sky-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-sky-700">完成</button>}
        </footer>
      </div>
    </div>
  )
}
