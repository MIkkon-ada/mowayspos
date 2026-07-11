import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiGet } from '../api/client'
import { fetchVoiceContext } from '../api/updates'
import { useProject } from '../context/ProjectContext'
import { VoiceUpdateDetailDrawer } from '../features/voice-update/VoiceUpdateDetailDrawer'
import { VoiceUpdateHistoryPanel } from '../features/voice-update/VoiceUpdateHistoryPanel'
import { VoiceUpdateInputPanel } from '../features/voice-update/VoiceUpdateInputPanel'
import { VoiceUpdateResultPanel } from '../features/voice-update/VoiceUpdateResultPanel'
import { useVoiceDraft } from '../features/voice-update/useVoiceDraft'
import { useVoiceExtraction } from '../features/voice-update/useVoiceExtraction'
import { useVoiceHistory } from '../features/voice-update/useVoiceHistory'
import { useVoiceRecorder } from '../features/voice-update/useVoiceRecorder'
import { useVoiceSubmission } from '../features/voice-update/useVoiceSubmission'
import { useVoiceUpload } from '../features/voice-update/useVoiceUpload'
import { formatTime } from '../features/voice-update/voiceUpdateHelpers'
import { getProjectStatusLabel, isProjectActive, isProjectArchived } from '../domain/projectLifecycleStatus'

type AvailableProvider = { provider: string; display_name: string; model: string }
type InputMode = 'voice' | 'upload' | 'text'

