import { afterEach, describe, expect, it, vi } from 'vitest'
import { batchImportProjects, createProject, createProjectCloseRequest } from './projects'

afterEach(() => vi.unstubAllGlobals())

describe('project close request retry identity', () => {
  it('sends the stable request id with close request materials', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () => JSON.stringify({ id: 18, project_id: 3, status: 'pending' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createProjectCloseRequest(3, {
      summary: '项目总结',
      objective_result: '目标结果',
      unfinished_items: [],
      remaining_risks: [],
      handover_plan: '移交完成',
      retrospective: '复盘完成',
    }, 'close-request-0001')

    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body as string)).toMatchObject({
      summary: '项目总结',
      client_request_id: 'close-request-0001',
    })
  })

  it('sends the stable request id with project creation', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () => JSON.stringify({ id: 21, name: '新项目' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createProject({ name: '新项目' }, 'project-create-retry-0001')

    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body as string)).toMatchObject({
      name: '新项目',
      client_request_id: 'project-create-retry-0001',
    })
  })

  it('sends the stable request id with project batch imports', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ ok: true, projects_created: 1 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await batchImportProjects([{ project_name: '项目', key_task: '重点工作' }], 'project-batch-retry-0001')

    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body as string)).toMatchObject({
      rows: [{ project_name: '项目', key_task: '重点工作' }],
      client_request_id: 'project-batch-retry-0001',
    })
  })
})
