import type { Dispatch, SetStateAction } from 'react'
import type { TaskReport, TaskReportProgress, UserSubtaskContext } from '../../api/updates'

type VoiceUpdateOwnershipReviewPanelProps = {
  phase: 'input' | 'extracting' | 'extracted' | 'submitting' | 'submitted'
  taskReports: TaskReport[]
  setTaskReports: Dispatch<SetStateAction<TaskReport[]>>
  voiceSubtasksContext: UserSubtaskContext[]
}

const MATCH_LABELS = {
  needs_confirmation: '需要确认归属',
  unmatched: '无法匹配',
} as const

function evidenceText(report: TaskReportProgress): string {
  const evidence = report.evidence?.filter(Boolean) ?? []
  if (evidence.length > 0) return evidence.join('；')
  return report.completed || ''
}

function candidateLabel(item: UserSubtaskContext): string {
  return `${item.project_name || '未命名项目'} > ${item.parent_key_task || '未命名重点工作'} > ${item.subtask_title || item.title || '未命名关键任务'}`
}

export function VoiceUpdateOwnershipReviewPanel({
  phase,
  taskReports,
  setTaskReports,
  voiceSubtasksContext,
}: VoiceUpdateOwnershipReviewPanelProps) {
  const unresolvedReports = taskReports
    .map((report, index) => ({ report, index }))
    .filter((item): item is { report: TaskReportProgress; index: number } =>
      item.report.type === 'progress'
      && Boolean(item.report.match_status)
      && item.report.match_status !== 'matched',
    )

  if (phase === 'input') return null

  if (phase === 'extracting') {
    return (
      <section className="voice-update-left-ai-result" aria-label="AI 提取结果">
        <header>
          <h2>AI 提取结果</h2>
          <span>正在分析</span>
        </header>
        <div className="voice-update-left-ai-empty is-loading">
          <strong>AI 正在提取结构化内容...</strong>
          <p>请稍等，原始汇报内容已保留。</p>
        </div>
      </section>
    )
  }

  if (taskReports.length === 0) {
    return (
      <section className="voice-update-left-ai-result" aria-label="AI 提取结果">
        <header>
          <h2>AI 提取结果</h2>
          <span>未识别到任务</span>
        </header>
        <div className="voice-update-left-ai-empty">
          <strong>暂无可确认的提取结果</strong>
          <p>AI 没有识别出明确的工作项。可以补充“本次完成、下一步计划、问题、成果”等信息后重新提取，或直接在右侧手动填写。</p>
        </div>
      </section>
    )
  }

  if (unresolvedReports.length === 0) {
    return (
      <section className="voice-update-left-ai-result" aria-label="AI 提取结果">
        <header>
          <h2>AI 提取结果</h2>
          <span>AI 已识别 {taskReports.length} 项工作</span>
        </header>
        <div className="voice-update-left-ai-empty is-success">
          <strong>已完成提取</strong>
          <p>结构化内容已同步到右侧，请检查后提交至 AI 确认中心。</p>
        </div>
      </section>
    )
  }

  function applyOwnership(index: number, candidateId: number | null, candidates: UserSubtaskContext[]) {
    const selected = candidates.find((item) => (item.subtask_id ?? item.id) === candidateId)
    setTaskReports((previous) => previous.map((report, reportIndex) => {
      if (reportIndex !== index || report.type !== 'progress') return report
      if (!selected) return { ...report, matched_subtask_id: null }
      return {
        ...report,
        matched_subtask_id: candidateId,
        matched_subtask_title: selected.subtask_title || selected.title,
        parent_task_id: selected.parent_task_id ?? null,
        parent_key_task: selected.parent_key_task,
        project_id: selected.project_id ?? selected.parent_project_id ?? null,
        project_name: selected.project_name || '',
        match_status: 'matched',
        match_reason: '用户手动确认归属',
        match_confidence: 1,
      }
    }))
  }

  return (
    <section className="voice-update-left-ai-result" aria-label="AI 提取结果">
      <header>
        <h2>AI 提取结果</h2>
        <span>AI 已识别 {taskReports.length} 项工作</span>
      </header>

      <div className="voice-update-left-ai-list">
        {unresolvedReports.map(({ report, index }) => {
          const candidates = report.match_candidates?.length ? report.match_candidates : voiceSubtasksContext
          const status = report.match_status === 'unmatched' ? 'unmatched' : 'needs_confirmation'
          const tone = status === 'unmatched' ? 'is-unmatched' : 'is-needs-confirmation'
          return (
            <article className={`voice-update-left-ai-card ${tone}`} key={index}>
              <h3>{MATCH_LABELS[status]}</h3>
              <p>{report.match_reason || 'AI 未能明确匹配到具体关键任务，请手动确认归属。'}</p>
              <strong>原文证据：</strong>
              <blockquote>“{evidenceText(report) || '暂无原文证据'}”</blockquote>
              <select
                value={report.matched_subtask_id ?? ''}
                onChange={(event) => applyOwnership(index, event.target.value ? Number(event.target.value) : null, candidates)}
              >
                <option value="">请选择候选任务，不会自动选中</option>
                {candidates.map((candidate) => (
                  <option key={candidate.subtask_id ?? candidate.id} value={candidate.subtask_id ?? candidate.id}>
                    {candidateLabel(candidate)}
                  </option>
                ))}
              </select>
            </article>
          )
        })}
      </div>
    </section>
  )
}
