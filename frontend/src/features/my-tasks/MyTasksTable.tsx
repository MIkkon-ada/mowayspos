import type { MyTaskRow } from './myTasksViewModel'

type Props = {
  rows: MyTaskRow[]
  page: number
  pageSize: number
  total: number
  totalPages: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
  onOpenDetail: (row: MyTaskRow) => void
  onOpenProject: (row: MyTaskRow) => void
  onOpenSubmit: (row: MyTaskRow) => void
}

function PlanTime({ row }: { row: MyTaskRow }) {
  if (row.planStart && row.planEnd) {
    return <><span>{row.planStart}</span><span>{row.planEnd}</span></>
  }
  return <span>{row.planTime || '未填写'}</span>
}

export function MyTasksTable({
  rows, page, pageSize, total, totalPages,
  onPageChange, onPageSizeChange, onOpenDetail, onOpenProject, onOpenSubmit,
}: Props) {
  const pageNumbers = Array.from({ length: totalPages }, (_, index) => index + 1)

  return (
    <section className="my-task-table-card" aria-label="个人任务列表">
      <div className="my-task-table-scroll">
        <table className="my-task-table">
          <thead>
            <tr>
              <th>#</th>
              <th>关键任务</th>
              <th>所属项目 / 重点工作</th>
              <th>计划时间</th>
              <th>状态</th>
              <th>当前进展</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id} tabIndex={0} onClick={() => onOpenDetail(row)} onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') onOpenDetail(row)
              }}>
                <td className="my-task-index">{(page - 1) * pageSize + index + 1}</td>
                <td>
                  <button type="button" className="my-task-title-button" onClick={(event) => {
                    event.stopPropagation()
                    onOpenDetail(row)
                  }}>{row.title}</button>
                  <p className="my-task-criteria">{row.completionCriteria || '未填写完成标准'}</p>
                </td>
                <td>
                  <strong className="my-task-project-name">{row.projectName}</strong>
                  <span className="my-task-workstream-name">{row.workstreamName}</span>
                </td>
                <td><span className="my-task-plan-time"><PlanTime row={row} /></span></td>
                <td><span className={`my-task-status my-task-status--${row.statusTone}`}>{row.status}</span></td>
                <td><p className="my-task-progress">{row.progressText}</p></td>
                <td>
                  <details className="my-task-actions" onClick={(event) => event.stopPropagation()}>
                    <summary aria-label={`打开 ${row.title} 操作菜单`}><span aria-hidden="true">•••</span></summary>
                    <div className="my-task-actions-menu">
                      <button type="button" onClick={() => onOpenProject(row)}><span aria-hidden="true">↗</span>查看工作推进</button>
                      <button type="button" onClick={() => onOpenSubmit(row)}><span aria-hidden="true">▤</span>提交工作汇报</button>
                    </div>
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer className="my-task-pagination">
        <div className="my-task-page-size">
          <span>每页</span>
          <select aria-label="每页任务数" value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
            {[10, 20, 50].map((size) => <option key={size} value={size}>{size}</option>)}
          </select>
          <span>条，共 {total} 条</span>
        </div>
        <nav aria-label="任务分页">
          <button type="button" disabled={page === 1} onClick={() => onPageChange(page - 1)}>上一页</button>
          {pageNumbers.map((number) => (
            <button type="button" key={number} className={number === page ? 'is-current' : ''} aria-current={number === page ? 'page' : undefined} onClick={() => onPageChange(number)}>{number}</button>
          ))}
          <button type="button" disabled={page === totalPages} onClick={() => onPageChange(page + 1)}>下一页</button>
        </nav>
      </footer>
    </section>
  )
}
