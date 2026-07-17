import type { ReactNode } from 'react'
import type { SubTaskDetail } from '../../api/subtasks'
import type { VoiceTaskContext } from './useVoiceTaskBinding'

type VoiceUpdateTaskContextDrawerProps = {
  open: boolean
  loading: boolean
  detail: SubTaskDetail | null
  taskContext: VoiceTaskContext | null
  projectName: string
  onClose: () => void
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="voice-update-context-row">
      <span>{label}</span>
      <strong>{children || '—'}</strong>
    </div>
  )
}

export function VoiceUpdateTaskContextDrawer({
  open,
  loading,
  detail,
  taskContext,
  projectName,
  onClose,
}: VoiceUpdateTaskContextDrawerProps) {
  if (!open) return null
  const achievements = detail?.related_achievements ?? []
  const issues = detail?.related_issues ?? []

  return (
    <div className="voice-update-drawer-backdrop" onClick={onClose}>
      <aside className="voice-update-drawer voice-update-task-context-drawer" onClick={(event) => event.stopPropagation()} aria-label="关键任务详情">
        <header className="voice-update-drawer-header">
          <div>
            <p>任务上下文</p>
            <h2>关键任务详情</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭任务详情">×</button>
        </header>
        {loading ? (
          <div className="voice-update-drawer-state">正在加载任务详情…</div>
        ) : (
          <div className="voice-update-drawer-content">
            <DetailRow label="关键任务名称">{detail?.title || taskContext?.title}</DetailRow>
            <DetailRow label="所属项目">{projectName}</DetailRow>
            <DetailRow label="所属重点工作">{taskContext?.parent_key_task || detail?.parent_task?.key_task}</DetailRow>
            <DetailRow label="责任人">{detail?.assignee || taskContext?.assignee}</DetailRow>
            <DetailRow label="计划时间">{detail?.plan_time || taskContext?.plan_time}</DetailRow>
            <DetailRow label="当前状态">{detail?.status || taskContext?.status}</DetailRow>
            <DetailRow label="完成标准">{detail?.completion_criteria || taskContext?.completion_criteria}</DetailRow>
            <DetailRow label="当前进展">{detail?.notes || taskContext?.notes}</DetailRow>

            <section className="voice-update-context-list">
              <h3>关联成果</h3>
              {achievements.length === 0
                ? <p>暂无关联成果</p>
                : achievements.map((item) => <div key={item.id}><strong>{item.name}</strong><span>{item.achievement_type} · {item.status}</span></div>)}
            </section>
            <section className="voice-update-context-list">
              <h3>关联问题</h3>
              {issues.length === 0
                ? <p>暂无关联问题</p>
                : issues.map((item) => <div key={item.id}><strong>{item.description}</strong><span>{item.issue_type} · {item.status}</span></div>)}
            </section>
          </div>
        )}
      </aside>
    </div>
  )
}
