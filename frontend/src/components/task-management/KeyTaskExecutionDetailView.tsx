import type { Project, ProjectMember, TaskItem } from '../../types'
import type { SubTaskDetail, SubTaskPayload } from '../../api/subtasks'
import { KeyTaskExecutionWorkspace } from '../key-task-workspace/KeyTaskExecutionWorkspace'

type Props = {
  project: Project | null
  task: TaskItem | null
  subTask: SubTaskDetail
  projectMembers: ProjectMember[]
  onBack: () => void
  canManageSchedules?: boolean
  canChangeAssignee?: boolean
  onSchedulesChanged?: () => void
  onEditSubTask?: (payload: Omit<SubTaskPayload, 'project_id'>) => Promise<void>
}

/** Both task-management and My Tasks enter the same Key Task execution workspace. */
export function KeyTaskExecutionDetailView({ project, subTask, onBack }: Props) {
  return <KeyTaskExecutionWorkspace keyTaskId={subTask.id} projectId={project?.id ?? null} onBack={onBack} />
}
