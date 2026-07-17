import { VoiceUpdateEditableFieldsSection } from './VoiceUpdateEditableFieldsSection'
import { VoiceUpdateTaskReportsSection } from './VoiceUpdateTaskReportsSection'
import type { VoiceUpdateResultCardProps } from './voiceUpdateResultTypes'

export function VoiceUpdateResultCard(props: VoiceUpdateResultCardProps) {
  const {
    result,
    error,
    phase,
    editValues,
    editingField,
    setEditingField,
    setEditValues,
    taskReports,
    setTaskReports,
    keyTaskIssues,
    setKeyTaskIssues,
    selectedSubtaskId,
    proposedSubtasks,
    setProposedSubtasks,
    cardEdits,
    updateCardEdit,
    projectTasksForSuggest,
    voiceSubtasksContext,
    currentUserName,
    onExtract,
    hasSelectedTask,
    hasText,
  } = props

  return (
    <section className="voice-update-result-panel" aria-label="AI 提取结果预览">
      <header className="voice-update-panel-header voice-update-result-header">
        <div className="voice-update-panel-heading">
          <span className="voice-update-panel-step">3</span>
          <div>
            <h2>AI 提取结果（预览）</h2>
            <p>AI 已提取以下结构化内容，请检查并完善</p>
          </div>
        </div>
        {phase === 'extracted' && (
          <button type="button" className="voice-update-reextract-button" onClick={onExtract}>重新提取</button>
        )}
      </header>

      <div className="voice-update-result-body">
        {phase === 'extracting' && (
          <div className="voice-update-result-state"><strong>AI 正在提取结构化内容…</strong><span>原始汇报内容已保留</span></div>
        )}
        {error && (
          <div className="voice-update-result-state is-error">
            <strong>{error}</strong>
            {phase === 'input' && hasSelectedTask && hasText && <button type="button" className="voice-update-retry-button" onClick={onExtract}>重新提取</button>}
          </div>
        )}

        <VoiceUpdateTaskReportsSection
          phase={phase}
          taskReports={taskReports}
          setTaskReports={setTaskReports}
          keyTaskIssues={keyTaskIssues}
          setKeyTaskIssues={setKeyTaskIssues}
          selectedSubtaskId={selectedSubtaskId}
          cardEdits={cardEdits}
          updateCardEdit={updateCardEdit}
          projectTasksForSuggest={projectTasksForSuggest}
          voiceSubtasksContext={voiceSubtasksContext}
        />

        {result && (
          <VoiceUpdateEditableFieldsSection
            phase={phase}
            editValues={editValues}
            editingField={editingField}
            setEditingField={setEditingField}
            setEditValues={setEditValues}
            proposedSubtasks={proposedSubtasks}
            setProposedSubtasks={setProposedSubtasks}
            currentUserName={currentUserName}
            taskReports={taskReports}
          />
        )}
      </div>
    </section>
  )
}
