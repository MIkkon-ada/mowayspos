import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { analyzeProgressReview, deleteMeeting, fetchMeetingRevisions, fetchMeetings, fetchProjectMeetingReviewPackage, patchMeetingStatus, projectMeetingDocumentDownloadUrl, reviewProjectMeeting, updateMeeting, type MeetingRevisionItem, type ProjectMeetingRun } from '../api/meetings'
import { useProject } from '../context/ProjectContext'
import type { MeetingItem } from '../types'
import { InfoRow, MeetingSection, renderJsonList } from '../features/meeting/meetingShared'
import { toast } from '../utils/toast'
import { SkeletonTableRows } from '../components/Skeleton'
import { NewMeetingModal } from '../features/meeting/NewMeetingModal'
import { KickoffAgentWorkspace } from '../features/meeting/KickoffAgentWorkspace'
import { MeetingProgressReviewSection } from '../features/meeting/MeetingProgressReviewSection'
import { MeetingDetailWorkspace } from '../features/meeting/MeetingDetailWorkspace'
import { STATUS_CONFIG, fmtTime, getStatus, type PublishStatus } from '../features/meeting/meetingUtils'
import { getProjectDisplayName } from '../domain/projectDisplay'
import { isProjectArchived } from '../domain/projectLifecycleStatus'
import { ProjectMeetingReviewWorkspace } from '../features/meeting/ProjectMeetingReviewWorkspace'
import { MobileMeetingTimeline } from '../features/mobile-core-pages/MobileMeetingTimeline'

