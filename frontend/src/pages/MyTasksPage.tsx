import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { MyTaskDetailDrawer } from '../features/my-tasks/MyTaskDetailDrawer'
import { MyTasksStatusSummary } from '../features/my-tasks/MyTasksStatusSummary'
import { MyTasksTable } from '../features/my-tasks/MyTasksTable'
import { MyTasksHelpPanel } from '../features/my-tasks/MyTasksHelpPanel'
import { useMyTasks } from '../features/my-tasks/useMyTasks'
import {
  countMyTaskStatuses,
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
  const [selectedRow, setSelectedRow] = useState<MyTaskRow | null>(null)
  const urlProjectApplied = useRef(false)

  const counts = useMemo(() => countMyTaskStatuses(rows), [rows])
  const projectOptions = useMemo(() => getMyTaskProjectOptions(rows), [rows])
  const filteredRows = useMemo(() => filterMyTaskRows(rows, { status, projectId, search }), [rows, status, projectId, search])
  const pagination = useMemo(() => paginateMyTaskRows(filteredRows, page, pageSize), [filteredRows, page, pageSize])

  useEffect(() => {
    if (loading || urlProjectApplied.current) return
    urlProjectApplied.current = true
    const requested = Number(searchParams.get('projectId'))
    if (Number.isInteger(requested) && projectOptions.some((project) => project.id === requested)) setProjectId(requested)
  }, [loading, projectOptions, searchParams])

  useEffect(() => { setPage(1) }, [status, projectId, search, pageSize])
  useEffect(() => { if (page !== pagination.page) setPage(pagination.page) }, [page, pagination.page])

  const openProject = (row: MyTaskRow) => {
    if (row.projectId !== null) navigate(`/work/tasks?projectId=${row.projectId}`)
  }
  const openSubmit = (row: MyTaskRow) => {
    if (row.projectId !== null) navigate(`/work/submit?projectId=${row.projectId}&subtaskId=${row.id}`)
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

  return (
    <div className="my-tasks-page">
      <header className="my-tasks-header">
        <div>
          <p className="my-task-eyebrow">个人工作</p>
          <h1>我的任务</h1>
          <p>汇总你在所有进行中项目里的关键任务，快速掌握优先级与当前进展。</p>
        </div>
        <button type="button" className="my-task-refresh" onClick={refresh} disabled={loading}>
          <span className={loading ? 'is-spinning' : ''} aria-hidden="true">↻</span>
          <span>{formatRefreshTime(lastRefreshedAt)}</span>
        </button>
      </header>

      <main className="my-tasks-content">
        <section className="my-task-toolbar" aria-label="任务筛选">
          <div className="my-task-status-tabs" role="tablist" aria-label="任务状态">
            {FILTERS.map((item) => (
              <button type="button" role="tab" aria-selected={status === item} key={item} className={status === item ? 'is-active' : ''} onClick={() => setStatus(item)}>
                {item}<span>{counts[item]}</span>
              </button>
            ))}
          </div>
          <div className="my-task-filter-row">
            <label className="my-task-project-filter">
              <span>项目</span>
              <select value={projectId ?? ''} onChange={(event) => setProjectId(event.target.value ? Number(event.target.value) : null)}>
                <option value="">全部项目</option>
                {projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
            </label>
            <label className="my-task-search">
              <span aria-hidden="true">⌕</span>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索任务、完成标准、项目、重点工作或进展" />
            </label>
          </div>
        </section>

        {partialError && (
          <div className="my-task-warning" role="status"><span aria-hidden="true">!</span><span>部分项目任务加载失败：{failedProjects.map((project) => project.name).join('、')}。已保留其余项目结果。</span><button type="button" onClick={refresh}>重试</button></div>
        )}

        {loading && <div className="my-task-state"><span className="my-task-state-icon is-spinning" aria-hidden="true">↻</span><h2>正在汇总跨项目任务</h2><p>请稍候，我们正在逐个读取你参与的进行中项目。</p></div>}
        {!loading && error && <div className="my-task-state is-error"><span className="my-task-state-icon" aria-hidden="true">!</span><h2>任务加载失败</h2><p>暂时无法读取你参与项目中的任务，请稍后重试。</p><button type="button" onClick={refresh}>重新加载</button></div>}
        {noActiveProjects && <div className="my-task-state"><span className="my-task-state-icon" aria-hidden="true">◇</span><h2>暂无进行中的项目</h2><p>你当前没有可汇总任务的进行中项目。</p><button type="button" onClick={() => navigate('/member/projects')}>查看我的项目</button></div>}
        {noTasks && <div className="my-task-state"><span className="my-task-state-icon" aria-hidden="true">✓</span><h2>暂无分配给你的任务</h2><p>进行中项目已经加载完成，但还没有以当前账号姓名分配给你的关键任务。</p></div>}
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
            onOpenDetail={setSelectedRow}
            onOpenProject={openProject}
            onOpenSubmit={openSubmit}
          />
        )}

        {!loading && rows.length > 0 && (
          <div className="my-task-bottom-grid">
            <MyTasksStatusSummary counts={counts} />
            <section className="my-task-quick-actions">
              <div><p className="my-task-eyebrow">快捷入口</p><h2>快速操作</h2><p>{onlyProject ? `当前筛选：${onlyProject.name}` : '选择任务后可进入对应项目继续推进'}</p></div>
              <div className="my-task-action-buttons">
                <button type="button" disabled={!onlyProject} onClick={() => onlyProject && navigate(`/work/tasks?projectId=${onlyProject.id}`)}><b aria-hidden="true">▦</b><span>查看工作推进<small>{onlyProject ? onlyProject.name : '请先筛选单个项目'}</small></span></button>
                <button type="button" disabled={!onlyProject} onClick={() => onlyProject && navigate(`/work/submit?projectId=${onlyProject.id}`)}><b aria-hidden="true">↗</b><span>提交工作汇报<small>{onlyProject ? '带入当前项目上下文' : '也可从任务操作菜单进入'}</small></span></button>
              </div>
            </section>
            <MyTasksHelpPanel />
          </div>
        )}
      </main>

      <MyTaskDetailDrawer row={selectedRow} onClose={() => setSelectedRow(null)} onOpenProject={openProject} onOpenSubmit={openSubmit} />
    </div>
  )
}
