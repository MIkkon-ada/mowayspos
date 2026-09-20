import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { KeyTaskExecutionWorkspace } from '../components/key-task-workspace/KeyTaskExecutionWorkspace'

type DetailRouteState = { projectId?: number | null }

export function MyTaskDetailPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { taskId: taskIdParam } = useParams()
  const [searchParams] = useSearchParams()
  const taskId = Number(taskIdParam)
  const routeState = location.state as DetailRouteState | null
  const rawProjectId = searchParams.get('projectId') ?? routeState?.projectId
  const projectId = rawProjectId == null ? null : Number(rawProjectId)
  if (!Number.isInteger(taskId) || taskId <= 0) return <main className="p-8"><p className="text-sm text-red-700">关键任务编号无效。</p><button type="button" onClick={() => navigate('/member/tasks')} className="mt-3 rounded border px-3 py-2 text-sm">返回我的任务</button></main>
  const resolvedProjectId = typeof projectId === 'number' && Number.isInteger(projectId) && projectId > 0 ? projectId : null
  return <KeyTaskExecutionWorkspace keyTaskId={taskId} projectId={resolvedProjectId} onBack={() => navigate('/member/tasks')} />
}
