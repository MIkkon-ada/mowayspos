import type { Project } from '../../types'
import type { VoiceTaskContext } from './useVoiceTaskBinding'

type VoiceUpdateTaskBindingBarProps = {
  activeProjects: Project[]
  selectedProject: Project | null
  selectedProjectId: number | null
  selectedSubtaskId: number | null
  selectedTaskContext: VoiceTaskContext | null
  taskOptions: VoiceTaskContext[]
  taskLoading: boolean
  taskError: string | null
  controlsLocked: boolean
  onProjectChange: (projectId: number | null) => void
  onTaskChange: (subtaskId: number | null) => void
  onOpenTaskDetail: () => void
}

export function VoiceUpdateTaskBindingBar({
  activeProjects,
  selectedProject,
  selectedProjectId,
  selectedSubtaskId,
  selectedTaskContext,
  taskOptions,
  taskLoading,
  taskError,
  controlsLocked,
  onProjectChange,
  onTaskChange,
  onOpenTaskDetail,
}: VoiceUpdateTaskBindingBarProps) {
  return (
    <section className="voice-update-binding" aria-label="汇报任务绑定">
      <label className="voice-update-binding-field">
        <span>所属项目 <span aria-hidden="true">*</span></span>
        <select
          value={selectedProjectId ?? ''}
          disabled={controlsLocked}
          onChange={(event) => onProjectChange(event.target.value ? Number(event.target.value) : null)}
        >
          <option value="">请选择所属项目</option>
          {selectedProject && !activeProjects.some((project) => project.id === selectedProject.id) && (
            <option value={selectedProject.id}>{selectedProject.name}（只读）</option>
          )}
          {activeProjects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
      </label>

      <label className="voice-update-binding-field voice-update-binding-task">
        <span>关键任务 <span aria-hidden="true">*</span></span>
        <select
          value={selectedSubtaskId ?? ''}
          disabled={controlsLocked || !selectedProjectId || taskLoading}
          onChange={(event) => onTaskChange(event.target.value ? Number(event.target.value) : null)}
        >
          <option value="">{taskLoading ? '正在加载关键任务…' : '请选择关键任务'}</option>
          {taskOptions.map((task) => (
            <option key={task.id} value={task.id}>{task.title} — {task.parent_key_task || '未标注重点工作'}</option>
          ))}
        </select>
      </label>

      <div className="voice-update-binding-plan">
        <span>计划时间</span>
        <strong>{selectedTaskContext?.plan_time || '—'}</strong>
      </div>

      <button
        type="button"
        className="voice-update-task-detail-button"
        disabled={!selectedSubtaskId || taskLoading}
        onClick={onOpenTaskDetail}
      >
        查看任务详情
      </button>

      {selectedProjectId && !taskLoading && taskOptions.length === 0 && !taskError && (
        <div className="voice-update-binding-message">
          <strong>当前项目暂无可汇报的关键任务</strong>
          <span>请联系项目负责人确认任务派发和责任人配置。</span>
        </div>
      )}
      {taskError && <div className="voice-update-binding-message is-error">{taskError}</div>}
    </section>
  )
}
