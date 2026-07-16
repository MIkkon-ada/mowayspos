import { lazy, Suspense, useEffect, useState } from 'react'
import { Routes, Route, Navigate, useParams, useLocation } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { RequireAuth } from './guards/RequireAuth'
import { RequireProject } from './guards/RequireProject'
import { RequireCapability } from './guards/RequireCapability'
import {
  LoginRoute,
  ProjectsLanding,
  RootRedirect,
  CenterMessage,
} from '../layouts/AppLayout'
import { ProjectLayout } from '../layouts/ProjectLayout'
import { AdminLayout } from '../layouts/AdminLayout'

const DashboardPage = lazy(() => import('../pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const ConfirmPage = lazy(() => import('../pages/ConfirmPage').then((m) => ({ default: m.ConfirmPage })))
const MeetingPage = lazy(() => import('../pages/MeetingPage').then((m) => ({ default: m.MeetingPage })))
const TaskManagementPage = lazy(() => import('../pages/TaskManagementPage').then((m) => ({ default: m.TaskManagementPage })))
const VoiceUpdatePage = lazy(() => import('../pages/VoiceUpdatePage').then((m) => ({ default: m.VoiceUpdatePage })))
const AchievementsPage = lazy(() => import('../pages/AchievementsPage').then((m) => ({ default: m.AchievementsPage })))
const IssuesPage = lazy(() => import('../pages/IssuesPage').then((m) => ({ default: m.IssuesPage })))
const CoordinatePage = lazy(() => import('../pages/CoordinatePage').then((m) => ({ default: m.CoordinatePage })))
const NotificationCenterPage = lazy(() => import('../pages/NotificationCenterPage').then((m) => ({ default: m.NotificationCenterPage })))
const SettingsPage = lazy(() => import('../pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const ProjectAdminPage = lazy(() => import('../pages/ProjectAdminPage').then((m) => ({ default: m.ProjectAdminPage })))
const ProjectMembersPage = lazy(() => import('../pages/ProjectMembersPage').then((m) => ({ default: m.ProjectMembersPage })))
const SetupPage = lazy(() => import('../pages/SetupPage').then((m) => ({ default: m.SetupPage })))
const ChangePasswordPage = lazy(() => import('../pages/ChangePasswordPage').then((m) => ({ default: m.ChangePasswordPage })))
const ProjectManagementPage = lazy(() => import('../pages/ProjectManagementPage').then((m) => ({ default: m.ProjectManagementPage })))
const ProjectArchivePage = lazy(() => import('../pages/ProjectArchivePage').then((m) => ({ default: m.ProjectArchivePage })))
const NoAccessPage = lazy(() => import('../pages/NoAccessPage').then((m) => ({ default: m.NoAccessPage })))
const ClientPortalPlaceholderPage = lazy(() => import('../pages/ClientPortalPlaceholderPage').then((m) => ({ default: m.ClientPortalPlaceholderPage })))
const MemberProjectsPage = lazy(() => import('../pages/MemberProjectsPage').then((m) => ({ default: m.MemberProjectsPage })))
const MemberProjectTasksPage = lazy(() => import('../pages/MemberProjectTasksPage').then((m) => ({ default: m.MemberProjectTasksPage })))

function HomeIndex() {
  const { currentUser, globalUserRoles } = useProject()
  const isPrivileged = !!(
    currentUser?.is_tech_admin ||
    currentUser?.is_ceo ||
    currentUser?.can_view_all ||
    globalUserRoles.some((role) => ['owner', 'coordinator', 'project_ceo'].includes(role))
  )
  return <Navigate to={isPrivileged ? '/home/dashboard' : '/member/projects'} replace />
}

function LegacyProjectRedirect({ to, includeProjectId = false }: { to: string; includeProjectId?: boolean }) {
  const { projectId } = useParams()
  const target = includeProjectId && projectId ? `${to}?projectId=${projectId}` : to
  return <Navigate to={target} replace />
}

function LegacyMemberProjectRedirect() {
  const { projectId } = useParams()
  return <Navigate to={projectId ? `/member/projects/${projectId}` : '/member/projects'} replace />
}

function LegacyCoachDecisionRedirect() {
  const { projectId } = useParams()
  const location = useLocation()

  const params = new URLSearchParams(location.search)
  params.set('view', 'ceo')

  if (projectId) {
    params.set('projectId', projectId)
  }

  return (
    <Navigate
      to={`/work/confirmations?${params.toString()}`}
      replace
    />
  )
}

type SetupState = 'loading' | 'needed' | 'done'

export function AppRoutes() {
  const { authState } = useProject()
  const [setupState, setSetupState] = useState<SetupState>('loading')

  useEffect(() => {
    fetch('/api/setup/status')
      .then((r) => r.json())
      .then((d) => setSetupState(d.initialized ? 'done' : 'needed'))
      .catch(() => setSetupState('done'))
  }, [])

  if (setupState === 'loading' || authState === 'loading') {
    return <CenterMessage title="加载中..." />
  }

  if (setupState === 'needed') {
    return (
      <Suspense fallback={<CenterMessage title="加载中..." />}>
        <Routes>
          <Route path="/setup" element={<SetupPage />} />
          <Route path="*" element={<Navigate to="/setup" replace />} />
        </Routes>
      </Suspense>
    )
  }

  return (
    <Suspense fallback={<CenterMessage title="加载中..." />}>
      <Routes>
        <Route path="/setup" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<LoginRoute />} />
        <Route
          path="/no-access"
          element={
            <RequireAuth>
              <NoAccessPage />
            </RequireAuth>
          }
        />
        <Route
          path="/change-password"
          element={
            <RequireAuth>
              <ChangePasswordPage forced={false} />
            </RequireAuth>
          }
        />
        <Route
          path="/home"
          element={
            <RequireAuth>
              <ProjectLayout />
            </RequireAuth>
          }
        >
          <Route index element={<HomeIndex />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="notifications" element={<NotificationCenterPage />} />
          <Route
            path="settings"
            element={
              <RequireCapability mode="tech_admin">
                <SettingsPage />
              </RequireCapability>
            }
          />
          <Route
            path="projects"
            element={
              <RequireCapability mode="project_view">
                <ProjectManagementPage />
              </RequireCapability>
            }
          />
          <Route
            path="projects/:projectId/archive"
            element={
              <RequireCapability mode="project_view">
                <ProjectArchivePage />
              </RequireCapability>
            }
          />
        </Route>
        <Route
          path="/work"
          element={
            <RequireAuth>
              <ProjectLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/work/tasks" replace />} />
          <Route path="submit" element={<VoiceUpdatePage />} />
          <Route path="confirmations" element={<ConfirmPage />} />
          <Route path="tasks" element={<TaskManagementPage />} />
          <Route path="achievements" element={<AchievementsPage />} />
          <Route path="issues" element={<IssuesPage />} />
          <Route path="org" element={<CoordinatePage />} />
          <Route path="decisions" element={<LegacyCoachDecisionRedirect />} />
          <Route path="meetings" element={<MeetingPage />} />
          <Route path="notifications" element={<NotificationCenterPage />} />
        </Route>
        <Route
          path="/member"
          element={
            <RequireAuth>
              <ProjectLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/member/projects" replace />} />
          <Route path="projects" element={<MemberProjectsPage />} />
          <Route path="projects/:projectId" element={<MemberProjectTasksPage />} />
        </Route>
        <Route
          path="/projects"
          element={
            <RequireAuth>
              <ProjectsLanding />
            </RequireAuth>
          }
        />
        <Route
          path="/project/:projectId"
          element={
            <RequireAuth>
              <RequireProject>
                <ProjectLayout />
              </RequireProject>
            </RequireAuth>
          }
        >
          <Route index element={<LegacyProjectRedirect to="/home/dashboard" />} />
          <Route path="dashboard" element={<LegacyProjectRedirect to="/home/dashboard" />} />
          <Route path="tasks" element={<LegacyProjectRedirect to="/work/tasks" includeProjectId />} />
          <Route path="mytasks" element={<LegacyMemberProjectRedirect />} />
          <Route path="achievements" element={<LegacyProjectRedirect to="/work/achievements" includeProjectId />} />
          <Route path="issues" element={<LegacyProjectRedirect to="/work/issues" includeProjectId />} />
          <Route path="confirm" element={<LegacyProjectRedirect to="/work/confirmations" includeProjectId />} />
          <Route path="coordinate" element={<LegacyProjectRedirect to="/work/org" includeProjectId />} />
          <Route path="org" element={<LegacyProjectRedirect to="/work/org" includeProjectId />} />
          <Route path="decisions" element={<LegacyCoachDecisionRedirect />} />
          <Route path="notifications" element={<LegacyProjectRedirect to="/home/notifications" />} />
          <Route path="submit" element={<LegacyProjectRedirect to="/work/submit" includeProjectId />} />
          <Route path="meeting" element={<MeetingPage />} />
          <Route path="settings" element={<LegacyProjectRedirect to="/home/settings" />} />
        </Route>
        <Route
          path="/client/*"
          element={
            <RequireAuth>
              <RequireCapability mode="client_preview">
                <ClientPortalPlaceholderPage />
              </RequireCapability>
            </RequireAuth>
          }
        />
        <Route
          path="/admin/projects"
          element={
            <RequireAuth>
              <RequireCapability mode="project_admin">
                <AdminLayout />
              </RequireCapability>
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/home/projects" replace />} />
          <Route path=":projectId/members" element={<ProjectMembersPage />} />
        </Route>
        <Route path="*" element={<RootRedirect />} />
      </Routes>
    </Suspense>
  )
}
