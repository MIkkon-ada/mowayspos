import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiGet } from '../api/client'
import { getProject } from '../api/projects'
import { useProject } from '../context/ProjectContext'
import { VoiceUpdateDetailDrawer } from '../features/voice-update/VoiceUpdateDetailDrawer'
import { VoiceUpdateHistoryDrawer } from '../features/voice-update/VoiceUpdateHistoryDrawer'
import { VoiceUpdateInputPanel, type VoiceInputMode } from '../features/voice-update/VoiceUpdateInputPanel'
import { VoiceUpdateResultPanel } from '../features/voice-update/VoiceUpdateResultPanel'
import { VoiceUpdateSubmitPanel } from '../features/voice-update/VoiceUpdateSubmitPanel'
import { VoiceUpdateTaskBindingBar } from '../features/voice-update/VoiceUpdateTaskBindingBar'
import { VoiceUpdateTaskContextDrawer } from '../features/voice-update/VoiceUpdateTaskContextDrawer'
import { DRAFT_KEY, useVoiceDraft } from '../features/voice-update/useVoiceDraft'
import { useVoiceExtraction } from '../features/voice-update/useVoiceExtraction'
import { useVoiceHistory } from '../features/voice-update/useVoiceHistory'
import { useVoiceRecorder } from '../features/voice-update/useVoiceRecorder'
import { useVoiceSubmission } from '../features/voice-update/useVoiceSubmission'
import { readVoiceDraftState, useVoiceTaskBinding } from '../features/voice-update/useVoiceTaskBinding'
import { useVoiceUpload } from '../features/voice-update/useVoiceUpload'
import { canExtractVoiceUpdate } from '../features/voice-update/voiceUpdateResultTypes'
import type { VoiceReportScope } from '../features/voice-update/voiceUpdateResultTypes'
import { formatTime } from '../features/voice-update/voiceUpdateHelpers'
import { getProjectStatusLabel, isProjectActive, isProjectArchived } from '../domain/projectLifecycleStatus'
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
  const [searchParams] = useSearchParams()
  const draftState = useMemo(() => readVoiceDraftState(localStorage.getItem(DRAFT_KEY)), [])
  const requestedProjectId = parseId(searchParams.get('projectId'))
  const requestedSubtaskId = parseId(searchParams.get('subtaskId'))
  const requestedSubmissionId = parseId(searchParams.get('submissionId'))
  const historyRequested = searchParams.get('history') === '1'
  const [mode, setMode] = useState<VoiceInputMode>(draftState.mode ?? 'text')
  const [text, setText] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('deepseek')
  const [reportScope, setReportScope] = useState<VoiceReportScope>('all')
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [providers, setProviders] = useState<AvailableProvider[]>([])
  const [historyOpen, setHistoryOpen] = useState(false)
  const [resolvedProjectDetail, setResolvedProjectDetail] = useState<Project | null>(null)
  const projectSelectionInitialized = useRef(false)
  const historyDeepLinkHandled = useRef(false)

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
    apiGet<AvailableProvider[]>('/api/llm-config/available')
      .then(setProviders)
      .catch(() => setProviders([]))
  }, [])

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
      else setReportScope('project')
      projectSelectionInitialized.current = true
      return
    }
    setSelectedProjectId(null)
    setReportScope('all')
    projectSelectionInitialized.current = true
  }, [pageProjects, requestedProjectId, requestedSubtaskId, searchParams])

  const taskBinding = useVoiceTaskBinding({
    scope: reportScope,
    selectedProjectId,
    enabled: reportScope === 'all' || selectedProjectIsActive,
    requestedSubtaskId: selectedProjectId === requestedProjectId ? requestedSubtaskId : null,
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

  const { recording, transcribing, timer, startRecording, stopRecording } = useVoiceRecorder({ setText, setError: setExtractionError })
  const { uploading, uploadFileName, uploadInputRef, handleUploadFile } = useVoiceUpload({ setText, setError: setExtractionError })
  const historyState = useVoiceHistory({ activeProjectId: selectedProjectId })
  useEffect(() => {
    if (!historyRequested || historyDeepLinkHandled.current) return
    historyDeepLinkHandled.current = true
    setHistoryOpen(true)
    if (requestedSubmissionId) void historyState.handleSelectUpdate(requestedSubmissionId)
  }, [historyRequested, requestedSubmissionId, historyState])
  const { draftSaved, saveDraft } = useVoiceDraft({ text, selectedProvider, setText, setSelectedProvider })
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
  })

  const controlsLocked = phase === 'extracting' || phase === 'submitting'
  const extractDisabled = !canExtractVoiceUpdate({
    scope: reportScope,
    candidateCount: taskBinding.taskOptions.length,
    projectId: selectedProjectId,
    selectedTaskContext: taskBinding.selectedTaskContext,
    text,
    projectActive: reportScope === 'all' || selectedProjectIsActive,
    recording,
    transcribing,
    uploading,
    phase,
  })

  function handleProjectChange(projectId: number | null) {
    if (controlsLocked) return
    resetExtractionState()
    setSelectedProjectId(projectId)
  }

  function handleScopeChange(scope: VoiceReportScope) {
    if (controlsLocked) return
    resetExtractionState()
    setReportScope(scope)
    if (scope === 'all') setSelectedProjectId(null)
  }

  function handleTaskChange(subtaskId: number | null) {
    if (controlsLocked) return
    resetExtractionState()
    taskBinding.selectTask(subtaskId)
  }

  function handleSaveDraft() {
    saveDraft()
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({
        text,
        provider: selectedProvider,
        mode,
        projectId: selectedProjectId,
        subtaskId: taskBinding.selectedSubtaskId,
      }))
    } catch {
      // Existing draft behavior intentionally ignores storage failures.
    }
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
          controlsLocked={controlsLocked}
          selectedProjectIsActive={selectedProjectIsActive}
          onProjectChange={handleProjectChange}
          onScopeChange={handleScopeChange}
          onTaskChange={handleTaskChange}
          onOpenTaskDetail={taskBinding.openTaskDetail}
        />
        <button type="button" className="voice-update-history-button" onClick={() => setHistoryOpen(true)}>历史提交</button>
      </header>

      {noActiveProjects ? (
        <div className="voice-update-empty-page">
          <div><h2>暂无可提交汇报的执行中项目</h2><p>项目进入执行阶段后，可在这里提交工作进展。</p></div>
        </div>
      ) : (
        <div className="voice-update-editor-shell">
          <main className="voice-update-main-scroll">
            <div className="voice-update-workspace">
              <VoiceUpdateInputPanel
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
                timerLabel={formatTime(timer)}
                text={text}
                onTextChange={setText}
                uploading={uploading}
                uploadFileName={uploadFileName}
                uploadInputRef={uploadInputRef}
                onUploadFile={handleUploadFile}
                onStartRecording={startRecording}
                onStopRecording={stopRecording}
                onExtract={handleExtract}
              />
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
              onResetExtractionState={resetExtractionState}
              onClear={() => resetExtractionState({ clearText: true })}
              onSubmitFinal={handleSubmitFinal}
              onViewSubmissionHistory={() => setHistoryOpen(true)}
              projectArchived={projectArchived || Boolean(selectedProject && !selectedProjectIsActive)}
              projectSubmitBlockedReason={projectSubmitBlockedReason}
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
        currentUserName={currentUser?.name}
        onResubmitted={async (id) => { await historyState.refreshHistory(); void historyState.handleSelectUpdate(id) }}
        onRestartFromSubmission={(detailItem) => {
          resetExtractionState()
          const taskReports = Array.isArray(detailItem.human_result?.task_reports)
            ? detailItem.human_result.task_reports as Array<Record<string, unknown>>
            : []
          const evidence = taskReports.flatMap((report) =>
            Array.isArray(report.evidence)
              ? report.evidence.filter((item): item is string => typeof item === 'string' && Boolean(item.trim()))
              : [],
          )
          const completed = taskReports
            .map((report) => typeof report.completed === 'string' ? report.completed.trim() : '')
            .filter(Boolean)
          setText(evidence.length > 0
            ? evidence.join('。')
            : completed.join('。') || detailItem.transcript_text || '')
          if (detailItem.project_id) {
            setReportScope('project')
            setSelectedProjectId(detailItem.project_id)
          }
          historyState.setDetailItem(null)
          historyState.setShowTranscript(false)
        }}
      />
    </div>
  )
}
