import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  confirmAchievementSubmission,
  createAchievementSubmission,
  deleteAchievement,
  fetchAchievementSubmissions,
  fetchAchievements,
  rejectAchievementSubmission,
  updateAchievement,
  withdrawAchievementSubmission,
} from '../api/achievements'
import { fetchTasks } from '../api/tasks'
import { useProject } from '../context/ProjectContext'
import { getAchievementAddressAction } from '../domain/achievementFlow'
import type { AchievementItem, AchievementSubmissionItem, TaskItem } from '../types'
import { getProjectDisplayName, getProjectIdFromRecord } from '../domain/projectDisplay'
import { isProjectArchived } from '../domain/projectLifecycleStatus'

const TYPE_COLORS: Record<string, { bg: string; color: string; letter: string; letterBg: string }> = {
  '方案':   { bg: 'linear-gradient(135deg,#2563EB,#3B82F6)', color: '#1D4ED8', letter: 'W',  letterBg: '#DBEAFE' },
  '模板':   { bg: 'linear-gradient(135deg,#D97706,#F59E0B)', color: '#92400E', letter: 'P',  letterBg: '#FEF3C7' },
  'SOP':    { bg: 'linear-gradient(135deg,#059669,#10B981)', color: '#065F46', letter: 'X',  letterBg: '#D1FAE5' },
  'Prompt': { bg: 'linear-gradient(135deg,#7C3AED,#A78BFA)', color: '#5B21B6', letter: 'P',  letterBg: '#EDE9FE' },
  'Agent':  { bg: 'linear-gradient(135deg,#9D174D,#EC4899)', color: '#9D174D', letter: 'AI', letterBg: '#FCE7F3' },
  '文档':   { bg: 'linear-gradient(135deg,#0369A1,#0EA5E9)', color: '#0369A1', letter: 'D',  letterBg: '#E0F2FE' },
}

function getTypeStyle(type?: string) {
  return TYPE_COLORS[type ?? ''] ?? { bg: 'linear-gradient(135deg,#6B7280,#9CA3AF)', color: '#374151', letter: 'F', letterBg: '#F3F4F6' }
}

const SUB_STATUS_STYLE: Record<string, { label: string; bg: string; color: string }> = {
  '待确认': { label: '待确认', bg: '#FEF3C7', color: '#92400E' },
  '已确认': { label: '已入库', bg: '#D1FAE5', color: '#065F46' },
  '已退回': { label: '已退回', bg: '#FEE2E2', color: '#991B1B' },
  '已撤回': { label: '已撤回', bg: '#F1F5F9', color: '#64748B' },
}

