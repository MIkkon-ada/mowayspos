import { useEffect, useState } from 'react'
import { fmtDate } from '../utils/time'
import { fetchIssues, fetchMyIssues, deleteIssue, resolveIssue, closeIssue, assignIssueHelper, requestIssueCeo, createIssue } from '../api/issues'
import { useProject } from '../context/ProjectContext'
import { toast } from '../utils/toast'
import type { IssueItem } from '../types'
import { getProjectDisplayName } from '../domain/projectDisplay'
import { isProjectArchived } from '../domain/projectLifecycleStatus'

const PRI_STYLE: Record<string, string> = {
  '高': 'bg-red-100 text-red-700',
  '中': 'bg-amber-100 text-amber-700',
  '低': 'bg-emerald-100 text-emerald-700',
}

const STATUS_STYLE: Record<string, { badge: string; dot: string }> = {
  '待处理': { badge: 'bg-amber-100 text-amber-700', dot: '#F59E0B' },
  '处理中': { badge: 'bg-blue-100 text-blue-700', dot: '#3B82F6' },
  '待决策': { badge: 'bg-purple-100 text-purple-700', dot: '#7C3AED' },
  '已解决': { badge: 'bg-emerald-100 text-emerald-700', dot: '#10B981' },
  '已关闭': { badge: 'bg-slate-100 text-slate-500', dot: '#94A3B8' },
  '已决策': { badge: 'bg-purple-100 text-purple-600', dot: '#7C3AED' },
}

const TYPE_STYLE: Record<string, string> = {
  '问题': 'bg-orange-50 text-orange-700 border-orange-200',
  '风险': 'bg-red-50 text-red-700 border-red-200',
  '待协调': 'bg-blue-50 text-blue-700 border-blue-200',
  '需决策': 'bg-purple-50 text-purple-700 border-purple-200',
}

