import { apiGet, apiPatch, apiPost, apiPut, apiUpload } from './client'
import type { MeetingItem } from '../types'

export type MeetingRevisionItem = {
  id: number
  meeting_id: number
  version_no: number
  is_legacy_snapshot: boolean
  saved_by: string
  saved_at?: string
  transcript_text: string
  title?: string
  meeting_date?: string
  host?: string
  summary?: string
  task_list_json?: string
  decision_items_json?: string
  risk_items_json?: string
  publish_status?: string
}

export function fetchMeetings(projectId: number): Promise<MeetingItem[]> {
  return apiGet<MeetingItem[]>(`/api/meetings?project_id=${projectId}`)
}

export function fetchMeetingRevisions(meetingId: number): Promise<MeetingRevisionItem[]> {
  return apiGet<MeetingRevisionItem[]>(`/api/meetings/${meetingId}/revisions`)
}

export type MeetingProgressStatus = 'completed' | 'in_progress' | 'blocked' | 'not_started' | 'not_mentioned'
export type MeetingProgressReviewStatus = 'pending' | 'accepted' | 'ignored'

export type MeetingProgressReviewItem = {
  id: number
  project_id: number
  meeting_id: number
  baseline_run_id: number
  baseline_task_id?: number | null
  baseline_subtask_id?: number | null
  member_name: string
  baseline_snapshot_json: string
  report_text: string
  status: MeetingProgressStatus
  evidence_quote: string
  suggested_task_status: string
  review_status: MeetingProgressReviewStatus
  reviewer_person_id?: number | null
  reviewed_at?: string | null
  review_comment?: string
  validation_json: string
  analysis_version: number
}

export type MeetingProgressReviewAnalysis = {
  meeting_id: number
  analysis_version: number
  reviews: MeetingProgressReviewItem[]
}

export function analyzeProgressReview(meetingId: number): Promise<MeetingProgressReviewAnalysis> {
  return apiPost<MeetingProgressReviewAnalysis>(`/api/meetings/${meetingId}/progress-review/analyze`)
}

export function fetchProgressReviews(meetingId: number): Promise<MeetingProgressReviewItem[]> {
  return apiGet<MeetingProgressReviewItem[]>(`/api/meetings/${meetingId}/progress-review`)
}

export function patchProgressReview(
  meetingId: number,
  reviewId: number,
  payload: {
    status?: MeetingProgressStatus
    suggested_task_status?: string
    review_status?: 'pending' | 'ignored'
    review_comment?: string
  },
): Promise<MeetingProgressReviewItem> {
  return apiPatch<MeetingProgressReviewItem>(`/api/meetings/${meetingId}/progress-review/${reviewId}`, payload)
}

export function confirmProgressReview(
  meetingId: number,
  reviewId: number,
  payload: { status?: MeetingProgressStatus; suggested_task_status?: string; review_comment?: string },
): Promise<MeetingProgressReviewItem & { task_updated: boolean }> {
  return apiPost<MeetingProgressReviewItem & { task_updated: boolean }>(`/api/meetings/${meetingId}/progress-review/${reviewId}/confirm`, payload)
}

export function patchMeetingStatus(
  id: number,
  publish_status: 'draft' | 'published' | 'returned',
): Promise<MeetingItem> {
  return apiPatch<MeetingItem>(`/api/meetings/${id}/status`, { publish_status })
}

export type MeetingAnalyzeResult = {
  title: string
  meeting_type: string
  meeting_date: string
  host: string
  participants: string
  summary: string
  reports_json: string        // 按人头的汇报结构（项目汇报模式）
  task_list_json: string      // 行动清单
  confirmed_items_json: string
  decision_items_json: string
  risk_items_json: string
  transcript_text: string
  analysis_id: number | null
  change_set: MeetingChangeSet | null
}

