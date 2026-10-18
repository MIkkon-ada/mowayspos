import { afterEach, describe, expect, it, vi } from 'vitest'
import { batchCreateTasks, createTask } from './tasks'

afterEach(() => vi.unstubAllGlobals())

describe('task create retry identity', () => {
  it('sends the stable request identity with the create payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () => JSON.stringify({ id: 12, key_task: '重点工作' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createTask({ project_id: 3, key_task: '重点工作' }, 'task-request-0001')

    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body as string)).toMatchObject({
      project_id: 3,
      key_task: '重点工作',
      client_request_id: 'task-request-0001',
    })
  })

  it('sends the batch retry identity with the outline import payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () => JSON.stringify([{ id: 12, key_task: '重点工作' }]),
    })
    vi.stubGlobal('fetch', fetchMock)

    await batchCreateTasks({
      project_id: 3,
      tasks: [{
        key_task: '重点工作', owner: '', coordinator: '', collaborators: '', plan_time: '',
        status: '未开始', key_achievement: '', completion_standard: '',
      }],
    }, 'outline-batch-0001')

    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body as string)).toMatchObject({
      project_id: 3,
      tasks: [{ key_task: '重点工作' }],
      client_request_id: 'outline-batch-0001',
    })
  })
})
