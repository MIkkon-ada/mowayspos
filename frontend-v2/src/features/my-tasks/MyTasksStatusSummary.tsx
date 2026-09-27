import type { MyTaskStatusCounts } from './myTasksViewModel'

const items = [
  { key: '未开始', color: '#94a3b8' },
  { key: '进行中', color: '#2563eb' },
  { key: '延期', color: '#ef4444' },
  { key: '已完成', color: '#10b981' },
  { key: '暂缓', color: '#f59e0b' },
] as const

export function MyTasksStatusSummary({ counts }: { counts: MyTaskStatusCounts }) {
  const total = Math.max(counts.全部, 1)
  let cursor = 0
  const stops = items.map((item) => {
    const start = cursor
    cursor += counts[item.key] / total * 100
    return `${item.color} ${start}% ${cursor}%`
  }).join(', ')
  return (
    <section className="my-task-status-summary">
      <div>
        <p className="my-task-eyebrow">状态概览</p>
        <h2>我的任务分布</h2>
        <p>按当前已加载的全部项目任务统计</p>
      </div>
      <div className="my-task-donut" style={{ background: counts.全部 ? `conic-gradient(${stops})` : '#e2e8f0' }}>
        <div><strong>{counts.全部}</strong><span>任务</span></div>
      </div>
      <ul>
        {items.map((item) => (
          <li key={item.key}><i style={{ background: item.color }} /><span>{item.key}</span><strong>{counts[item.key]}</strong></li>
        ))}
      </ul>
    </section>
  )
}
