import { useState } from 'react'
import type { Project } from '../../types'
import type { VoiceTaskContext } from './useVoiceTaskBinding'
import type { VoiceReportScope } from './voiceUpdateResultTypes'

type VoiceUpdateTaskBindingBarProps = {
  scope: VoiceReportScope
  activeProjects: Project[]
  selectedProject: Project | null
  selectedProjectId: number | null
  selectedSubtaskId: number | null
  selectedTaskContext: VoiceTaskContext | null
  taskOptions: VoiceTaskContext[]
  taskLoading: boolean
  taskError: string | null
  controlsLocked: boolean
  selectedProjectIsActive: boolean
  onProjectChange: (projectId: number | null) => void
  onScopeChange: (scope: VoiceReportScope) => void
  onTaskChange: (subtaskId: number | null) => void
  onQuickTaskSelect: (projectId: number, subtaskId: number) => void
  onOpenTaskDetail: () => void
}

export function VoiceUpdateTaskBindingBar({
  scope,
  activeProjects,
  selectedProject,
  selectedProjectId,
  selectedSubtaskId,
  selectedTaskContext,
  taskOptions,
  taskLoading,
  taskError,
  controlsLocked,
  selectedProjectIsActive,
  onProjectChange,
  onScopeChange,
  onTaskChange,
  onQuickTaskSelect,
  onOpenTaskDetail,
}: VoiceUpdateTaskBindingBarProps) {
  const [scopeMenuOpen, setScopeMenuOpen] = useState(false)
  const [hoveredScope, setHoveredScope] = useState<VoiceReportScope | null>(null)
  const scopeLabel = scope === 'project' ? '指定项目' : scope === 'task' ? '指定关键任务' : '我的全部工作'

  function chooseScope(nextScope: VoiceReportScope) {
    onScopeChange(nextScope)
    setScopeMenuOpen(false)
    setHoveredScope(null)
  }

  return (
    <section className="voice-update-binding" aria-label="汇报任务绑定">
      <div className="voice-update-scope-menu" onMouseLeave={() => setHoveredScope(null)}>
        <button type="button" className="voice-update-scope-trigger" disabled={controlsLocked} onClick={() => setScopeMenuOpen((open) => !open)} aria-expanded={scopeMenuOpen}>
          <span>{scopeLabel}</span><span className="voice-update-binding-scope-arrow" aria-hidden="true" />
        </button>
        {scopeMenuOpen && <div className="voice-update-scope-options">
          <button type="button" className={scope === 'all' ? 'is-selected' : ''} onClick={() => chooseScope('all')}>我的全部工作</button>
          <div className="voice-update-scope-option-group" onMouseEnter={() => setHoveredScope('project')}>
            <button type="button" className={scope === 'project' ? 'is-selected' : ''} onClick={() => chooseScope('project')}>指定项目 <span>›</span></button>
            {hoveredScope === 'project' && <div className="voice-update-scope-submenu">
              {activeProjects.map((project) => <button type="button" key={project.id} onClick={() => { onScopeChange('project'); onProjectChange(project.id); setScopeMenuOpen(false) }}>{project.name}</button>)}
            </div>}
          </div>
          <div className="voice-update-scope-option-group" onMouseEnter={() => setHoveredScope('task')}>
            <button type="button" className={scope === 'task' ? 'is-selected' : ''} onClick={() => chooseScope('task')}>指定关键任务 <span>›</span></button>
            {hoveredScope === 'task' && <div className="voice-update-scope-submenu voice-update-scope-task-submenu">
              {taskOptions.length ? taskOptions.map((task) => <button type="button" key={task.id} onClick={() => { const projectId = task.project_id ?? task.parent_project_id; if (projectId) onQuickTaskSelect(projectId, task.id); setScopeMenuOpen(false) }}><strong>{task.title}</strong><small>{task.project_name || task.parent_key_task}</small></button>) : <p>暂无可选关键任务</p>}
            </div>}
          </div>
        </div>}
      </div>

      {scope !== 'all' && (
      <label className="voice-update-binding-field">
        <span>所属项目{scope === 'task' && <span aria-hidden="true">*</span>}</span>
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
      )}

      {scope === 'task' && (
      <label className="voice-update-binding-field voice-update-binding-task">
        <span>关键任务 <span aria-hidden="true">*</span></span>
        <select
          value={selectedSubtaskId ?? ''}
          disabled={controlsLocked || !selectedProjectIsActive || !selectedProjectId || taskLoading}
          onChange={(event) => onTaskChange(event.target.value ? Number(event.target.value) : null)}
        >
          <option value="">{!selectedProjectIsActive && selectedProjectId ? '非执行项目不可提交汇报' : taskLoading ? '正在加载关键任务…' : '请选择关键任务'}</option>
          {taskOptions.map((task) => (
            <option key={task.id} value={task.id}>{task.title} — {task.parent_key_task || '未标注重点工作'}</option>
          ))}
        </select>
      </label>
      )}

      {scope !== 'all' && selectedTaskContext && <div className="voice-update-binding-plan">
        <span>计划时间</span>
        <strong>{selectedTaskContext.plan_time}</strong>
      </div>}

      {scope === 'task' && <button
        type="button"
        className="voice-update-task-detail-button"
        disabled={!selectedSubtaskId || taskLoading}
        onClick={onOpenTaskDetail}
      >
        查看任务详情
      </button>}

      {selectedProjectId && selectedProjectIsActive && !taskLoading && taskOptions.length === 0 && !taskError && (
        <div className="voice-update-binding-message">
          <strong>当前项目暂无可汇报的关键任务</strong>
          <span>请联系项目负责人确认任务派发和责任人配置。</span>
        </div>
      )}
      {taskError && <div className="voice-update-binding-message is-error">{taskError}</div>}
    </section>
  )
}
