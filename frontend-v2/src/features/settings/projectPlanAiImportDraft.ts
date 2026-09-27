import type { BatchImportRow } from '../../api/projects'
import type { ProjectPlanAiPreview, ProjectPlanAiSubTask, ProjectPlanAiTask } from '../../api/projectPlanAiImport'

function clean(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function planTime(start: string, end: string): string {
  if (start && end) return `${start}~${end}`
  return start || end
}

function evidenceNotes(task: ProjectPlanAiTask, subtask: ProjectPlanAiSubTask): string {
  const lines: string[] = []
  if (clean(task.process)) lines.push(`推进流程：${clean(task.process)}`)
  const seen = new Set<string>()
  for (const evidence of [...(task.evidence ?? []), ...(subtask.evidence ?? [])]) {
    const label = `${clean(evidence.file_name)} · ${clean(evidence.location)}`
    if (label !== ' · ' && !seen.has(label)) {
      seen.add(label)
      lines.push(`来源：${label}`)
    }
  }
  return lines.join('\n')
}

export function draftToBatchImportRows(
  draft: ProjectPlanAiPreview,
  projectNameOverride = '',
): BatchImportRow[] {
  const projectName = clean(projectNameOverride) || clean(draft.project_profile?.name)
  if (!projectName) throw new Error('AI 未识别到项目名称，请手动填写')
  if (!draft.tasks.length) throw new Error('AI 未识别到重点工作')

  const rows: BatchImportRow[] = []
  draft.tasks.forEach((task) => {
    const workstream = clean(task.title)
    if (!workstream) throw new Error('存在空的重点工作')
    if (!task.subtasks?.length) throw new Error(`重点工作“${workstream}”缺少关键任务`)
    task.subtasks.forEach((subtask) => {
      const keyTask = clean(subtask.title)
      if (!keyTask) throw new Error(`重点工作“${workstream}”存在空关键任务`)
      const planStart = clean(subtask.plan_start) || clean(task.plan_start)
      const planEnd = clean(subtask.plan_end) || clean(task.plan_end)
      rows.push({
        project_name: projectName,
        project_objective: clean(draft.project_profile?.objectives),
        workstream,
        key_task: keyTask,
        key_achievement: clean(task.goal),
        completion_standard: clean(task.acceptance_criteria) || clean(subtask.evaluation_standard),
        owner: clean(subtask.assignee_name) || clean(task.owner_name),
        collaborators: (subtask.helper_names ?? []).map(clean).filter(Boolean).join('、'),
        plan_time: planTime(planStart, planEnd),
        plan_start: planStart,
        plan_end: planEnd,
        workstream_plan_start: clean(task.plan_start),
        workstream_plan_end: clean(task.plan_end),
        status: clean(subtask.status) || clean(task.status) || '未开始',
        notes: evidenceNotes(task, subtask),
      })
    })
  })
  return rows
}
