import type { TaskStatItem } from '../types'

type TaskStatusChipsProps = {
  stats: TaskStatItem[]
}

const CHIP_CLASS: Record<TaskStatItem['tone'], string> = {
  total: 'chip-notstart',
  notstart: 'chip-notstart',
  progress: 'chip-progress',
  done: 'chip-done',
  delayed: 'chip-delayed',
  paused: 'chip-paused',
}

export function TaskStatusChips({ stats }: TaskStatusChipsProps) {
  return (
    <section className="task-summary-bar">
      <div className="task-status-chips">
        {stats.map((item) => (
          <button key={item.label} type="button" className={`chip ${CHIP_CLASS[item.tone]}`}>
            <div className="chip-icon">
              <span className="chip-dot" />
            </div>
            <div>
              <p>{item.label}</p>
              <strong>{item.value}</strong>
            </div>
          </button>
        ))}
      </div>

      <div className="batch-bar" role="toolbar" aria-label="批量操作">
        <span className="batch-count">已选择 1 项</span>
        <button type="button" className="batch-link">
          清除选择
        </button>
        <span className="batch-divider" />
        <button type="button" className="batch-link">
          批量更新状态
        </button>
        <button type="button" className="batch-link">
          批量调整负责人
        </button>
        <button type="button" className="batch-link">
          批量添加说明
        </button>
      </div>
    </section>
  )
}
