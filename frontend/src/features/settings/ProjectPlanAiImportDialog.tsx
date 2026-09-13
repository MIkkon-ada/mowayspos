import { useMemo, useRef, useState } from 'react'
import type { Project } from '../../types'
import type { BatchImportResult, BatchImportRow } from '../../api/projects'
import {
  applyAiProjectPlan,
  previewAiProjectPlan,
  type ProjectPlanAiPreview,
} from '../../api/projectPlanAiImport'
import { draftToBatchImportRows } from './projectPlanAiImportDraft'

type Phase = 'idle' | 'reading' | 'analyzing' | 'review' | 'importing' | 'success' | 'error'

type Props = {
  open: boolean
  projects: Project[]
  onClose: () => void
  onImported: (result: BatchImportResult) => void
}

function editRow(rows: BatchImportRow[], index: number, field: keyof BatchImportRow, value: string): BatchImportRow[] {
  return rows.map((row, rowIndex) => rowIndex === index ? { ...row, [field]: value } : row)
}

export function ProjectPlanAiImportDialog({ open, projects, onClose, onImported }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [projectName, setProjectName] = useState('')
  const [targetProjectId, setTargetProjectId] = useState('')
  const [preview, setPreview] = useState<ProjectPlanAiPreview | null>(null)
  const [rows, setRows] = useState<BatchImportRow[]>([])
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState('')

  const busy = phase === 'reading' || phase === 'analyzing' || phase === 'importing'
  const workstreamCount = useMemo(() => new Set(rows.map((row) => `${row.project_name}::${row.workstream ?? ''}`)).size, [rows])
  const selectedProject = projects.find((item) => String(item.id) === targetProjectId)

  function reset() {
    setFile(null)
    setText('')
    setProjectName('')
    setTargetProjectId('')
    setPreview(null)
    setRows([])
    setPhase('idle')
    setError('')
  }

  function close() {
    if (busy) return
    reset()
    onClose()
  }

  function selectFile(nextFile: File | null) {
    if (!nextFile) return
    setFile(nextFile)
    setText('')
    setPreview(null)
    setRows([])
    setError('')
    setPhase('idle')
  }

  async function analyze() {
    const source = file ?? (text.trim() ? new File([text], '粘贴的工作计划.tsv', { type: 'text/tab-separated-values' }) : null)
    if (!source) {
      setError('请先选择文件或粘贴工作计划内容')
      setPhase('error')
      return
    }
    setError('')
    setPhase('reading')
    try {
      setPhase('analyzing')
      const result = await previewAiProjectPlan(source, {
        projectName: projectName.trim(),
        targetProjectId: targetProjectId ? Number(targetProjectId) : undefined,
      })
      const normalized = draftToBatchImportRows(result, selectedProject?.name || projectName)
      setPreview(result)
      setRows(normalized)
      setPhase('review')
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'AI 分析失败，请检查文件后重试')
      setPhase('error')
    }
  }

  async function confirmImport() {
    if (!rows.length || rows.some((row) => !row.project_name.trim() || !row.workstream?.trim() || !row.key_task.trim())) {
      setError('项目、重点工作和关键任务不能为空')
      setPhase('error')
      return
    }
    setPhase('importing')
    setError('')
    try {
      const result = await applyAiProjectPlan(rows)
      setPhase('success')
      onImported(result)
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '导入失败，请检查后重试')
      setPhase('error')
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-3" onClick={close}>
      <div className="flex max-h-[92vh] w-[min(1180px,96vw)] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <header className="flex items-start justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-bold text-slate-800">
              AI 工作计划导入
              <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700">智能识别</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">支持 Excel、CSV、TSV 和复制粘贴；表名和表头不需要固定。</p>
          </div>
          <button type="button" onClick={close} disabled={busy} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 disabled:opacity-40" aria-label="关闭">
            <svg style={{ width: 15, height: 15 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </header>

        <main className="flex-1 space-y-4 overflow-y-auto px-6 py-4">
          <div className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-[1fr_1fr]">
            <label className="text-xs font-semibold text-slate-600">
              导入到已有项目（可选）
              <select value={targetProjectId} onChange={(event) => { setTargetProjectId(event.target.value); setPreview(null); setRows([]) }} disabled={busy} className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal text-slate-700 outline-none focus:border-sky-400">
                <option value="">AI 自动识别或新建项目</option>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-600">
              新项目名称（可选）
              <input value={projectName} onChange={(event) => setProjectName(event.target.value)} disabled={busy || Boolean(targetProjectId)} placeholder="未填写时由 AI 从材料中提取" className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal text-slate-700 outline-none focus:border-sky-400 disabled:bg-slate-100" />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-[0.9fr_1.1fr]">
            <section className="rounded-xl border border-slate-200 p-4">
              <div className="flex items-center justify-between">
                <div className="text-xs font-bold text-slate-700">1. 提供工作计划</div>
                <button type="button" onClick={() => fileInputRef.current?.click()} disabled={busy} className="rounded-lg border border-sky-200 px-3 py-1.5 text-xs font-semibold text-sky-700 hover:bg-sky-50 disabled:opacity-40">选择文件</button>
                <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv,.tsv,.txt,.docx,.doc,.pdf" className="hidden" onChange={(event) => selectFile(event.target.files?.[0] ?? null)} />
              </div>
              <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">{file ? `已选择：${file.name}` : '也可以直接粘贴 Excel 内容'}</div>
              <textarea value={text} onChange={(event) => { setText(event.target.value); setFile(null); setPreview(null); setRows([]) }} disabled={busy} placeholder="粘贴表格内容，AI 会自动识别表头、重点工作和关键任务" className="mt-3 h-48 w-full resize-none rounded-lg border border-slate-200 p-3 font-mono text-xs outline-none focus:border-sky-400 disabled:bg-slate-50" />
              <button type="button" onClick={() => void analyze()} disabled={busy || (!file && !text.trim())} className="mt-3 w-full rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40">
                {phase === 'reading' ? '读取文件…' : phase === 'analyzing' ? 'AI 分析中…' : '开始 AI 分析'}
              </button>
            </section>

            <section className="rounded-xl border border-slate-200 p-4">
              <div className="text-xs font-bold text-slate-700">2. AI 识别结果</div>
              {!preview && phase !== 'error' && <div className="mt-3 rounded-lg border border-dashed border-slate-200 px-4 py-8 text-center text-xs text-slate-400">分析后将在这里预览项目、重点工作和关键任务</div>}
              {preview && (
                <>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full bg-emerald-50 px-2 py-1 font-semibold text-emerald-700">{preview.fallback_mode === 'ai' ? `AI：${preview.model_name || '已配置模型'}` : '规则兜底：待人工核对'}</span>
                    {preview.source_files.map((source) => <span key={source} className="rounded-full bg-slate-100 px-2 py-1 text-slate-500">{source}</span>)}
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="rounded-lg bg-slate-50 px-2 py-2"><strong className="block text-base text-slate-800">{new Set(rows.map((row) => row.project_name)).size}</strong>项目</div>
                    <div className="rounded-lg bg-slate-50 px-2 py-2"><strong className="block text-base text-slate-800">{workstreamCount}</strong>重点工作</div>
                    <div className="rounded-lg bg-slate-50 px-2 py-2"><strong className="block text-base text-slate-800">{rows.length}</strong>关键任务</div>
                  </div>
                  {preview.warnings.length > 0 && <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">AI 提示 {preview.warnings.length} 项需要人工核对：{preview.warnings.slice(0, 2).map((warning) => warning.message).join('；')}</div>}
                </>
              )}
            </section>
          </div>

          {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">{error}</div>}

          {rows.length > 0 && (
            <section className="rounded-xl border border-slate-200">
              <div className="border-b border-slate-200 px-4 py-3 text-xs font-bold text-slate-700">3. 确认并修正导入内容</div>
              <div className="max-h-[34vh] overflow-auto">
                <table className="w-full min-w-[980px] text-xs">
                  <thead className="sticky top-0 bg-slate-50 text-left text-slate-500">
                    <tr>{['项目', '重点工作', '关键任务', '负责人', '状态', '计划时间', '备注/来源'].map((label) => <th key={label} className="whitespace-nowrap px-3 py-2 font-semibold">{label}</th>)}</tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => <tr key={`${row.workstream}-${row.key_task}-${index}`} className="border-t border-slate-100 align-top">
                      {(['project_name', 'workstream', 'key_task', 'owner', 'status', 'plan_time', 'notes'] as const).map((field) => <td key={field} className="px-2 py-1.5">
                        <input value={String(row[field] ?? '')} onChange={(event) => setRows((current) => editRow(current, index, field, event.target.value))} className="w-full min-w-[90px] rounded border border-transparent bg-transparent px-1 py-1 text-slate-700 outline-none hover:border-slate-200 focus:border-sky-300 focus:bg-white" />
                      </td>)}
                    </tr>)}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </main>

        <footer className="flex items-center justify-between border-t border-slate-200 px-6 py-4">
          <div className="text-xs text-slate-400">{phase === 'success' ? '导入已提交' : rows.length ? '确认后才会写入项目数据' : 'AI 只生成预览，不会直接写入数据库'}</div>
          <div className="flex gap-2">
            <button type="button" onClick={close} disabled={busy} className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 disabled:opacity-40">{phase === 'success' ? '关闭' : '取消'}</button>
            <button type="button" onClick={() => void confirmImport()} disabled={busy || !rows.length || phase !== 'review'} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40">{phase === 'importing' ? '导入中…' : `确认导入 ${rows.length || ''} 条`}</button>
          </div>
        </footer>
      </div>
    </div>
  )
}
