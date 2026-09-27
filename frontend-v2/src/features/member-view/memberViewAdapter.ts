/**
 * 成员视图适配器（Project → Workstream → KeyTask 三层映射）
 *
 * 将 MockMemberProject（含 workstreams → tasks）转换为
 * 统一的三层展示结构：MemberProjectCard → MemberWorkstreamGroup → MemberProjectTask。
 */
import {
  MEMBER_VIEW_MOCK_TODAY,
  type MockMemberProject,
  type MockMemberSubmission,
  type MockMemberTask,
  type MockMemberWorkstream,
} from './memberViewMock'

export type MemberActionType =
  | 'submit_progress'
  | 'resubmit_progress'
  | 'supplement_collaboration'
  | 'feedback_problem'
  | 'view_detail'

export type MemberTaskRole = '关键任务承担者' | '协助人'

export type MemberProjectCard = {
  project_id: string
  project_name: string
  project_status: string
  project_description: string
  my_workstream_count: number
  my_owned_key_task_count: number
  my_assisted_key_task_count: number
  my_pending_action_count: number
  latest_reminder: string
  nearest_due_task: string
  nearest_due_label: string
}

export type MemberProjectTask = {
  task_id: string
  task_name: string
  project_id: string
  project_name: string
  workstream_id: string
  workstream_name: string
  my_role: MemberTaskRole
  task_status: string
  latest_progress_summary: string
  pm_confirm_status: string
  due_date: string
  due_label: string
  action_type: MemberActionType
  owner_name?: string
  my_collaboration?: string
  pm_feedback?: string
}

export type MemberWorkstreamGroup = {
  workstream_id: string
  workstream_name: string
  workstream_description: string
  evaluation_criteria: string
  project_id: string
  owned_task_count: number
  assisted_task_count: number
  pending_action_count: number
  tasks: MemberProjectTask[]
}

export type MemberTaskDetail = MemberProjectTask & {
  plan_start_date: string
  plan_end_date: string
  task_description: string
  evaluation_criteria: string
  latest_progress: string
  progress_history: Array<{
    date: string
    summary: string
    status: string
  }>
  pm_feedback?: string
  linked_achievements: string[]
  linked_issues: string[]
  linked_risks: string[]
}

export type MemberSubmissionRecord = {
  submission_id: string
  task_id: string
  task_name: string
  project_id: string
  submitted_at: string
  submitter: string
  content_summary: string
  ai_extract_result: string
  pm_status: string
  pm_feedback?: string
  final_write_targets: string[]
}

export type MemberProjectView = {
  project: MemberProjectCard
  workstreamGroups: MemberWorkstreamGroup[]
  allTasks: MemberProjectTask[]
  ownedTasks: MemberProjectTask[]
  assistedTasks: MemberProjectTask[]
  submissions: MemberSubmissionRecord[]
}

export type MemberProgressDraft = {
  completed: string
  nextPlan: string
  issues: string
  achievements: string
}

function dayStart(date: string) {
  return new Date(`${date}T00:00:00`)
}

export function getMemberDueLabel(dueDate: string, today = MEMBER_VIEW_MOCK_TODAY): string {
  const due = dayStart(dueDate)
  const base = dayStart(today)
  const days = Math.round((due.getTime() - base.getTime()) / 86_400_000)
  if (days < 0) return '已逾期'
  if (days === 0) return '今日截止'
  if (days === 7) return '7天内截止'
  return `${days}天后截止`
}

export function getMemberActionType(task: MockMemberTask): MemberActionType {
  if (task.role === 'assistant') return 'supplement_collaboration'
  if (task.pmStatus === '被退回需修改') return 'resubmit_progress'
  return 'submit_progress'
}

function toRoleLabel(task: MockMemberTask): MemberTaskRole {
  return task.role === 'owner' ? '关键任务承担者' : '协助人'
}

function flattenTasks(project: MockMemberProject) {
  return project.workstreams.flatMap((workstream) => (
    workstream.tasks.map((task) => ({ workstream, task }))
  ))
}

function isPendingTask(task: MockMemberTask) {
  const dueLabel = getMemberDueLabel(task.dueDate)
  return (
    task.pmStatus === '被退回需修改' ||
    task.pmStatus === '待 PM 确认' ||
    dueLabel === '今日截止' ||
    dueLabel === '已逾期'
  )
}

function toProjectTask(
  project: MockMemberProject,
  workstream: MockMemberWorkstream,
  task: MockMemberTask,
): MemberProjectTask {
  return {
    task_id: task.id,
    task_name: task.name,
    project_id: project.id,
    project_name: project.name,
    workstream_id: workstream.id,
    workstream_name: workstream.name,
    my_role: toRoleLabel(task),
    task_status: task.status,
    latest_progress_summary: task.latestProgress,
    pm_confirm_status: task.pmStatus,
    due_date: task.dueDate,
    due_label: getMemberDueLabel(task.dueDate),
    action_type: getMemberActionType(task),
    owner_name: task.ownerName,
    my_collaboration: task.myCollaboration,
    pm_feedback: task.pmFeedback,
  }
}

