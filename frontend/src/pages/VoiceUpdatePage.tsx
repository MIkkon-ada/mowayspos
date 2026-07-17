import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiGet } from '../api/client'
import { getProject } from '../api/projects'
import { useProject } from '../context/ProjectContext'
import { VoiceUpdateDetailDrawer } from '../features/voice-update/VoiceUpdateDetailDrawer'
import { VoiceUpdateFlowStepper } from '../features/voice-update/VoiceUpdateFlowStepper'
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
  const navigate = useNavigate()
  const { currentProjectId, currentUser, projects } = useProject()
  const [searchParams] = useSearchParams()
  const draftState = useMemo(() => readVoiceDraftState(localStorage.getItem(DRAFT_KEY)), [])
  const requestedProjectId = parseId(searchParams.get('projectId'))
  const requestedSubtaskId = parseId(searchParams.get('subtaskId'))
  const [mode, setMode] = useState<VoiceInputMode>(draftState.mode ?? 'text')
  const [text, setText] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('deepseek')
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [providers, setProviders] = useState<AvailableProvider[]>([])
  const [historyOpen, setHistoryOpen] = useState(false)
  const [resolvedProjectDetail, setResolvedProjectDetail] = useState<Project | null>(null)
  const projectSelectionInitialized = useRef(false)

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
    ? `当前项目处于“${selectedProjectStatusLabel || '非执行阶段'}”，只能查看历史汇报，不能提取或提交新汇报。`
    : null
  const projectSubmitBlockedReason = !selectedProject
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
      projectSelectionInitialized.current = true
      return
    }
    const contextProject = currentProjectId ? activeProjects.find((project) => project.id === currentProjectId) : null
    const draftProject = draftState.projectId ? activeProjects.find((project) => project.id === draftState.projectId) : null
    setSelectedProjectId(contextProject?.id ?? draftProject?.id ?? (activeProjects.length === 1 ? activeProjects[0].id : null))
    projectSelectionInitialized.current = true
  }, [activeProjects, currentProjectId, draftState.projectId, pageProjects, requestedProjectId, searchParams])

  const taskBinding = useVoiceTaskBinding({
    selectedProjectId,
    enabled: selectedProjectIsActive,
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
    selectedProjectId,
    selectedTaskContext: taskBinding.selectedTaskContext,
    selectedProjectIsActive,
    currentUser,
    text,
    mode,
    selectedProvider,
    setText,
  })

  const { recording, transcribing, timer, startRecording, stopRecording } = useVoiceRecorder({ setText, setError: setExtractionError })
  const { uploading, uploadFileName, uploadInputRef, handleUploadFile } = useVoiceUpload({ setText, setError: setExtractionError })
  const historyState = useVoiceHistory({ activeProjectId: selectedProjectId })
  const { draftSaved, saveDraft } = useVoiceDraft({ text, selectedProvider, setText, setSelectedProvider })
  const { submittedAt, handleSubmitFinal } = useVoiceSubmission({
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
    projectId: selectedProjectId,
    selectedTaskContext: taskBinding.selectedTaskContext,
    text,
    projectActive: selectedProjectIsActive,
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
        <div><h1>工作汇报</h1><p>汇报工作进展，AI 提取结构化内容并提交确认</p></div>
        <button type="button" className="voice-update-history-button" onClick={() => setHistoryOpen(true)}>查看历史汇报</button>
      </header>

      {noActiveProjects ? (
        <div className="voice-update-empty-page">
          <div><h2>暂无可提交汇报的执行中项目</h2><p>项目进入执行阶段后，可在这里提交工作进展。</p></div>
        </div>
      ) : (
        <>
          <VoiceUpdateFlowStepper phase={phase} selectedProjectId={selectedProjectId} selectedSubtaskId={taskBinding.selectedSubtaskId} />
          <VoiceUpdateTaskBindingBar
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
            onTaskChange={handleTaskChange}
            onOpenTaskDetail={taskBinding.openTaskDetail}
          />

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
                transcribing={transcribing}
                recording={recording}
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
            onGoToConfirmations={() => navigate(`/work/confirmations?projectId=${selectedProjectId}`)}
            projectArchived={projectArchived || Boolean(selectedProject && !selectedProjectIsActive)}
            projectSubmitBlockedReason={projectSubmitBlockedReason}
          />
        </>
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
        onRestartFromTranscript={(transcript) => {
          resetExtractionState()
          setText(transcript)
          historyState.setDetailItem(null)
          historyState.setShowTranscript(false)
        }}
      />
    </div>
  )
}
