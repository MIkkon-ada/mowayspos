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
    proposedSubtasks,
    setProposedSubtasks,
    cardEdits,
    updateCardEdit,
    projectTasksForSuggest,
    voiceSubtasksContext,
    currentUserName,
  } = props

  return (
    <div className="bg-white rounded-2xl border flex-1 flex flex-col overflow-hidden" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
      <div className="flex items-center justify-between px-5 py-3.5 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#6366F1,#0EA5E9)' }}>
            <svg style={{ width: 12, height: 12, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h2 className="text-sm font-bold text-slate-800">AI 提取结果预览</h2>
        </div>
        {result && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            {phase === 'submitted' ? (
              <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-semibold">已提交，等待负责人确认</span>
            ) : (
              <>
                <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-semibold">步骤2/2：确认并提交</span>
                <span className="text-slate-200">|</span>
                <button
                  onClick={() => setEditingField(editingField ? null : 'all')}
                  className="flex items-center gap-0.5 text-blue-500 hover:text-blue-700 font-medium"
                >
                  <svg style={{ width: 11, height: 11 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  {editingField ? '完成编辑' : '编辑全部'}
                </button>
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {!result && !error && phase !== 'extracting' && (
          <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <svg style={{ width: 48, height: 48, marginBottom: 12 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <p className="text-sm font-medium">步骤 1/2：输入内容后点击“AI提取”</p>
            <p className="text-xs mt-1">AI 提取完成后，再确认提交给负责人</p>
          </div>
        )}

        {phase === 'extracting' && !result && (
          <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <svg className="animate-spin" style={{ width: 40, height: 40, marginBottom: 12, color: '#0369A1' }} fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-sm font-medium text-blue-600">AI 正在分析提取中...</p>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
            <svg style={{ width: 14, height: 14, color: '#DC2626' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-xs text-red-700 font-medium">{error}</span>
          </div>
        )}

        <VoiceUpdateTaskReportsSection
          phase={phase}
          taskReports={taskReports}
          setTaskReports={setTaskReports}
          keyTaskIssues={keyTaskIssues}
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
      </div>
    </div>
  )
}
