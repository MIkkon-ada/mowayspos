import { useEffect, useMemo, useRef, useState } from 'react'
import type { Project, ProjectCloseCheckItem, ProjectCloseRequest, ProjectCloseRequestCreatePayload, ProjectCloseResidualItem } from '../../types'
import { ApiError } from '../../api/client'
import {
  approveProjectCloseRequest, archiveProject, cancelProjectCloseRequest, createProjectCloseRequest,
  getProjectCloseRequest, getProjectCloseRequests, rejectProjectCloseRequest, updateProjectCloseRequest,
} from '../../api/projects'
import { getProjectPrimaryStatus, getProjectStatusLabel } from '../../domain/projectLifecycleStatus'
import { canCreateProjectCloseRequest, canEditProjectCloseRequest, canReviewProjectCloseRequest, type ProjectCloseRoles } from '../../domain/projectCloseUi'
import { toast } from '../../utils/toast'

type Props = {
  open: boolean
  project: Project | null
  currentPersonId: number | null
  roles: ProjectCloseRoles
  initialRequestId?: number | null
  onClose: () => void
  onChanged: (projectId: number, requestId?: number | null) => Promise<void>
}

const EMPTY_ITEM: ProjectCloseResidualItem = {
  description: '', reason: '', owner: '', handover_to: '', follow_up_plan: '', expected_resolution: '',
}
const EMPTY_FORM: ProjectCloseRequestCreatePayload = {
  summary: '', objective_result: '', unfinished_items: [], remaining_risks: [], handover_plan: '', retrospective: '',
}

function freshEmptyForm(): ProjectCloseRequestCreatePayload {
  return { ...EMPTY_FORM, unfinished_items: [], remaining_risks: [] }
}

export function extractProjectCloseBlockers(error: unknown): ProjectCloseCheckItem[] {
  if (!(error instanceof ApiError) || error.status !== 409 || !error.body || typeof error.body !== 'object') return []
  const detail = (error.body as { detail?: unknown }).detail
  if (!detail || typeof detail !== 'object' || (detail as { code?: unknown }).code !== 'PROJECT_CLOSE_BLOCKED') return []
  const blockers = (detail as { blockers?: unknown }).blockers
  return Array.isArray(blockers) ? blockers.filter((item): item is ProjectCloseCheckItem => Boolean(item && typeof item === 'object' && typeof (item as ProjectCloseCheckItem).message === 'string')) : []
}

function formFromRequest(request: ProjectCloseRequest): ProjectCloseRequestCreatePayload {
  return {
    summary: request.summary, objective_result: request.objective_result,
    unfinished_items: request.unfinished_items.map((item) => ({ ...item })),
    remaining_risks: request.remaining_risks.map((item) => ({ ...item })),
    handover_plan: request.handover_plan, retrospective: request.retrospective,
  }
}

function validateForm(form: ProjectCloseRequestCreatePayload): string {
  if (![form.summary, form.objective_result, form.handover_plan, form.retrospective].every((value) => value.trim())) return '请完整填写项目总结、目标完成情况、交接计划和项目复盘。'
  const incomplete = [...form.unfinished_items, ...form.remaining_risks].some((item) => Object.values(item).some((value) => !value.trim()))
  return incomplete ? '每条未完成事项和剩余风险的六个字段都必须填写完整。' : ''
}

