import { useCallback, useEffect, useState } from 'react'
import { fetchMyTasks } from '../../api/subtasks'
import { useProject } from '../../context/ProjectContext'
import type { Project } from '../../types'
import { buildMyTaskRows, type MyTaskRow } from './myTasksViewModel'

type MyTaskProject = Pick<Project, 'id' | 'name'>

export function useMyTasks() {
  const { currentUser } = useProject()
  const [rows, setRows] = useState<MyTaskRow[]>([])
  const [activeProjects, setActiveProjects] = useState<MyTaskProject[]>([])
  const [ambiguousAssignmentCount, setAmbiguousAssignmentCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null)
  const [refreshVersion, setRefreshVersion] = useState(0)

  const refresh = useCallback(() => setRefreshVersion((version) => version + 1), [])

  useEffect(() => {
    const handleFocus = () => refresh()
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [refresh])

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()
    setLoading(true)
    setError(false)
    fetchMyTasks(controller.signal).then((result) => {
      if (cancelled) return
      setActiveProjects(result.projects)
      setRows(buildMyTaskRows(result.tasks, result.projects))
      setAmbiguousAssignmentCount(result.ambiguous_assignment_count)
      setLastRefreshedAt(new Date())
    }).catch(() => {
      if (cancelled) return
      setRows([])
      setActiveProjects([])
      setAmbiguousAssignmentCount(0)
      setError(true)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [currentUser?.account_id, currentUser?.person_id, currentUser?.username, refreshVersion])

  return {
    rows,
    activeProjects,
    failedProjects: [] as MyTaskProject[],
    loading,
    error,
    partialError: false,
    ambiguousAssignmentCount,
    lastRefreshedAt,
    refresh,
  }
}
