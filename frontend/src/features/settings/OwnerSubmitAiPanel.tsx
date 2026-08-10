import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import {
  createInitAnalysisRun,
  deleteInitAttachment,
  downloadInitAttachmentUrl,
  getInitAnalysisRun,
  getLatestInitAnalysisRun,
  listInitAttachments,
  ProjectInitApiError,
  retryInitAnalysisRun,
  type AgentSubTask,
  type AgentTask,
  type ProjectInitAiDraft,
  type ProjectInitAnalysisRun,
  type ProjectInitAttachment,
  type ProjectInitCurrentDraft,
  type ProjectInitDraft,
  uploadInitAttachments,
} from '../../api/projectInitAi'

const MAX_FILE_BYTES = 25 * 1024 * 1024
const MAX_FILES = 10
const MAX_TOTAL_BYTES = 100 * 1024 * 1024
const POLL_INTERVAL_MS = 1500
const ACCEPTED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt'] as const

type PanelState = 'idle' | 'uploading' | 'analyzing' | 'preview' | 'failed'
type UploadStatus = 'queued' | 'uploading' | 'success' | 'failed' | 'cancelled'
export type ProjectInitAiDecisionAction = 'merge' | 'keep' | 'skip' | 'confirm'

export type ProjectInitAiDecision = {
  key: string
  action: ProjectInitAiDecisionAction
  itemType: 'task' | 'subtask'
  taskIndex: number
  subtaskIndex?: number
  title: string
}

type UploadItem = {
  id: string
  file: File
  status: UploadStatus
  progress: number
  error: string
  attachment?: ProjectInitAttachment
}

export type OwnerSubmitAiPanelProps = {
  projectId: number
  currentDraft: ProjectInitCurrentDraft
  existingAttachments?: ProjectInitAttachment[]
  onApplyDraft: (draft: ProjectInitAiDraft, decisions: ProjectInitAiDecision[]) => void | Promise<void>
  onClose?: () => void
  disabled?: boolean
}

function isTerminal(status: ProjectInitAnalysisRun['status'] | undefined): boolean {
  return status === 'completed' || status === 'partial_failed' || status === 'failed'
}

function isAiDraft(draft: ProjectInitDraft): draft is ProjectInitAiDraft {
  return !Array.isArray(draft) && Array.isArray(draft.tasks)
}

function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function errorMessage(error: unknown): string {
  if (error instanceof ProjectInitApiError) return error.detail
  if (error instanceof Error) return error.message
  return '操作失败，请稍后重试'
}

function statusLabel(status: ProjectInitAnalysisRun['status']): string {
  return {
    queued: '排队中',
    processing: '处理中',
    retrying: '重试中',
    completed: '已完成',
    partial_failed: '部分失败',
    failed: '失败',
  }[status]
}

function stageLabel(stage: ProjectInitAnalysisRun['stage']): string {
  return {
    reading: '读取文件',
    parsing: '提取结构',
    extracting: '生成草稿',
    matching: '匹配人员',
    merging: '合并结果',
    retrying: '重试中',
    completed: '已完成',
    failed: '分析失败',
    stale: '已中断',
  }[stage]
}

function duplicateLabel(status: AgentTask['merge_status']): string {
  if (status === 'definite_duplicate') return '确定重复'
  if (status === 'possible_duplicate') return '疑似重复'
  return '新增候选'
}

function warningText(task: AgentTask | AgentSubTask): string[] {
  return task.warnings
    .filter((warning) => /ambiguous|inactive|unmatched|person_not_found/i.test(`${warning.code} ${warning.message}`))
    .map((warning) => warning.message)
}

function sourceLabel(task: AgentTask | AgentSubTask): string {
  return task.source || 'AI 分析结果'
}

function EvidenceList({
  projectId,
  evidence,
  sourceLabel,
}: {
  projectId: number
  evidence: AgentTask['evidence']
  sourceLabel: string
}) {
  if (evidence.length === 0) return <p className="text-xs text-slate-400">暂无来源证据</p>
  return (
    <ul className="space-y-1.5" aria-label="来源证据">
      {evidence.map((item, index) => (
        <li key={`${item.file_name}-${item.location}-${index}`} className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <div className="flex flex-wrap items-center gap-2 font-semibold text-slate-700">
            {item.attachment_id ? (
              <button
                type="button"
                className="text-blue-700 underline underline-offset-2 hover:text-blue-900"
                onClick={() => window.open(downloadInitAttachmentUrl(projectId, item.attachment_id as number), '_blank', 'noopener,noreferrer')}
              >
                {item.file_name}
              </button>
            ) : <span>{item.file_name}</span>}
            <span className="font-normal text-slate-400">{item.location}</span>
            <span className="rounded bg-white px-1.5 py-0.5 text-[10px] text-slate-400">source_label: {sourceLabel || item.file_name}</span>
            <span className="rounded bg-white px-1.5 py-0.5 text-[10px] text-slate-400">attachment_id: {item.attachment_id ?? '—'}</span>
          </div>
          <p className="mt-1 line-clamp-3 leading-5">quote: {item.excerpt}</p>
        </li>
      ))}
    </ul>
  )
}

