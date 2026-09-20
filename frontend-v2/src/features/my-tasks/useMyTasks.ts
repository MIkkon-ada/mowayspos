import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchSubtasksByAssignee } from '../../api/subtasks'
import { useProject } from '../../context/ProjectContext'
import { isProjectActive } from '../../domain/projectLifecycleStatus'
import type { Project } from '../../types'
import { mergeMyTaskProjectResults, type MyTaskRow } from './myTasksViewModel'

export function useMyTasks() {
  const { currentUser, projects } = useProject()
  const activeProjects = useMemo(() => projects.filter(isProjectActive), [projects])
  const [rows, setRows] = useState<MyTaskRow[]>([])
  const [successProjects, setSuccessProjects] = useState<Project[]>([])
  const [failedProjects, setFailedProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null)
  const [refreshVersion, setRefreshVersion] = useState(0)

  const refresh = useCallback(() => setRefreshVersion((version) => version + 1), [])

  useEffect(() => {
    let cancelled = false
    const assignee = currentUser?.name?.trim()
    if (!currentUser || !assignee) {
      setRows([])
      setSuccessProjects([])
      setFailedProjects([])
      setLoading(false)
      return () => { cancelled = true }
    }
    if (activeProjects.length === 0) {
      setRows([])
      setSuccessProjects([])
      setFailedProjects([])
      setLastRefreshedAt(new Date())
      setLoading(false)
      return () => { cancelled = true }
    }

    setLoading(true)
    Promise.allSettled(
      activeProjects.map((project) => fetchSubtasksByAssignee(currentUser.name, project.id)),
    ).then((results) => {
      if (cancelled) return
      const merged = mergeMyTaskProjectResults(activeProjects, results, assignee)
      const successIds = new Set(merged.successProjectIds)
      const failedIds = new Set(merged.failedProjectIds)
      setRows(merged.rows)
      setSuccessProjects(activeProjects.filter((project) => successIds.has(project.id)))
      setFailedProjects(activeProjects.filter((project) => failedIds.has(project.id)))
      setLastRefreshedAt(new Date())
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })

    return () => { cancelled = true }
  }, [activeProjects, currentUser?.name, refreshVersion])

  return {
    rows,
    activeProjects,
    successProjects,
    failedProjects,
    loading,
    error: !loading && activeProjects.length > 0 && successProjects.length === 0 && failedProjects.length === activeProjects.length,
    partialError: successProjects.length > 0 && failedProjects.length > 0,
    lastRefreshedAt,
    refresh,
  }
}
