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

  const emptyMessage = !hasSelectedTask
    ? '选择关键任务并输入内容后，点击“AI 提取”'
    : !hasText
      ? '输入本次工作内容后，点击“AI 提取”。'
      : '点击“AI 提取”，生成本次汇报的结构化预览。'

  return (
    <section className="voice-update-result-panel" aria-label="AI 提取结果预览">
      <header className="voice-update-result-header">
        <div>
          <h2>AI 提取结果（预览）</h2>
          <p>AI 已提取以下结构化内容，请检查并完善</p>
        </div>
        {phase === 'extracted' && <span className="voice-update-recommended">可人工修改</span>}
      </header>

      <div className="voice-update-result-body">
        {!result && phase !== 'extracting' && !error && (
          <div className="voice-update-result-empty"><strong>{emptyMessage}</strong></div>
        )}
        {phase === 'extracting' && (
          <div className="voice-update-result-empty"><strong>AI 正在提取结构化内容…</strong><span>原始汇报内容已保留</span></div>
        )}
        {error && (
          <div className="voice-update-result-empty">
            <strong>{error}</strong>
            {phase === 'input' && hasSelectedTask && hasText && <button type="button" className="voice-update-retry-button" onClick={onExtract}>重新提取</button>}
          </div>
        )}

        {result && (
          <>
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
          </>
        )}
      </div>
    </section>
  )
}