export function AchievementsPage() {
  const { projects, currentUser } = useProject()
  const [searchParams] = useSearchParams()

  // ── tab ───────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<'formal' | 'pending'>('formal')

  // ── filter ────────────────────────────────────────────────────
  const [filterType, setFilterType] = useState('')
  const [filterProjectId, setFilterProjectId] = useState<number | null>(() => {
    const rawProjectId = searchParams.get('projectId')
    if (!rawProjectId) return null
    const parsed = Number(rawProjectId)
    return Number.isFinite(parsed) ? parsed : null
  })

  // ── formal achievements ───────────────────────────────────────
  const [items, setItems] = useState<AchievementItem[]>([])
  const [selected, setSelected] = useState<AchievementItem | null>(null)
  const [loading, setLoading] = useState(false)

  // ── create / submit form ──────────────────────────────────────
  const [createOpen, setCreateOpen] = useState(false)
  const [createSaving, setCreateSaving] = useState(false)
  const [createError, setCreateError] = useState('')
  const [createProjectId, setCreateProjectId] = useState<number | null>(null)
  const [createRelatedTaskId, setCreateRelatedTaskId] = useState<number | null>(null)
  const [createFormTasks, setCreateFormTasks] = useState<TaskItem[]>([])
  const [createFormTasksLoading, setCreateFormTasksLoading] = useState(false)
  const [createForm, setCreateForm] = useState({
    name: '',
    achievement_type: '方案',
    version: 'V0.1',
    file_link: '',
    scenario: '',
    reuse_tag: '',
  })

  // ── pending submissions ───────────────────────────────────────
  const [submissions, setSubmissions] = useState<AchievementSubmissionItem[]>([])
  const [selectedSubmission, setSelectedSubmission] = useState<AchievementSubmissionItem | null>(null)
  const [submissionsLoading, setSubmissionsLoading] = useState(false)
  const [rejectModalOpen, setRejectModalOpen] = useState(false)
  const [rejectTarget, setRejectTarget] = useState<AchievementSubmissionItem | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [subActionLoading, setSubActionLoading] = useState(false)
  const [subActionErr, setSubActionErr] = useState('')

  // ── detail panel task linking (formal tab) ────────────────────
  const [projectTasks, setProjectTasks] = useState<TaskItem[]>([])
  const [tasksForProjectId, setTasksForProjectId] = useState<number | null>(null)
  const [taskPickerOpen, setTaskPickerOpen] = useState(false)
  const [taskPickerLoading, setTaskPickerLoading] = useState(false)
  const [taskLinking, setTaskLinking] = useState(false)
  const [taskLinkErr, setTaskLinkErr] = useState('')

  // ── derived ───────────────────────────────────────────────────
  const currentProject = projects.find((p) => p.id === filterProjectId) ?? null
  const projectArchived = isProjectArchived(currentProject)
  const filtered = items.filter((i) => !filterType || i.achievement_type === filterType)

  // ── effects ───────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchAchievements(filterProjectId)
      .then((d) => { if (!cancelled) { setItems(d); if (d.length > 0) setSelected(d[0]) } })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [filterProjectId])

  useEffect(() => {
    if (activeTab !== 'pending') return
    setSubmissionsLoading(true)
    fetchAchievementSubmissions({ project_id: filterProjectId })
      .then((d) => {
        setSubmissions(d)
        setSelectedSubmission((prev) => {
          if (!prev) return d[0] ?? null
          return d.find((item) => item.id === prev.id) ?? d[0] ?? null
        })
      })
      .catch(() => {})
      .finally(() => setSubmissionsLoading(false))
  }, [activeTab, filterProjectId])

  useEffect(() => {
    if (!createProjectId) { setCreateFormTasks([]); setCreateRelatedTaskId(null); return }
    setCreateFormTasksLoading(true)
    setCreateRelatedTaskId(null)
    fetchTasks(createProjectId)
      .then((ts) => setCreateFormTasks(ts.filter((t) => !t.is_deleted)))
      .catch(() => {})
      .finally(() => setCreateFormTasksLoading(false))
  }, [createProjectId])

  useEffect(() => {
    if (!selected) return
    const projId = resolveSelectedProjectId()
    if (!projId || projId === tasksForProjectId) return
    fetchTasks(projId)
      .then((ts) => { setProjectTasks(ts); setTasksForProjectId(projId) })
      .catch(() => {})
  }, [selected?.id])

  // ── helpers ───────────────────────────────────────────────────

  function resolveSelectedProjectId(): number | null {
    if (!selected) return null
    return selected.project_id ?? getProjectIdFromRecord(selected) ?? null
  }

  function canReviewSubmission(sub: AchievementSubmissionItem): boolean {
    if (currentUser?.is_tech_admin) return true
    const projName = getProjectDisplayName(projects, sub)
    const role = currentUser?.project_roles[projName]
    return role === 'owner' || role === '项目负责人'
  }

  function canWithdrawSubmission(sub: AchievementSubmissionItem): boolean {
    return sub.submitter === currentUser?.name || sub.submitter === currentUser?.username
  }

  function openResetCreateForm() {
    setCreateError('')
    setCreateProjectId(filterProjectId)
    setCreateRelatedTaskId(null)
    setCreateFormTasks([])
    setCreateForm({ name: '', achievement_type: '方案', version: 'V0.1', file_link: '', scenario: '', reuse_tag: '' })
    setCreateOpen(true)
  }

  // ── formal achievement actions ────────────────────────────────

  function handleOpenAchievementAddress(item: AchievementItem) {
    const action = getAchievementAddressAction(item.file_link)
    if (!action.ok) { alert(action.message); return }
    window.open(action.url, '_blank', 'noopener,noreferrer')
  }

  function openTaskPickerFor(item: AchievementItem) {
    const projId = item.project_id ?? getProjectIdFromRecord(item) ?? null
    if (!projId) { alert('该成果未关联专项，无法查找重点工作'); return }
    setSelected(item)
    setTaskLinkErr('')
    setTaskPickerOpen(true)
    if (projId !== tasksForProjectId) {
      setTaskPickerLoading(true)
      fetchTasks(projId)
        .then((ts) => { setProjectTasks(ts); setTasksForProjectId(projId) })
        .catch(() => {})
        .finally(() => setTaskPickerLoading(false))
    }
  }

  async function handleLinkTask(taskId: number | null) {
    if (!selected) return
    setTaskLinking(true)
    setTaskLinkErr('')
    try {
      const updated = await updateAchievement(selected.id, {
        project_id: resolveSelectedProjectId() ?? selected.project_id ?? 0,
        name: selected.name ?? '',
        achievement_type: selected.achievement_type ?? '方案',
        related_task_id: taskId,
        owner: selected.owner ?? '',
        version: selected.version ?? 'V0.1',
        file_link: selected.file_link ?? '',
        scenario: selected.scenario ?? '',
        reuse_tag: selected.reuse_tag ?? '',
        status: selected.status ?? '草稿',
        source_type: (selected['source_type'] as string | undefined) ?? '人工录入',
      })
      setSelected(updated)
      setItems((prev) => prev.map((it) => (it.id === updated.id ? updated : it)))
      setTaskPickerOpen(false)
    } catch (err: unknown) {
      setTaskLinkErr(err instanceof Error ? err.message : '关联失败，请重试')
    } finally {
      setTaskLinking(false)
    }
  }

  // ── submission form ───────────────────────────────────────────

  async function handleSubmitForReview() {
    if (!createForm.name.trim()) { setCreateError('请先填写成果名称'); return }
    if (!createProjectId) { setCreateError('请选择所属专项'); return }
    if (!createRelatedTaskId) { setCreateError('请选择关联重点工作'); return }
    setCreateSaving(true)
    setCreateError('')
    try {
      const sub = await createAchievementSubmission({
        project_id: createProjectId,
        related_task_id: createRelatedTaskId,
        name: createForm.name.trim(),
        achievement_type: createForm.achievement_type || '方案',
        version: createForm.version || 'V0.1',
        file_link: createForm.file_link.trim(),
        scenario: createForm.scenario.trim(),
        reuse_tag: createForm.reuse_tag.trim(),
      })
      setSubmissions((prev) => [sub, ...prev])
      setSelectedSubmission(sub)
      setCreateOpen(false)
      setActiveTab('pending')
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : '提交失败，请稍后重试')
    } finally {
      setCreateSaving(false)
    }
  }

  // ── submission review actions ─────────────────────────────────

  async function handleConfirmSubmission(sub: AchievementSubmissionItem) {
    if (!confirm(`确认将「${sub.name}」正式入库？`)) return
    setSubActionLoading(true)
    setSubActionErr('')
    try {
      const result = await confirmAchievementSubmission(sub.id)
      setSubmissions((prev) => prev.map((s) => (s.id === sub.id ? result.submission : s)))
      setSelectedSubmission(result.submission)
      setItems((prev) => [result.achievement, ...prev])
    } catch (err: unknown) {
      setSubActionErr(err instanceof Error ? err.message : '操作失败')
    } finally {
      setSubActionLoading(false)
    }
  }

  async function handleRejectSubmission() {
    if (!rejectTarget) return
    setSubActionLoading(true)
    setSubActionErr('')
    try {
      const updated = await rejectAchievementSubmission(rejectTarget.id, rejectReason)
      setSubmissions((prev) => prev.map((s) => (s.id === rejectTarget.id ? updated : s)))
      setSelectedSubmission(updated)
      setRejectModalOpen(false)
    } catch (err: unknown) {
      setSubActionErr(err instanceof Error ? err.message : '操作失败')
    } finally {
      setSubActionLoading(false)
    }
  }

  async function handleWithdrawSubmission(sub: AchievementSubmissionItem) {
    if (!confirm(`确认撤回「${sub.name}」的提交？`)) return
    setSubActionLoading(true)
    setSubActionErr('')
    try {
      const updated = await withdrawAchievementSubmission(sub.id)
      setSubmissions((prev) => prev.map((s) => (s.id === sub.id ? updated : s)))
      setSelectedSubmission(updated)
    } catch (err: unknown) {
      setSubActionErr(err instanceof Error ? err.message : '操作失败')
    } finally {
      setSubActionLoading(false)
    }
  }

  // ── render ────────────────────────────────────────────────────

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="h-16 flex items-center px-6 gap-3 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1">
          <h1 className="text-base font-bold text-slate-800">成果库</h1>
          <p className="text-xs text-slate-400 mt-0.5">沉淀方案、模板、SOP、Prompt、Agent 等可复用资产</p>
        </div>
        {/* Tab switcher */}
        <div className="flex items-center bg-slate-100 rounded-lg p-0.5 gap-0.5">
          {(['formal', 'pending'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className="px-3 py-1.5 rounded-md text-xs font-semibold transition-all"
              style={{
                background: activeTab === tab ? 'white' : 'transparent',
                color: activeTab === tab ? '#0369A1' : '#64748B',
                boxShadow: activeTab === tab ? '0 1px 3px rgba(15,23,42,0.08)' : 'none',
              }}
            >
              {tab === 'formal' ? '正式成果' : `待确认成果${submissions.filter((s) => s.status === '待确认').length > 0 ? ` (${submissions.filter((s) => s.status === '待确认').length})` : ''}`}
            </button>
          ))}
        </div>
        <select
          value={filterProjectId ?? ''}
          onChange={(e) => setFilterProjectId(e.target.value === '' ? null : Number(e.target.value))}
          className="text-sm border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none"
        >
          <option value="">全部专项</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {activeTab === 'formal' && (
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="text-sm border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none">
            <option value="">全部类型</option>
            {['方案', '模板', 'SOP', 'Prompt', 'Agent', '文档'].map((t) => <option key={t}>{t}</option>)}
          </select>
        )}
        <button
          type="button"
          onClick={openResetCreateForm}
          className="cursor-pointer flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-semibold hover:opacity-90"
          style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)', boxShadow: '0 2px 8px rgba(3,105,161,0.25)' }}
        >
          <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" /></svg>
          登记成果
        </button>
      </header>

      {/* ── Create / Submit modal ── */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(15,23,42,0.45)' }}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
              <div>
                <h3 className="text-base font-bold text-slate-800">登记成果</h3>
                <p className="text-xs text-slate-400 mt-0.5">提交后由项目负责人确认入库，成果库只登记索引和存储地址</p>
              </div>
              <button type="button" onClick={() => { if (!createSaving) setCreateOpen(false) }} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
                <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              {createError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{createError}</div>
              )}
              <div className="grid grid-cols-2 gap-4">
                {/* Project select — required */}
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-slate-600">所属专项 <span className="text-red-400">*</span></span>
                  <select
                    value={createProjectId ?? ''}
                    onChange={(e) => setCreateProjectId(e.target.value === '' ? null : Number(e.target.value))}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-400 bg-white"
                  >
                    <option value="">请选择专项</option>
                    {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </label>
                {/* Task select — required */}
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-slate-600">关联重点工作 <span className="text-red-400">*</span></span>
                  <select
                    value={createRelatedTaskId ?? ''}
                    onChange={(e) => setCreateRelatedTaskId(e.target.value === '' ? null : Number(e.target.value))}
                    disabled={!createProjectId || createFormTasksLoading}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-400 bg-white disabled:bg-slate-50 disabled:text-slate-400"
                  >
                    <option value="">
                      {!createProjectId ? '请先选择专项' : createFormTasksLoading ? '加载中…' : createFormTasks.length === 0 ? '该专项暂无任务' : '请选择重点工作'}
                    </option>
                    {createFormTasks.map((t) => <option key={t.id} value={t.id}>{t.key_task}</option>)}
                  </select>
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-slate-600">成果名称 <span className="text-red-400">*</span></span>
                  <input
                    value={createForm.name}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, name: e.target.value }))}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-400"
                    placeholder="例如：知识资产AI化方案"
                  />
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-slate-600">成果类型</span>
                  <select
                    value={createForm.achievement_type}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, achievement_type: e.target.value }))}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-400 bg-white"
                  >
                    {['方案', '模板', 'SOP', 'Prompt', 'Agent', '文档'].map((t) => <option key={t}>{t}</option>)}
                  </select>
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-slate-600">版本</span>
                  <input
                    value={createForm.version}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, version: e.target.value }))}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-400"
                    placeholder="V0.1"
                  />
                </label>
                <label className="space-y-1.5">
                  <span className="text-xs font-semibold text-slate-600">复用标签</span>
                  <input
                    value={createForm.reuse_tag}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, reuse_tag: e.target.value }))}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-400"
                    placeholder="例如：内测、自动化、AI"
                  />
                </label>
              </div>
              <label className="space-y-1.5 block">
                <span className="text-xs font-semibold text-slate-600">成果存储地址</span>
                <input
                  value={createForm.file_link}
                  onChange={(e) => setCreateForm((prev) => ({ ...prev, file_link: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-400"
                  placeholder="可填知识库地址、网盘链接、在线文档地址或本地路径"
                />
              </label>
              <label className="space-y-1.5 block">
                <span className="text-xs font-semibold text-slate-600">使用场景</span>
                <textarea
                  value={createForm.scenario}
                  onChange={(e) => setCreateForm((prev) => ({ ...prev, scenario: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-400 resize-none"
                  rows={3}
                  placeholder="例如：专项内复用、内部演示、制度落地"
                />
              </label>
            </div>
            <div className="px-6 py-4 border-t flex items-center justify-between gap-3" style={{ borderColor: '#E9EFF6' }}>
              <span className="text-xs text-slate-400">* 提交后由项目负责人审核确认入库，文件本体请存放在知识库。</span>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => setCreateOpen(false)} disabled={createSaving} className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50">取消</button>
                <button type="button" onClick={handleSubmitForReview} disabled={createSaving || projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined} className="px-4 py-2 rounded-lg text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
                  {createSaving ? '提交中...' : '提交审核'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Reject modal ── */}
      {rejectModalOpen && rejectTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(15,23,42,0.45)' }}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
              <h3 className="text-base font-bold text-slate-800">退回成果</h3>
              <button type="button" onClick={() => setRejectModalOpen(false)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
                <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="px-6 py-5">
              <p className="text-sm text-slate-600 mb-3">退回「<span className="font-semibold text-slate-800">{rejectTarget.name}</span>」，请填写退回原因：</p>
              {subActionErr && <div className="mb-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{subActionErr}</div>}
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="请填写退回原因，提交人将看到此说明"
                rows={3}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-400 resize-none"
              />
            </div>
            <div className="px-6 py-4 border-t flex justify-end gap-2" style={{ borderColor: '#E9EFF6' }}>
              <button type="button" onClick={() => setRejectModalOpen(false)} disabled={subActionLoading} className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50">取消</button>
              <button type="button" onClick={handleRejectSubmission} disabled={subActionLoading || projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined} className="px-4 py-2 rounded-lg text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#DC2626,#EF4444)' }}>
                {subActionLoading ? '退回中...' : '确认退回'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Task picker modal ── */}
      {taskPickerOpen && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(15,23,42,0.45)' }}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
              <div>
                <h3 className="text-base font-bold text-slate-800">关联重点工作</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  {getProjectDisplayName(projects, selected) ? `显示「${getProjectDisplayName(projects, selected)}」下的重点工作` : '显示当前项目的重点工作'}
                </p>
              </div>
              <button type="button" onClick={() => { setTaskPickerOpen(false); setTaskLinkErr('') }} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
                <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            {taskLinkErr && <div className="mx-6 mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{taskLinkErr}</div>}
            <div className="max-h-80 overflow-y-auto px-6 py-4">
              {taskPickerLoading ? (
                <div className="text-center text-slate-400 text-sm py-6">加载中…</div>
              ) : projectTasks.length === 0 ? (
                <div className="text-center text-slate-400 text-sm py-6">该项目下暂无重点工作</div>
              ) : (
                <div className="space-y-2">
                  {projectTasks.map((task) => {
                    const isCurrent = task.id === selected.related_task_id
                    return (
                      <button
                        key={task.id}
                        type="button"
                        disabled={taskLinking}
                        onClick={() => handleLinkTask(task.id)}
                        className="w-full text-left px-4 py-3 rounded-xl border transition-all hover:bg-sky-50 disabled:opacity-50"
                        style={{ border: isCurrent ? '1.5px solid #0369A1' : '1px solid #E9EFF6', background: isCurrent ? '#F0F9FF' : 'white' }}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-slate-800">{task.key_task}</span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">{task.status}</span>
                        </div>
                        {task.owner && <p className="text-xs text-slate-400 mt-0.5">负责人：{task.owner}</p>}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
            {selected.related_task_id != null && (
              <div className="px-6 py-3 border-t flex items-center justify-between" style={{ borderColor: '#E9EFF6' }}>
                <span className="text-xs text-slate-400">
                  当前已关联：{projectTasks.find((t) => t.id === selected.related_task_id)?.key_task ?? `任务 #${selected.related_task_id}`}
                </span>
                <button type="button" disabled={taskLinking} onClick={() => handleLinkTask(null)} className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50">取消关联</button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Stats (formal tab only) ── */}
      {activeTab === 'formal' && (
        <div className="bg-white border-b px-6 py-4 flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: '成果总数',   val: items.length,                                    icon: '📦', bg: 'linear-gradient(135deg,#0369A1,#0EA5E9)', color: '#0369A1' },
              { label: '本月新增',   val: 0,                                               icon: '📈', bg: 'linear-gradient(135deg,#059669,#34D399)',   color: '#059669' },
              { label: '可复用成果', val: items.filter((i) => i.reuse_tag).length,         icon: '🔄', bg: 'linear-gradient(135deg,#7C3AED,#A78BFA)',   color: '#7C3AED' },
              { label: '待确认提交', val: submissions.filter((s) => s.status === '待确认').length, icon: '⏳', bg: 'linear-gradient(135deg,#D97706,#FBBF24)',   color: '#D97706' },
            ].map(({ label, val, icon, bg, color }) => (
              <div key={label} className="rounded-xl border p-4 flex items-center gap-4" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)', background: 'white' }}>
                <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 text-white text-2xl" style={{ background: bg }}>{icon}</div>
                <div>
                  <p className="text-xs text-slate-500 font-medium">{label}</p>
                  <p className="text-3xl font-bold leading-none mt-1" style={{ color }}>{val}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── PENDING TAB ── */}
      {activeTab === 'pending' && (
        <div className="flex-1 overflow-hidden flex" style={{ background: '#F1F5F9' }}>
          <div className="flex-1 overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-800">待确认成果</h2>
              <span className="text-xs text-slate-400">
                {submissionsLoading ? '加载中…' : `共 ${submissions.length} 条`}
              </span>
            </div>
            {subActionErr && (
              <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{subActionErr}</div>
            )}
            {submissionsLoading ? (
              <div className="text-center text-slate-400 py-12 text-sm">加载中…</div>
            ) : submissions.length === 0 ? (
              <div className="text-center text-slate-400 py-12 text-sm">暂无成果提交记录</div>
            ) : (
              <div className="space-y-3">
                {submissions.map((sub) => {
                  const ts = getTypeStyle(sub.achievement_type)
                  const st = SUB_STATUS_STYLE[sub.status] ?? { label: sub.status, bg: '#F1F5F9', color: '#64748B' }
                  const taskName = sub.related_task_id != null
                    ? (createFormTasks.find((t) => t.id === sub.related_task_id)?.key_task ?? `任务 #${sub.related_task_id}`)
                    : undefined
                  const isSelected = selectedSubmission?.id === sub.id
                  return (
                    <div
                      key={sub.id}
                      onClick={() => setSelectedSubmission(sub)}
                      className="bg-white rounded-xl border p-4 cursor-pointer transition-all"
                      style={{
                        borderColor: isSelected ? '#0369A1' : '#E9EFF6',
                        boxShadow: isSelected ? '0 0 0 3px rgba(3,105,161,0.12)' : '0 1px 3px rgba(15,23,42,0.05)',
                        background: isSelected ? '#F0F9FF' : 'white',
                      }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3 min-w-0">
                          <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-white text-sm font-bold" style={{ background: ts.bg }}>{ts.letter}</div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="text-sm font-bold text-slate-800">{sub.name}</p>
                              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold" style={{ background: ts.letterBg, color: ts.color }}>{sub.achievement_type ?? '文件'}</span>
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold" style={{ background: st.bg, color: st.color }}>{st.label}</span>
                            </div>
                            <div className="flex items-center gap-3 mt-1 text-xs text-slate-400 flex-wrap">
                              {getProjectDisplayName(projects, sub) && <span>{getProjectDisplayName(projects, sub)}</span>}
                              {taskName && <span>关联：{taskName}</span>}
                              <span>提交人：{sub.submitter}</span>
                              <span>{sub.created_at?.slice(0, 10)}</span>
                            </div>
                            <p className="text-xs text-slate-400 mt-0.5 truncate max-w-xs">地址：{sub.file_link || '无'}</p>
                            {sub.status === '已退回' && sub.reject_reason && (
                              <p className="text-xs text-red-600 mt-1.5 bg-red-50 rounded-lg px-2 py-1.5">退回原因：{sub.reject_reason}</p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 flex-shrink-0">
                          {sub.status === '待确认' && canReviewSubmission(sub) && (
                            <>
                              <button
                                type="button"
                                disabled={subActionLoading}
                                onClick={(e) => { e.stopPropagation(); handleConfirmSubmission(sub) }}
                                className="px-3 py-1.5 rounded-lg text-white text-xs font-semibold hover:opacity-90 disabled:opacity-50"
                                style={{ background: 'linear-gradient(135deg,#059669,#10B981)' }}
                              >确认入库</button>
                              <button
                                type="button"
                                disabled={subActionLoading}
                                onClick={(e) => { e.stopPropagation(); setRejectTarget(sub); setRejectReason(''); setSubActionErr(''); setRejectModalOpen(true) }}
                                className="px-3 py-1.5 rounded-lg border text-xs font-semibold text-red-500 border-red-200 hover:bg-red-50 disabled:opacity-50"
                              >退回</button>
                            </>
                          )}
                          {sub.status === '待确认' && canWithdrawSubmission(sub) && !canReviewSubmission(sub) && (
                            <button
                              type="button"
                              disabled={subActionLoading}
                              onClick={(e) => { e.stopPropagation(); handleWithdrawSubmission(sub) }}
                              className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-500 hover:bg-slate-50 disabled:opacity-50"
                            >撤回</button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {selectedSubmission && (
            <div style={{ width: 340, flexShrink: 0, borderLeft: '1px solid #E9EFF6', background: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div className="flex items-center justify-between px-4 py-3.5 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                <h2 className="text-sm font-bold text-slate-800">待确认成果详情</h2>
                <button onClick={() => setSelectedSubmission(null)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors">
                  <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                <div className="flex items-start gap-3">
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 text-white font-bold" style={{ background: getTypeStyle(selectedSubmission.achievement_type).bg }}>
                    {getTypeStyle(selectedSubmission.achievement_type).letter}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-800 leading-snug">{selectedSubmission.name}</p>
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold" style={{ background: getTypeStyle(selectedSubmission.achievement_type).letterBg, color: getTypeStyle(selectedSubmission.achievement_type).color }}>
                        {selectedSubmission.achievement_type ?? '文件'}
                      </span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold" style={{ background: (SUB_STATUS_STYLE[selectedSubmission.status] ?? SUB_STATUS_STYLE['待确认']).bg, color: (SUB_STATUS_STYLE[selectedSubmission.status] ?? SUB_STATUS_STYLE['待确认']).color }}>
                        {(SUB_STATUS_STYLE[selectedSubmission.status] ?? { label: selectedSubmission.status }).label}
                      </span>
                    </div>
                  </div>
                </div>
                {[
                  { label: '所属专项', value: getProjectDisplayName(projects, selectedSubmission) },
                  { label: '关联任务', value: selectedSubmission.related_task_id != null ? `任务 #${selectedSubmission.related_task_id}` : undefined },
                  { label: '提交人', value: selectedSubmission.submitter },
                  { label: '版本', value: selectedSubmission.version ?? 'V0.1' },
                  { label: '存储地址', value: selectedSubmission.file_link || '无' },
                  { label: '使用场景', value: selectedSubmission.scenario },
                  { label: '复用标签', value: selectedSubmission.reuse_tag },
                  { label: '审核人', value: selectedSubmission.reviewer },
                  { label: '审核时间', value: selectedSubmission.reviewed_at?.slice(0, 10) },
                  { label: '退回原因', value: selectedSubmission.reject_reason },
                  { label: '提交时间', value: selectedSubmission.created_at?.slice(0, 10) },
                ].map(({ label, value }) => value ? (
                  <div key={label} className="flex gap-2 text-xs py-1.5 border-b border-slate-50">
                    <span className="w-20 flex-shrink-0 text-slate-500 font-semibold">{label}</span>
                    <span className="text-slate-800 break-all">{value}</span>
                  </div>
                ) : null)}
              </div>
              {selectedSubmission.status === '待确认' && (
                <div className="px-4 py-3 border-t flex gap-2 flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                  {canReviewSubmission(selectedSubmission) && (
                    <>
                      <button
                        type="button"
                        disabled={subActionLoading}
                        onClick={() => handleConfirmSubmission(selectedSubmission)}
                        className="flex-1 py-2 rounded-lg text-white text-xs font-bold hover:opacity-90 disabled:opacity-50"
                        style={{ background: 'linear-gradient(135deg,#059669,#10B981)' }}
                      >确认入库</button>
                      <button
                        type="button"
                        disabled={subActionLoading}
                        onClick={() => { setRejectTarget(selectedSubmission); setRejectReason(''); setSubActionErr(''); setRejectModalOpen(true) }}
                        className="flex-1 py-2 rounded-lg border border-red-200 text-red-500 text-xs font-semibold hover:bg-red-50 disabled:opacity-50"
                      >退回</button>
                    </>
                  )}
                  {canWithdrawSubmission(selectedSubmission) && !canReviewSubmission(selectedSubmission) && (
                    <button
                      type="button"
                      disabled={subActionLoading}
                      onClick={() => handleWithdrawSubmission(selectedSubmission)}
                      className="flex-1 py-2 rounded-lg border border-slate-200 text-slate-600 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50"
                    >撤回</button>
                  )}
                  {!canReviewSubmission(selectedSubmission) && !canWithdrawSubmission(selectedSubmission) && (
                    <div className="w-full rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500 text-center">
                      仅项目负责人或技术管理员可确认入库
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── FORMAL TAB ── */}
      {activeTab === 'formal' && (
        <div className="flex-1 overflow-hidden flex" style={{ background: '#F1F5F9' }}>
          {/* Card grid */}
          <div className="flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="text-center text-slate-400 py-8 text-sm">加载中…</div>
            ) : (
              <>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-bold text-slate-800">成果列表 <span className="text-slate-400 font-normal">（共 {filtered.length} 项）</span></h2>
                </div>
                <div className="grid grid-cols-4 gap-3">
                  {filtered.map((item) => {
                    const ts = getTypeStyle(item.achievement_type)
                    const isSelected = selected?.id === item.id
                    return (
                      <div
                        key={item.id}
                        onClick={() => setSelected(item)}
                        className="bg-white rounded-xl cursor-pointer transition-all"
                        style={{
                          border: `1.5px solid ${isSelected ? '#0369A1' : '#E9EFF6'}`,
                          padding: 14,
                          boxShadow: isSelected ? '0 0 0 3px rgba(3,105,161,0.12)' : '0 1px 3px rgba(15,23,42,0.05)',
                          background: isSelected ? '#F0F9FF' : 'white',
                        }}
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-white text-sm font-bold" style={{ background: ts.bg }}>{ts.letter}</div>
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold" style={{ background: ts.letterBg, color: ts.color }}>{item.achievement_type ?? '文件'}</span>
                        </div>
                        <p className="text-sm font-bold text-slate-800 leading-snug mb-1">{item.name ?? '-'}</p>
                        <p className="text-xs text-slate-400 mb-2.5">{getProjectDisplayName(projects, item)}</p>
                        <div className="space-y-1 mb-3 text-xs text-slate-500">
                          <div className="flex items-center gap-1.5">
                            <svg style={{ width: 11, height: 11, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                            {item.owner ?? '-'} · {item.version ?? 'v1.0'}
                          </div>
                          <div className="flex items-center gap-1.5">
                            <svg style={{ width: 11, height: 11, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            {item.created_at?.slice(0, 10) ?? '-'}
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 pt-2.5 border-t border-slate-100">
                          <button className="flex-1 text-xs font-semibold text-blue-600 hover:text-blue-800 py-1.5 rounded-lg hover:bg-blue-50 transition-colors" onClick={(e) => e.stopPropagation()}>查看</button>
                          <button className="flex-1 text-xs font-semibold text-slate-500 hover:text-slate-700 py-1.5 rounded-lg hover:bg-slate-100 transition-colors" onClick={(e) => { e.stopPropagation(); openTaskPickerFor(item) }}>关联</button>
                          <button
                            className="flex-1 text-xs font-semibold text-slate-500 hover:text-slate-700 py-1.5 rounded-lg hover:bg-slate-100 transition-colors flex items-center justify-center gap-1"
                            onClick={(e) => { e.stopPropagation(); handleOpenAchievementAddress(item) }}
                          >
                            <svg style={{ width: 11, height: 11 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                            打开
                          </button>
                          {currentUser?.is_tech_admin && (
                            <button
                              className="flex-1 text-xs font-semibold text-red-400 hover:text-red-600 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
                              onClick={(e) => {
                                e.stopPropagation()
                                if (!confirm(`确认删除「${item.name}」？`)) return
                                deleteAchievement(item.id)
                                  .then(() => { setItems((prev) => prev.filter((a) => a.id !== item.id)); if (selected?.id === item.id) setSelected(null) })
                                  .catch(() => alert('删除失败'))
                              }}
                            >删除</button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                  {filtered.length === 0 && (
                    <div className="col-span-4 py-12 text-center text-slate-400 text-sm">暂无成果数据</div>
                  )}
                </div>
                {filtered.length > 0 && (
                  <div className="flex items-center justify-between mt-4">
                    <span className="text-xs text-slate-400">共 {filtered.length} 条</span>
                    <button className="w-7 h-7 rounded-lg text-white text-xs font-bold" style={{ background: '#0369A1' }}>1</button>
                    <select className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white text-slate-500 cursor-pointer focus:outline-none">
                      <option>10 条/页</option>
                    </select>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Detail panel */}
          {selected && (
            <div style={{ width: 300, flexShrink: 0, borderLeft: '1px solid #E9EFF6', background: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div className="flex items-center justify-between px-4 py-3.5 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                <h2 className="text-sm font-bold text-slate-800">成果详情</h2>
                <button onClick={() => setSelected(null)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors">
                  <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                <div className="flex items-start gap-3">
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 text-white font-bold" style={{ background: getTypeStyle(selected.achievement_type).bg }}>
                    {getTypeStyle(selected.achievement_type).letter}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-800 leading-snug">{selected.name ?? '-'}</p>
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold" style={{ background: getTypeStyle(selected.achievement_type).letterBg, color: getTypeStyle(selected.achievement_type).color }}>
                        {selected.achievement_type ?? '文件'}
                      </span>
                    </div>
                  </div>
                </div>
                {(() => {
                  const relatedTaskName = selected.related_task_id != null
                    ? (projectTasks.find((t) => t.id === selected.related_task_id)?.key_task ?? `任务 #${selected.related_task_id}`)
                    : undefined
                  return [
                    { label: '负责人',   value: selected.owner },
                    { label: '所属专项', value: getProjectDisplayName(projects, selected) },
                    { label: '关联任务', value: relatedTaskName },
                    { label: '版本',     value: selected.version ?? 'V0.1' },
                    { label: '状态',     value: selected.status ?? '进行中' },
                    { label: '存储地址', value: selected.file_link },
                    { label: '使用场景', value: selected.scenario },
                    { label: '审核人',   value: selected.confirmed_by },
                    { label: '审核时间', value: selected.confirmed_at?.slice(0, 10) },
                    { label: '来源提交', value: selected.source_submission_id != null ? `来源提交 #${selected.source_submission_id}` : undefined },
                    { label: '成果登记来源', value: selected.source_achievement_submission_id != null ? `成果提交 #${selected.source_achievement_submission_id}` : undefined },
                    { label: '创建时间', value: selected.created_at?.slice(0, 10) },
                  ].map(({ label, value }) => value ? (
                    <div key={label} className="flex gap-2 text-xs py-1.5 border-b border-slate-50">
                      <span className="w-16 flex-shrink-0 text-slate-500 font-semibold">{label}</span>
                      <span className="text-slate-800 break-all">{value}</span>
                    </div>
                  ) : null)
                })()}
              </div>
              <div className="px-4 py-3 border-t flex gap-2 flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                <button
                  className="flex-1 py-2 rounded-lg text-white text-xs font-bold hover:opacity-90"
                  style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
                  onClick={() => handleOpenAchievementAddress(selected)}
                >打开成果地址</button>
                <button
                  className="flex-1 py-2 rounded-lg border border-slate-200 text-slate-600 text-xs font-semibold hover:bg-slate-50"
                  onClick={() => openTaskPickerFor(selected)}
                >关联任务</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
