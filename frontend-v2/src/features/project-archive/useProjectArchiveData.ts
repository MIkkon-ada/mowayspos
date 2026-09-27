import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useProject } from '../../context/ProjectContext'
import { getProject, getProjectCloseRequests, getProjectMembers } from '../../api/projects'
import { fetchTasks } from '../../api/tasks'
import { fetchSubtasksByProject, type SubTaskWithParent } from '../../api/subtasks'
import { fetchAchievements } from '../../api/achievements'
import { fetchIssues } from '../../api/issues'
import { fetchMeetings } from '../../api/meetings'
import { fetchUpdates, type UpdateHistoryItem } from '../../api/updates'
import { fetchTargetLogs, type OperationLogItem } from '../../api/logs'
import type { AchievementItem, IssueItem, MeetingItem, Project, ProjectCloseRequest, ProjectMember, TaskItem } from '../../types'

export type ArchiveModuleKey = 'members' | 'tasks' | 'subtasks' | 'achievements' | 'issues' | 'meetings' | 'updates' | 'closeRequests' | 'logs'

export type ProjectArchiveData = {
  project: Project
  members: ProjectMember[]
  tasks: TaskItem[]
  subtasks: SubTaskWithParent[]
  achievements: AchievementItem[]
  issues: IssueItem[]
  meetings: MeetingItem[]
  updates: UpdateHistoryItem[]
  closeRequests: ProjectCloseRequest[]
  logs: OperationLogItem[]
}

type ArchiveDataState = {
  loading: boolean
  data: ProjectArchiveData | null
  projectError: string | null
  moduleErrors: Partial<Record<ArchiveModuleKey, string>>
}

const initialState: ArchiveDataState = { loading: true, data: null, projectError: null, moduleErrors: {} }

function resultValue<T>(result: PromiseSettledResult<T>, key: ArchiveModuleKey, errors: ArchiveDataState['moduleErrors'], fallback: T): T {
  if (result.status === 'fulfilled') return result.value
  errors[key] = '数据暂时无法加载'
  return fallback
}

export function useProjectArchiveData(): ArchiveDataState & { projectId: number | null } {
  const { projectId: rawProjectId } = useParams()
  const { currentUser } = useProject()
  const projectId = useMemo(() => {
    const parsed = Number(rawProjectId)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null
  }, [rawProjectId])
  const [state, setState] = useState<ArchiveDataState>(initialState)

  useEffect(() => {
    let cancelled = false
    if (projectId === null) {
      setState({ loading: false, data: null, projectError: '项目编号无效', moduleErrors: {} })
      return () => { cancelled = true }
    }

    setState(initialState)
    const logsRequest = currentUser?.is_tech_admin
      ? fetchTargetLogs('project', projectId)
      : Promise.resolve([] as OperationLogItem[])

    Promise.allSettled([
      getProject(projectId),
      getProjectMembers(projectId),
      fetchTasks(projectId),
      fetchSubtasksByProject(projectId),
      fetchAchievements(projectId),
      fetchIssues(projectId),
      fetchMeetings(projectId),
      fetchUpdates(projectId),
      getProjectCloseRequests(projectId),
      logsRequest,
    ]).then((results) => {
      if (cancelled) return
      const [projectResult, membersResult, tasksResult, subtasksResult, achievementsResult, issuesResult, meetingsResult, updatesResult, closeRequestsResult, logsResult] = results
      if (projectResult.status === 'rejected') {
        setState({ loading: false, data: null, projectError: '项目档案无法加载，请确认项目存在且当前账号具有查看权限', moduleErrors: {} })
        return
      }
      const moduleErrors: ArchiveDataState['moduleErrors'] = {}
      setState({
        loading: false,
        projectError: null,
        moduleErrors,
        data: {
          project: projectResult.value,
          members: resultValue(membersResult, 'members', moduleErrors, [] as ProjectMember[]),
          tasks: resultValue(tasksResult, 'tasks', moduleErrors, [] as TaskItem[]),
          subtasks: resultValue(subtasksResult, 'subtasks', moduleErrors, [] as SubTaskWithParent[]),
          achievements: resultValue(achievementsResult, 'achievements', moduleErrors, [] as AchievementItem[]),
          issues: resultValue(issuesResult, 'issues', moduleErrors, [] as IssueItem[]),
          meetings: resultValue(meetingsResult, 'meetings', moduleErrors, [] as MeetingItem[]),
          updates: resultValue(updatesResult, 'updates', moduleErrors, [] as UpdateHistoryItem[]),
          closeRequests: resultValue(closeRequestsResult, 'closeRequests', moduleErrors, [] as ProjectCloseRequest[]),
          logs: resultValue(logsResult, 'logs', moduleErrors, [] as OperationLogItem[]),
        },
      })
    })

    return () => { cancelled = true }
  }, [currentUser?.is_tech_admin, projectId])

  return { ...state, projectId }
}
