import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { getUpdate } from '../api/updates'
import type { UpdateDetail } from '../api/updates'
import { getProject } from '../api/projects'
import { getAITaskExtractionModels } from '../api/aiConfig'
import { useProject } from '../context/ProjectContext'
import { VoiceUpdateDetailDrawer } from '../features/voice-update/VoiceUpdateDetailDrawer'
import { VoiceUpdateHistoryDrawer } from '../features/voice-update/VoiceUpdateHistoryDrawer'
import { VoiceUpdateInputPanel, type VoiceInputMode } from '../features/voice-update/VoiceUpdateInputPanel'
import { VoiceUpdateOwnershipReviewPanel } from '../features/voice-update/VoiceUpdateOwnershipReviewPanel'
import { VoiceUpdateResultPanel } from '../features/voice-update/VoiceUpdateResultPanel'
import { VoiceUpdateSubmitPanel } from '../features/voice-update/VoiceUpdateSubmitPanel'
import { VoiceUpdateTaskBindingBar } from '../features/voice-update/VoiceUpdateTaskBindingBar'
import { VoiceUpdateTaskContextDrawer } from '../features/voice-update/VoiceUpdateTaskContextDrawer'
import {
  DRAFT_KEY,
  getVoiceDraftStorageKey,
  readVoiceDraftLastContext,
  readVoiceDraftStorage,
  getVoiceResubmissionDraftStorageKey,
  saveVoiceDraftLastContext,
  useVoiceDraft,
} from '../features/voice-update/useVoiceDraft'
import { useVoiceExtraction } from '../features/voice-update/useVoiceExtraction'
import { useVoiceHistory } from '../features/voice-update/useVoiceHistory'
import { useVoiceRecorder } from '../features/voice-update/useVoiceRecorder'
import { useVoiceSubmission } from '../features/voice-update/useVoiceSubmission'
import { readVoiceDraftState, useVoiceTaskBinding } from '../features/voice-update/useVoiceTaskBinding'
import { useVoiceUpload } from '../features/voice-update/useVoiceUpload'
import { useVoiceDocumentUpload } from '../features/voice-update/useVoiceDocumentUpload'
import { canExtractVoiceUpdate } from '../features/voice-update/voiceUpdateResultTypes'
import type { VoiceReportScope } from '../features/voice-update/voiceUpdateResultTypes'
import { formatTime } from '../features/voice-update/voiceUpdateHelpers'
import { getProjectStatusLabel, isProjectActive, isProjectArchived } from '../domain/projectLifecycleStatus'
import * as SS from '../domain/submissionStatus'
import type { WorkReportEntryIntent } from '../domain/workReportEntry'
import type { Project } from '../types'
import '../features/voice-update/voiceUpdateFlow.css'

type AvailableProvider = { provider: string; display_name: string; model: string }

