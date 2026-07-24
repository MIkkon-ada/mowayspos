import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getCurrentUser, login as apiLogin, logout as apiLogout } from '../api/auth'
import { getProjectCapabilities, getProjects } from '../api/projects'
import { ApiError } from '../api/client'
import { normalizeLoginError } from '../domain/authFlow'
import type { CurrentUser, Project, ProjectCapabilities } from '../types'

const LS_LAST_PROJECT = 'bowei_last_project_id'

function parseProjectIdFromPath(pathname: string): number | null {
  const m = pathname.match(/^\/project\/(\d+)/)
  return m ? Number(m[1]) : null
}

type ProjectContextValue = {
  authState: 'loading' | 'unauthenticated' | 'authenticated'
  currentUser: CurrentUser | null
  authDefaultRoute: string | null
  projects: Project[]
  currentProjectId: number | null
  currentProject: Project | null
  currentProjectDisplayName: string | null
  currentProjectRoles: string[]
  globalUserRoles: string[]
  currentCapabilities: ProjectCapabilities | null
  loading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  setCurrentProjectId: (id: number | null) => void
  reloadProjects: () => Promise<void>
  refreshUser: () => Promise<void>
  getPreferredProjectId: () => number | null
}

const ProjectContext = createContext<ProjectContextValue | null>(null)

export function ProjectProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()

  const [authState, setAuthState] = useState<'loading' | 'unauthenticated' | 'authenticated'>('loading')
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentCapabilities, setCurrentCapabilities] = useState<ProjectCapabilities | null>(null)

  const currentProjectId = useMemo(
    () => parseProjectIdFromPath(location.pathname),
    [location.pathname],
  )

  useEffect(() => {
    if (currentProjectId !== null) {
      localStorage.setItem(LS_LAST_PROJECT, String(currentProjectId))
    }
  }, [currentProjectId])

  const setCurrentProjectId = useCallback(
    (id: number | null) => {
      if (id === null) {
        navigate('/projects')
      } else {
        localStorage.setItem(LS_LAST_PROJECT, String(id))
        const subPath = location.pathname.split('/').slice(3).join('/')
        navigate(`/project/${id}${subPath ? `/${subPath}` : ''}`)
      }
    },
    [navigate, location.pathname],
  )

  const reloadProjects = useCallback(async () => {
    const list = await getProjects()
    setProjects(list)
  }, [])

  const getPreferredProjectId = useCallback((): number | null => {
    if (projects.length === 0) return null
    if (projects.length === 1) return projects[0].id
    const saved = localStorage.getItem(LS_LAST_PROJECT)
    const savedId = saved ? Number(saved) : NaN
    return projects.find((p) => p.id === savedId)?.id ?? null
  }, [projects])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const user = await getCurrentUser()
        if (cancelled) return
        setCurrentUser(user)
        await reloadProjects()
        if (!cancelled) setAuthState('authenticated')
      } catch (err) {
        if (cancelled) return
        setAuthState('unauthenticated')
        if (!(err instanceof ApiError && err.isUnauthorized)) {
          setError(err instanceof Error ? err.message : '初始化失败')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [reloadProjects])

  const login = useCallback(
    async (username: string, password: string) => {
      setLoading(true)
      setError(null)
      try {
      await apiLogin(username, password)
      const user = await getCurrentUser()
      setCurrentUser(user)
      await reloadProjects()
      setAuthState('authenticated')
      } catch (err) {
        setError(normalizeLoginError(err))
        throw err
      } finally {
        setLoading(false)
      }
    },
    [reloadProjects],
  )

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } catch {
      // 忽略退出接口错误
    }
    setCurrentUser(null)
    setProjects([])
    setError(null)
    setAuthState('unauthenticated')
    navigate('/login')
  }, [navigate])

  const currentProject = useMemo(
    () => projects.find((p) => p.id === currentProjectId) ?? null,
    [projects, currentProjectId],
  )

  const globalUserRoles = useMemo(() => {
    const s = new Set<string>()
    projects.forEach((p) => (p.user_roles ?? []).forEach((r) => s.add(r)))
    return Array.from(s)
  }, [projects])

  useEffect(() => {
    if (currentProjectId === null || authState !== 'authenticated') {
      setCurrentCapabilities(null)
      return
    }
    let cancelled = false
    getProjectCapabilities(currentProjectId)
      .then((caps) => { if (!cancelled) setCurrentCapabilities(caps) })
      .catch(() => { if (!cancelled) setCurrentCapabilities(null) })
    return () => { cancelled = true }
  }, [currentProjectId, authState])

  const refreshUser = useCallback(async () => {
    const user = await getCurrentUser()
    setCurrentUser(user)
  }, [])

  const value: ProjectContextValue = {
    authState,
    currentUser,
    authDefaultRoute: currentUser?.default_route ?? null,
    projects,
    currentProjectId,
    currentProject,
    currentProjectDisplayName: currentProject?.name ?? null,
    currentProjectRoles: currentProject?.user_roles ?? [],
    globalUserRoles,
    currentCapabilities,
    loading,
    error,
    login,
    logout,
    setCurrentProjectId,
    reloadProjects,
    refreshUser,
    getPreferredProjectId,
  }

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
}

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext)
  if (!ctx) {
    throw new Error('useProject 必须在 ProjectProvider 内使用')
  }
  return ctx
}
