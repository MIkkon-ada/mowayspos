import { useMemo, useRef, useState } from 'react'
import type { Project } from '../../types'
import type { BatchImportResult, BatchImportRow } from '../../api/projects'
import {
  applyAiProjectPlan,
  previewAiProjectPlan,
  type ProjectPlanAiPreview,
} from '../../api/projectPlanAiImport'
import { draftToBatchImportRows } from './projectPlanAiImportDraft'
import { groupImportRows } from './projectPlanAiImportView'

type Phase = 'idle' | 'reading' | 'analyzing' | 'review' | 'importing' | 'success' | 'error'
type SourceMode = 'upload' | 'paste'

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
  const [sourceMode, setSourceMode] = useState<SourceMode>('upload')
  const [projectName, setProjectName] = useState('')
  const [targetProjectId, setTargetProjectId] = useState('')
  const [preview, setPreview] = useState<ProjectPlanAiPreview | null>(null)
  const [rows, setRows] = useState<BatchImportRow[]>([])
  const [phase, setPhase] = useState<Phase>('idle')
  const [expandedRow, setExpandedRow] = useState<number | null>(null)
  const [error, setError] = useState('')

  const busy = phase === 'reading' || phase === 'analyzing' || phase === 'importing'
  const groups = useMemo(() => groupImportRows(rows), [rows])
  const projectCount = useMemo(() => new Set(rows.map((row) => row.project_name)).size, [rows])
  const selectedProject = projects.find((item) => String(item.id) === targetProjectId)

  function reset() {
    setFile(null)
    setText('')
    setSourceMode('upload')
    setProjectName('')
    setTargetProjectId('')
    setPreview(null)
    setRows([])
    setExpandedRow(null)
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
    setExpandedRow(null)
    setError('')
    setPhase('idle')
  }

  function switchSourceMode(nextMode: SourceMode) {
    setSourceMode(nextMode)
    setFile(null)
    setText('')
    setPreview(null)
    setRows([])
    setExpandedRow(null)
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
      setExpandedRow(null)
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
      <div className="flex max-h-[92vh] w-[min(760px,96vw)] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <header className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <div className="text-base font-bold text-slate-800">导入工作计划</div>
            <p className="mt-1 text-xs text-slate-500">表名和表头不需要固定，AI 会先识别，再由你确认写入。</p>
          </div>
          <button type="button" onClick={close} disabled={busy} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 disabled:opacity-40" aria-label="关闭">
            <svg style={{ width: 15, height: 15 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </header>

        <main className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <section className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <div className="mb-2 text-xs font-semibold text-slate-600">导入位置</div>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="text-xs text-slate-500">
                已有项目（可选）
                <select value={targetProjectId} onChange={(event) => { setTargetProjectId(event.target.value); setPreview(null); setRows([]) }} disabled={busy} className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-sky-400">
                  <option value="">AI 自动识别或新建项目</option>
                  {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                </select>
              </label>
              <label className="text-xs text-slate-500">
                新项目名称（可选）
                <input value={projectName} onChange={(event) => setProjectName(event.target.value)} disabled={busy || Boolean(targetProjectId)} placeholder="留空则从材料中识别" className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-sky-400 disabled:bg-slate-100" />
              </label>
            </div>
          </section>

          {phase !== 'review' && phase !== 'success' && (
            <section className="rounded-xl border border-slate-200 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-slate-800">提供工作计划</h2>
                  <p className="mt-1 text-xs text-slate-500">支持 Excel、CSV、TSV、文档和复制粘贴。</p>
                </div>
                <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
                  {([['upload', '上传文件'], ['paste', '粘贴表格']] as const).map(([mode, label]) => (
                    <button key={mode} type="button" aria-pressed={sourceMode === mode} onClick={() => switchSourceMode(mode)} disabled={busy} className={`rounded-md px-2.5 py-1.5 text-xs font-semibold ${sourceMode === mode ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {sourceMode === 'upload' ? (
                <button type="button" onClick={() => fileInputRef.current?.click()} disabled={busy} className="flex min-h-28 w-full flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 text-center hover:border-sky-300 hover:bg-sky-50 disabled:opacity-40">
                  <span className="text-sm font-semibold text-slate-700">{file ? file.name : '选择工作计划文件'}</span>
                  <span className="mt-1 text-xs text-slate-400">点击选择或拖入文件</span>
                </button>
              ) : (
                <textarea value={text} onChange={(event) => { setText(event.target.value); setFile(null); setPreview(null); setRows([]) }} disabled={busy} placeholder="粘贴表格内容，AI 会自动识别表头、重点工作和关键任务" aria-label="工作计划内容" className="h-28 w-full resize-none rounded-lg border border-slate-200 p-3 font-mono text-xs outline-none focus:border-sky-400 disabled:bg-slate-50" />
              )}
              <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv,.tsv,.txt,.docx,.doc,.pdf" aria-label="工作计划文件" className="hidden" onChange={(event) => selectFile(event.target.files?.[0] ?? null)} />
              <button type="button" onClick={() => void analyze()} disabled={busy || (!file && !text.trim())} className="mt-3 w-full rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40">
                {phase === 'reading' ? '读取文件…' : phase === 'analyzing' ? 'AI 分析中…' : '开始分析'}
              </button>
            </section>
          )}

          {preview && (
            <section className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-bold text-slate-800">{phase === 'review' ? '复核导入内容' : '导入结果'}</h2>
                  <p className="mt-1 text-xs text-slate-500">确认前不会写入项目数据。</p>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${preview.fallback_mode === 'ai' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                  {preview.fallback_mode === 'ai' ? 'AI 已识别' : '规则降级 · 请核对'}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span>{projectCount} 个项目</span><span className="text-slate-300">·</span><span>{groups.length} 项重点工作</span><span className="text-slate-300">·</span><span>{rows.length} 项关键任务</span>
                {preview.source_files.map((source) => <span key={source} className="rounded-full bg-slate-100 px-2 py-1">来源：{source}</span>)}
              </div>
              {preview.warnings.length > 0 && <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">有 {preview.warnings.length} 项需要人工核对：{preview.warnings.slice(0, 2).map((warning) => warning.message).join('；')}</div>}
            </section>
          )}

          {rows.length > 0 && (
            <section className="space-y-3">
              {groups.map((group) => (
                <div key={group.key} className="rounded-xl border border-slate-200 bg-white">
                  <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
                    <div>
                      <div className="text-sm font-bold text-slate-800">{group.workstream || '未识别重点工作'}</div>
                      <div className="mt-1 text-xs text-slate-500">{group.projectName} · {group.rows.length} 项关键任务</div>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-500">重点工作</span>
                  </div>
                  <div className="divide-y divide-slate-100">
                    {group.rows.map((row) => {
                      const index = rows.indexOf(row)
                      const isExpanded = expandedRow === index
                      return (
                        <div key={`${row.workstream}-${row.key_task}-${index}`} className="px-4 py-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-slate-800">{row.key_task}</div>
                              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                                <span>{row.owner || '未分配'}</span><span>{row.plan_time || '未设置时间'}</span><span>{row.status || '未开始'}</span>
                              </div>
                            </div>
                            <button type="button" onClick={() => setExpandedRow(isExpanded ? null : index)} className="shrink-0 rounded-md px-2 py-1 text-xs font-semibold text-sky-700 hover:bg-sky-50">{isExpanded ? '收起' : `编辑任务 ${row.key_task}`}</button>
                          </div>
                          {isExpanded && (
                            <div className="mt-3 grid gap-2 border-t border-slate-100 pt-3 sm:grid-cols-2">
                              {([['owner', '负责人'], ['status', '状态'], ['plan_start', '开始日期'], ['plan_end', '结束日期'], ['notes', '备注']] as const).map(([field, label]) => (
                                <label key={field} className="text-xs text-slate-500">
                                  {label}
                                  <input aria-label={`${label}：${row.key_task}`} value={String(row[field] ?? '')} onChange={(event) => setRows((current) => editRow(current, index, field, event.target.value))} className="mt-1 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm text-slate-700 outline-none focus:border-sky-400" />
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </section>
          )}

          {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">{error}</div>}
        </main>

        <footer className="flex items-center justify-between gap-3 border-t border-slate-200 px-5 py-3">
          <div className="text-xs text-slate-400">{phase === 'success' ? '导入已提交' : rows.length ? '确认后才会写入项目数据' : 'AI 只生成预览，不会直接写入数据库'}</div>
          <div className="flex gap-2">
            <button type="button" onClick={close} disabled={busy} className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 disabled:opacity-40">{phase === 'success' ? '关闭' : '取消'}</button>
            <button type="button" onClick={() => void confirmImport()} disabled={busy || !rows.length || phase !== 'review'} className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40">{phase === 'importing' ? '导入中…' : `确认导入${rows.length ? ` ${rows.length} 条` : ''}`}</button>
          </div>
        </footer>
      </div>
    </div>
  )
}
