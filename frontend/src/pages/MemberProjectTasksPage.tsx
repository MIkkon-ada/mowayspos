import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

/**
 * 成员项目任务页 — 已去除 mock 数据。
 * 直接跳转到真实工作推进表，按 projectId 筛选。
 */
export function MemberProjectTasksPage() {
  const navigate = useNavigate()
  const { projectId = '' } = useParams()

  useEffect(() => {
    navigate(`/work/tasks?projectId=${projectId}`, { replace: true })
  }, [navigate, projectId])

  return (
    <div className="flex h-full items-center justify-center bg-slate-100">
      <p className="text-sm text-slate-400">正在跳转到工作推进表…</p>
    </div>
  )
}