function parseId(value: string | null): number | null {
  if (!value) return null
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

export function VoiceUpdatePage() {
  const { currentUser, projects } = useProject()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()
  const requestedProjectId = parseId(searchParams.get('projectId'))
  const requestedSubtaskId = parseId(searchParams.get('subtaskId'))
  const requestedSubmissionId = parseId(searchParams.get('submissionId'))
  const requestedResubmitId = parseId(searchParams.get('resubmitId'))
  const requestedEntryIntent = searchParams.get('entryIntent')
  const entryIntent: WorkReportEntryIntent = requestedEntryIntent === 'issue' || requestedEntryIntent === 'achievement'
    ? requestedEntryIntent
    : 'report'
  const historyRequested = searchParams.get('history') === '1'
  const savedDraftContext = useMemo(() => {
    try { return readVoiceDraftLastContext(currentUser) } catch { return null }
  }, [currentUser])
  const savedDraftContextIsAvailable = savedDraftContext?.projectId == null
    || projects.some((project) => project.id === savedDraftContext.projectId)
  const initialProjectId = requestedProjectId ?? (
    savedDraftContextIsAvailable ? savedDraftContext?.projectId ?? null : null
  )
  const initialScope: VoiceReportScope = requestedProjectId
    ? requestedSubtaskId ? 'task' : 'project'
    : savedDraftContextIsAvailable ? savedDraftContext?.scope ?? 'all' : 'all'
  const initialDraftStorageKey = getVoiceDraftStorageKey(currentUser, initialProjectId)
  const initialDraftState = useMemo(() => {
    try {
      return readVoiceDraftState(readVoiceDraftStorage(currentUser, initialProjectId))
    } catch {
      return {}
    }
  }, [currentUser, initialDraftStorageKey, initialProjectId])
  useEffect(() => {
    try {
      localStorage.removeItem(DRAFT_KEY)
    } catch {
      // Ignore unavailable browser storage.
    }
  }, [])
  const [mode, setMode] = useState<VoiceInputMode>(initialDraftState.mode ?? 'text')
  const [text, setText] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('capability')
  const [reportScope, setReportScope] = useState<VoiceReportScope>(() => requestedProjectId && initialDraftState.scope === 'task'
    ? 'task'
    : initialScope)
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(() => initialProjectId)
  const [quickSubtaskId, setQuickSubtaskId] = useState<number | null>(null)
  const [providers, setProviders] = useState<AvailableProvider[]>([
    { provider: 'capability', display_name: 'AI能力策略', model: '模型信息加载中' },
  ])
  const [historyOpen, setHistoryOpen] = useState(false)
  const [resubmission, setResubmission] = useState<{ id: number; rejectReason: string; supplementNote: string } | null>(null)
  const [resubmitLoadError, setResubmitLoadError] = useState<string | null>(null)
  const [resolvedProjectDetail, setResolvedProjectDetail] = useState<Project | null>(null)
  const projectSelectionInitialized = useRef(false)
  const historyDeepLinkHandled = useRef(false)
  const draftProjectId = reportScope === 'all' ? null : selectedProjectId
  const draftStorageKey = draftProjectId !== null || reportScope === 'all'
    ? getVoiceDraftStorageKey(currentUser, draftProjectId)
    : null
  const draftState = useMemo(() => {
    try {
      return readVoiceDraftState(draftStorageKey ? readVoiceDraftStorage(currentUser, draftProjectId) : null)
    } catch {
      return {}
    }
  }, [currentUser, draftProjectId, draftStorageKey])

  useEffect(() => {
    setMode(draftState.mode ?? 'text')
  }, [draftStorageKey, draftState.mode])

  useEffect(() => {
    saveVoiceDraftLastContext(currentUser, {
      projectId: reportScope === 'all' ? null : selectedProjectId,
      scope: reportScope,
    })
  }, [currentUser, reportScope, selectedProjectId])

  useEffect(() => {
    let cancelled = false
    getAITaskExtractionModels()
      .then(({ primary_model_name, fallback_model_names }) => {
        if (cancelled) return
        const modelNames = [
          primary_model_name,
          fallback_model_names.length ? `备用：${fallback_model_names.join('、')}` : null,
        ].filter((name): name is string => Boolean(name))
        setProviders([{
          provider: 'capability',
          display_name: 'AI能力策略',
          model: modelNames.join('；') || '未配置模型',
        }])
      })
      .catch(() => {
        if (!cancelled) setProviders([{ provider: 'capability', display_name: 'AI能力策略', model: '模型信息暂不可用' }])
      })
    return () => { cancelled = true }
  }, [])

  const pageProjects = useMemo(() => {
    const projectsById = new Map(projects.map((project) => [project.id, project]))
    if (resolvedProjectDetail) projectsById.set(resolvedProjectDetail.id, resolvedProjectDetail)
    return Array.from(projectsById.values())
  }, [projects, resolvedProjectDetail])
  const activeProjects = useMemo(() => pageProjects.filter(isProjectActive), [pageProjects])
  const selectedProject = useMemo(
    () => pageProjects.find((project) => project.id === selectedProjectId) ?? null,
    [pageProjects, selectedProjectId],
  )
  const selectedProjectIsActive = selectedProject ? isProjectActive(selectedProject) : false
  const projectArchived = isProjectArchived(selectedProject)
  const selectedProjectStatusLabel = selectedProject ? getProjectStatusLabel(selectedProject) : ''
  const projectInactiveMessage = selectedProject
    ? `当前项目处于"${selectedProjectStatusLabel || '非执行阶段'}"，只能查看历史汇报，不能提取或提交新汇报。`
    : null
  const projectSubmitBlockedReason = reportScope === 'all'
    ? null
    : !selectedProject
      ? '请先选择所属项目。'
      : selectedProjectIsActive
        ? null
        : projectInactiveMessage

  useEffect(() => {
    let cancelled = false
    projectSelectionInitialized.current = false
    setResolvedProjectDetail(null)
    if (!requestedProjectId || projects.some((project) => project.id === requestedProjectId)) return

    setSelectedProjectId(null)
    getProject(requestedProjectId)
      .then((project) => { if (!cancelled) setResolvedProjectDetail(project) })
      .catch(() => { if (!cancelled) setResolvedProjectDetail(null) })
    return () => { cancelled = true }
  }, [projects, requestedProjectId])

  useEffect(() => {
    if (projectSelectionInitialized.current) return
    if (searchParams.get('projectId')) {
      const requestedProject = pageProjects.find((project) => project.id === requestedProjectId)
      if (!requestedProject) return
      setSelectedProjectId(requestedProject.id)
      if (requestedSubtaskId) setReportScope('task')
      else setReportScope(draftState.scope === 'task' ? 'task' : 'project')
      projectSelectionInitialized.current = true
      return
    }
    setSelectedProjectId(initialProjectId)
    setReportScope(initialScope)
    projectSelectionInitialized.current = true
  }, [initialProjectId, initialScope, pageProjects, requestedProjectId, requestedSubtaskId, searchParams])

  const taskBinding = useVoiceTaskBinding({
    scope: reportScope,
    selectedProjectId,
    enabled: reportScope === 'all' || selectedProjectIsActive,
    requestedSubtaskId: quickSubtaskId ?? (selectedProjectId === requestedProjectId ? requestedSubtaskId : null),
    restoredSubtaskId: !requestedSubtaskId && selectedProjectId === draftState.projectId ? draftState.subtaskId ?? null : null,
  })

  const {
    phase,
    setPhase,
    result,
    error: extractionError,
    editValues,
    setEditValues,
    editingField,
    setEditingField,
    proposedSubtasks,
    setProposedSubtasks,
    taskReports,
    setTaskReports,
    keyTaskIssues,
    setKeyTaskIssues,
    cardEdits,
    updateCardEdit,
    projectTasksForSuggest,
    voiceSubtasksContext,
    resetExtractionState,
    handleExtract,
    setError: setExtractionError,
  } = useVoiceExtraction({
    reportScope,
    selectedProjectId,
    selectedTaskContext: taskBinding.selectedTaskContext,
    voiceCandidates: reportScope === 'task' && taskBinding.selectedTaskContext ? [taskBinding.selectedTaskContext] : taskBinding.taskOptions,
    selectedProjectIsActive: reportScope === 'all' || selectedProjectIsActive,
    currentUser,
    text,
    mode,
    selectedProvider,
    setText,
  })

  const { uploading, uploadFileName, uploadInputRef, handleUploadFile } = useVoiceUpload({ setText, setError: setExtractionError })
  const {
    documentUploading,
    documentFileName,
    documentCharCount,
    documentInputRef,
    handleDocumentFile,
    removeDocument,
  } = useVoiceDocumentUpload({ setText, setError: setExtractionError })
  const canRecord = reportScope === 'task'
    && selectedProjectIsActive
    && selectedProjectId !== null
    && taskBinding.selectedSubtaskId !== null
    && !uploading
    && !documentUploading
  const {
    recorderState,
    recording,
    transcribing,
    timer,
    startRecording,
    stopRecording,
  } = useVoiceRecorder({
    projectId: selectedProjectId,
    selectedTaskId: taskBinding.selectedSubtaskId,
    canRecord,
    initialText: text,
    setText,
    setError: setExtractionError,
  })
  const mediaActive = ['connecting', 'starting', 'recording', 'stopping'].includes(recorderState)
  const historyState = useVoiceHistory({ activeProjectId: selectedProjectId })
  useEffect(() => {
    if (!historyRequested || historyDeepLinkHandled.current) return
    historyDeepLinkHandled.current = true
    setHistoryOpen(true)
    if (requestedSubmissionId) void historyState.handleSelectUpdate(requestedSubmissionId)
  }, [historyRequested, requestedSubmissionId, historyState])
  const resubmitDraftStorageKey = getVoiceResubmissionDraftStorageKey(currentUser, requestedResubmitId)
  const setVoiceDraftText = useCallback((value: string) => {
    if (!requestedResubmitId) setText(value)
  }, [requestedResubmitId])

  useEffect(() => {
    if (!requestedResubmitId) {
      setResubmission(null)
      setResubmitLoadError(null)
      return
    }
    let cancelled = false
    setResubmission(null)
    setResubmitLoadError(null)
    getUpdate(requestedResubmitId).then((detail: UpdateDetail) => {
      if (cancelled) return
      if (!SS.RETURNED_TO_SUBMITTER.has(SS.normalize(detail.confirm_status))) {
        setResubmitLoadError('这条汇报已不处于退回状态，不能继续修订。请刷新提交记录。')
        return
      }
      const routeDraft = location.state as { transcriptText?: string; supplementNote?: string } | null
      let savedDraft: { text?: string; supplementNote?: string } | null = null
      try {
        const raw = resubmitDraftStorageKey ? localStorage.getItem(resubmitDraftStorageKey) : null
        savedDraft = raw ? JSON.parse(raw) as { text?: string; supplementNote?: string } : null
      } catch {
        savedDraft = null
      }
      resetExtractionState()
      setText(savedDraft?.text ?? routeDraft?.transcriptText ?? detail.transcript_text)
      setResubmission({
        id: detail.id,
        rejectReason: detail.reject_reason ?? '',
        supplementNote: savedDraft?.supplementNote ?? routeDraft?.supplementNote ?? '',
      })
      const projectId = detail.project_id ?? null
      const subtaskId = detail.related_subtask_id ?? null
      setSelectedProjectId(projectId)
      setReportScope(subtaskId ? 'task' : projectId ? 'project' : 'all')
      setQuickSubtaskId(subtaskId)
    }).catch((error: unknown) => {
      if (!cancelled) setResubmitLoadError(error instanceof Error ? error.message : '无法读取退回汇报，请刷新提交记录后重试。')
    })
    return () => { cancelled = true }
  }, [requestedResubmitId])

  useEffect(() => {
    if (!resubmission || !resubmitDraftStorageKey) return
    try {
      localStorage.setItem(resubmitDraftStorageKey, JSON.stringify({ text, supplementNote: resubmission.supplementNote }))
    } catch {
      // Keep the in-memory revision even when browser storage is unavailable.
    }
  }, [resubmission, resubmitDraftStorageKey, text])

  const { draftSaved, saveDraft } = useVoiceDraft({
    currentUser,
    projectId: draftProjectId,
    scope: reportScope,
    text,
    selectedProvider,
    setText: setVoiceDraftText,
    setSelectedProvider,
  })
  const { submittedAt, handleSubmitFinal } = useVoiceSubmission({
    reportScope,
    selectedProjectId,
    selectedSubtaskId: taskBinding.selectedSubtaskId,
    selectedTaskContext: taskBinding.selectedTaskContext,
    currentUser,
    text,
    mode,
    result,
    editValues,
    taskReports,
    keyTaskIssues,
    cardEdits,
    proposedSubtasks,
    projectTasksForSuggest,
    projects: pageProjects,
    setPhase,
    setError: setExtractionError,
    refreshHistory: historyState.refreshHistory,
    resubmission: resubmission ? {
      id: resubmission.id,
      supplementNote: resubmission.supplementNote,
      draftStorageKey: resubmitDraftStorageKey,
    } : undefined,
    onResubmitted: async (id) => {
      setResubmission(null)
      setHistoryOpen(true)
      const next = new URLSearchParams()
      next.set('history', '1')
      next.set('submissionId', String(id))
      if (selectedProjectId) next.set('projectId', String(selectedProjectId))
      setSearchParams(next, { replace: true })
      await historyState.handleSelectUpdate(id)
    },
  })

  const resubmissionLoading = Boolean(requestedResubmitId && !resubmission && !resubmitLoadError)
  const pageSubmitBlockedReason = resubmissionLoading
    ? '正在读取退回汇报…'
    : projectSubmitBlockedReason
  const controlsLocked = phase === 'extracting' || phase === 'submitting' || mediaActive || uploading || documentUploading || resubmissionLoading
  const extractDisabled = !canExtractVoiceUpdate({
    scope: reportScope,
    candidateCount: taskBinding.taskOptions.length,
    projectId: selectedProjectId,
    selectedTaskContext: taskBinding.selectedTaskContext,
    text,
    projectActive: reportScope === 'all' || selectedProjectIsActive,
    recording,
    uploading: uploading || documentUploading,
    phase,
  }) || resubmissionLoading

  function persistDraftSnapshot() {
    if (!draftStorageKey) return
    try {
      localStorage.setItem(draftStorageKey, JSON.stringify({
        text,
        provider: selectedProvider,
        mode,
        projectId: selectedProjectId,
        subtaskId: taskBinding.selectedSubtaskId,
        scope: reportScope,
      }))
      saveVoiceDraftLastContext(currentUser, {
        projectId: reportScope === 'all' ? null : selectedProjectId,
        scope: reportScope,
      })
    } catch {
      // Ignore unavailable browser storage.
    }
  }

  function handleProjectChange(projectId: number | null) {
    if (controlsLocked || resubmission) return
    persistDraftSnapshot()
    resetExtractionState()
    removeDocument()
    setQuickSubtaskId(null)
    setSelectedProjectId(projectId)
  }

  function handleScopeChange(scope: VoiceReportScope) {
    if (controlsLocked || resubmission) return
    persistDraftSnapshot()
    resetExtractionState()
    removeDocument()
    setQuickSubtaskId(null)
    setReportScope(scope)
    if (scope === 'all') setSelectedProjectId(null)
  }

  function handleTaskChange(subtaskId: number | null) {
    if (controlsLocked || resubmission) return
    resetExtractionState()
    removeDocument()
    setQuickSubtaskId(null)
    taskBinding.selectTask(subtaskId)
  }

  function handleQuickTaskSelect(projectId: number, subtaskId: number) {
    if (controlsLocked || resubmission) return
    persistDraftSnapshot()
    resetExtractionState()
    removeDocument()
    setQuickSubtaskId(subtaskId)
    setSelectedProjectId(projectId)
    setReportScope('task')
  }

  function handleSaveDraft() {
    if (resubmission && resubmitDraftStorageKey) {
      try { localStorage.setItem(resubmitDraftStorageKey, JSON.stringify({ text, supplementNote: resubmission.supplementNote })) } catch { /* keep in-memory draft */ }
      return
    }
    saveDraft()
    persistDraftSnapshot()
  }

  function handleReportTextChange(value: string) {
    if (resubmission && phase === 'extracted') resetExtractionState()
    setText(value)
  }

  function handleReviseAndReextract(id: number, transcriptText: string, supplementNote: string) {
    const detail = historyState.detailItem
    if (!detail || detail.id !== id) return
    const next = new URLSearchParams()
    next.set('resubmitId', String(id))
    if (detail.project_id) next.set('projectId', String(detail.project_id))
    if (detail.related_subtask_id) next.set('subtaskId', String(detail.related_subtask_id))
    historyState.setDetailItem(null)
    setHistoryOpen(false)
    navigate(`/work/submit?${next.toString()}`, { state: { transcriptText, supplementNote } })
  }

  const noActiveProjects = activeProjects.length === 0 && !selectedProject
  return (
    <div className="voice-update-page">
      <header className="voice-update-header">
        <div className="voice-update-title"><h1>工作汇报</h1></div>
        <VoiceUpdateTaskBindingBar
          scope={reportScope}
          activeProjects={activeProjects}
          selectedProject={selectedProject}
          selectedProjectId={selectedProjectId}
          selectedSubtaskId={taskBinding.selectedSubtaskId}
          selectedTaskContext={taskBinding.selectedTaskContext}
          taskOptions={taskBinding.taskOptions}
          taskLoading={taskBinding.taskLoading}
          taskError={taskBinding.taskError}
          controlsLocked={controlsLocked || Boolean(resubmission)}
          selectedProjectIsActive={selectedProjectIsActive}
          onProjectChange={handleProjectChange}
          onScopeChange={handleScopeChange}
          onTaskChange={handleTaskChange}
          onQuickTaskSelect={handleQuickTaskSelect}
          onOpenTaskDetail={taskBinding.openTaskDetail}
        />
        <button type="button" className="voice-update-history-button" onClick={() => setHistoryOpen(true)}>历史提交</button>
      </header>

      {resubmitLoadError ? (
        <div className="voice-update-empty-page"><div><h2>无法修订这条汇报</h2><p>{resubmitLoadError}</p></div></div>
      ) : noActiveProjects ? (
        <div className="voice-update-empty-page">
          <div><h2>暂无可提交汇报的执行中项目</h2><p>项目进入执行阶段后，可在这里提交工作进展。</p></div>
        </div>
      ) : (
        <div className="voice-update-editor-shell">
          <main className="voice-update-main-scroll">
            <div className="voice-update-workspace">
              <div className="voice-update-left-column">
                {resubmission && (
                  <div className="mb-3 rounded-xl border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-900">
                    <strong>正在修订原汇报</strong>
                    <p className="mt-1 text-xs">退回原因：{resubmission.rejectReason || '未说明'}</p>
                  </div>
                )}
                <VoiceUpdateInputPanel
                  entryIntent={entryIntent}
                  mode={mode}
                  onModeChange={setMode}
                  providers={providers}
                  selectedProvider={selectedProvider}
                  onSelectedProviderChange={setSelectedProvider}
                  phase={phase}
                  controlsLocked={controlsLocked}
                  extractDisabled={extractDisabled}
                  recording={recording}
                  transcribing={transcribing}
                  mediaActive={mediaActive}
                  recorderState={recorderState}
                  canRecord={canRecord}
                  timerLabel={formatTime(timer)}
                  text={text}
                  onTextChange={handleReportTextChange}
                  uploading={uploading}
                  uploadFileName={uploadFileName}
                  uploadInputRef={uploadInputRef}
                  onUploadFile={handleUploadFile}
                  documentUploading={documentUploading}
                  documentFileName={documentFileName}
                  documentCharCount={documentCharCount}
                  documentInputRef={documentInputRef}
                  onDocumentFile={handleDocumentFile}
                  onRemoveDocument={removeDocument}
                  onStartRecording={startRecording}
                  onStopRecording={stopRecording}
                  onExtract={handleExtract}
                />
                <VoiceUpdateOwnershipReviewPanel
                  phase={phase}
                  taskReports={taskReports}
                  setTaskReports={setTaskReports}
                  voiceSubtasksContext={voiceSubtasksContext}
                />
              </div>
              <VoiceUpdateResultPanel
                result={result}
                error={extractionError}
                phase={phase}
                editValues={editValues}
                editingField={editingField}
                setEditingField={setEditingField}
                setEditValues={setEditValues}
                taskReports={taskReports}
                setTaskReports={setTaskReports}
                keyTaskIssues={keyTaskIssues}
                setKeyTaskIssues={setKeyTaskIssues}
                selectedProjectId={selectedProjectId}
                selectedSubtaskId={taskBinding.selectedSubtaskId}
                proposedSubtasks={proposedSubtasks}
                setProposedSubtasks={setProposedSubtasks}
                cardEdits={cardEdits}
                updateCardEdit={updateCardEdit}
                projectTasksForSuggest={projectTasksForSuggest}
                voiceSubtasksContext={voiceSubtasksContext}
                currentUserName={currentUser?.name}
                onExtract={handleExtract}
                hasSelectedTask={Boolean(taskBinding.selectedSubtaskId)}
                hasText={Boolean(text.trim())}
              />
            </div>
          </main>
          <VoiceUpdateSubmitPanel
              phase={phase}
              reportScope={reportScope}
              taskReports={taskReports}
              cardEdits={cardEdits}
              currentUserName={currentUser?.name}
              selectedProjectName={selectedProject?.name ?? null}
              isProjectSelected={selectedProjectId !== null}
              selectedSubtaskId={taskBinding.selectedSubtaskId}
              text={text}
              submittedAt={submittedAt}
              draftSaved={draftSaved}
              onSaveDraft={handleSaveDraft}
              onResetExtractionState={(options) => { resetExtractionState(options); removeDocument() }}
              onClear={() => { resetExtractionState({ clearText: true }); removeDocument() }}
              onSubmitFinal={handleSubmitFinal}
              onViewSubmissionHistory={() => setHistoryOpen(true)}
              projectArchived={projectArchived || Boolean(selectedProject && !selectedProjectIsActive)}
              projectSubmitBlockedReason={pageSubmitBlockedReason}
              isResubmission={Boolean(resubmission)}
          />
        </div>
      )}

      <VoiceUpdateHistoryDrawer
        open={historyOpen}
        selectedProjectId={selectedProjectId}
        history={historyState.history}
        currentUserName={currentUser?.name}
        onClose={() => setHistoryOpen(false)}
        onSelectUpdate={historyState.handleSelectUpdate}
      />
      <VoiceUpdateTaskContextDrawer
        open={taskBinding.taskDetailOpen}
        loading={taskBinding.taskDetailLoading}
        detail={taskBinding.taskDetail}
        taskContext={taskBinding.selectedTaskContext}
        projectName={selectedProject?.name ?? ''}
        onClose={taskBinding.closeTaskDetail}
      />
      <VoiceUpdateDetailDrawer
        detailItem={historyState.detailItem}
        detailLoading={historyState.detailLoading}
        showTranscript={historyState.showTranscript}
        onClose={() => { historyState.setDetailItem(null); historyState.setDetailLoading(false); historyState.setShowTranscript(false) }}
        onToggleTranscript={() => historyState.setShowTranscript((value) => !value)}
        onReviseAndReextract={handleReviseAndReextract}
      />
    </div>
  )
}