export function ProjectCloseFlowDrawer({ open, project, currentPersonId, roles, initialRequestId, onClose, onChanged }: Props) {
  const [request, setRequest] = useState<ProjectCloseRequest | null>(null)
  const [form, setForm] = useState<ProjectCloseRequestCreatePayload>(freshEmptyForm)
  const [initialForm, setInitialForm] = useState(() => JSON.stringify(freshEmptyForm()))
  const [reviewComment, setReviewComment] = useState('')
  const [initialReviewComment, setInitialReviewComment] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [busyAction, setBusyAction] = useState('')
  const [errorText, setErrorText] = useState('')
  const [runtimeBlockers, setRuntimeBlockers] = useState<ProjectCloseCheckItem[]>([])
  const [mutationCommittedButRefreshFailed, setMutationCommittedButRefreshFailed] = useState(false)
  const loadGenerationRef = useRef(0)

  const status = getProjectPrimaryStatus(project)
  const canCreate = canCreateProjectCloseRequest(status, roles)
  const canEdit = request ? canEditProjectCloseRequest(status, request.requester_person_id, currentPersonId, roles) : false
  const canReview = canReviewProjectCloseRequest(status, roles)
  const dirty = JSON.stringify(form) !== initialForm || reviewComment !== initialReviewComment
  const writesDisabled = Boolean(busyAction) || mutationCommittedButRefreshFailed
  const blockers = runtimeBlockers.length > 0 ? runtimeBlockers : request?.blockers ?? []
  const warnings = request?.warnings ?? []

  async function loadRequest() {
    if (!project) return
    const generation = ++loadGenerationRef.current
    const emptyForm = freshEmptyForm()
    setRequest(null)
    setForm(emptyForm)
    setInitialForm(JSON.stringify(emptyForm))
    setReviewComment('')
    setInitialReviewComment('')
    setRuntimeBlockers([])
    setErrorText('')
    setLoadFailed(false)
    setMutationCommittedButRefreshFailed(false)
    setLoading(true)
    try {
      let row: ProjectCloseRequest | null = null
      if (initialRequestId != null) row = await getProjectCloseRequest(project.id, initialRequestId)
      else if (status !== 'active') {
        const rows = await getProjectCloseRequests(project.id, status === 'pending_close' ? 'pending' : undefined)
        row = rows.find((item) => item.status === 'approved') ?? rows[0] ?? null
      }
      if (generation !== loadGenerationRef.current) return
      setRequest(row)
      const next = row ? formFromRequest(row) : freshEmptyForm()
      const nextReviewComment = row?.review_comment ?? ''
      setForm(next)
      setInitialForm(JSON.stringify(next))
      setReviewComment(nextReviewComment)
      setInitialReviewComment(nextReviewComment)
    } catch (error) {
      if (generation !== loadGenerationRef.current) return
      setLoadFailed(true)
      setErrorText(error instanceof Error ? error.message : '结束申请加载失败')
    } finally {
      if (generation === loadGenerationRef.current) setLoading(false)
    }
  }

  useEffect(() => {
    if (open && project) void loadRequest()
    else loadGenerationRef.current += 1
    return () => { loadGenerationRef.current += 1 }
  }, [open, project?.id, status, initialRequestId])

  function tryClose() {
    if (busyAction) return
    if (dirty && !window.confirm('结束材料尚未保存，确认离开吗？')) return
    loadGenerationRef.current += 1
    onClose()
  }

  async function runAction(name: string, action: () => Promise<ProjectCloseRequest | { ok: boolean; status: string }>, success: string) {
    if (!project || busyAction || mutationCommittedButRefreshFailed) return
    setMutationCommittedButRefreshFailed(false)
    setBusyAction(name); setErrorText(''); setRuntimeBlockers([])
    let result: ProjectCloseRequest | { ok: boolean; status: string }
    try {
      result = await action()
    } catch (error) {
      const parsed = extractProjectCloseBlockers(error)
      if (parsed.length) setRuntimeBlockers(parsed)
      else { const message = error instanceof Error ? error.message : '操作失败'; setErrorText(message); toast.error(message) }
      setBusyAction('')
      return
    }

    const requestId = 'id' in result ? result.id : request?.id
    if ('id' in result) {
      setRequest(result)
      const nextForm = formFromRequest(result)
      const nextReviewComment = result.review_comment ?? ''
      setForm(nextForm)
      setInitialForm(JSON.stringify(nextForm))
      setReviewComment(nextReviewComment)
      setInitialReviewComment(nextReviewComment)
    }
    toast.success(success)
    try {
      await onChanged(project.id, requestId)
      setMutationCommittedButRefreshFailed(false)
    } catch {
      setMutationCommittedButRefreshFailed(true)
      toast.warning('操作已成功，但项目状态刷新失败，请刷新页面后继续。')
    } finally {
      setBusyAction('')
    }
  }

  function save(create: boolean) {
    if (!project) return
    const validation = validateForm(form)
    if (validation) { setErrorText(validation); return }
    void runAction(create ? 'create' : 'save', () => create
      ? createProjectCloseRequest(project.id, form)
      : updateProjectCloseRequest(project.id, request!.id, form), create ? '结束申请已提交' : '结束材料已保存')
  }

  const actionHint = useMemo(() => {
    if (canCreate) return roles.isSuperAdmin ? '你可以技术兜底发起项目结束申请。' : '你是项目负责人，可以提交项目结束申请。'
    if (canReview) return '你可以审核本次项目结束申请。'
    if (canEdit) return '你可以修改或取消自己提交的结束申请。'
    return '当前为只读查看，不能执行项目结束操作。'
  }, [canCreate, canReview, canEdit, roles.isSuperAdmin])

  if (!open || !project) return null
  const readOnly = !canCreate && !canEdit
  return (
    <div className="fixed inset-0 z-[70] bg-slate-950/40" onClick={tryClose}>
      <aside className="ml-auto flex h-full w-full max-w-[800px] flex-col bg-white shadow-2xl" onClick={(event) => event.stopPropagation()} aria-label="项目结束流程">
        <header className="flex items-start justify-between border-b border-slate-200 px-6 py-4">
          <div><h2 className="text-lg font-bold text-slate-900">{project.name}</h2><p className="mt-1 text-xs text-slate-500">{getProjectStatusLabel(project)} · {actionHint}</p></div>
          <button type="button" onClick={tryClose} disabled={Boolean(busyAction)} className="rounded-lg px-3 py-1 text-xl text-slate-400 hover:bg-slate-100">×</button>
        </header>
        <main className="flex-1 space-y-5 overflow-y-auto bg-slate-50 px-6 py-5">
          {loading && <div className="rounded-xl bg-white p-8 text-center text-sm text-slate-400">正在加载结束申请…</div>}
          {errorText && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{errorText}</div>}
          {mutationCommittedButRefreshFailed && <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800">操作已成功。当前页面状态未刷新，请刷新页面后继续，勿重复提交。</div>}
          <CheckItems title="暂不能结束" items={blockers} className="border-red-200 bg-red-50 text-red-800" />
          <CheckItems title="结束前提醒" items={warnings} className="border-orange-200 bg-orange-50 text-orange-800" />
          {!loading && ((canCreate && !loadFailed) || request) && (
            <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="text-sm font-bold text-slate-800">结束材料</h3>
              <TextField label="项目总结" value={form.summary} readOnly={readOnly} onChange={(value) => setForm({ ...form, summary: value })} />
              <TextField label="目标完成情况" value={form.objective_result} readOnly={readOnly} onChange={(value) => setForm({ ...form, objective_result: value })} />
              <ResidualList title="未完成事项" addLabel="添加未完成事项" value={form.unfinished_items} readOnly={readOnly} onChange={(value) => setForm({ ...form, unfinished_items: value })} />
              <ResidualList title="剩余风险" addLabel="添加剩余风险" value={form.remaining_risks} readOnly={readOnly} onChange={(value) => setForm({ ...form, remaining_risks: value })} />
              <TextField label="交接计划" value={form.handover_plan} readOnly={readOnly} onChange={(value) => setForm({ ...form, handover_plan: value })} />
              <TextField label="项目复盘" value={form.retrospective} readOnly={readOnly} onChange={(value) => setForm({ ...form, retrospective: value })} />
              {canCreate && <p className="text-xs text-slate-500">提交时系统会自动检查待确认汇报、重大决策、待审核成果和其他结束阻断项。</p>}
            </section>
          )}
          {request && <section className="rounded-xl border border-slate-200 bg-white p-5"><h3 className="text-sm font-bold text-slate-800">审核意见</h3><textarea value={reviewComment} onChange={(event) => setReviewComment(event.target.value)} readOnly={!canReview || request.status !== 'pending'} className="mt-3 min-h-24 w-full rounded-lg border border-slate-200 p-3 text-sm outline-none read-only:bg-slate-50" placeholder={canReview ? '批准可不填；退回必须填写审核意见' : '暂无审核意见'} /><p className="mt-2 text-xs text-slate-400">申请人：{request.requester_name || '-'}　审核人：{request.reviewer_name || '-'}</p></section>}
        </main>
        <footer className="flex flex-wrap justify-end gap-2 border-t border-slate-200 bg-white px-6 py-4">
          <button type="button" onClick={tryClose} disabled={Boolean(busyAction)} className="rounded-lg border border-slate-200 px-4 py-2 text-sm">关闭</button>
          {canCreate && !loadFailed && <button type="button" onClick={() => save(true)} disabled={writesDisabled} className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busyAction === 'create' ? '提交中…' : roles.isSuperAdmin ? '提交结束申请（技术兜底）' : '提交结束申请'}</button>}
          {canEdit && request?.status === 'pending' && <><button type="button" onClick={() => save(false)} disabled={writesDisabled} className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">保存修改</button><button type="button" onClick={() => { if (window.confirm('确认取消本次结束申请？')) void runAction('cancel', () => cancelProjectCloseRequest(project.id, request.id), '结束申请已取消') }} disabled={writesDisabled} className="rounded-lg border border-orange-300 px-4 py-2 text-sm text-orange-700 disabled:opacity-50">取消申请</button></>}
          {canReview && request?.status === 'pending' && <><button type="button" onClick={() => { if (!reviewComment.trim()) { setErrorText('退回修改必须填写审核意见。'); return } if (window.confirm('确认退回本次结束申请？')) void runAction('reject', () => rejectProjectCloseRequest(project.id, request.id, { review_comment: reviewComment.trim() }), '结束申请已退回') }} disabled={writesDisabled} className="rounded-lg border border-orange-300 px-4 py-2 text-sm text-orange-700 disabled:opacity-50">退回修改</button><button type="button" onClick={() => { if (window.confirm('确认批准项目结束？')) void runAction('approve', () => approveProjectCloseRequest(project.id, request.id, { review_comment: reviewComment.trim() }), '项目已批准结束') }} disabled={writesDisabled} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">批准结束</button></>}
          {status === 'ended' && roles.isSuperAdmin && <button type="button" onClick={() => { if (window.confirm('确认归档该项目？')) void runAction('archive', () => archiveProject(project.id), '项目已归档') }} disabled={writesDisabled} className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">归档项目</button>}
        </footer>
      </aside>
    </div>
  )
}

function CheckItems({ title, items, className }: { title: string; items: ProjectCloseCheckItem[]; className: string }) {
  if (!items.length) return null
  return <section className={`rounded-xl border px-4 py-3 ${className}`}><h3 className="text-sm font-bold">{title}</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{items.map((item, index) => <li key={`${item.code}-${index}`}>{item.message}</li>)}</ul></section>
}

function TextField({ label, value, readOnly, onChange }: { label: string; value: string; readOnly: boolean; onChange: (value: string) => void }) {
  return <label className="block"><span className="text-xs font-semibold text-slate-600">{label}<span className="text-red-500"> *</span></span><textarea value={value} readOnly={readOnly} onChange={(event) => onChange(event.target.value)} className="mt-1 min-h-20 w-full rounded-lg border border-slate-200 p-3 text-sm outline-none read-only:bg-slate-50" /></label>
}

function ResidualList({ title, addLabel, value, readOnly, onChange }: { title: string; addLabel: string; value: ProjectCloseResidualItem[]; readOnly: boolean; onChange: (value: ProjectCloseResidualItem[]) => void }) {
  const fields: Array<[keyof ProjectCloseResidualItem, string]> = [['description', '事项描述'], ['reason', '原因'], ['owner', '责任人'], ['handover_to', '交接给'], ['follow_up_plan', '后续计划'], ['expected_resolution', '预计解决时间']]
  return <div><div className="flex items-center justify-between"><h4 className="text-xs font-semibold text-slate-600">{title}</h4>{!readOnly && <button type="button" onClick={() => onChange([...value, { ...EMPTY_ITEM }])} className="text-xs font-semibold text-sky-700">+ {addLabel}</button>}</div>{value.length === 0 ? <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-400">无</p> : <div className="mt-2 space-y-3">{value.map((item, index) => <div key={index} className="rounded-lg border border-slate-200 bg-slate-50 p-3"><div className="grid grid-cols-1 gap-2 sm:grid-cols-2">{fields.map(([key, label]) => <label key={key} className="text-xs text-slate-500">{label}<input value={item[key]} readOnly={readOnly} onChange={(event) => { const next = value.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: event.target.value } : row); onChange(next) }} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm outline-none read-only:bg-slate-100" /></label>)}</div>{!readOnly && <button type="button" onClick={() => onChange(value.filter((_, rowIndex) => rowIndex !== index))} className="mt-2 text-xs text-red-600">删除当前项</button>}</div>)}</div>}</div>
}
