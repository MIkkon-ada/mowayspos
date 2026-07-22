import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { VoiceUpdateDetailDrawer } from '../features/voice-update/VoiceUpdateDetailDrawer'
import { VoiceUpdateHistoryPanel } from '../features/voice-update/VoiceUpdateHistoryPanel'
import { VoiceUpdateInputPanel } from '../features/voice-update/VoiceUpdateInputPanel'
import { VoiceUpdateResultPanel } from '../features/voice-update/VoiceUpdateResultPanel'
import { useVoiceExtraction } from '../features/voice-update/useVoiceExtraction'
import { useVoiceSubmission } from '../features/voice-update/useVoiceSubmission'
import { useVoiceHistory } from '../features/voice-update/useVoiceHistory'
import { useVoiceDraft } from '../features/voice-update/useVoiceDraft'
import { useVoiceRecorder } from '../features/voice-update/useVoiceRecorder'
import { useVoiceUpload } from '../features/voice-update/useVoiceUpload'
import { formatTime } from '../features/voice-update/voiceUpdateHelpers'
import { fetchVoiceContext } from '../api/updates'
import { canExtractVoiceUpdate } from '../features/voice-update/voiceUpdateResultTypes'
import { isProjectActive, isProjectArchived } from '../domain/projectLifecycleStatus'
import type { Project } from '../types'

function fmtProjectName(p: Project | undefined): string {
  if (!p) return ''
  if (p.short_name) return p.short_name
  return p.name.length > 12 ? `${p.name.slice(0, 10)}…` : p.name
}

