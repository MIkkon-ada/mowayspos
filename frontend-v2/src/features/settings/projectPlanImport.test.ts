import { describe, expect, it } from 'vitest'
import { parseProjectPlanImportText, toBatchImportRows } from './projectPlanImport'

describe('parseProjectPlanImportText', () => {
  it('parses the exported work plan with a title row and carries merged values forward', () => {
    const text = [
      '模拟项目目标与重点工作计划表',
      '目标\t重点工作\t评价标准\t序号\t关键任务\t责任人\t计划开始时间\t计划结束时间\t协同人\t完成情况\t备注\t项目经理\t重点工作计划开始时间\t重点工作计划结束时间',
      '目标A\t重点工作A\t标准A\t1\t任务A\t负责人A\t2026-09-15\t2026-09-20\t协同人A\t未开始\t备注A\t项目经理\t2026-09-15\t2026-09-20',
      '\t\t标准A\t2\t任务B\t负责人B\t2026-09-21\t2026-09-25\t协同人B\t进行中\t备注B\t项目经理\t\t',
    ].join('\n')

    const result = parseProjectPlanImportText(text)

    expect(result.errors).toEqual([])
    expect(result.rows).toHaveLength(2)
    expect(result.rows[0]).toMatchObject({
      project_name: '模拟项目',
      work_area: '重点工作A',
      key_task: '任务A',
      owner: '负责人A',
      plan_time: '2026-09-15~2026-09-20',
    })
    expect(result.rows[1]).toMatchObject({
      project_name: '模拟项目',
      work_area: '重点工作A',
      key_task: '任务B',
      plan_time: '2026-09-21~2026-09-25',
    })
  })

  it('keeps the legacy simplified import format working', () => {
    const result = parseProjectPlanImportText([
      '项目\t关键任务\t负责人\t统筹人\t计划时间\t当前状态\t问题',
      '旧项目\t旧任务\t负责人A\t统筹人A\t2026-09\t未开始\t无',
    ].join('\n'))

    expect(result.errors).toEqual([])
    expect(result.rows).toEqual([expect.objectContaining({
      project_name: '旧项目',
      work_area: '旧任务',
      key_task: '旧任务',
      plan_time: '2026-09',
    })])
  })

  it('converts the page-safe normalized row to the backend import contract', () => {
    const result = parseProjectPlanImportText([
      '项目\t重点工作\t关键任务',
      '项目A\t工作区A\t任务A',
    ].join('\n'))

    expect(toBatchImportRows(result.rows)[0]).toMatchObject({ workstream: '工作区A' })
  })

  it('reports missing required fields instead of silently dropping rows', () => {
    const missingProject = parseProjectPlanImportText([
      '项目\t重点工作\t关键任务',
      '\t重点工作A\t任务A',
    ].join('\n'))
    const missingWorkstream = parseProjectPlanImportText([
      '项目\t重点工作\t关键任务',
      '项目A\t\t任务B',
    ].join('\n'))
    const missingKeyTask = parseProjectPlanImportText([
      '项目\t重点工作\t关键任务',
      '项目A\t重点工作A\t',
    ].join('\n'))

    expect(missingProject.rows).toEqual([])
    expect(missingWorkstream.rows).toEqual([])
    expect(missingKeyTask.rows).toEqual([])
    expect(missingProject.errors.map((item) => item.row)).toEqual([2])
    expect(missingWorkstream.errors.map((item) => item.row)).toEqual([2])
    expect(missingKeyTask.errors.map((item) => item.row)).toEqual([2])
  })
})