function DecisionButtons({
  value,
  disabled,
  onChange,
}: {
  value?: ProjectInitAiDecisionAction
  disabled?: boolean
  onChange: (value: ProjectInitAiDecisionAction) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="候选项处理决定">
      {(['merge', 'keep', 'skip', 'confirm'] as const).map((action) => (
        <button
          key={action}
          type="button"
          disabled={disabled}
          aria-pressed={value === action}
          onClick={() => onChange(action)}
          className={`rounded-md border px-2 py-1 text-[11px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${value === action ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:bg-blue-50'}`}
        >
          {{ merge: '合并', keep: '保留', skip: '跳过', confirm: '确认' }[action]}
        </button>
      ))}
    </div>
  )
}

export function OwnerSubmitAiPanel({
  projectId,
  currentDraft,
  existingAttachments,
  onApplyDraft,
  onClose,
  disabled = false,
}: OwnerSubmitAiPanelProps) {
  const [panelState, setPanelState] = useState<PanelState>('idle')
  const [queue, setQueue] = useState<UploadItem[]>([])
  const [attachments, setAttachments] = useState<ProjectInitAttachment[]>(() => existingAttachments ?? [])
  const [run, setRun] = useState<ProjectInitAnalysisRun>()
  const [draft, setDraft] = useState<ProjectInitAiDraft>()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [decisions, setDecisions] = useState<Record<string, ProjectInitAiDecisionAction>>({})
  const mountedRef = useRef(true)
  const pollInFlightRef = useRef(false)
  const uploadControllerRef = useRef<AbortController | undefined>(undefined)

  const successfulAttachmentIds = useMemo(
    () => queue.flatMap((item) => item.attachment ? [item.attachment.id] : []),
    [queue],
  )

  const updateRun = useCallback((nextRun: ProjectInitAnalysisRun) => {
    if (!mountedRef.current) return
    setRun(nextRun)
    if (isAiDraft(nextRun.draft)) setDraft(nextRun.draft)
    setPanelState(nextRun.status === 'failed' ? 'failed' : isTerminal(nextRun.status) ? 'preview' : 'analyzing')
    setError(nextRun.status === 'failed' ? nextRun.error_message : '')
  }, [])

  const pollRun = useCallback(async () => {
    if (!run || isTerminal(run.status) || pollInFlightRef.current) return
    pollInFlightRef.current = true
    try {
      updateRun(await getInitAnalysisRun(projectId, run.id))
    } catch (nextError) {
      if (mountedRef.current) setError(errorMessage(nextError))
    } finally {
      pollInFlightRef.current = false
    }
  }, [projectId, run, updateRun])

  useEffect(() => {
    mountedRef.current = true
    let cancelled = false
    setLoading(true)
    Promise.all([
      listAttachmentsSafely(projectId, existingAttachments ?? []),
      getLatestInitAnalysisRun(projectId).catch((nextError) => {
        if (nextError instanceof ProjectInitApiError && nextError.status === 404) return undefined
        throw nextError
      }),
    ])
      .then(([nextAttachments, latestRun]) => {
        if (cancelled || !mountedRef.current) return
        setAttachments(nextAttachments)
        if (latestRun) updateRun(latestRun)
        else setPanelState('idle')
      })
      .catch((nextError) => {
        if (!cancelled && mountedRef.current) {
          setError(errorMessage(nextError))
          setPanelState('failed')
        }
      })
      .finally(() => {
        if (!cancelled && mountedRef.current) setLoading(false)
      })
    return () => {
      cancelled = true
      mountedRef.current = false
      uploadControllerRef.current?.abort()
    }
  }, [existingAttachments, projectId, updateRun])

  useEffect(() => {
    if (!run || isTerminal(run.status)) return undefined
    const timer = window.setInterval(() => { void pollRun() }, POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [pollRun, run])

  function addFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (selected.length === 0) return
    const nextQueue = [...queue]
    const totalExisting = nextQueue.reduce((sum, item) => sum + item.file.size, 0)
    let total = totalExisting
    for (const file of selected) {
      const extension = extensionOf(file.name)
      let itemError = ''
      if (!ACCEPTED_EXTENSIONS.includes(extension as typeof ACCEPTED_EXTENSIONS[number])) itemError = '文件类型不支持'
      else if (file.size > MAX_FILE_BYTES) itemError = '单文件不能超过 25 MiB'
      else if (nextQueue.length >= MAX_FILES) itemError = '最多选择 10 个文件'
      else if (total + file.size > MAX_TOTAL_BYTES) itemError = '文件总大小不能超过 100 MiB'
      if (!itemError) total += file.size
      nextQueue.push({ id: `${file.name}-${file.lastModified}-${Math.random()}`, file, status: itemError ? 'failed' : 'queued', progress: 0, error: itemError })
    }
    setQueue(nextQueue.slice(0, MAX_FILES))
    setError('')
  }

  function updateQueueItem(id: string, patch: Partial<UploadItem>) {
    if (!mountedRef.current) return
    setQueue((items) => items.map((item) => item.id === id ? { ...item, ...patch } : item))
  }

  async function removeItem(item: UploadItem) {
    if (item.attachment) {
      try {
        await deleteInitAttachment(projectId, item.attachment.id)
        setAttachments((items) => items.filter((attachment) => attachment.id !== item.attachment?.id))
      } catch (nextError) {
        setError(errorMessage(nextError))
        return
      }
    }
    setQueue((items) => items.filter((current) => current.id !== item.id))
  }

  async function startAnalysis() {
    const pending = queue.filter((item) => item.status === 'queued' || item.status === 'failed' && !item.attachment)
    if (pending.length === 0 && successfulAttachmentIds.length === 0) {
      setError('请先选择至少一个有效文件')
      return
    }
    setError('')
    setPanelState('uploading')
    const controller = new AbortController()
    uploadControllerRef.current = controller
    const uploadedIds = [...successfulAttachmentIds]
    try {
      for (const item of pending) {
        if (controller.signal.aborted) return
        updateQueueItem(item.id, { status: 'uploading', progress: 0, error: '' })
        try {
          const uploaded = await uploadInitAttachments(projectId, [item.file], (progress) => updateQueueItem(item.id, { progress }), controller.signal)
          const attachment = uploaded[0]
          if (!attachment) throw new Error('上传响应缺少附件')
          uploadedIds.push(attachment.id)
          setAttachments((items) => [...items.filter((current) => current.id !== attachment.id), attachment])
          updateQueueItem(item.id, { status: 'success', progress: 100, attachment })
        } catch (nextError) {
          if (nextError instanceof DOMException && nextError.name === 'AbortError') {
            updateQueueItem(item.id, { status: 'cancelled', error: '已取消' })
            return
          }
          updateQueueItem(item.id, { status: 'failed', error: errorMessage(nextError) })
        }
      }
      if (uploadedIds.length === 0) {
        setPanelState('failed')
        setError('没有可用于分析的已上传文件')
        return
      }
      const nextRun = await createInitAnalysisRun(projectId, uploadedIds, currentDraft)
      updateRun(nextRun)
    } catch (nextError) {
      if (nextError instanceof DOMException && nextError.name === 'AbortError') return
      setError(errorMessage(nextError))
      setPanelState('failed')
    } finally {
      uploadControllerRef.current = undefined
    }
  }

  async function retryAnalysis() {
    if (!run || run.status !== 'failed') return
    setError('')
    setPanelState('analyzing')
    try {
      updateRun(await retryInitAnalysisRun(projectId, run.id))
    } catch (nextError) {
      setError(errorMessage(nextError))
      setPanelState('failed')
    }
  }

  function setDecision(key: string, action: ProjectInitAiDecisionAction) {
    setDecisions((current) => ({ ...current, [key]: action }))
  }

  function applyDraft() {
    if (!draft) return
    const selected: ProjectInitAiDecision[] = []
    draft.tasks.forEach((task, taskIndex) => {
      const taskKey = `task-${taskIndex}`
      if (decisions[taskKey]) selected.push({ key: taskKey, action: decisions[taskKey], itemType: 'task', taskIndex, title: task.title })
      task.subtasks.forEach((subtask, subtaskIndex) => {
        const key = `${taskKey}-subtask-${subtaskIndex}`
        if (decisions[key]) selected.push({ key, action: decisions[key], itemType: 'subtask', taskIndex, subtaskIndex, title: subtask.title })
      })
    })
    if (selected.length === 0) {
      setError('请至少为一个候选项选择处理方式')
      return
    }
    void onApplyDraft(draft, selected)
  }

  const renderWarnings = (item: AgentTask | AgentSubTask) => {
    const warnings = warningText(item)
    if (warnings.length === 0) return null
    return <div role="alert" className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">{warnings.join('；')}（未自动绑定）</div>
  }

  if (loading) return <section aria-busy="true" className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">正在加载 AI 分析状态…</section>

  return (
    <section aria-labelledby="owner-submit-ai-title" className="space-y-4 rounded-2xl border border-blue-100 bg-white p-5 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="owner-submit-ai-title" className="text-base font-bold text-slate-900">AI 从文件生成</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">上传项目资料，读取文件、提取结构、匹配人员并生成草稿。AI 只提供预览，不会直接修改项目。</p>
        </div>
        {onClose && <button type="button" onClick={onClose} disabled={disabled || panelState === 'uploading'} className="rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 disabled:opacity-50" aria-label="关闭 AI 文件面板">关闭</button>}
      </header>

      {error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      {(panelState === 'idle' || panelState === 'uploading') && (
        <div className="space-y-3">
          <label htmlFor="owner-submit-ai-files" className="block cursor-pointer rounded-xl border-2 border-dashed border-blue-200 bg-blue-50/50 p-5 text-center hover:border-blue-400">
            <span className="block text-sm font-semibold text-blue-800">选择资料文件</span>
            <span className="mt-1 block text-xs text-blue-600">PDF、DOC、DOCX、XLS、XLSX、TXT；单个不超过 25 MiB</span>
            <input id="owner-submit-ai-files" type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.txt" onChange={addFiles} disabled={disabled || panelState === 'uploading'} className="sr-only" aria-describedby="owner-submit-ai-file-help" />
          </label>
          <p id="owner-submit-ai-file-help" className="text-xs text-slate-400">最多 10 个文件，合计不超过 100 MiB。文件内容通过上传接口发送，不会放入 JSON。</p>
          {queue.length > 0 && <ul className="space-y-2" aria-label="文件上传队列">{queue.map((item) => (
            <li key={item.id} className="rounded-xl border border-slate-200 p-3">
              <div className="flex items-center gap-3">
                <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-700">{item.file.name}</span>
                <span className="shrink-0 text-xs text-slate-400">{formatBytes(item.file.size)}</span>
                <span className={`shrink-0 text-xs ${item.status === 'failed' ? 'text-red-600' : item.status === 'success' ? 'text-emerald-600' : 'text-slate-500'}`}>{item.status === 'uploading' ? `${item.progress}%` : item.status === 'success' ? '已上传' : item.status === 'failed' ? '失败' : item.status === 'cancelled' ? '已取消' : '待上传'}</span>
                {item.status === 'uploading' ? (
                  <button type="button" onClick={() => uploadControllerRef.current?.abort()} className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50" aria-label={`取消上传 ${item.file.name}`}>取消</button>
                ) : (
                  <button type="button" onClick={() => void removeItem(item)} className="rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100" aria-label={`移除 ${item.file.name}`}>移除</button>
                )}
              </div>
              {(item.status === 'uploading' || item.status === 'success') && <progress className="mt-2 h-1.5 w-full" max={100} value={item.progress} aria-label={`${item.file.name} 上传进度`} />}
              {item.error && <p className="mt-1 text-xs text-red-600">{item.error}</p>}
            </li>
          ))}</ul>}
          {attachments.length > 0 && <p className="text-xs text-slate-500">已有附件：{attachments.map((attachment) => attachment.original_name).join('、')}</p>}
          <button type="button" onClick={() => void startAnalysis()} disabled={disabled || panelState === 'uploading' || queue.every((item) => item.status === 'failed')} className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">{panelState === 'uploading' ? '上传中…' : '开始分析'}</button>
        </div>
      )}

      {panelState === 'analyzing' && run && (
        <div className="space-y-4 rounded-xl bg-slate-50 p-4" aria-live="polite">
          <div className="flex items-center justify-between gap-3"><span className="text-sm font-semibold text-slate-800">{stageLabel(run.stage)}</span><span className="text-xs text-slate-500">{statusLabel(run.status)} · {run.progress}%</span></div>
          <progress className="h-2 w-full" max={100} value={run.progress} aria-label="AI 分析进度" />
          <p className="text-xs text-slate-500">分析会自动轮询最新进度，请不要关闭此面板。</p>
        </div>
      )}

      {panelState === 'failed' && run && (
        <div className="space-y-3 rounded-xl border border-red-100 bg-red-50 p-4"><p className="text-sm font-semibold text-red-800">分析失败</p><p className="text-xs text-red-700">{run.error_message || error || '未能生成草稿'}</p><button type="button" onClick={() => void retryAnalysis()} disabled={disabled} className="rounded-lg bg-red-600 px-3 py-2 text-xs font-bold text-white hover:bg-red-700 disabled:opacity-50">重新分析</button></div>
      )}

      {panelState === 'preview' && run && draft && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 p-3"><div><span className="text-sm font-semibold text-slate-800">{stageLabel(run.stage)}</span><span className="ml-2 text-xs text-slate-500">{statusLabel(run.status)} · {run.progress}%</span></div><span className="text-xs text-slate-500">{draft.tasks.length} 项重点工作待确认</span></div>
          {run.status === 'partial_failed' && <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">部分文件分析失败，下面仅展示已成功生成的结果。</div>}
          {draft.tasks.length === 0 && <p className="rounded-xl border border-slate-200 p-4 text-sm text-slate-500">暂无可预览草稿。</p>}
          <div className="space-y-3">{draft.tasks.map((task, taskIndex) => {
            const taskKey = `task-${taskIndex}`
            return <article key={taskKey} className="rounded-xl border border-slate-200 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-bold text-slate-900">{task.title}</h3><p className="mt-1 text-xs text-slate-600">{task.description || '暂无描述'}</p><p className="mt-1 text-xs text-slate-500">负责人：{task.owner_name || '未匹配'} · 时间：{task.plan_start || '—'} 至 {task.plan_end || '—'} · 状态：{task.status || '—'} · 优先级：{task.priority || '—'}</p></div><div className="text-right"><span className="rounded-full bg-blue-50 px-2 py-1 text-[11px] font-semibold text-blue-700">{duplicateLabel(task.merge_status)}</span><DecisionButtons value={decisions[taskKey]} disabled={disabled} onChange={(action) => setDecision(taskKey, action)} /></div></div>
              {renderWarnings(task)}
              <div className="mt-3"><p className="mb-1 text-xs font-semibold text-slate-500">来源证据</p><EvidenceList projectId={projectId} evidence={task.evidence} sourceLabel={sourceLabel(task)} /></div>
              <div className="mt-4 space-y-2 border-l-2 border-slate-100 pl-3"><p className="text-xs font-semibold text-slate-500">关键任务 / 子任务</p>{task.subtasks.map((subtask, subtaskIndex) => { const key = `${taskKey}-subtask-${subtaskIndex}`; return <div key={key} className="rounded-lg border border-slate-100 p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-xs font-semibold text-slate-800">{subtask.title}</p><p className="mt-1 text-[11px] text-slate-500">负责人：{subtask.assignee_name || '未匹配'} · 协助人：{subtask.helper_names.join('、') || '—'} · 时间：{subtask.plan_start || '—'} 至 {subtask.plan_end || '—'}</p><p className="mt-1 text-[11px] text-slate-500">状态：{subtask.status || '—'} · 优先级：{subtask.priority || '—'}</p></div><div className="space-y-1 text-right"><span className="block rounded-full bg-slate-50 px-2 py-1 text-[10px] text-slate-600">{duplicateLabel(subtask.merge_status)}</span><DecisionButtons value={decisions[key]} disabled={disabled} onChange={(action) => setDecision(key, action)} /></div></div>{renderWarnings(subtask)}<div className="mt-2"><EvidenceList projectId={projectId} evidence={subtask.evidence} sourceLabel={sourceLabel(subtask)} /></div></div> })}</div>
            </article>
          })}</div>
          <button type="button" onClick={applyDraft} disabled={disabled || Object.keys(decisions).length === 0} className="w-full rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">应用到推进表</button>
        </div>
      )}
    </section>
  )
}

async function listAttachmentsSafely(projectId: number, fallback: ProjectInitAttachment[]): Promise<ProjectInitAttachment[]> {
  try {
    return await listInitAttachments(projectId)
  } catch (nextError) {
    if (nextError instanceof ProjectInitApiError && nextError.status === 404) return fallback
    throw nextError
  }
}
