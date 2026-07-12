import type { VoiceUpdateSubmitPanelProps } from './voiceUpdateResultTypes'

export function VoiceUpdateSubmitPanel({
  phase,
  taskReports,
  cardEdits,
  currentUserName,
  selectedProjectName,
  isProjectSelected,
  text,
  submittedAt,
  draftSaved,
  onSaveDraft,
  onExtract,
  onResetExtractionState,
  onSubmitFinal,
  projectArchived = false,
  projectSubmitBlockedReason = null,
}: VoiceUpdateSubmitPanelProps) {
  return (
    <div className="bg-white rounded-2xl border p-5 flex-shrink-0" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold text-slate-700">关联与确认</h3>
          <span className="text-xs text-slate-400">{phase === 'input' || phase === 'extracting' ? '步骤 1/2' : phase === 'extracted' || phase === 'submitting' ? '步骤 2/2' : ''}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs" style={{ color: '#D97706' }}>
          <svg style={{ width: 12, height: 12 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="font-medium">AI 提取后需确认，再提交给负责人审核</span>
        </div>
      </div>

      <div className="mb-4 rounded-xl border px-3 py-2 text-xs flex items-center justify-between gap-3" style={{ borderColor: '#E2E8F0', background: '#F8FAFC' }}>
        <span className="text-slate-500 font-semibold">所属项目</span>
        <span className="font-semibold text-slate-700">
          {isProjectSelected ? (selectedProjectName || '已选择') : '请选择项目'}
        </span>
      </div>
      {projectSubmitBlockedReason && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700">
          {projectSubmitBlockedReason}
        </div>
      )}

      {phase === 'submitted' ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 p-3 rounded-xl" style={{ background: '#F0FDF4', border: '1px solid #BBF7D0' }}>
            <svg style={{ width: 16, height: 16, color: '#059669' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm text-emerald-700 font-semibold">已提交，等待负责人确认</p>
              <p className="text-xs text-emerald-600 mt-0.5">提交时间：{submittedAt}</p>
            </div>
          </div>
          <button
            onClick={() => onResetExtractionState({ clearText: true })}
            className="cursor-pointer w-full py-2.5 rounded-xl border-2 text-sm font-semibold transition-all hover:bg-slate-50"
            style={{ borderColor: '#E2E8F0', color: '#475569' }}
          >
            继续提交新进展
          </button>
        </div>
      ) : (
        <>
          <div className="mb-4 flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-400">提交人</span>
            <span className="text-sm font-semibold text-slate-700">{currentUserName ?? '—'}</span>
          </div>

          {(phase === 'input' || phase === 'extracting') && (
            <div className="flex items-center gap-3">
              <button
                className="cursor-pointer flex-1 py-2.5 rounded-xl border-2 text-sm font-semibold transition-all disabled:opacity-50"
                style={{ borderColor: draftSaved ? '#34D399' : '#E2E8F0', color: draftSaved ? '#059669' : '#475569', background: draftSaved ? '#F0FDF4' : 'white' }}
                onClick={onSaveDraft}
                disabled={phase === 'extracting' || projectArchived}
                title={projectArchived ? '项目已归档，不可提交汇报。' : undefined}
              >
                {draftSaved ? '✓ 已保存草稿' : '保存草稿'}
              </button>
              <button
                onClick={onExtract}
                disabled={phase === 'extracting' || !text.trim() || Boolean(projectSubmitBlockedReason)}
                title={projectSubmitBlockedReason ?? undefined}
                className="cursor-pointer flex-1 py-2.5 rounded-xl text-white text-sm font-bold transition-all hover:opacity-90 disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)', boxShadow: '0 2px 8px rgba(3,105,161,0.3)' }}
              >
                {phase === 'extracting' ? 'AI提取中...' : 'AI提取'}
              </button>
            </div>
          )}

          {(phase === 'extracted' || phase === 'submitting') && (
            <div className="space-y-2">
              <p className="text-xs text-slate-400">确认AI提取结果无误后，提交给项目负责人审核</p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => onResetExtractionState()}
                  disabled={phase === 'submitting'}
                  className="cursor-pointer flex-1 py-2.5 rounded-xl border-2 text-sm font-semibold transition-all hover:bg-slate-50 disabled:opacity-50"
                  style={{ borderColor: '#E2E8F0', color: '#475569' }}
                >
                  重新提取
                </button>
                {(() => {
                  const hasMissingSuggest = taskReports.some((r, i) => {
                    if ((r as Record<string, unknown>).type !== 'suggest_new_subtask') return false
                    const hasParent = !!(r as Record<string, unknown>).parent_task_id
                    return !hasParent && !(cardEdits[i]?.modified && cardEdits[i].taskId)
                  })
                  const blockedByArchived = projectArchived
                  return (
                    <button
                      onClick={onSubmitFinal}
                      disabled={phase === 'submitting' || hasMissingSuggest || Boolean(projectSubmitBlockedReason)}
                      title={
                        projectSubmitBlockedReason
                          ? projectSubmitBlockedReason
                          : blockedByArchived
                          ? '项目已归档，不可提交汇报。'
                          : hasMissingSuggest
                            ? '请先为所有建议新关键任务选择归属重点工作'
                            : undefined
                      }
                      className="cursor-pointer flex-[2] py-2.5 rounded-xl text-white text-sm font-bold transition-all hover:opacity-90 disabled:opacity-50"
                      style={{
                        background: hasMissingSuggest ? '#94A3B8' : 'linear-gradient(135deg,#059669,#0EA5E9)',
                        boxShadow: hasMissingSuggest ? 'none' : '0 2px 8px rgba(5,150,105,0.3)',
                      }}
                    >
                      {phase === 'submitting'
                        ? '提交中...'
                        : projectSubmitBlockedReason
                            ? projectSubmitBlockedReason.includes('选择') ? '请先选择所属项目' : '项目未进入执行阶段'
                        : hasMissingSuggest
                            ? '请先选择归属重点工作'
                            : '提交给负责人'}
                    </button>
                  )
                })()}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