export function VoiceUpdatePage() {
  const { id } = useParams<{ id: string }>()
  const projectId = id ? Number(id) : null
  const navigate = useNavigate()
  const { projects, currentUser, loading: projectsLoading } = useProject()

  const user = currentUser ? { name: currentUser.display_name ?? currentUser.username ?? '' } : null

  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(projectId)
  const [hasSubtasks, setHasSubtasks] = useState<boolean | null>(null)
  const [text, setText] = useState('')
  const [mode, setMode] = useState<'text' | 'voice' | 'upload'>('text')
  const [selectedProvider, setSelectedProvider] = useState('anthropic')

  const projectOptions = projects.filter((p) => p.id != null && p.name)
  const selectedProject = selectedProjectId
    ? projects.find((p) => p.id === selectedProjectId) ?? null
    : null

  const projectActive = selectedProject ? isProjectActive(selectedProject) : false
  const projectArchived = selectedProject ? isProjectArchived(selectedProject) : false
  const projectSubmitBlockedReason: string | null = (() => {
    if (projectArchived) return '项目已归档，无法提交工作汇报'
    if (selectedProject && !projectActive) return '项目尚未进入执行阶段，暂不能提交工作汇报'
    return null
  })()

  const { draftSaved, saveDraft } = useVoiceDraft({
    text,
    selectedProvider,
    setText,
    setSelectedProvider,
  })

  const { recording, transcribing, timer, startRecording, stopRecording } = useVoiceRecorder({
    setText,
    setError: () => {},
  })
  const { uploading, uploadFileName, uploadInputRef, handleUploadFile } = useVoiceUpload({
    setText,
    setError: () => {},
  })

  const {
    history,
    detailItem,
    detailLoading,
    showTranscript,
    setShowTranscript,
    setDetailItem,
    refreshHistory,
    handleSelectUpdate,
  } = useVoiceHistory()

  const {
    phase,
    setPhase,
    result,
    error: extractionError,
    setError: setExtractionError,
    editValues,
    setEditValues,
    editingField,
    setEditingField,
    taskReports,
    cardEdits,
    updateCardEdit,
    proposedSubtasks,
    keyTaskIssues,
    projectTasksForSuggest,
    resetExtractionState,
    handleExtract,
  } = useVoiceExtraction({
    selectedProjectId,
    selectedTaskContext: null,
    selectedProjectIsActive: projectActive,
    currentUser: user,
    text,
    mode,
    selectedProvider,
    setText,
  })

  const { submittedAt, submittedSubmissionId, handleSubmitFinal } = useVoiceSubmission({
    selectedProjectId,
    selectedSubtaskId: null,
    selectedTaskContext: null,
    currentUser: user,
    text,
    mode,
    result,
    editValues,
    taskReports,
    keyTaskIssues,
    cardEdits,
    proposedSubtasks,
    projectTasksForSuggest: projectTasksForSuggest.map((t) => ({ id: t.id, key_task: t.key_task })),
    projects,
    setPhase,
    setError: setExtractionError,
    refreshHistory,
  })

  const extractDisabled = !canExtractVoiceUpdate({
    projectId: selectedProjectId,
    selectedTaskContext: null,
    text,
    projectActive,
    recording,
    transcribing,
    uploading,
    phase,
    requireTaskBinding: false,
  })

  const controlsLocked = phase === 'extracting' || phase === 'submitting'

  // 检查用户是否有可汇报的子任务
  useEffect(() => {
    let cancelled = false
    setHasSubtasks(null)
    fetchVoiceContext(null)
      .then((ctx) => {
        if (!cancelled) {
          const hasAny = Array.isArray(ctx) ? ctx.some((c: Record<string, unknown>) => c.id) : false
          setHasSubtasks(hasAny)
        }
      })
      .catch(() => {
        if (!cancelled) setHasSubtasks(false)
      })
    return () => {
      cancelled = true
    }
  }, [])



  // URL 中的项目变化时同步
  useEffect(() => {
    setSelectedProjectId(projectId)
  }, [projectId])

  const handleSelectProject = (id: number | null) => {
    setSelectedProjectId(id)
    resetExtractionState({ clearText: false })
    if (id) {
      navigate(`/project/${id}/work/submit`, { replace: true })
    } else {
      navigate('/work/submit', { replace: true })
    }
  }

  const handleClear = () => {
    setText('')
    resetExtractionState({ clearText: true })
  }

  const handleRestartFromTranscript = (transcript: string) => {
    setText(transcript)
    resetExtractionState({ clearText: false })
  }

  // 空状态：无子任务
  if (hasSubtasks === false) {
    return (
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="voice-update-header">
          <div className="voice-update-header-title-row">
            <h1>工作汇报</h1>
          </div>
        </header>
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center">
            <p className="text-slate-400 text-sm">暂无可汇报的关键任务</p>
            <p className="text-slate-300 text-xs mt-1">
              请联系项目负责人分配关键任务后即可开始汇报
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="voice-update-header">
        <div className="voice-update-header-title-row">
          <h1>工作汇报</h1>
          <span className="voice-update-header-desc">
            {selectedProject
              ? fmtProjectName(selectedProject)
              : '我的全部工作'}
          </span>
        </div>
        <div className="voice-update-header-actions">
          <select
            className="voice-update-project-select"
            value={selectedProjectId ?? ''}
            onChange={(e) => {
              const val = e.target.value
              handleSelectProject(val ? Number(val) : null)
            }}
          >
            <option value="">我的全部工作</option>
            {projectOptions.map((p) => (
              <option key={p.id} value={p.id!}>
                {fmtProjectName(p)}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* 项目已归档提示 */}
      {projectSubmitBlockedReason && (
        <div
          style={{
            padding: '8px 20px',
            fontSize: 12,
            color: '#B45309',
            background: '#FFFBEB',
            borderBottom: '1px solid #FDE68A',
          }}
        >
          ⚠ {projectSubmitBlockedReason}
        </div>
      )}

      {/* Main content: two columns */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(360px,1fr) minmax(360px,1fr)',
          gap: 0,
          flex: 1,
          overflow: 'hidden',
        }}
      >
        {/* 左栏：输入 */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            borderRight: '1px solid #E9EFF6',
          }}
        >
          <VoiceUpdateInputPanel
            mode={mode}
            onModeChange={setMode}
            providers={[
              { provider: 'anthropic', display_name: 'Anthropic', model: 'claude-sonnet' },
              { provider: 'dashscope', display_name: 'DashScope', model: 'qwen-max' },
              { provider: 'deepseek', display_name: 'DeepSeek', model: 'deepseek-chat' },
              { provider: 'glm', display_name: 'GLM', model: 'glm-4' },
            ]}
            selectedProvider={selectedProvider}
            onProviderChange={setSelectedProvider}
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
        </div>

        {/* 右栏：结果 + 历史 + Footer */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* 结果区 */}
          <div className="flex-1 overflow-y-auto">
            {phase === 'input' && (
              <div
                className="flex-1 flex items-center justify-center p-8"
                style={{ minHeight: 200 }}
              >
                <p className="text-slate-300 text-sm">
                  输入内容后点击「AI 提取」查看结构化结果
                </p>
              </div>
            )}

            {(phase === 'extracting' ||
              phase === 'extracted' ||
              phase === 'submitting' ||
              phase === 'submitted') && (
              <VoiceUpdateResultPanel
                phase={phase}
                result={result}
                error={extractionError}
                editValues={editValues}
                setEditValues={setEditValues}
                editingField={editingField}
                setEditingField={setEditingField}
                taskReports={taskReports}
                cardEdits={cardEdits}
                updateCardEdit={updateCardEdit}
                projectTasksForSuggest={projectTasksForSuggest}
                hasSelectedTask={false}
                hasText={text.trim().length > 0}
                selectedSubtaskId={null}
                onExtract={handleExtract}
                onSubmitFinal={handleSubmitFinal}
                controlsLocked={controlsLocked}
                extractDisabled={extractDisabled}
                submittedAt={submittedAt}
                submittedSubmissionId={submittedSubmissionId}
                projectArchived={projectArchived}
                projectSubmitBlockedReason={projectSubmitBlockedReason}
                onClearText={() => setText('')}
                onShowHistory={() => {}}
                draftSaved={false}
                onSaveDraft={() => {}}
                onClear={handleClear}
                onViewSubmissionHistory={() => {}}
              />
            )}
          </div>

          {/* 历史面板 */}
          <div style={{ borderTop: '1px solid #E9EFF6', flexShrink: 0 }}>
            <VoiceUpdateHistoryPanel
              history={history}
              currentUserName={currentUser?.display_name ?? currentUser?.username ?? ''}
              onSelectUpdate={handleSelectUpdate}
            />
          </div>

          {/* Footer */}
          <footer style={{ borderTop: '1px solid #E9EFF6', flexShrink: 0 }}>
            {phase === 'submitted' ? (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: 12,
                  padding: '12px 20px',
                }}
              >
                <span style={{ color: '#10B981', fontSize: 13, fontWeight: 500 }}>
                  ✓ 已提交至 AI 确认中心
                  {submittedAt ? ` · ${submittedAt}` : ''}
                </span>
                <button
                  type="button"
                  style={{
                    padding: '6px 16px',
                    fontSize: 13,
                    border: '1px solid #D1D5DB',
                    borderRadius: 8,
                    color: '#374151',
                    background: '#fff',
                    cursor: 'pointer',
                  }}
                  onClick={() => resetExtractionState({ clearText: true })}
                >
                  继续提交新汇报
                </button>
                {submittedSubmissionId && (
                  <button
                    type="button"
                    style={{
                      padding: '6px 16px',
                      fontSize: 13,
                      borderRadius: 8,
                      color: '#fff',
                      background: '#2563EB',
                      border: 'none',
                      cursor: 'pointer',
                    }}
                    onClick={() => handleSelectUpdate(submittedSubmissionId)}
                  >
                    查看本条记录
                  </button>
                )}
              </div>
            ) : (
              <>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 20px',
                  }}
                >
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      type="button"
                      style={{
                        padding: '6px 16px',
                        fontSize: 13,
                        border: '1px solid #D1D5DB',
                        borderRadius: 8,
                        color: '#374151',
                        background: '#fff',
                        cursor: 'pointer',
                      }}
                      onClick={saveDraft}
                    >
                      {draftSaved ? '已保存' : '保存草稿'}
                    </button>
                    <button
                      type="button"
                      style={{
                        padding: '6px 16px',
                        fontSize: 13,
                        border: '1px solid #D1D5DB',
                        borderRadius: 8,
                        color: '#6B7280',
                        background: '#fff',
                        cursor: 'pointer',
                      }}
                      onClick={handleClear}
                    >
                      清空内容
                    </button>
                  </div>
                  <button
                    type="button"
                    disabled={phase !== 'extracted' || !!projectSubmitBlockedReason}
                    style={{
                      padding: '6px 24px',
                      fontSize: 13,
                      borderRadius: 8,
                      color: '#fff',
                      background:
                        phase === 'extracted' && !projectSubmitBlockedReason ? '#2563EB' : '#9CA3AF',
                      border: 'none',
                      cursor:
                        phase === 'extracted' && !projectSubmitBlockedReason
                          ? 'pointer'
                          : 'not-allowed',
                    }}
                    onClick={handleSubmitFinal}
                  >
                    提交至 AI 确认中心
                  </button>
                </div>
                {phase !== 'input' && (
                  <div style={{ padding: '0 20px 10px' }}>
                    <span style={{ fontSize: 11, color: '#9CA3AF' }}>
                      提交后将进入 AI 确认中心，由项目负责人审核确认后写入工作推进表
                    </span>
                  </div>
                )}
              </>
            )}
          </footer>
        </div>
      </div>

      {/* Detail Drawer */}
      <VoiceUpdateDetailDrawer
        detailItem={detailItem}
        detailLoading={detailLoading}
        showTranscript={showTranscript}
        onClose={() => setDetailItem(null)}
        onToggleTranscript={() => setShowTranscript(!showTranscript)}
        onRestartFromTranscript={handleRestartFromTranscript}
        currentUserName={currentUser?.display_name ?? currentUser?.username ?? ''}
        onResubmitted={async (id: number) => {
          await refreshHistory()
          await handleSelectUpdate(id)
        }}
      />
    </div>
  )
}
