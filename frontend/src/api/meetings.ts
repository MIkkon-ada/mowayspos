import { apiGet, apiPatch, apiPost, apiUpload } from './client'
import type { MeetingItem } from '../types'

export function fetchMeetings(projectId: number): Promise<MeetingItem[]> {
  return apiGet<MeetingItem[]>(`/api/meetings?project_id=${projectId}`)
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
  decision_items_json: string
  risk_items_json: string
  transcript_text: string
}

export function analyzeMeeting(
  text: string,
  project_id: number,
): Promise<MeetingAnalyzeResult> {
  return apiPost<MeetingAnalyzeResult>('/api/meetings/analyze', { text, project_id })
}

export function transcribeAudio(file: File): Promise<{ text: string }> {
  const fd = new FormData()
  fd.append('file', file, file.name)
  return apiUpload<{ text: string }>('/api/transcribe', fd)
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