export function VoiceUpdatePage() {
  const { currentProjectId, currentUser, projects } = useProject()
  const [searchParams] = useSearchParams()
  const [mode, setMode] = useState<InputMode>('text')
  const [text, setText] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('deepseek')
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [providers, setProviders] = useState<AvailableProvider[]>([])
  const projectSelectionInitialized = useRef(false)
  const [hasSubtasks, setHasSubtasks] = useState<boolean | null>(null)
  const projectInactiveMessage = '项目尚未进入执行阶段，暂不能提交正式工作汇报，请完成立项审核后再提交。'
  const missingProjectSubmitMessage = '请先选择所属项目，再提交给负责人。'
  const missingProjectExtractMessage = '请先选择所属项目，再进行 AI 提取。'

  // 进入页面时检查用户是否有可汇报的关键任务
  useEffect(() => {
    fetchVoiceContext()
      .then((subs) => setHasSubtasks(subs.length > 0))
      .catch(() => setHasSubtasks(false))
  }, [])

  useEffect(() => {
    apiGet<AvailableProvider[]>('/api/llm-config/available')
      .then(setProviders)
      .catch(() => setProviders([]))
  }, [])

  const activeProjects = useMemo(
    () => projects.filter((project) => isProjectActive(project)),
    [projects],
  )

  useEffect(() => {
    if (projects.length === 0) return
    const rawProjectId = searchParams.get('projectId')
    const parsedProjectId = rawProjectId ? Number(rawProjectId) : null

    if (parsedProjectId && projects.some((project) => project.id === parsedProjectId)) {
      setSelectedProjectId(parsedProjectId)
      projectSelectionInitialized.current = true
      return
    }

    if (projectSelectionInitialized.current) return

    const contextProject = currentProjectId != null
      ? projects.find((project) => project.id === currentProjectId)
      : null
    if (!rawProjectId && contextProject) {
      setSelectedProjectId(contextProject.id)
      projectSelectionInitialized.current = true
      return
    }

    if (!rawProjectId && activeProjects.length === 1) {
      setSelectedProjectId(activeProjects[0].id)
      projectSelectionInitialized.current = true
      return
    }

    projectSelectionInitialized.current = true
  }, [activeProjects, currentProjectId, projects, searchParams])

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  )
  const projectArchived = isProjectArchived(selectedProject)
  const selectedProjectIsActive = selectedProject ? isProjectActive(selectedProject) : false
  const selectedProjectStatusLabel = selectedProject ? getProjectStatusLabel(selectedProject) : ''
  const projectSubmitBlockedReason = !selectedProject
    ? missingProjectSubmitMessage
    : selectedProjectIsActive
      ? null
      : projectInactiveMessage
  const projectExtractBlockedReason = !selectedProject
    ? missingProjectExtractMessage
    : selectedProjectIsActive
      ? null
      : projectInactiveMessage

  const {
    phase,
    setPhase,
    result,
    editValues,
    setEditValues,
    editingField,
    setEditingField,
    proposedSubtasks,
    setProposedSubtasks,
    taskReports,
    setTaskReports,
    keyTaskIssues,
    cardEdits,
    updateCardEdit,
    projectTasksForSuggest,
    voiceSubtasksContext,
    resetExtractionState,
    handleExtract,
    setError: setExtractionError,
  } = useVoiceExtraction({
    currentProjectId,
    selectedProjectId,
    currentUser,
    text,
    mode,
    selectedProvider,
    projects,
    setText,
  })

  const { recording, transcribing, timer, startRecording, stopRecording } = useVoiceRecorder({
    setText,
    setError: setExtractionError,
  })

  const { uploading, uploadFileName, uploadInputRef, handleUploadFile } = useVoiceUpload({
    setText,
    setError: setExtractionError,
  })

  const {
    history,
    detailItem,
    detailLoading,
    showTranscript,
    setShowTranscript,
    setDetailItem,
    setDetailLoading,
    refreshHistory,
    handleSelectUpdate,
  } = useVoiceHistory({ activeProjectId: selectedProjectId })

  const { draftSaved, saveDraft } = useVoiceDraft({
    text,
    selectedProvider,
    setText,
    setSelectedProvider,
  })

  const { submittedAt, handleSubmitFinal } = useVoiceSubmission({
    currentProjectId,
    selectedProjectId,
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
    projects,
    setPhase,
    setError: setExtractionError,
    refreshHistory,
  })

  function handleBoundProjectExtract() {
    if (projectExtractBlockedReason) {
      setExtractionError(projectExtractBlockedReason)
      return
    }
    handleExtract()
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {hasSubtasks === false && (
        <div className="flex-1 flex items-center justify-center" style={{ background: '#F1F5F9' }}>
          <div className="text-center max-w-md">
            <div className="mx-auto mb-4 w-16 h-16 rounded-full flex items-center justify-center" style={{ background: '#F1F5F9' }}>
              <svg style={{ width: 32, height: 32 }} fill="none" stroke="#94A3B8" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
            </div>
            <h2 className="text-lg font-bold text-slate-700 mb-2">暂无可汇报的关键任务</h2>
            <p className="text-sm text-slate-400 leading-relaxed">您当前没有被分配任何关键任务。请联系项目负责人为您分配任务后再进行工作汇报。</p>
          </div>
        </div>
      )}
      {hasSubtasks === null && (
        <div className="flex-1 flex items-center justify-center" style={{ background: '#F1F5F9' }}>
          <p className="text-sm text-slate-400">加载中…</p>
        </div>
      )}
      {hasSubtasks === true && (
        <>
      <header className="h-16 flex items-center px-6 gap-4 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1">
          <h1 className="text-base font-bold text-slate-800">工作汇报</h1>
          <p className="text-xs text-slate-400 mt-0.5">通过录音、上传音频或粘贴文本，快速生成项目进展更新</p>
        </div>
      </header>

      <div className="px-6 py-3 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3 flex-wrap">
            <label className="text-xs font-semibold text-slate-500" htmlFor="voice-update-project-select">所属项目</label>
            <select
              id="voice-update-project-select"
              value={selectedProjectId ?? ''}
              onChange={(event) => setSelectedProjectId(event.target.value ? Number(event.target.value) : null)}
              className="h-9 min-w-[220px] rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 outline-none focus:border-sky-400"
            >
              <option value="">所属项目：请选择项目</option>
              {selectedProject && !selectedProjectIsActive && (
                <option value={selectedProject.id}>
                  {selectedProject.name}（{selectedProjectStatusLabel || '非执行阶段'}）
                </option>
              )}
              {activeProjects.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
            {selectedProject && (
              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${selectedProjectIsActive ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                {selectedProjectIsActive ? '进行中' : selectedProjectStatusLabel || '非执行阶段'}
              </span>
            )}
          </div>
          <div className="text-xs text-slate-400">
            AI 负责提取内容，项目归属以你选择的项目为准。
            {selectedProjectIsActive && <span className="ml-1">AI 可辅助识别关键任务，但所属项目以当前选择为准。</span>}
          </div>
          {projectSubmitBlockedReason && (
            <div className="basis-full rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700">
              {projectSubmitBlockedReason}
            </div>
          )}
        </div>
      </div>

      <main className="flex-1 overflow-y-auto p-5" style={{ background: '#F1F5F9' }}>
        <div className="grid gap-5 min-h-full" style={{ gridTemplateColumns: '360px minmax(0, 1fr)' }}>
          <VoiceUpdateInputPanel
            mode={mode}
            onModeChange={setMode}
            providers={providers}
            selectedProvider={selectedProvider}
            onSelectedProviderChange={setSelectedProvider}
            phase={phase}
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
            onClearText={() => setText('')}
          />

          <div className="flex flex-col gap-4 min-w-0">
            <VoiceUpdateResultPanel
              result={result}
              error={error}
              phase={phase}
              text={text}
              editValues={editValues}
              editingField={editingField}
              setEditingField={setEditingField}
              setEditValues={setEditValues}
              taskReports={taskReports}
              setTaskReports={setTaskReports}
              keyTaskIssues={keyTaskIssues}
              proposedSubtasks={proposedSubtasks}
              setProposedSubtasks={setProposedSubtasks}
              cardEdits={cardEdits}
              updateCardEdit={updateCardEdit}
              projectTasksForSuggest={projectTasksForSuggest}
              voiceSubtasksContext={voiceSubtasksContext}
              currentUserName={currentUser?.name}
              selectedProjectName={selectedProject?.name ?? null}
              isProjectSelected={selectedProjectId !== null}
              submittedAt={submittedAt}
              draftSaved={draftSaved}
              onSaveDraft={saveDraft}
              onExtract={handleBoundProjectExtract}
              onResetExtractionState={resetExtractionState}
              onSubmitFinal={handleSubmitFinal}
              projectArchived={projectArchived}
              projectSubmitBlockedReason={projectSubmitBlockedReason}
            />

            <VoiceUpdateHistoryPanel
              history={history}
              currentUserName={currentUser?.name}
              onSelectUpdate={handleSelectUpdate}
            />

            <VoiceUpdateDetailDrawer
              detailItem={detailItem}
              detailLoading={detailLoading}
              showTranscript={showTranscript}
              onClose={() => {
                setDetailItem(null)
                setDetailLoading(false)
                setShowTranscript(false)
              }}
              onToggleTranscript={() => setShowTranscript((v) => !v)}
              onRestartFromTranscript={(transcript) => {
                setText(transcript)
                setPhase('input')
                setDetailItem(null)
                setShowTranscript(false)
              }}
            />
          </div>
        </div>
      </main>
        </>
      )}
    </div>
  )
}