export function MeetingPage() {
  const { currentProjectId, projects, currentUser, currentProjectRoles } = useProject()
  const navigate = useNavigate()
  const { meetingId: pathMeetingId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlProjectId = searchParams.get('projectId')
  const urlMeetingId = pathMeetingId ?? searchParams.get('meetingId')
  const effectiveProjectId = urlProjectId ? Number(urlProjectId) : currentProjectId
  const [meetings, setMeetings] = useState<MeetingItem[]>([])
  const [selected, setSelected] = useState<MeetingItem | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [deletingMeetingId, setDeletingMeetingId] = useState<number | null>(null)
  const [returnNote, setReturnNote] = useState('')
  const [showReturnInput, setShowReturnInput] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [editingItem, setEditingItem] = useState<MeetingItem | null>(null)
  const [projectQuery, setProjectQuery] = useState('')
  const [meetingQuery, setMeetingQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [timeFilter, setTimeFilter] = useState('')
  const [projectMeetings, setProjectMeetings] = useState<Record<number, MeetingItem[]>>({})
  const [revisions, setRevisions] = useState<MeetingRevisionItem[]>([])
  const [selectedRevision, setSelectedRevision] = useState<MeetingRevisionItem | null>(null)
  const [progressReviewRefresh, setProgressReviewRefresh] = useState(0)
  const [projectMeetingReview, setProjectMeetingReview] = useState<ProjectMeetingRun | null>(null)

  const currentProject = projects.find((p) => p.id === currentProjectId) ?? null
  const effectiveProject = projects.find((p) => p.id === effectiveProjectId) ?? null
  const pending_kickoff = String(effectiveProject?.lifecycle_status ?? effectiveProject?.status ?? '') === 'pending_kickoff'
  const projectArchived = isProjectArchived(effectiveProject)
  const canDeleteMeeting = Boolean(currentUser?.is_tech_admin || (effectiveProject?.user_roles ?? currentProjectRoles).includes('owner'))
  const legacySelected = selected as MeetingItem
  const noProject = !effectiveProjectId
  const normalizedProjectQuery = projectQuery.trim().toLowerCase()
  const projectIds = projects.map((project) => project.id).join(',')
  const visibleProjects = normalizedProjectQuery
    ? projects.filter((project) => {
        const manager = project.owners?.[0] ?? project.coordinator ?? ''
        return [project.name, project.code ?? '', manager].some((value) => value.toLowerCase().includes(normalizedProjectQuery))
      })
    : projects

  useEffect(() => {
    if (!effectiveProjectId) return
    let cancelled = false
    setLoading(true)
    fetchMeetings(effectiveProjectId)
      .then((d) => {
        if (!cancelled) {
          setMeetings(d)
          setSelected(urlMeetingId ? d.find((item) => String(item.id) === urlMeetingId) ?? null : null)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [effectiveProjectId, urlMeetingId])

  useEffect(() => {
    if (!selected) {
      setRevisions([])
      setSelectedRevision(null)
      return
    }
    let cancelled = false
    fetchMeetingRevisions(selected.id)
      .then((rows) => {
        if (cancelled) return
        setRevisions(rows)
        setSelectedRevision(rows[0] ?? null)
      })
      .catch(() => {
        if (!cancelled) {
          setRevisions([])
          setSelectedRevision(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [selected?.id])

  useEffect(() => {
    const sourceId = Number((selected as (MeetingItem & { document_source_id?: number | null }) | null)?.document_source_id ?? 0)
    if (!selected || !sourceId) {
      setProjectMeetingReview(null)
      return
    }
    let cancelled = false
    fetchProjectMeetingReviewPackage(selected.id)
      .then((pkg) => { if (!cancelled) setProjectMeetingReview(pkg) })
      .catch(() => { if (!cancelled) setProjectMeetingReview(null) })
    return () => { cancelled = true }
  }, [selected?.id])

  useEffect(() => {
    if (effectiveProjectId || !projectIds) return
    let cancelled = false
    setProjectMeetings({})
    Promise.all(projects.map(async (project) => [project.id, await fetchMeetings(project.id).catch(() => [])] as const))
      .then((entries) => {
        if (cancelled) return
        setProjectMeetings(Object.fromEntries(entries))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [effectiveProjectId, projectIds])

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

  async function handleCreated(m: MeetingItem) {
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
    try {
      await analyzeProgressReview(m.id)
      setProgressReviewRefresh((value) => value + 1)
    } catch {
      toast.error('会议已保存，但成员完成情况分析未完成，可在详情中重试')
    }
  }

  async function handleDeleteMeeting(meeting: MeetingItem) {
    const title = meeting.title ?? '未命名会议'
    if (!window.confirm('确认删除会议纪要「' + title + '」吗？此操作不可恢复。')) return
    setDeletingMeetingId(meeting.id)
    try {
      await deleteMeeting(meeting.id)
      setMeetings((rows) => rows.filter((row) => row.id !== meeting.id))
      setSelected((row) => row?.id === meeting.id ? null : row)
      toast.success('会议纪要已删除')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '删除会议纪要失败')
    } finally {
      setDeletingMeetingId(null)
    }
  }

  const statusOptions = [...new Set(meetings.map((meeting) => getStatus(meeting)))]
  const timeOptions = [...new Set(meetings.map((meeting) => meeting.meeting_date?.slice(0, 4)).filter(Boolean))].sort().reverse() as string[]
  const normalizedMeetingQuery = meetingQuery.trim().toLowerCase()
  const filtered = meetings
    .filter((meeting) => {
      const haystack = [meeting.title, meeting.summary, meeting.host].filter(Boolean).join(' ').toLowerCase()
      return (!normalizedMeetingQuery || haystack.includes(normalizedMeetingQuery))
        && (!statusFilter || getStatus(meeting) === statusFilter)
        && (!timeFilter || meeting.meeting_date?.startsWith(timeFilter))
    })
    .sort((a, b) => new Date(b.meeting_date ?? '').getTime() - new Date(a.meeting_date ?? '').getTime())
  const selStatus = selected ? getStatus(selected) : 'draft'
  const statusCfg = STATUS_CONFIG[selStatus]
  const projectMemberCount = effectiveProject ? Object.values(effectiveProject.member_counts ?? {}).reduce((sum, count) => sum + count, 0) : 0
  const projectDate = (value?: string) => value ? value.slice(0, 10).replace(/-/g, '/') : '-'
  const meetingEditor = effectiveProjectId && !pending_kickoff && (showNewModal || editingItem)
     ? <NewMeetingModal
         projectId={effectiveProjectId}
         editItem={editingItem ?? undefined}
        onClose={() => {
          setShowNewModal(false)
          setEditingItem(null)
        }}
        onCreated={handleCreated}
      />
    : null

  if (meetingEditor) return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {meetingEditor}
    </div>
  )

  if (selected && projectMeetingReview) {
    const snapshot = projectMeetingReview.snapshot
    const project = snapshot.project
    const workstreams = snapshot.workstreams ?? []
    const keyTasks = workstreams.flatMap((workstream) => (workstream.key_tasks ?? []).map((task) => ({
      id: task.id,
      workstreamId: workstream.id,
      title: task.title,
      status: task.status,
      progress: '',
    })))
    const scheduleChanges = projectMeetingReview.review_package?.proposals ?? projectMeetingReview.result.execution_schedule_changes ?? []
    const meetingDraft = selected
    const isOwner = Boolean(currentUser?.is_tech_admin || currentProjectRoles.includes('owner'))
    return (
      <div className="flex flex-1 flex-col overflow-hidden">
        <main className="flex-1 overflow-y-auto">
          <ProjectMeetingReviewWorkspace
            projectContext={{
              projectId: effectiveProjectId ?? project?.id ?? 0,
              projectName: project?.name ?? effectiveProject?.name ?? '',
              projectCode: project?.code ?? '',
              members: (snapshot.members ?? []).map((member) => ({ id: member.person_id, name: member.name, role: member.role })),
              workstreams: workstreams.map((workstream) => ({ id: workstream.id, title: workstream.key_task, status: workstream.status })),
              keyTasks,
            }}
            meetingDraft={{
              id: meetingDraft.id,
              project_id: meetingDraft.project_id,
              title: meetingDraft.title ?? '',
              meeting_type: meetingDraft.meeting_type ?? '',
              meeting_date: meetingDraft.meeting_date ?? '',
              location: meetingDraft.location ?? '',
              host: meetingDraft.host ?? '',
              participants: meetingDraft.participants ?? '',
              organizer: meetingDraft.organizer ?? '',
              copied_to: meetingDraft.copied_to ?? '',
              summary: meetingDraft.summary ?? '',
              publish_status: meetingDraft.publish_status ?? 'draft',
              decisions: projectMeetingReview.result.decisions ?? [],
              actions: [...(projectMeetingReview.result.completed_items ?? []), ...(projectMeetingReview.result.next_stage_work ?? [])],
              risks: projectMeetingReview.result.risks ?? [],
              sourceFilename: projectMeetingReview.document?.original_name,
            }}
            meetingInfoEvidence={projectMeetingReview.result.meeting_info_evidence ?? {}}
            summaryEvidence={projectMeetingReview.result.summary_evidence}
            openQuestions={projectMeetingReview.result.open_questions ?? []}
            agentAudit={projectMeetingReview.audit}
            scheduleChanges={scheduleChanges.map((change, index) => {
              const agentChange = projectMeetingReview.result.execution_schedule_changes?.[index]
              const workstreamId = change.parent_workstream_id ?? change.target?.workstream_id ?? agentChange?.parent_workstream_id ?? agentChange?.target?.workstream_id ?? null
              const parentSubtaskId = change.parent_subtask_id ?? change.target?.key_task_id ?? agentChange?.parent_subtask_id ?? agentChange?.target?.key_task_id ?? null
              return {
                id: change.id,
                scheduleId: change.target_id,
                workstreamId,
                parentSubtaskId,
                keyTaskId: parentSubtaskId ?? 0,
                workstreamTitle: workstreams.find((workstream) => workstream.id === workstreamId)?.key_task ?? '未匹配重点工作',
                keyTaskTitle: keyTasks.find((task) => task.id === parentSubtaskId)?.title ?? '未匹配关键任务',
                title: String(change.proposed.title ?? change.action),
                before: change.before,
                proposed: change.proposed,
                evidence: change.evidence,
                reason: change.reason,
                confidence: change.confidence,
                needsConfirmation: Boolean(change.needs_confirmation ?? agentChange?.needs_confirmation),
                validationState: change.validation.state,
                validationErrors: change.validation.errors,
                executionStatus: change.execution_status,
                conflictReason: change.conflict_reason,
                lineage: change.lineage,
              }
            })}
            isOwner={isOwner}
            onSaveDraft={async (draft) => {
              setActionLoading(true)
              try {
                const updated = await updateMeeting(selected.id, {
                  project_id: Number(draft.project_id ?? selected.project_id ?? effectiveProjectId),
                  title: draft.title ?? '',
                  meeting_type: draft.meeting_type ?? '',
                  meeting_date: draft.meeting_date ?? '',
                  location: draft.location ?? '',
                  host: draft.host ?? '',
                  participants: draft.participants ?? '',
                  organizer: draft.organizer ?? '',
                  copied_to: draft.copied_to ?? '',
                  agenda_items_json: selected.agenda_items_json ?? '[]',
                  prior_action_items_json: selected.prior_action_items_json ?? '[]',
                  source_mode: selected.source_mode ?? 'ai_analysis',
                  summary: draft.summary ?? '',
                  task_list_json: selected.task_list_json ?? '[]',
                  decision_items_json: selected.decision_items_json ?? '[]',
                  risk_items_json: selected.risk_items_json ?? '[]',
                  transcript_text: String(selected.transcript_text ?? ''),
                })
                setSelected(updated)
                setMeetings((current) => current.map((item) => item.id === updated.id ? updated : item))
                toast.success('负责人编辑已保存，尚未回填任何子计划')
              } catch {
                toast.error('保存负责人编辑失败，请稍后重试')
              } finally {
                setActionLoading(false)
              }
            }}
            onPublish={async () => {
              setActionLoading(true)
              try {
                const updated = await reviewProjectMeeting(selected.id, { action: 'publish' })
                setSelected(updated)
                setMeetings((current) => current.map((item) => item.id === updated.id ? updated : item))
                toast.success('会议纪要已发布，项目计划尚未变更')
              } catch { toast.error('发布失败，请检查审核状态或权限') } finally { setActionLoading(false) }
            }}
            onApplyChanges={async (proposalIds) => {
              setActionLoading(true)
              try {
                const updated = await reviewProjectMeeting(selected.id, { action: 'apply_changes', proposal_ids: proposalIds })
                setSelected(updated)
                setMeetings((current) => current.map((item) => item.id === updated.id ? updated : item))
                const refreshed = await fetchProjectMeetingReviewPackage(updated.id).catch(() => null)
                if (refreshed) setProjectMeetingReview(refreshed)
                toast.success('已回填选中的执行安排变更')
              } catch { toast.error('回填失败，项目计划未变更；请检查提案状态或数据冲突') } finally { setActionLoading(false) }
            }}
            onReturn={async (reason) => {
              setActionLoading(true)
              try {
                const updated = await reviewProjectMeeting(selected.id, { action: 'return', reason })
                setSelected(updated)
                setProjectMeetingReview(null)
                toast.success('会议纪要已退回，并记录退回原因')
              } catch { toast.error('退回失败，请稍后重试') } finally { setActionLoading(false) }
            }}
            onDownload={() => { window.open(projectMeetingDocumentDownloadUrl(selected.id), '_blank', 'noopener,noreferrer') }}
            busy={actionLoading}
          />
        </main>
      </div>
    )
  }

  if (selected) return (
    <div className="flex flex-1 flex-col overflow-hidden meeting-list-view">
      <header className="flex min-h-16 shrink-0 items-center border-b bg-white px-4 py-3 lg:px-6" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
          <span>会议纪要</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-800">会议详情</span>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto bg-slate-100 p-4 lg:p-6">
        <MeetingDetailWorkspace
          meeting={selected}
          projectName={effectiveProject?.name ?? ''}
          projectArchived={projectArchived}
          actionLoading={actionLoading}
          onBack={() => {
            setSelected(null)
            navigate(`/work/meetings?projectId=${effectiveProjectId}`)
          }}
          onEdit={() => setEditingItem(selected)}
          onStatusChange={(status) => { void handleStatusChange(status) }}
        />
      </main>
    </div>
  )

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <header className="min-h-16 flex flex-wrap items-center px-4 py-3 lg:px-6 gap-4 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1 min-w-0">
          {effectiveProjectId ? (
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-500">
              <span>会议纪要</span>
              <span className="text-slate-300">/</span>
              <span className="text-slate-800">会议列表</span>
            </div>
          ) : <h1 className="text-base font-bold text-slate-800">会议纪要</h1>}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!effectiveProjectId && (
            <div className="relative">
              <svg className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="11" cy="11" r="7" strokeWidth="2" />
                <path strokeLinecap="round" strokeWidth="2" d="m20 20-3.5-3.5" />
              </svg>
              <input
                aria-label="搜索项目"
                value={projectQuery}
                onChange={(event) => setProjectQuery(event.target.value)}
                placeholder="搜索项目名称、编号或项目经理"
                className="w-64 rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm text-slate-700 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              />
            </div>
          )}
          {effectiveProjectId && (
            <div className="relative hidden min-[900px]:block">
              <svg className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="11" cy="11" r="7" strokeWidth="2" />
                <path strokeLinecap="round" strokeWidth="2" d="m20 20-3.5-3.5" />
              </svg>
              <input
                aria-label="搜索会议主题"
                value={meetingQuery}
                onChange={(event) => setMeetingQuery(event.target.value)}
                placeholder="搜索会议主题"
                className="w-56 rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm text-slate-700 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
              />
            </div>
          )}
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
            {pending_kickoff ? '发起启动会确认' : '新建会议纪要'}
          </button>
        </div>
      </header>

      <main className={`flex-1 overflow-y-auto p-4 lg:p-6 ${effectiveProjectId ? 'meeting-list-view' : ''}`} style={{ background: '#F1F5F9' }}>
        {!effectiveProjectId && !loading && (
          <div className="mx-auto mt-4 w-full max-w-[1280px]">
            <div className="p-2 sm:p-4">
              <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-bold text-slate-800 mb-2">选择项目</h2>
                  <p className="text-sm text-slate-500">选择项目查看对应的会议记录</p>
                </div>
                <span className="text-sm text-slate-400">共 {visibleProjects.length} 个项目</span>
              </div>
              <div className="project-selector-table overflow-hidden rounded-xl border border-slate-200 bg-white text-left shadow-sm">
                <div className="overflow-x-auto">
                  <div className="min-w-[880px]">
                    <div className="grid grid-cols-[minmax(280px,2fr)_120px_150px_minmax(220px,1.4fr)_150px] items-center gap-4 border-b border-slate-200 bg-slate-50/70 px-5 py-3 text-xs font-medium text-slate-500">
                      <span>项目名称</span>
                      <span>状态</span>
                      <span>项目经理</span>
                      <span>最近会议</span>
                      <span className="text-right">操作</span>
                    </div>
                    {visibleProjects.map((p, index) => {
                  const manager = p.owners?.[0] ?? p.coordinator ?? '—'
                  const shortDate = (value?: string) => {
                    if (!value) return '—'
                    const [, month, day] = value.split('-')
                    if (!month || !day) return value
                    return `${month.padStart(2, '0')}/${day.slice(0, 2).padStart(2, '0')}`
                  }
                  const statusLabel = p.is_active ? '进行中' : '未启用'
                  const projectMeetingList = projectMeetings[p.id] ?? []
                  const recentMeeting = [...projectMeetingList].sort((a, b) => {
                    const aTime = a.meeting_date ? new Date(a.meeting_date).getTime() : Number.NEGATIVE_INFINITY
                    const bTime = b.meeting_date ? new Date(b.meeting_date).getTime() : Number.NEGATIVE_INFINITY
                    return bTime - aTime
                  })[0]
                  const iconClass = ['bg-sky-500', 'bg-violet-500', 'bg-orange-500'][index % 3]

                  return (
                    <button
                      key={p.id}
                      onClick={() => setSearchParams((prev) => { prev.set('projectId', String(p.id)); return prev })}
                      className="grid w-full grid-cols-[minmax(280px,2fr)_120px_150px_minmax(220px,1.4fr)_150px] items-center gap-4 border-b border-slate-100 px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-sky-50/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-400"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${iconClass} text-white shadow-sm`}>
                          <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 3v3m0 12v3M3 12h3m12 0h3M5.64 5.64l2.12 2.12m8.48 8.48 2.12 2.12m0-12.72-2.12 2.12m-8.48 8.48-2.12 2.12M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
                          </svg>
                        </div>
                        <div className="min-w-0 truncate text-base font-semibold text-slate-800" title={p.name}>{p.name}</div>
                      </div>
                      <span className={`w-fit rounded-full px-2.5 py-1 text-[11px] font-medium ${p.is_active ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'}`}>{statusLabel}</span>
                      <span className="truncate text-sm text-slate-700" title={manager}>{manager}</span>
                      {recentMeeting ? (
                        <span className="truncate text-sm text-slate-700" title={`${recentMeeting.title ?? '未命名会议'} · ${shortDate(recentMeeting.meeting_date)}`}>
                          {recentMeeting.title ?? '未命名会议'} <span className="text-slate-400">· {shortDate(recentMeeting.meeting_date)}</span>
                        </span>
                      ) : <span className="text-sm text-slate-400">暂无会议记录</span>}
                      <span className="text-right text-sm font-medium text-sky-600">查看会议纪要　→</span>
                    </button>
                  )
                    })}
                  </div>
                </div>
              </div>
              {visibleProjects.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-200 py-12 text-center text-sm text-slate-400">未找到匹配项目</div>
              )}
            </div>
          </div>
        )}
        {effectiveProjectId && (
          <>
            <div className="mx-auto w-full max-w-[1180px] space-y-4">
              <button
                type="button"
                onClick={() => setSearchParams((prev) => { prev.delete('projectId'); prev.delete('meetingId'); return prev })}
                className="inline-flex items-center gap-2 px-1 text-sm font-medium text-slate-500 transition hover:text-sky-600"
              >
                <span className="text-lg leading-none">←</span>
                返回项目选择
              </button>

              <section className="meeting-project-strip rounded-xl border border-slate-200 bg-white px-5 py-3.5 shadow-sm">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-sky-500 text-white shadow-sm">
                    <svg width="25" height="25" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 3v3m0 12v3M3 12h3m12 0h3M5.64 5.64l2.12 2.12m8.48 8.48 2.12 2.12m0-12.72-2.12 2.12m-8.48 8.48-2.12 2.12M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
                    </svg>
                  </div>
                  <div className="flex min-w-0 flex-wrap items-center gap-3">
                      <h2 className="truncate text-lg font-semibold text-slate-800">{effectiveProject?.name ?? '项目会议列表'}</h2>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${effectiveProject?.is_active ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'}`}>
                        {effectiveProject?.is_active ? '进行中' : '未启用'}
                      </span>
                      <span className="h-4 w-px bg-slate-200" aria-hidden="true" />
                      <span className="text-sm text-slate-500">项目经理：{effectiveProject?.owners?.[0] ?? effectiveProject?.coordinator ?? '—'}</span>
                  </div>
                </div>
              </section>
            </div>

            {pending_kickoff && showNewModal && <KickoffAgentWorkspace projectId={effectiveProjectId} onClose={() => setShowNewModal(false)} />}
            {loading && (
              <div className="mx-auto w-full max-w-[1180px] rounded-xl border bg-white p-4" style={{ borderColor: '#E9EFF6' }}>
                <table className="w-full text-sm"><tbody><SkeletonTableRows rows={6} cols={6} /></tbody></table>
              </div>
            )}

        {selected && (
          <MeetingDetailWorkspace
            meeting={selected}
            projectName={effectiveProject?.name ?? ''}
            projectArchived={projectArchived}
            actionLoading={actionLoading}
            onBack={() => {
              setSelected(null)
              setSearchParams((prev) => { prev.delete('meetingId'); return prev })
            }}
            onEdit={() => setEditingItem(selected)}
            onStatusChange={(status) => { void handleStatusChange(status) }}
          />
        )}

          {selected && (() => {
            const selected = legacySelected
            return false && (
          <div className="mx-auto grid w-full max-w-[1180px] grid-cols-2 gap-5 lg:grid-cols-3 xl:grid-cols-5">
            <div className="bg-white rounded-2xl border p-5 col-span-2 lg:col-span-3 xl:col-span-2 overflow-y-auto" style={{ maxHeight: 560, borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
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
                <div className="text-xs font-semibold text-sky-700">AI 提取纪要</div>
                <MeetingSection title="会议信息">
                  <InfoRow label="会议名称" value={selected.title ?? '-'} />
                  <InfoRow label="日期" value={selected.meeting_date ?? '-'} />
                  <InfoRow label="主持人" value={selected.host ?? '-'} />
                </MeetingSection>
                {selected.summary && (
                  <MeetingSection title="会议要点">
                    <p className="text-xs text-slate-600 leading-relaxed">{selected.summary}</p>
                  </MeetingSection>
                )}
                {selected.task_list_json && <MeetingSection title="行动清单">{renderJsonList(selected.task_list_json!, '#94A3B8')}</MeetingSection>}
                {selected.decision_items_json && <MeetingSection title="决策事项">{renderJsonList(selected.decision_items_json!, '#3B82F6')}</MeetingSection>}
              </div>
            </div>

            <div className="col-span-2 lg:col-span-3 xl:col-span-3 flex flex-col gap-4">
              <div className="bg-white rounded-2xl border p-5" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-bold text-slate-800">提交原文</h2>
                  {selStatus === 'draft' && <span className="rounded-full bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-700">草稿 · 未进入 AI 确认中心</span>}
                </div>
                <p className="whitespace-pre-wrap text-xs leading-6 text-slate-600">{String(selected.transcript_text || '-')}</p>
              </div>
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
            )
          })()}

        {selected && revisions.length > 0 && (
          <div className="bg-white rounded-2xl border p-5 mb-5" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-bold text-slate-800">纪要版本历史</h2>
              <span className="text-[11px] text-slate-400">只读</span>
            </div>
            <div className="flex flex-wrap gap-2 mb-3">
              {revisions.map((revision) => (
                <button
                  key={revision.id}
                  type="button"
                  onClick={() => setSelectedRevision(revision)}
                  className={`rounded-lg border px-2.5 py-1.5 text-xs ${selectedRevision?.id === revision.id ? 'border-sky-400 bg-sky-50 text-sky-700' : 'border-slate-200 text-slate-600'}`}
                >
                  {revision.is_legacy_snapshot ? '升级前历史快照' : `V${revision.version_no}`}
                </button>
              ))}
            </div>
            {selectedRevision && (
              <div className="rounded-xl bg-slate-50 p-3 text-xs text-slate-600">
                <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
                  <span>{selectedRevision.saved_by || '系统'} · {fmtTime(selectedRevision.saved_at)}</span>
                  <span>只读版本</span>
                </div>
                <p className="whitespace-pre-wrap leading-6">{selectedRevision.summary || '暂无摘要'}</p>
                <details className="app-disclosure mt-2">
                  <summary className="cursor-pointer text-sky-700">查看该版本原始转写</summary>
                  <p className="mt-2 whitespace-pre-wrap leading-6">{selectedRevision.transcript_text}</p>
                </details>
              </div>
            )}
          </div>
        )}

        {!loading && <div className="min-[800px]:hidden pt-3">
          <MobileMeetingTimeline meetings={filtered} loading={loading} onOpen={(meeting) => {
            setSelected(meeting)
            setShowReturnInput(false)
            navigate(`/work/meetings/detail/${meeting.id}?projectId=${effectiveProjectId}`)
          }} />
        </div>}

        {!loading && (
        <div className="hidden min-[800px]:block">
        <section className="meeting-list-workspace mx-auto w-full max-w-[1180px] overflow-hidden rounded-xl border bg-white shadow-sm" style={{ borderColor: '#E9EFF6' }}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4" style={{ borderColor: '#E9EFF6' }}>
            <h3 className="text-base font-semibold text-slate-800">会议记录 <span className="font-normal text-slate-400">{filtered.length} 条</span></h3>
            <div className="flex flex-1 flex-wrap items-center justify-end gap-2 sm:flex-none">
              <div className="relative min-w-[220px] flex-1 sm:w-[240px] sm:flex-none">
                <svg className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="11" cy="11" r="7" strokeWidth="2" />
                  <path strokeLinecap="round" strokeWidth="2" d="m20 20-3.5-3.5" />
                </svg>
                <input
                  aria-label="搜索会议主题和关键词"
                  value={meetingQuery}
                  onChange={(event) => setMeetingQuery(event.target.value)}
                  placeholder="搜索会议主题"
                  className="h-9 w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm text-slate-700 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                />
              </div>
            </div>
          </div>
          {filtered.length === 0 ? (
            <div className="flex min-h-[410px] flex-col items-center justify-center px-5 text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-50 text-xl text-slate-300" aria-hidden="true">▤</div>
              <h4 className="text-base font-medium text-slate-700">还没有会议纪要</h4>
              <p className="mt-2 text-sm text-slate-400">创建第一条会议纪要，记录项目关键决策和待办。</p>
              <button type="button" onClick={() => setShowNewModal(true)} disabled={projectArchived} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:bg-slate-300">
                <span className="text-lg leading-none">＋</span> 新建会议纪要
              </button>
            </div>
          ) : (
          <>
          <div className="overflow-x-auto">
             <table className="min-w-[940px] w-full table-fixed text-sm">
               <colgroup>
                 <col style={{ width: '390px' }} />
                 <col style={{ width: '150px' }} />
                 <col style={{ width: '110px' }} />
                 <col style={{ width: '170px' }} />
                 <col style={{ width: '120px' }} />
              </colgroup>
              <thead>
                <tr className="border-b" style={{ borderColor: '#E9EFF6' }}>
                  {['会议主题', '会议时间', '纪要状态', '最近更新', '操作'].map((h) => (
                    <th key={h} className="whitespace-nowrap bg-slate-50/70 px-5 py-3 text-left text-xs font-medium text-slate-500">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((m) => {
                  const st = getStatus(m)
                  const sc = STATUS_CONFIG[st]
                  const isSel = false
                  return (
                    <tr key={m.id} className="border-b transition-colors hover:bg-slate-50" style={{ borderColor: '#F1F5F9', background: isSel ? '#EFF6FF' : 'white' }}>
                      <td className="px-5 py-3.5 align-middle">
                        <div className="flex min-w-0 items-center gap-3">
                          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-500" aria-hidden="true">▣</span>
                          <div className="min-w-0">
                            <div className="truncate font-semibold text-slate-800" title={m.title ?? '-'}>{m.title ?? '-'}</div>
                            <div className="mt-1 truncate text-xs text-slate-400" title={m.summary ?? ''}>{m.summary || '暂无会议摘要'}</div>
                          </div>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3.5 align-middle text-slate-700">{fmtTime(m.meeting_date)}</td>
                      <td className="whitespace-nowrap px-5 py-3.5 align-middle">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${sc.cls}`}>{sc.label}</span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3.5 align-middle">
                        <div className="text-slate-700">{fmtTime(m.updated_at ?? m.created_at ?? m.meeting_date)}</div>
                        <div className="mt-1 text-xs text-slate-400">{m.host || '—'}</div>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3.5 align-middle">
                        <div className="flex items-center gap-2">
                          <button className="font-medium text-sky-600 hover:text-sky-700" onClick={() => {
                            setSelected(m)
                            setShowReturnInput(false)
                            navigate(`/work/meetings/detail/${m.id}?projectId=${effectiveProjectId}`)
                          }}>
                            查看
                          </button>
                          <button className="text-slate-400 hover:text-slate-600" disabled={projectArchived} title={projectArchived ? '项目已归档，不可写入。' : undefined} onClick={() => setEditingItem(m)}>编辑</button>
                          {canDeleteMeeting && !projectArchived && <button
                            type="button"
                            className="font-medium text-rose-600 hover:text-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={deletingMeetingId !== null}
                            onClick={() => void handleDeleteMeeting(m)}
                          >
                            {deletingMeetingId === m.id ? '删除中…' : '删除'}
                          </button>}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="border-t px-5 py-3 text-xs text-slate-400" style={{ borderColor: '#E9EFF6' }}>共 {filtered.length} 条</div>
          </>
          )}
        </section>
        </div>
        )}
          </>
        )}
      </main>

    </div>
  )
}