export type MeetingChangeProposal = {
  id: number
  action: 'create_workstream' | 'update_workstream' | 'create_subtask' | 'update_subtask'
  target_type: 'workstream' | 'subtask'
  target_id: number | null
  parent_workstream_id: number | null
  target: {
    project_id: number
    workstream_id?: number
    subtask_id?: number
    parent_workstream_id?: number
  }
  before: Record<string, unknown>
  proposed: Record<string, unknown>
  evidence: string[]
  reason: string
  confidence: number
  validation: { state: 'ready' | 'needs_review' | 'blocked'; errors: string[] }
  execution_status: 'pending' | 'executed'
  executed_by_person_id: number | null
  executed_at: string | null
  result_target_id: number | null
}

export type MeetingChangeSet = {
  id: number
  project_id: number
  status: 'draft' | 'attached' | 'executed'
  proposals: MeetingChangeProposal[]
}

export type ProposalEditPayload = {
  proposed: Record<string, unknown>
  evidence: string[]
  reason: string
}

export function fetchMeetingChangeSet(meetingId: number): Promise<MeetingChangeSet> {
  return apiGet<MeetingChangeSet>(`/api/meetings/${meetingId}/change-set`)
}

export function updateMeetingChangeProposal(
  meetingId: number,
  proposalId: number,
  payload: ProposalEditPayload,
): Promise<MeetingChangeProposal> {
  return apiPatch<MeetingChangeProposal>(
    `/api/meetings/${meetingId}/change-set/proposals/${proposalId}`,
    payload,
  )
}

export function executeMeetingChangeSet(
  meetingId: number,
  proposalIds: number[],
): Promise<MeetingChangeSet> {
  return apiPost<MeetingChangeSet>(
    `/api/meetings/${meetingId}/change-set/execute`,
    { proposal_ids: proposalIds },
  )
}

export type MeetingSkillReferenceFile = {
  source_id: string
  kind?: string
  filename?: string
}

export type MeetingSkillQuestion = {
  id: number
  code: string
  question: string
  question_kind: 'missing_material' | 'fact_ambiguity' | 'reference_conflict' | 'field_completion'
  blocking: boolean
  required: boolean
  action: 'answer' | 'material_upload'
  answer_mode?: 'single_choice' | 'multiple_choice' | 'free_text' | null
  allow_other: boolean
  allow_omit: boolean
  options: Array<{ value: string; label?: string }>
  evidence: Array<{ source_type: string; source_id: string; locator: string; quote?: string }>
  resolved_at?: string | null
}

export type MeetingSkillRun = {
  id: number
  project_id: number
  skill_name: string
  skill_version: string
  status: 'preflighting' | 'waiting_for_answers' | 'running' | 'ready_for_review'
  current_input_snapshot_id: number
  current_input_snapshot_version: number
  questions: MeetingSkillQuestion[]
  output: Record<string, unknown>
}

export function preflightMeetingSkill(payload: {
  project_id: number
  meeting_type: string
  transcript_text: string
  reference_files: MeetingSkillReferenceFile[]
}): Promise<MeetingSkillRun> {
  return apiPost<MeetingSkillRun>('/api/meetings/skill-runs/preflight', payload)
}

export function addMeetingSkillSnapshot(
  runId: number,
  payload: { transcript_text: string; reference_files: MeetingSkillReferenceFile[] },
): Promise<MeetingSkillRun> {
  return apiPost<MeetingSkillRun>(`/api/meetings/skill-runs/${runId}/snapshots`, payload)
}

export function answerMeetingSkillQuestions(
  runId: number,
  answers: Array<{ question_id: number; value?: unknown; omit?: boolean }>,
): Promise<MeetingSkillRun> {
  return apiPost<MeetingSkillRun>(`/api/meetings/skill-runs/${runId}/answers`, { answers })
}

export function resumeMeetingSkillRun(runId: number): Promise<MeetingSkillRun> {
  return apiPost<MeetingSkillRun>(`/api/meetings/skill-runs/${runId}/resume`)
}

export function analyzeMeeting(
  text: string,
  project_id: number,
  mode?: 'kickoff' | 'progress',
  member_names?: string[],
  skill_run_id?: number,
): Promise<MeetingAnalyzeResult> {
  return apiPost<MeetingAnalyzeResult>('/api/meetings/analyze', { text, project_id, mode, member_names, skill_run_id })
}

