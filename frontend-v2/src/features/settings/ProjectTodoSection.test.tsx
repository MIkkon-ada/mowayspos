import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ProjectTodoSection, type ProjectTodoViewModel } from './ProjectTodoSection'

const project = {
  id: 1,
  name: '测试项目',
  status: 'draft',
} as ProjectTodoViewModel['todo']['project']

function renderChecks(
  materialChecks: ProjectTodoViewModel['todo']['materialChecks'],
  secondaryAction?: ProjectTodoViewModel['todo']['secondaryAction'],
  secondaryActionLabel?: string,
) {
  const item = {
    todo: {
      project,
      action: 'edit',
      actionLabel: '继续完善项目',
      secondaryAction,
      secondaryActionLabel,
      title: '项目待完善',
      description: '请补充项目资料。',
      materialChecks,
    },
    ownerName: '负责人',
    coachName: 'Coach',
  } as ProjectTodoViewModel

  return renderToStaticMarkup(
    <ProjectTodoSection items={[item]} totalCount={1} onAction={() => undefined} />,
  )
}

describe('ProjectTodoSection material summaries', () => {
  it('shows real incomplete labels without blank labels', () => {
    const html = renderChecks([
      { key: 'objectives', label: '   ', complete: false },
      { key: 'period', label: '项目周期', complete: false },
    ])

    expect(html).toContain('待补充：项目周期')
    expect(html).not.toContain('待补充：、')
  })

  it('falls back to the incomplete count when all incomplete labels are blank', () => {
    const html = renderChecks([{ key: 'objectives', label: '  ', complete: false }])

    expect(html).toContain('尚有 1 项信息待完善')
    expect(html).not.toContain('待补充：')
  })

  it('does not render a completed summary for blank completed labels', () => {
    const html = renderChecks([{ key: 'objectives', label: ' ', complete: true }])

    expect(html).not.toContain('已完成 ')
  })

  it('shows complete state and nonblank completed labels', () => {
    const html = renderChecks([{ key: 'objectives', label: '项目目标', complete: true }])

    expect(html).toContain('项目计划已填写完整')
    expect(html).toContain('已完成 项目目标')
  })

  it('keeps the secondary edit action beside the primary dispatch action', () => {
    const html = renderChecks([], 'edit', '修改基础信息')

    expect(html).toContain('修改基础信息')
    expect(html).toContain('继续完善项目')
  })
})
