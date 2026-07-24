import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { MyTasksTable } from '../features/my-tasks/MyTasksTable'
import { useMyTasks } from '../features/my-tasks/useMyTasks'
import {
  filterMyTaskRows,
  getMyTaskProjectOptions,
  paginateMyTaskRows,
  type MyTaskRow,
  type MyTaskStatusFilter,
} from '../features/my-tasks/myTasksViewModel'
import '../features/my-tasks/myTasks.css'

const FILTERS: MyTaskStatusFilter[] = ['全部', '未开始', '进行中', '延期', '已完成', '暂缓']

function formatRefreshTime(value: Date | null): string {
  if (!value) return '尚未刷新'
  return `更新于 ${value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
}

export function MyTasksPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { rows, activeProjects, failedProjects, loading, error, partialError, lastRefreshedAt, refresh } = useMyTasks()
  const [status, setStatus] = useState<MyTaskStatusFilter>('全部')
  const [projectId, setProjectId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const urlProjectApplied = useRef(false)
  const defaultProjectApplied = useRef(false)

  const projectOptions = useMemo(() => getMyTaskProjectOptions(rows), [rows])
  const filteredRows = useMemo(() => filterMyTaskRows(rows, { status, projectId, search }), [rows, status, projectId, search])
  const pagination = useMemo(() => paginateMyTaskRows(filteredRows, page, pageSize), [filteredRows, page, pageSize])

  useEffect(() => {
    if (loading || urlProjectApplied.current) return
    urlProjectApplied.current = true
    const requested = Number(searchParams.get('projectId'))
    if (Number.isInteger(requested) && projectOptions.some((project) => project.id === requested)) setProjectId(requested)
  }, [loading, projectOptions, searchParams])

  useEffect(() => {
    if (loading || defaultProjectApplied.current || projectId !== null || projectOptions.length === 0) return
    defaultProjectApplied.current = true
    setProjectId(projectOptions[0].id)
  }, [loading, projectOptions, projectId])

  useEffect(() => { setPage(1) }, [status, projectId, search, pageSize])
  useEffect(() => { if (page !== pagination.page) setPage(pagination.page) }, [page, pagination.page])

  const openProject = (row: MyTaskRow) => {
    if (row.projectId !== null) navigate(`/work/tasks?projectId=${row.projectId}`)
  }
  const openSubmit = (row: MyTaskRow) => {
    if (row.projectId !== null) navigate(`/work/submit?projectId=${row.projectId}&subtaskId=${row.id}`)
  }
  const openDetail = (row: MyTaskRow) => {
    const params = new URLSearchParams()
    if (row.projectId !== null) params.set('projectId', String(row.projectId))
    navigate(`/member/tasks/${row.id}${params.size ? `?${params.toString()}` : ''}`)
  }
  const clearFilters = () => {
    setStatus('全部')
    setProjectId(null)
    setSearch('')
  }

  const noActiveProjects = !loading && activeProjects.length === 0
  const noTasks = !loading && !error && activeProjects.length > 0 && rows.length === 0
  const noFilteredTasks = !loading && rows.length > 0 && filteredRows.length === 0
  const onlyProject = projectId !== null ? projectOptions.find((project) => project.id === projectId) : null
  const selectedProjectId = onlyProject?.id ?? activeProjects[0]?.id ?? null
  const openSelectedProject = () => {
    if (selectedProjectId !== null) navigate(`/work/tasks?projectId=${selectedProjectId}`)
    else navigate('/member/projects')
  }

  return (
    <div className="my-tasks-page">
      <header className="my-tasks-header">
        <div>
          <h1>我的任务</h1>
        </div>
        <button type="button" className="my-task-refresh" onClick={refresh} disabled={loading}>
          <span className={loading ? 'is-spinning' : ''} aria-hidden="true">↻</span>
          <span>{formatRefreshTime(lastRefreshedAt)}</span>
        </button>
      </header>

      <main className="my-tasks-content">
        <section className="my-task-toolbar" aria-label="任务筛选">
          <label className="my-task-project-filter">
            <span className="my-task-filter-label">项目</span>
            <select value={projectId ?? ''} onChange={(event) => setProjectId(event.target.value ? Number(event.target.value) : null)}>
              <option value="">全部项目</option>
              {projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          </label>
          <label className="my-task-status-filter">
            <span className="my-task-filter-label">任务状态</span>
            <select value={status} onChange={(event) => setStatus(event.target.value as MyTaskStatusFilter)}>
              {FILTERS.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="my-task-search">
            <span aria-hidden="true">⌕</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索任务、完成标准、项目、重点工作或进展" />
          </label>
        </section>

        {partialError && (
          <div className="my-task-warning" role="status"><span aria-hidden="true">!</span><span>部分项目任务加载失败：{failedProjects.map((project) => project.name).join('、')}。已保留其余项目结果。</span><button type="button" onClick={refresh}>重试</button></div>
        )}

        {loading && <div className="my-task-state"><span className="my-task-state-icon is-spinning" aria-hidden="true">↻</span><h2>正在汇总跨项目任务</h2><p>请稍候，我们正在逐个读取你参与的进行中项目。</p></div>}
        {!loading && error && <div className="my-task-state is-error"><span className="my-task-state-icon" aria-hidden="true">!</span><h2>任务加载失败</h2><p>暂时无法读取你参与项目中的任务，请稍后重试。</p><button type="button" onClick={refresh}>重新加载</button></div>}
        {noActiveProjects && <div className="my-task-state"><span className="my-task-state-icon" aria-hidden="true">◇</span><h2>暂无进行中的项目</h2><p>你当前没有可汇总任务的进行中项目。</p><div className="my-task-empty-actions"><button type="button" onClick={() => navigate('/member/projects')}>创建新任务</button><button type="button" onClick={() => navigate('/member/projects')}>查看项目详情</button></div></div>}
        {noTasks && <div className="my-task-state"><span className="my-task-state-icon" aria-hidden="true">✓</span><h2>暂无分配给你的任务</h2><p>进行中项目已经加载完成，但还没有以当前账号姓名分配给你的关键任务。</p><div className="my-task-empty-actions"><button type="button" onClick={openSelectedProject}>创建新任务</button><button type="button" onClick={openSelectedProject}>查看项目详情</button></div></div>}
        {noFilteredTasks && <div className="my-task-state"><span className="my-task-state-icon" aria-hidden="true">⌕</span><h2>没有符合条件的任务</h2><p>调整项目、状态或搜索关键词后再试。</p><button type="button" onClick={clearFilters}>清除筛选</button></div>}

        {!loading && !error && filteredRows.length > 0 && (
          <MyTasksTable
            rows={pagination.items}
            page={pagination.page}
            pageSize={pagination.pageSize}
            total={pagination.total}
            totalPages={pagination.totalPages}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
            onOpenDetail={openDetail}
            onOpenProject={openProject}
            onOpenSubmit={openSubmit}
          />
        )}
      </main>
    </div>
  )
}