export function transcribeAudio(file: File): Promise<{ text: string }> {
  const fd = new FormData()
  fd.append('file', file, file.name)
  return apiUpload<{ text: string }>('/api/transcribe', fd)
}

export function extractMeetingDocumentText(
  projectId: number,
  file: File,
): Promise<{ filename: string; text: string; standard_minutes?: StandardMeetingMinutes }> {
  const fd = new FormData()
  fd.append('file', file, file.name)
  return apiUpload<{ filename: string; text: string; standard_minutes?: StandardMeetingMinutes }>(`/api/meetings/extract-document-text?project_id=${projectId}`, fd)
}

export type StandardMeetingMinutes = {
  is_standard_minutes: boolean
  title?: string
  meeting_date?: string
  location?: string
  meeting_type?: string
  host?: string
  participants?: string
  organizer?: string
  copied_to?: string
  agenda_items?: string[]
  summary?: string
  current_action_items?: Array<Record<string, string>>
  prior_action_items?: Array<Record<string, string>>
}

export function createKickoffRun(projectId: number, transcriptText: string): Promise<{ id: number }> {
  return apiPost(`/api/meetings/kickoff-runs?project_id=${projectId}`, { transcript_text: transcriptText })
}

export type KickoffProposal = {
  id: number
  proposal_type: string
  target_type: string
  target_id: number | null
  before_json: string
  proposed_json: string
  evidence_json: string
  validation_json: string
  review_status: 'pending' | 'approved' | 'returned'
  review_comment: string
}

export type KickoffRun = {
  id: number
  project_id: number
  status: 'draft' | 'submitted' | 'approved'
  snapshot_json: string
  result_json: string
  proposals: KickoffProposal[]
}

export function fetchKickoffRuns(projectId: number): Promise<KickoffRun[]> {
  return apiGet<KickoffRun[]>(`/api/meetings/kickoff-runs?project_id=${projectId}`)
}

export function submitKickoffRun(runId: number, summary: string): Promise<KickoffRun> {
  return apiPost<KickoffRun>(`/api/meetings/kickoff-runs/${runId}/submit`, { summary })
}

export function reviewKickoffProposal(
  runId: number,
  proposalId: number,
  status: 'approved' | 'returned',
  reviewComment = '',
): Promise<KickoffProposal> {
  return apiPatch<KickoffProposal>(`/api/meetings/kickoff-runs/${runId}/proposals/${proposalId}/review`, {
    status,
    review_comment: reviewComment,
  })
}

export function confirmKickoffStart(runId: number): Promise<{ project: unknown; meeting: unknown }> {
  return apiPost(`/api/meetings/kickoff-runs/${runId}/confirm-start`, {})
}

export function createMeeting(payload: {
  project_id: number
  analysis_id?: number | null
  title: string
  meeting_type: string
  meeting_date: string
  location: string
  host: string
  participants: string
  organizer: string
  copied_to: string
  agenda_items_json: string
  prior_action_items_json: string
  source_mode: 'standard_minutes' | 'ai_analysis'
  summary: string
  task_list_json: string
  decision_items_json: string
  risk_items_json: string
  transcript_text: string
  skill_run_id?: number
}): Promise<MeetingItem> {
  return apiPost<MeetingItem>('/api/meetings', payload)
}

export function updateMeeting(
  id: number,
  payload: {
    project_id: number
    title: string
    meeting_type: string
    meeting_date: string
    location: string
    host: string
    participants: string
    organizer: string
    copied_to: string
    agenda_items_json: string
    prior_action_items_json: string
    source_mode: 'standard_minutes' | 'ai_analysis'
    summary: string
    task_list_json: string
    decision_items_json: string
    risk_items_json: string
    transcript_text: string
    skill_run_id?: number
  },
): Promise<MeetingItem> {
  return apiPut<MeetingItem>(`/api/meetings/${id}`, payload)
}
