import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getProject } from '../api/projects'
import { OwnerSubmitWorkbench } from '../features/settings/OwnerSubmitModal'
import type { Project } from '../types'

export function ProjectOwnerSubmitPage() {
  const { projectId: rawProjectId } = useParams<{ projectId: string }>()
  const projectId = Number(rawProjectId)
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const goToProjectDetail = () => {
    if (Number.isFinite(projectId)) {
      navigate(`/home/projects/${projectId}`)
    } else {
      navigate('/home/projects')
    }
  }

  useEffect(() => {
    if (!Number.isFinite(projectId)) {
      setLoading(false)
      setLoadError('项目编号无效')
      return
    }

    let active = true
    setLoading(true)
    setLoadError(null)
    setProject(null)

    void getProject(projectId)
      .then((nextProject) => {
        if (active) setProject(nextProject)
      })
      .catch(() => {
        if (active) setLoadError('项目不存在或暂时无法加载')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [projectId])

  if (loading || !project) {
    return (
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#F1F5F9] p-4 sm:p-6">
        <div className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col rounded-xl border border-slate-200 bg-white p-6">
          <button
            type="button"
            onClick={goToProjectDetail}
            className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-sky-600 hover:text-sky-700"
          >
            <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
            </svg>
            返回项目详情
          </button>
          <p className="flex flex-1 items-center justify-center text-sm text-slate-400">
            {loading ? '正在加载项目方案…' : loadError}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#F1F5F9] p-4 sm:p-6">
      <div className="mx-auto flex min-h-0 w-full max-w-[1400px] flex-1 flex-col">
        <OwnerSubmitWorkbench
          project={project}
          onClose={goToProjectDetail}
          onSuccess={goToProjectDetail}
        />
      </div>
    </div>
  )
}