export function IssuesPage() {
  const { currentProjectId, currentUser, globalUserRoles, projects } = useProject()
  const [issues, setIssues] = useState<IssueItem[]>([])
  const [selected, setSelected] = useState<IssueItem | null>(null)
  const [loading, setLoading] = useState(false)
  const [filterStatus, setFilterStatus] = useState('')
  const [filterType, setFilterType] = useState('')
  const [filterPriority, setFilterPriority] = useState('')
  const [checked, setChecked] = useState<Set<number>>(new Set())

  const canDelete = currentUser?.is_tech_admin || globalUserRoles.includes('owner')
  const isCEO = !!(currentUser?.is_ceo || globalUserRoles.includes('project_ceo'))
  const canOwnerAction = canDelete

  // 普通用户只看自己上报的问题；负责人/企业教练/管理员看项目整体问题
  const isPrivileged = canDelete || isCEO

  const currentProject = projects.find((p) => p.id === currentProjectId) ?? null
  const projectArchived = isProjectArchived(currentProject)

  function issueProjectName(issue: IssueItem) {
    return getProjectDisplayName(projects, issue) || '-'
  }

  // right panel action state
  const [actionLoading, setActionLoading] = useState(false)
  const [actionErr, setActionErr] = useState('')
  const [resolutionInput, setResolutionInput] = useState('')
  const [helperInput, setHelperInput] = useState('')
  const [ceoTarget, setCeoTarget] = useState('')
  const [ceoNote, setCeoNote] = useState('')
  const [showCeoForm, setShowCeoForm] = useState(false)
  const [closeReason, setCloseReason] = useState('')
  const [handlerReplyInput, setHandlerReplyInput] = useState('')

  // add issue modal
  const [addOpen, setAddOpen] = useState(false)

  // inline delete confirm (avoids browser confirm())
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [bulkDeletePending, setBulkDeletePending] = useState(false)

  // reset processing area when selection changes
  useEffect(() => {
    setActionErr('')
    setResolutionInput(selected?.resolution ?? '')
    setHandlerReplyInput(selected?.handler_reply ?? '')
    setHelperInput(selected?.helper ?? '')
    setCeoTarget('')
    setCeoNote('')
    setShowCeoForm(false)
    setCloseReason('')
    setDeleteTarget(null)
  }, [selected?.id])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const fetcher = isPrivileged ? fetchIssues() : fetchMyIssues()
    fetcher
      .then((d) => { if (!cancelled) { setIssues(d); if (d.length > 0) setSelected(d[0]) } })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [isPrivileged])

  const filtered = issues.filter((i) => {
    if (filterStatus && i.status !== filterStatus) return false
    if (filterType && i.issue_type !== filterType) return false
    if (filterPriority && i.priority !== filterPriority) return false
    return true
  })

  const allChecked = filtered.length > 0 && filtered.every((i) => checked.has(i.id))

  function toggleAll() {
    if (allChecked) setChecked(new Set())
    else setChecked(new Set(filtered.map((i) => i.id)))
  }

  function toggleOne(id: number, e: React.MouseEvent) {
    e.stopPropagation()
    setChecked((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function reload() {
    const fetcher = isPrivileged ? fetchIssues() : fetchMyIssues()
    fetcher.then((d) => setIssues(d)).catch(() => {})
  }

  async function doAction(fn: () => Promise<IssueItem>) {
    setActionLoading(true)
    setActionErr('')
    try {
      const updated = await fn()
      setIssues((prev) => prev.map((i) => i.id === updated.id ? updated : i))
      setSelected(updated)
      setShowCeoForm(false)
    } catch (e: unknown) {
      setActionErr(e instanceof Error ? e.message : '操作失败')
    } finally {
      setActionLoading(false)
    }
  }

  function handleResolve() {
    if (!selected) return
    doAction(() => resolveIssue(selected.id, resolutionInput.trim(), handlerReplyInput.trim()))
  }

  function handleClose() {
    if (!selected) return
    doAction(() => closeIssue(selected.id, closeReason.trim(), handlerReplyInput.trim()))
  }

  function handleAssignHelper() {
    if (!selected || !helperInput.trim()) return
    doAction(() => assignIssueHelper(selected.id, helperInput.trim()))
  }

  function handleRequestCeo() {
    if (!selected || !ceoTarget.trim()) return
    doAction(() => requestIssueCeo(selected.id, ceoTarget.trim(), ceoNote.trim()))
  }

  async function confirmDelete(id: number) {
    await deleteIssue(id).catch(() => {})
    if (selected?.id === id) setSelected(null)
    setDeleteTarget(null)
    reload()
    toast.success('已删除')
  }

  async function confirmBulkDelete() {
    const ids = [...checked]
    await Promise.all(ids.map((id) => deleteIssue(id).catch(() => {})))
    setChecked(new Set())
    if (selected && ids.includes(selected.id)) setSelected(null)
    setBulkDeletePending(false)
    reload()
    toast.success(`已删除 ${ids.length} 条问题`)
  }

  const waiting = issues.filter((i) => i.status === '待处理').length
  const processing = issues.filter((i) => i.status === '处理中').length
  const resolved = issues.filter((i) => i.status === '已解决').length
  const decisions = issues.filter((i) => i.issue_type === '需决策' || i.status === '待决策').length

  return (
    <>
    <div className="flex-1 flex flex-col overflow-hidden">
      <header className="h-16 flex items-center px-6 gap-3 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1">
          <h1 className="text-base font-bold text-slate-800">问题与决策</h1>
          <p className="text-xs text-slate-400 mt-0.5">跟踪项目卡点、风险、待办事项与待决策事项</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="text-sm border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none">
            <option value="">全部类型</option><option>问题</option><option>风险</option><option>待协调</option><option>需决策</option>
          </select>
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="text-sm border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none">
            <option value="">全部状态</option><option>待处理</option><option>处理中</option><option>待决策</option><option>已解决</option><option>已关闭</option>
          </select>
          <select value={filterPriority} onChange={(e) => setFilterPriority(e.target.value)} className="text-sm border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none">
            <option value="">全部优先级</option><option>高</option><option>中</option><option>低</option>
          </select>
        </div>
        <button onClick={() => setAddOpen(true)} disabled={projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined} className="cursor-pointer flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)', boxShadow: '0 2px 8px rgba(3,105,161,0.25)' }}>
          <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" /></svg>
          新增问题
        </button>
      </header>

      <div className="flex-1 overflow-hidden flex" style={{ background: '#F1F5F9' }}>
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Stat cards */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: '待处理问题', val: waiting, color: '#D97706', bg: 'linear-gradient(135deg,#D97706,#FBBF24)' },
              { label: '处理中', val: processing, color: '#2563EB', bg: 'linear-gradient(135deg,#2563EB,#60A5FA)', accent: '#2563EB' },
              { label: '已解决', val: resolved, color: '#059669', bg: 'linear-gradient(135deg,#059669,#34D399)', accent: '#059669' },
              { label: '待决策事项', val: decisions, color: '#7C3AED', bg: 'linear-gradient(135deg,#7C3AED,#A78BFA)', accent: '#7C3AED' },
            ].map(({ label, val, color, bg, accent }) => (
              <div key={label} className="bg-white rounded-2xl border p-4 flex items-center gap-4" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)', borderLeft: accent ? `3px solid ${accent}` : undefined }}>
                <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 text-white" style={{ background: bg }}>
                  <svg style={{ width: 22, height: 22 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                </div>
                <div>
                  <p className="text-xs text-slate-500 font-medium">{label}</p>
                  <p className="text-3xl font-bold leading-none mt-1" style={{ color }}>{val}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Issue table */}
          <div className="bg-white rounded-2xl border p-5" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <h2 className="text-sm font-bold text-slate-800">问题清单</h2>
                <span className="text-xs text-slate-400">共 {filtered.length} 条</span>
              </div>
              {checked.size > 0 && (
                <div className="flex items-center gap-3">
                  <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-lg">已选 {checked.size} 项</span>
                  <button onClick={() => setChecked(new Set())} className="text-xs text-slate-500 hover:text-slate-700 font-medium cursor-pointer">清除</button>
                  {canDelete && !bulkDeletePending && (
                    <button onClick={() => setBulkDeletePending(true)} className="cursor-pointer flex items-center gap-1.5 text-xs font-semibold text-red-500 hover:text-red-700 px-2.5 py-1.5 rounded-lg hover:bg-red-50">
                      <svg style={{ width: 12, height: 12 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      批量删除
                    </button>
                  )}
                  {canDelete && bulkDeletePending && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-red-600 font-semibold">确认删除 {checked.size} 条？</span>
                      <button onClick={confirmBulkDelete} className="text-xs font-bold text-white bg-red-500 hover:bg-red-600 px-2.5 py-1 rounded-lg">确认</button>
                      <button onClick={() => setBulkDeletePending(false)} className="text-xs text-slate-500 hover:text-slate-700">取消</button>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs" style={{ minWidth: 900, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#E8EDF5', borderBottom: '1px solid #C7D2E8' }}>
                    <th className="py-2.5 px-3" style={{ width: 36 }}>
                      <input type="checkbox" checked={allChecked} onChange={toggleAll} style={{ width: 15, height: 15, accentColor: '#0369A1', cursor: 'pointer' }} />
                    </th>
                    {['问题描述', '问题类型', '关联专项', '负责人', '协助人', '优先级', '状态', '预计解决', '需决策人', '操作'].map((h) => (
                      <th key={h} className="text-left font-semibold pb-2.5 pr-3 py-2.5" style={{ color: '#475569' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={11} className="py-12 text-center text-slate-400">加载中…</td></tr>
                  ) : filtered.map((issue) => {
                    const isSelected = selected?.id === issue.id
                    const statusStyle = STATUS_STYLE[issue.status ?? ''] ?? { badge: 'bg-slate-100 text-slate-600', dot: '#94A3B8' }
                    return (
                      <tr
                        key={issue.id}
                        onClick={() => setSelected(issue)}
                        className="cursor-pointer transition-colors"
                        style={{ borderBottom: '1px solid #E2E8F0', background: isSelected ? '#EFF6FF' : 'white' }}
                      >
                        <td className="py-3 px-3" onClick={(e) => toggleOne(issue.id, e)}>
                          <input type="checkbox" checked={checked.has(issue.id)} onChange={() => {}} style={{ width: 15, height: 15, accentColor: '#0369A1', cursor: 'pointer' }} />
                        </td>
                        <td className="py-3 pr-3" style={{ maxWidth: 220 }}>
                          <p className="font-semibold text-slate-800 leading-snug">{issue.description ?? '-'}</p>
                          <p className="text-slate-400 mt-0.5">ISSUE-{issue.id}</p>
                        </td>
                        <td className="py-3 pr-3">
                          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold border ${TYPE_STYLE[issue.issue_type ?? ''] ?? 'bg-slate-50 text-slate-600 border-slate-200'}`}>
                            {issue.issue_type ?? '-'}
                          </span>
                        </td>
                        <td className="py-3 pr-3 text-slate-600">{issueProjectName(issue)}</td>
                        <td className="py-3 pr-3 text-slate-700 font-medium">{issue.owner ?? '-'}</td>
                        <td className="py-3 pr-3 text-slate-500">{issue.helper ?? '-'}</td>
                        <td className="py-3 pr-3">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold ${PRI_STYLE[issue.priority ?? ''] ?? 'bg-slate-100 text-slate-600'}`}>
                            {issue.priority ?? '-'}
                          </span>
                        </td>
                        <td className="py-3 pr-3">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${statusStyle.badge}`}>
                            <span className="w-1.5 h-1.5 rounded-full" style={{ background: statusStyle.dot }}></span>
                            {issue.status ?? '-'}
                          </span>
                        </td>
                        <td className="py-3 pr-3 text-slate-600 font-medium">{issue.expected_resolve_time ?? '-'}</td>
                        <td className="py-3 pr-3 text-slate-700">{issue.need_decision_by ?? '-'}</td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <button className="text-blue-500 hover:text-blue-700 font-semibold" onClick={(e) => { e.stopPropagation(); setSelected(issue) }}>查看</button>
                            {canDelete && (
                              <>
                                <span className="text-slate-200">|</span>
                                {deleteTarget === issue.id ? (
                                  <>
                                    <button className="text-red-600 font-bold text-xs" onClick={(e) => { e.stopPropagation(); confirmDelete(issue.id) }}>确认</button>
                                    <button className="text-slate-400 text-xs" onClick={(e) => { e.stopPropagation(); setDeleteTarget(null) }}>取消</button>
                                  </>
                                ) : (
                                  <button className="text-red-400 hover:text-red-600 font-semibold" onClick={(e) => { e.stopPropagation(); setDeleteTarget(issue.id) }}>删除</button>
                                )}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                  {!loading && filtered.length === 0 && (
                    <tr><td colSpan={11} className="py-12 text-center text-slate-400">暂无问题数据</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between mt-4 pt-4 border-t" style={{ borderColor: '#E9EFF6' }}>
              <span className="text-xs text-slate-400">共 {filtered.length} 条</span>
              <button className="w-7 h-7 rounded-lg text-white text-xs font-bold" style={{ background: '#0369A1' }}>1</button>
              <span className="text-xs text-slate-400">10 条/页</span>
            </div>
          </div>
        </div>

        {/* Right panel */}
        {selected && (() => {
          const st = selected.status ?? ''
          const tp = selected.issue_type ?? ''
          const isTerminal = st === '已解决' || st === '已关闭'
          const isClosed = st === '已关闭'
          const isDecision = tp === '需决策'
          const isCoordinate = tp === '待协调'
          return (
            <div style={{ width: 320, flexShrink: 0, background: '#fff', borderLeft: '1px solid #E9EFF6', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

              {/* ── Fixed header ── */}
              <div className="px-4 pt-4 pb-3 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-bold text-slate-800">问题详情</h2>
                  <button onClick={() => setSelected(null)} className="p-1 rounded-lg hover:bg-slate-100 text-slate-400">
                    <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
                <p className="text-xs font-semibold text-slate-700 leading-snug">{selected.description ?? '-'}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold ${PRI_STYLE[selected.priority ?? ''] ?? 'bg-slate-100 text-slate-600'}`}>{selected.priority ?? '-'}</span>
                  <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${STATUS_STYLE[st]?.badge ?? 'bg-slate-100 text-slate-600'}`}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: STATUS_STYLE[st]?.dot ?? '#94A3B8' }}></span>
                    {st || '-'}
                  </span>
                </div>
              </div>

              {/* ── Scrollable tracking info ── */}
              <div className="overflow-y-auto px-4 py-4" style={{ flex: '1 1 0', minHeight: 0 }}>
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">问题追踪</h3>
                <div className="space-y-2">
                  <div className="flex gap-2 text-xs py-1.5 border-b border-slate-50">
                    <span className="w-16 flex-shrink-0 text-slate-500 font-semibold">关联项目</span>
                    <span className="text-slate-800">{issueProjectName(selected)}</span>
                  </div>
                  {([
                    { label: '负责人', value: selected.owner },
                    { label: '协助人', value: selected.helper },
                    { label: '问题类型', value: tp },
                    { label: '需决策人', value: selected.need_decision_by },
                    { label: '预计解决', value: selected.expected_resolve_time },
                    { label: '创建时间', value: fmtDate(selected.created_at) },
                  ] as { label: string; value: string | undefined }[]).filter((r) => r.value).map(({ label, value }) => (
                    <div key={label} className="flex gap-2 text-xs py-1.5 border-b border-slate-50">
                      <span className="w-16 flex-shrink-0 text-slate-500 font-semibold">{label}</span>
                      <span className="text-slate-800">{value}</span>
                    </div>
                  ))}
                </div>
                {/* Show saved result only for terminal states */}
                {isTerminal && selected.resolution && (
                  <div className="mt-4">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                      {isDecision ? '决策结论' : '处理结论'}
                    </p>
                    <p className="text-xs text-slate-600 leading-relaxed p-3 rounded-xl" style={{ background: '#F0FDF4', border: '1px solid #BBF7D0' }}>{selected.resolution}</p>
                  </div>
                )}
                {isTerminal && selected.handler_reply && (
                  <div className="mt-3">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">回复给上报人</p>
                    <p className="text-xs text-amber-800 leading-relaxed p-3 rounded-xl" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>{selected.handler_reply}</p>
                  </div>
                )}
              </div>

              {/* ── Fixed processing area (hidden when 已关闭) ── */}
              {!isClosed && (
                <div className="px-4 py-3 border-t flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                  {actionErr && <p className="text-xs text-red-500 mb-2">{actionErr}</p>}

                  {/* ── Active: input forms ── */}
                  {!isTerminal && (
                    <>
                      {/* 待协调: helper assignment */}
                      {isCoordinate && (
                        <div className="mb-3">
                          <p className="text-xs font-semibold text-slate-500 mb-1">协助人</p>
                          <div className="flex gap-1.5">
                            <input
                              value={helperInput}
                              onChange={(e) => setHelperInput(e.target.value)}
                              placeholder="输入协助人姓名"
                              className="flex-1 text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-400"
                            />
                            {canOwnerAction && (
                              <button
                                onClick={handleAssignHelper}
                                disabled={actionLoading || !helperInput.trim() || projectArchived}
                                className="text-xs text-white font-semibold px-2.5 py-1.5 rounded-lg disabled:opacity-50"
                                style={{ background: '#0369A1' }}
                              >指定</button>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Resolution / decision textarea */}
                      <div className="mb-2">
                        <p className="text-xs font-semibold text-slate-500 mb-1">
                          {isDecision ? '决策结论' : '处理结论'}
                        </p>
                        <textarea
                          value={resolutionInput}
                          onChange={(e) => setResolutionInput(e.target.value)}
                          rows={2}
                          placeholder={isDecision
                            ? '请输入最终决策结论，例如：第一版先做关键词搜索，标签筛选放第二版'
                            : '请输入处理措施、结果或后续安排'}
                          className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-400 resize-none leading-relaxed"
                        />
                      </div>
                      {/* Handler reply — sent back to reporter */}
                      {selected.reporter && (
                        <div className="mb-2">
                          <p className="text-xs font-semibold text-slate-500 mb-1">
                            回复给上报人 <span className="font-normal text-slate-400">（{selected.reporter}，选填）</span>
                          </p>
                          <textarea
                            value={handlerReplyInput}
                            onChange={(e) => setHandlerReplyInput(e.target.value)}
                            rows={2}
                            placeholder="填写后会在上报人的工作台展示，告知处理结果"
                            className="w-full text-xs border border-amber-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-amber-400 resize-none leading-relaxed"
                            style={{ background: '#FFFBEB' }}
                          />
                        </div>
                      )}

                      {/* Primary action button */}
                      {canOwnerAction && (
                        <button
                          onClick={handleResolve}
                          disabled={actionLoading || projectArchived}
                          className="w-full py-2 rounded-lg text-white text-xs font-bold hover:opacity-90 disabled:opacity-50 mb-2"
                          style={{ background: isDecision ? 'linear-gradient(135deg,#7C3AED,#A78BFA)' : 'linear-gradient(135deg,#059669,#34D399)' }}
                        >
                          {isDecision ? '确认决策' : '标记已解决'}
                        </button>
                      )}

                      {/* 企业教练 escalation (not shown for decision issues — already is a decision) */}
                      {canOwnerAction && !isDecision && (
                        <div>
                          <button
                            onClick={() => setShowCeoForm(!showCeoForm)}
                            className="text-xs font-medium cursor-pointer"
                            style={{ color: showCeoForm ? '#94A3B8' : '#7C3AED' }}
                          >
                            {showCeoForm ? '▲ 收起' : '▼ 上报企业教练决策'}
                          </button>
                          {showCeoForm && (
                            <div className="mt-2 space-y-1.5">
                              <input
                                value={ceoTarget}
                                onChange={(e) => setCeoTarget(e.target.value)}
                                placeholder="决策人（如：企业教练）"
                                className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-purple-400"
                              />
                              <textarea
                                value={ceoNote}
                                onChange={(e) => setCeoNote(e.target.value)}
                                rows={2}
                                placeholder="上报说明（可选）"
                                className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-purple-400 resize-none"
                              />
                              <button
                                onClick={handleRequestCeo}
                                disabled={actionLoading || !ceoTarget.trim() || projectArchived}
                                className="w-full py-1.5 rounded-lg text-white text-xs font-bold hover:opacity-90 disabled:opacity-50"
                                style={{ background: '#7C3AED' }}
                              >确认上报</button>
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}

                  {/* ── Resolved: close section ── */}
                  {st === '已解决' && canOwnerAction && (
                    <>
                      <p className="text-xs font-semibold text-slate-500 mb-1">关闭说明（可选）</p>
                      <textarea
                        value={closeReason}
                        onChange={(e) => setCloseReason(e.target.value)}
                        rows={2}
                        placeholder="关闭原因或备注"
                        className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none resize-none mb-2 leading-relaxed"
                      />
                      <button
                        onClick={handleClose}
                        disabled={actionLoading}
                        className="w-full py-2 rounded-lg border border-slate-200 text-slate-600 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50"
                      >关闭事项</button>
                    </>
                  )}
                </div>
              )}
            </div>
          )
        })()}
      </div>
    </div>

    {addOpen && (
      <AddIssueModal
        projects={[]}
        currentProjectId={currentProjectId}
        onClose={() => setAddOpen(false)}
        onCreated={(item) => {
          setIssues((prev) => [item, ...prev])
          setSelected(item)
          setAddOpen(false)
          toast.success('问题已创建')
        }}
      />
    )}
    </>
  )
}

// ── AddIssueModal ──────────────────────────────────────────────────────────────

function AddIssueModal({ currentProjectId, onClose, onCreated }: {
  projects: { id: number; name: string }[]
  currentProjectId: number | null
  onClose: () => void
  onCreated: (item: IssueItem) => void
}) {
  const { projects } = useProject()
  const [form, setForm] = useState({
    project_id: currentProjectId ?? (projects[0]?.id ?? null) as number | null,
    issue_type: '问题',
    description: '',
    owner: '',
    priority: '中',
    expected_resolve_time: '',
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  function set(k: string, v: unknown) { setForm((f) => ({ ...f, [k]: v })) }

  async function handleSubmit() {
    if (!form.description.trim()) { setErr('请填写问题描述'); return }
    if (!form.project_id) { setErr('请选择关联专项'); return }
    setSaving(true); setErr('')
    try {
      const item = await createIssue({ ...form, project_id: form.project_id })
      onCreated(item)
    } catch (e) {
      setErr(e instanceof Error ? e.message : '创建失败，请重试')
    } finally { setSaving(false) }
  }

  const inputCls = 'w-full text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-blue-400 bg-white'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between border-b px-5 py-4" style={{ borderColor: '#E9EFF6' }}>
          <h2 className="text-base font-bold text-slate-800">新增问题</h2>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100">
            <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">关联专项 <span className="text-red-400">*</span></label>
            <select value={form.project_id ?? ''} onChange={(e) => set('project_id', Number(e.target.value) || null)} className={inputCls}>
              <option value="">请选择</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">问题类型</label>
            <select value={form.issue_type} onChange={(e) => set('issue_type', e.target.value)} className={inputCls}>
              <option>问题</option><option>风险</option><option>待协调</option><option>需决策</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">问题描述 <span className="text-red-400">*</span></label>
            <textarea value={form.description} onChange={(e) => set('description', e.target.value)} rows={3}
              placeholder="描述问题、影响范围和期望结果"
              className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-blue-400 resize-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5">负责人</label>
              <input value={form.owner} onChange={(e) => set('owner', e.target.value)} placeholder="姓名" className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5">优先级</label>
              <select value={form.priority} onChange={(e) => set('priority', e.target.value)} className={inputCls}>
                <option>高</option><option>中</option><option>低</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">预计解决时间</label>
            <input type="date" value={form.expected_resolve_time} onChange={(e) => set('expected_resolve_time', e.target.value)} className={inputCls} />
          </div>
          {err && <p className="text-xs text-red-500">{err}</p>}
        </div>
        <div className="flex justify-end gap-3 border-t px-5 py-4" style={{ borderColor: '#E9EFF6' }}>
          <button onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600">取消</button>
          <button onClick={handleSubmit} disabled={saving}
            className="rounded-xl px-5 py-2 text-sm font-bold text-white disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
            {saving ? '创建中...' : '创建问题'}
          </button>
        </div>
      </div>
    </div>
  )
}
