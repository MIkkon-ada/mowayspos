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
}

export function analyzeMeeting(
  text: string,
  project_id: number,
  mode?: 'kickoff' | 'progress',
  member_names?: string[],
): Promise<MeetingAnalyzeResult> {
  return apiPost<MeetingAnalyzeResult>('/api/meetings/analyze', { text, project_id, mode, member_names })
}

export function transcribeAudio(file: File): Promise<{ text: string }> {
  const fd = new FormData()
  fd.append('file', file, file.name)
  return apiUpload<{ text: string }>('/api/transcribe', fd)
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

export type TaskCardAction = 'create' | 'update_status' | 'add_note'

type SubTaskCurrentPayload = {
  title: string
  assignee: string
  plan_time: string
  status: string
  completion_criteria: string
  notes: string
}

export type TaskCard =
  | {
      action: 'create'
      parent_task_id: number
      parent_key_task: string
      title: string
      assignee: string
      plan_time: string
      notes: string
      evidence: string
    }
  | {
      action: 'update_status'
      subtask_id: number
      subtask_title: string
      new_status: string
      notes: string
      evidence: string
      current_payload?: SubTaskCurrentPayload
    }
  | {
      action: 'add_note'
      subtask_id: number
      subtask_title: string
      note: string
      evidence: string
      current_payload?: SubTaskCurrentPayload
    }

export function generateTaskCards(
  projectId: number,
  transcriptText: string,
  speakerMap: Record<string, string>,
): Promise<{ task_cards: TaskCard[] }> {
  return apiPost('/api/meetings/generate-task-cards', {
    project_id: projectId,
    transcript_text: transcriptText,
    speaker_map: speakerMap,
  })
}

export function createMeeting(payload: {
  project_id: number
  title: string
  meeting_type: string
  meeting_date: string
  host: string
  participants: string
  summary: string
  task_list_json: string
  decision_items_json: string
  risk_items_json: string
  transcript_text: string
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
    host: string
    participants: string
    summary: string
    task_list_json: string
    decision_items_json: string
    risk_items_json: string
    transcript_text: string
  },
): Promise<MeetingItem> {
  return apiPut<MeetingItem>(`/api/meetings/${id}`, payload)
}