export function toMemberTaskDetail(
  project: MockMemberProject,
  workstream: MockMemberWorkstream,
  task: MockMemberTask,
): MemberTaskDetail {
  return {
    ...toProjectTask(project, workstream, task),
    plan_start_date: task.planStartDate,
    plan_end_date: task.planEndDate,
    task_description: task.description,
    evaluation_criteria: task.evaluationCriteria,
    latest_progress: task.latestProgress,
    progress_history: task.history,
    pm_feedback: task.pmFeedback,
    linked_achievements: task.linkedAchievements,
    linked_issues: task.linkedIssues,
    linked_risks: task.linkedRisks,
  }
}

export function toMemberProjectCard(project: MockMemberProject): MemberProjectCard {
  const flattened = flattenTasks(project)
  const owned = flattened.filter(({ task }) => task.role === 'owner')
  const assisted = flattened.filter(({ task }) => task.role === 'assistant')
  const nearest = flattened.find(({ task }) => task.id === project.nearestDueTaskId) ?? flattened[0]
  return {
    project_id: project.id,
    project_name: project.name,
    project_status: project.status,
    project_description: project.description,
    my_workstream_count: project.workstreams.length,
    my_owned_key_task_count: owned.length,
    my_assisted_key_task_count: assisted.length,
    my_pending_action_count: flattened.filter(({ task }) => isPendingTask(task)).length,
    latest_reminder: project.latestReminder,
    nearest_due_task: nearest?.task.name ?? '',
    nearest_due_label: nearest ? getMemberDueLabel(nearest.task.dueDate) : '',
  }
}

export function toMemberWorkstreamGroup(
  project: MockMemberProject,
  workstream: MockMemberWorkstream,
  tasks = workstream.tasks,
): MemberWorkstreamGroup {
  return {
    workstream_id: workstream.id,
    workstream_name: workstream.name,
    workstream_description: workstream.description,
    evaluation_criteria: workstream.evaluationCriteria,
    project_id: project.id,
    owned_task_count: tasks.filter((task) => task.role === 'owner').length,
    assisted_task_count: tasks.filter((task) => task.role === 'assistant').length,
    pending_action_count: tasks.filter(isPendingTask).length,
    tasks: tasks.map((task) => toProjectTask(project, workstream, task)),
  }
}

export function toMemberSubmissionRecord(submission: MockMemberSubmission): MemberSubmissionRecord {
  return {
    submission_id: submission.id,
    task_id: submission.taskId,
    task_name: submission.taskName,
    project_id: submission.projectId,
    submitted_at: submission.submittedAt,
    submitter: submission.submitter,
    content_summary: submission.contentSummary,
    ai_extract_result: submission.aiExtractResult,
    pm_status: submission.pmStatus,
    pm_feedback: submission.pmFeedback,
    final_write_targets: submission.finalWriteTargets,
  }
}

export function createMemberProjectCards(projects: MockMemberProject[]): MemberProjectCard[] {
  return projects.map(toMemberProjectCard)
}

export function createMemberProjectView(
  projects: MockMemberProject[],
  projectId: string,
  extraSubmissions: MemberSubmissionRecord[] = [],
): MemberProjectView | null {
  const project = projects.find((item) => item.id === projectId)
  if (!project) return null
  const workstreamGroups = project.workstreams.map((workstream) => toMemberWorkstreamGroup(project, workstream))
  const allTasks = workstreamGroups.flatMap((group) => group.tasks)
  return {
    project: toMemberProjectCard(project),
    workstreamGroups,
    allTasks,
    ownedTasks: allTasks.filter((task) => task.my_role === '关键任务承担者'),
    assistedTasks: allTasks.filter((task) => task.my_role === '协助人'),
    submissions: [
      ...extraSubmissions.filter((record) => record.project_id === projectId),
      ...project.submissions.map(toMemberSubmissionRecord),
    ],
  }
}

export function filterMemberWorkstreamGroups(
  groups: MemberWorkstreamGroup[],
  role?: MemberTaskRole,
): MemberWorkstreamGroup[] {
  if (!role) return groups
  return groups
    .map((group) => {
      const tasks = group.tasks.filter((task) => task.my_role === role)
      return {
        ...group,
        owned_task_count: tasks.filter((task) => task.my_role === '关键任务承担者').length,
        assisted_task_count: tasks.filter((task) => task.my_role === '协助人').length,
        pending_action_count: tasks.filter((task) => (
          task.pm_confirm_status === '被退回需修改' ||
          task.pm_confirm_status === '待 PM 确认' ||
          task.due_label === '今日截止' ||
          task.due_label === '已逾期'
        )).length,
        tasks,
      }
    })
    .filter((group) => group.tasks.length > 0)
}

export function findMemberTaskDetail(
  projects: MockMemberProject[],
  projectId: string,
  taskId: string,
): MemberTaskDetail | null {
  const project = projects.find((item) => item.id === projectId)
  if (!project) return null
  for (const workstream of project.workstreams) {
    const task = workstream.tasks.find((item) => item.id === taskId)
    if (task) return toMemberTaskDetail(project, workstream, task)
  }
  return null
}

export function createMockProgressSubmission(
  task: MemberProjectTask,
  draft: MemberProgressDraft,
): MemberSubmissionRecord {
  return {
    submission_id: `mock-${task.task_id}-${Date.now()}`,
    task_id: task.task_id,
    task_name: task.task_name,
    project_id: task.project_id,
    submitted_at: '刚刚',
    submitter: '我',
    content_summary: draft.completed || '已提交本次进展',
    ai_extract_result: 'AI 已提取为关键任务进展草稿',
    pm_status: '待 PM 确认',
    final_write_targets: [],
  }
}
