import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchMeetings, patchMeetingStatus } from '../api/meetings'
import { useProject } from '../context/ProjectContext'
import type { MeetingItem } from '../types'
import { InfoRow, MeetingSection, renderJsonList } from '../features/meeting/meetingShared'
import { toast } from '../utils/toast'
import { SkeletonTableRows } from '../components/Skeleton'
import { NewMeetingModal } from '../features/meeting/NewMeetingModal'
import { STATUS_CONFIG, TYPE_STYLE, fmtTime, getStatus, typeLabel, type PublishStatus } from '../features/meeting/meetingUtils'
import { getProjectDisplayName } from '../domain/projectDisplay'
import { isProjectArchived } from '../domain/projectLifecycleStatus'

export function MeetingPage() {
  const { currentProjectId, projects } = useProject()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlProjectId = searchParams.get('projectId')
  const urlMeetingType = searchParams.get('meeting_type') ?? ''
  const effectiveProjectId = urlProjectId ? Number(urlProjectId) : currentProjectId
  const [meetings, setMeetings] = useState<MeetingItem[]>([])
  const [selected, setSelected] = useState<MeetingItem | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [typeFilter, setTypeFilter] = useState('')
  const [returnNote, setReturnNote] = useState('')
  const [showReturnInput, setShowReturnInput] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [editingItem, setEditingItem] = useState<MeetingItem | null>(null)

  const currentProject = projects.find((p) => p.id === currentProjectId) ?? null
  const projectArchived = isProjectArchived(currentProject)
  const noProject = !effectiveProjectId

  useEffect(() => {
    if (!effectiveProjectId) return
    let cancelled = false
    setLoading(true)
    fetchMeetings(effectiveProjectId)
      .then((d) => {
        if (!cancelled) {
          setMeetings(d)
          if (d.length > 0) setSelected(d[0])
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [effectiveProjectId])

  async function handleStatusChange(status: PublishStatus) {
    if (!selected) return
    setActionLoading(true)
    try {
      const updated = await patchMeetingStatus(selected.id, status)
      setMeetings((prev) => prev.map((m) => (m.id === updated.id ? updated : m)))
      setSelected(updated)
      if (status !== 'returned') setShowReturnInput(false)
      setReturnNote('')
    } catch {
      toast.error('操作失败，请稍后重试')
    } finally {
      setActionLoading(false)
    }
  }

  function handleCreated(m: MeetingItem) {
    setMeetings((prev) => {
      const idx = prev.findIndex((x) => x.id === m.id)
      if (idx >= 0) {
        const updated = [...prev]
        updated[idx] = m
        return updated
      }
      return [m, ...prev]
    })
    setSelected(m)
    setShowNewModal(false)
    setEditingItem(null)
  }

  const typeOptions = [...new Set(meetings.map((m) => typeLabel(m.meeting_type)).filter((l) => l !== '-'))]
  const filtered = typeFilter ? meetings.filter((m) => typeLabel(m.meeting_type) === typeFilter) : meetings
  const selStatus = selected ? getStatus(selected) : 'draft'
  const statusCfg = STATUS_CONFIG[selStatus]

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <header className="h-16 flex items-center px-6 gap-4 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1">
          <h1 className="text-base font-bold text-slate-800">会议纪要</h1>
        </div>

        <div className="flex items-center gap-2">
          <select
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="">全部类型</option>
            {typeOptions.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowNewModal(true)}
            disabled={noProject || projectArchived}
            title={projectArchived ? '项目已归档，不可写入。' : noProject ? '请先选择下方项目' : undefined}
            className="cursor-pointer flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)', boxShadow: '0 2px 8px rgba(3,105,161,0.25)' }}
          >
            <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            新建会议纪要
          </button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto p-6" style={{ background: '#F1F5F9' }}>
        {!effectiveProjectId && !loading && (
          <div className="max-w-md mx-auto mt-16">
            <div className="bg-white rounded-2xl border p-6 text-center" style={{ borderColor: '#E9EFF6' }}>
              <h2 className="text-base font-bold text-slate-700 mb-2">请选择要查看的项目</h2>
              <p className="text-sm text-slate-400 mb-5">选择一个项目，即可查看和创建会议纪要</p>
              <div className="space-y-2">
                {projects.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setSearchParams((prev) => { prev.set('projectId', String(p.id)); return prev })}
                    className="w-full text-left px-4 py-3 rounded-xl border border-slate-200 text-sm font-medium text-slate-700 hover:bg-blue-50 hover:border-blue-200 transition-colors"
                  >
                    <div>{p.name}</div>
                    {p.code && <div className="text-xs text-slate-400 mt-0.5">{p.code}</div>}
                  </button>
                ))}
              </div>
              <p className="text-xs text-slate-400 mt-4">
                或从左侧菜单进入任意项目功能区，顶部栏会自动切换当前项目
              </p>
            </div>
          </div>
        )}
        {effectiveProjectId && (
          <>
            {loading && (
              <div className="bg-white rounded-2xl border p-4" style={{ borderColor: '#E9EFF6' }}>
                <table className="w-full text-sm"><tbody><SkeletonTableRows rows={6} cols={6} /></tbody></table>
              </div>
            )}

        {selected && (
          <div className="grid grid-cols-5 gap-5 mb-5">
            <div className="bg-white rounded-2xl border p-5 col-span-2 overflow-y-auto" style={{ maxHeight: 560, borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#6366F1,#0EA5E9)' }}>
                    <svg style={{ width: 12, height: 12, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <h2 className="text-sm font-bold text-slate-800">会议纪要正文</h2>
                </div>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${statusCfg.cls}`}>{statusCfg.label}</span>
              </div>
              <div className="space-y-4">
                <MeetingSection title="会议信息">
                  <InfoRow label="会议名称" value={selected.title ?? '-'} />
                  <InfoRow label="日期" value={selected.meeting_date ?? '-'} />
                  <InfoRow label="主持人" value={selected.host ?? '-'} />
                  <InfoRow label="参会人" value={selected.participants ?? '-'} />
                  <InfoRow label="类型" value={typeLabel(selected.meeting_type)} />
                </MeetingSection>
                {selected.summary && (
                  <MeetingSection title="会议摘要">
                    <p className="text-xs text-slate-600 leading-relaxed">{selected.summary}</p>
                  </MeetingSection>
                )}
                {selected.task_list_json && <MeetingSection title="行动清单">{renderJsonList(selected.task_list_json, '#94A3B8')}</MeetingSection>}
                {selected.decision_items_json && <MeetingSection title="决策事项">{renderJsonList(selected.decision_items_json, '#3B82F6')}</MeetingSection>}
              </div>
            </div>

            <div className="col-span-3 flex flex-col gap-4">
              <div className="bg-white rounded-2xl border p-5" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
                <h2 className="text-sm font-bold text-slate-800 mb-4">相关信息</h2>
                <div className="space-y-2 text-xs">
                  <InfoRow label="关联专项" value={getProjectDisplayName(projects, selected) || '-'} />
                  <InfoRow label="创建时间" value={fmtTime(selected.created_at)} />
                </div>
              </div>
              <div className="bg-white rounded-2xl border p-5" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
                <h2 className="text-sm font-bold text-slate-800 mb-4">操作</h2>
                {selStatus === 'published' ? (
                  <div className="flex items-center gap-2 text-sm text-emerald-600 font-semibold py-2">
                    <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                    </svg>
                    已发布
                    <button className="ml-auto text-xs text-slate-400 hover:text-slate-600 border border-slate-200 rounded px-2 py-1" onClick={() => handleStatusChange('returned')} disabled={actionLoading || projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined}>
                      撤回
                    </button>
                  </div>
                ) : selStatus === 'returned' ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-sm text-red-500 font-semibold">
                      <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      已退回
                    </div>
                    <button className="w-full py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }} onClick={() => handleStatusChange('published')} disabled={actionLoading || projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined}>
                      {actionLoading ? '处理中...' : '重新发布'}
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex gap-3">
                      <button className="cursor-pointer flex-1 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }} onClick={() => handleStatusChange('published')} disabled={actionLoading || projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined}>
                        {actionLoading ? '处理中...' : '校对并发布'}
                      </button>
                      <button className="cursor-pointer flex-1 py-2.5 rounded-xl border-2 border-slate-200 text-slate-600 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50" onClick={() => setShowReturnInput((v) => !v)} disabled={actionLoading || projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined}>
                        退回修改
                      </button>
                    </div>
                    {showReturnInput && (
                      <div className="space-y-2">
                        <textarea
                          className="w-full border border-slate-200 rounded-lg p-2.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-300 resize-none"
                          rows={3}
                          placeholder="填写退回原因（可选）"
                          value={returnNote}
                          onChange={(e) => setReturnNote(e.target.value)}
                        />
                        <div className="flex gap-2 justify-end">
                          <button className="text-xs text-slate-400 hover:text-slate-600 px-3 py-1.5 rounded border border-slate-200" onClick={() => { setShowReturnInput(false); setReturnNote('') }}>
                            取消
                          </button>
                          <button className="text-xs text-white px-3 py-1.5 rounded font-semibold" style={{ background: '#EF4444' }} onClick={() => handleStatusChange('returned')} disabled={actionLoading || projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined}>
                            确认退回
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="bg-white rounded-2xl border p-5" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">会议记录列表</h2>
            <span className="text-xs text-slate-400">共 {filtered.length} 条</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b" style={{ borderColor: '#E9EFF6' }}>
                  {['会议名称', '类型', '日期', '关联专项', '纪要状态', '操作'].map((h) => (
                    <th key={h} className="text-left text-slate-400 font-semibold pb-2.5 pr-4">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((m) => {
                  const st = getStatus(m)
                  const sc = STATUS_CONFIG[st]
                  const isSel = selected?.id === m.id
                  return (
                    <tr key={m.id} className="cursor-pointer border-b hover:bg-slate-50 transition-colors" style={{ borderColor: '#F8FAFC', background: isSel ? '#EFF6FF' : 'white' }}>
                      <td className="py-3 pr-4 font-semibold text-slate-700">{m.title ?? '-'}</td>
                      <td className="py-3 pr-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold ${TYPE_STYLE[typeLabel(m.meeting_type)] ?? 'bg-slate-100 text-slate-600'}`}>
                          {typeLabel(m.meeting_type)}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-slate-500">{m.meeting_date ?? '-'}</td>
                      <td className="py-3 pr-4 text-slate-500">{getProjectDisplayName(projects, m) || '-'}</td>
                      <td className="py-3 pr-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${sc.cls}`}>{sc.label}</span>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <button className="text-blue-500 hover:text-blue-700 font-medium" onClick={() => { setSelected(m); setShowReturnInput(false) }}>
                            查看
                          </button>
                          <span className="text-slate-200">|</span>
                          <button className="text-slate-400 hover:text-slate-600 font-medium" disabled={projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined} onClick={() => setEditingItem(m)}>编辑</button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {filtered.length === 0 && !loading && (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      暂无会议记录
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-4 pt-4 border-t" style={{ borderColor: '#E9EFF6' }}>
            <span className="text-xs text-slate-400">{filtered.length} 条</span>
            <button className="w-7 h-7 rounded-lg text-white text-xs font-bold" style={{ background: '#0369A1' }}>
              1
            </button>
            <span className="text-xs text-slate-400">10 条 / 页</span>
          </div>
        </div>
          </>
        )}
      </main>

      {showNewModal && effectiveProjectId && <NewMeetingModal projectId={effectiveProjectId} defaultMeetingType={urlMeetingType} onClose={() => setShowNewModal(false)} onCreated={handleCreated} />}
      {editingItem && effectiveProjectId && <NewMeetingModal projectId={effectiveProjectId} editItem={editingItem} onClose={() => setEditingItem(null)} onCreated={handleCreated} />}
    </div>
  )
}
