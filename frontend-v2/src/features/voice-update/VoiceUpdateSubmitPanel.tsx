import type { VoiceUpdateSubmitPanelProps } from './voiceUpdateResultTypes'
import { hasUnconfirmedOwnership } from './voiceUpdateResultTypes'

export function VoiceUpdateSubmitPanel({
  phase,
  reportScope,
  taskReports,
  cardEdits,
  selectedSubtaskId,
  submittedAt,
  draftSaved,
  onSaveDraft,
  onResetExtractionState,
  onClear,
  onSubmitFinal,
  onViewSubmissionHistory,
  projectArchived = false,
  projectSubmitBlockedReason = null,
}: VoiceUpdateSubmitPanelProps) {
  const controlsLocked = phase === 'extracting' || phase === 'submitting'
  const hasMissingSuggestionOwner = taskReports.some((report, index) => (
    report.type === 'suggest_new_subtask'
    && !report.parent_task_id
    && !(cardEdits[index]?.modified && cardEdits[index]?.taskId)
  ))
  const hasUnconfirmedAgentOwnership = hasUnconfirmedOwnership(taskReports)
  const submitBlockedReason = hasUnconfirmedAgentOwnership
    ? '请先确认所有任务卡归属'
    : projectSubmitBlockedReason
  const canSubmit = phase === 'extracted'
    && (reportScope === 'task' ? Boolean(selectedSubtaskId) : taskReports.length > 0)
    && !submitBlockedReason
    && !hasMissingSuggestionOwner

  if (phase === 'submitted') {
    return (
      <footer className="voice-update-footer">
        <div className="voice-update-footer-bar">
          <div className="voice-update-submit-success">
            <span aria-hidden="true">✓</span>
            <span>已提交至 AI 确认中心{submittedAt ? ` · ${submittedAt}` : ''}</span>
          </div>
          <div className="voice-update-footer-note">提交后将进入 AI 确认中心，由项目负责人审核确认后写入工作推进表</div>
          <div className="voice-update-footer-actions">
            <button type="button" className="voice-update-footer-secondary" onClick={() => onResetExtractionState({ clearText: true })}>继续提交新汇报</button>
            <button type="button" className="voice-update-footer-primary" onClick={onViewSubmissionHistory}>查看提交记录</button>
          </div>
        </div>
      </footer>
    )
  }

  return (
    <footer className="voice-update-footer">
      <div className="voice-update-footer-bar">
        <div className="voice-update-footer-actions">
          <button type="button" className="voice-update-footer-secondary" onClick={onSaveDraft} disabled={controlsLocked || projectArchived}>
            {draftSaved ? '已保存草稿' : '保存草稿'}
          </button>
          <button type="button" className="voice-update-footer-secondary" onClick={onClear} disabled={controlsLocked}>清空内容</button>
        </div>
        <div className="voice-update-footer-note">
          提交后将进入 AI 确认中心，由项目负责人审核确认后写入工作推进表
        </div>
        <div className="voice-update-footer-actions">
          {submitBlockedReason && <span className="voice-update-footer-hint">{submitBlockedReason}</span>}
          <button type="button" className="voice-update-footer-primary" onClick={onSubmitFinal} disabled={!canSubmit}>
            {phase === 'extracting' ? 'AI 提取中' : phase === 'submitting' ? '提交中…' : '提交至 AI 确认中心'}
          </button>
        </div>
      </div>
    </footer>
  )
}
