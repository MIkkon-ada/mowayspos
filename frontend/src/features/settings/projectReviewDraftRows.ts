import type { Project, ProjectMember, TaskItem } from '../../types'
import type { SubTaskWithParent } from '../../api/subtasks'

export type ProjectReviewDraftRow = {
  objective: string
  keyTask: string
  standard: string
  seq: string
  subTask: string
  assignee: string
  planRange: string
  collaborator: string
  note: string
  isTaskOnly: boolean
}

const DASH = '—'

function legacyHelperAndNote(notes?: string): { helper: string; note: string } {
  const lines = (notes ?? '').split(/\r?\n/)
  let helper = ''
  const kept = lines.filter((line) => {
    const match = line.trim().match(/^协助人[：:]\s*(.+)$/)
    if (!match) return true
    helper ||= match[1].trim()
    return false
  })
  return { helper, note: kept.join('\n').trim() }
}

function keyTaskCollaborator(subtask: SubTaskWithParent, projectMembers: ProjectMember[]): string {
  const nameByPersonId = new Map(
    projectMembers.map((member) => [member.person_id, member.person_name_snapshot.trim()]),
  )
  const collaboratorIds = subtask.collaborator_ids ?? []
  const memberNames = collaboratorIds
    .map((personId) => nameByPersonId.get(personId) ?? '')
    .filter(Boolean)
  if (memberNames.length > 0) return [...new Set(memberNames)].join('、')

  return collaboratorIds.length === 0 ? legacyHelperAndNote(subtask.notes).helper || DASH : DASH
}

export function buildDraftRows(
  tasks: TaskItem[],
  subtasks: SubTaskWithParent[],
  project: Project,
  projectMembers: ProjectMember[],
): ProjectReviewDraftRow[] {
  const objectiveText = project.objectives?.trim()
  const objective = objectiveText ? (objectiveText.length > 10 ? `${objectiveText.slice(0, 10)}…` : objectiveText) : DASH
  const rows: ProjectReviewDraftRow[] = []

  for (const task of tasks) {
    const taskSubtasks = subtasks.filter((subtask) => subtask.parent_task_id === task.id || subtask.task_id === task.id)
    const workstreamGoal = task.key_achievement?.trim() || DASH
    if (taskSubtasks.length === 0) {
      rows.push({
        objective,
        keyTask: task.key_task || DASH,
        standard: workstreamGoal,
        seq: DASH,
        subTask: '关键任务待补充',
        assignee: task.owner?.trim() || DASH,
        planRange: task.plan_time?.trim() || DASH,
        collaborator: DASH,
        note: DASH,
        isTaskOnly: true,
      })
      continue
    }

    taskSubtasks.forEach((subtask, index) => {
      const legacy = legacyHelperAndNote(subtask.notes)
      const completionCriteria = subtask.completion_criteria?.trim() || task.completion_standard?.trim() || ''
      rows.push({
        objective,
        keyTask: task.key_task || DASH,
        standard: workstreamGoal,
        seq: String(index + 1),
        subTask: subtask.title?.trim() || DASH,
        assignee: subtask.assignee?.trim() || DASH,
        planRange: subtask.plan_time?.trim() || task.plan_time?.trim() || DASH,
        collaborator: keyTaskCollaborator(subtask, projectMembers),
        note: [completionCriteria, legacy.note].filter(Boolean).join('；') || DASH,
        isTaskOnly: false,
      })
    })
  }

  return rows
}
