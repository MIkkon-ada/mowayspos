/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  listAIModels: vi.fn(),
  listAICapabilityPolicies: vi.fn(),
  saveAICapabilityPolicy: vi.fn(),
  setAIModelEnabled: vi.fn(),
  testAIModel: vi.fn(),
}))

vi.mock('../../api/aiConfig', () => api)
vi.mock('./AIModelCard', () => ({ AIModelCard: () => null }))
vi.mock('./AIModelDrawer', () => ({ AIModelDrawer: () => null }))

import { AIConfigurationSection } from './AIConfigurationSection'

describe('AI capability policy configuration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.listAIModels.mockResolvedValue([{ id: 7, enabled: true, model_type: 'chat', display_name: 'DeepSeek' }])
    api.listAICapabilityPolicies.mockResolvedValue([])
  })
  afterEach(cleanup)

  it('shows every supported capability when no policy has been saved', async () => {
    render(<AIConfigurationSection />)

    expect(await screen.findByText('会议纪要 AI 分析')).toBeTruthy()
    expect(screen.getByText('工作汇报 / 文本任务提取')).toBeTruthy()
    expect(screen.getByText('项目立项方案 AI 分析')).toBeTruthy()
    expect(screen.getByText('关键任务计划 AI 拆解（文字 / 附件）')).toBeTruthy()
    expect(screen.getByText('实时语音转写')).toBeTruthy()
    expect(screen.getAllByText('未配置', { selector: '[data-policy-status]' })).toHaveLength(5)
  })

  it('creates a meeting policy from the selected enabled chat model', async () => {
    api.saveAICapabilityPolicy.mockResolvedValue({})
    render(<AIConfigurationSection />)

    const row = (await screen.findByText('会议纪要 AI 分析')).closest('.rounded-lg')
    expect(row).not.toBeNull()
    fireEvent.change(within(row as HTMLElement).getByRole('combobox'), { target: { value: '7' } })
    fireEvent.click(within(row as HTMLElement).getByRole('button', { name: '保存顺序' }))

    await waitFor(() => expect(api.saveAICapabilityPolicy).toHaveBeenCalledWith('meeting.analysis', {
      primary_model_id: 7,
      fallback_model_ids: [],
      timeout_seconds: 30,
      fallback_timeout_seconds: 25,
      max_attempts: 1,
      enabled: true,
    }))
  })

  it('preserves the configured fallback timeout when saving a policy', async () => {
    api.saveAICapabilityPolicy.mockResolvedValue({})
    api.listAICapabilityPolicies.mockResolvedValue([{
      id: 1,
      capability_key: 'project.init.analysis',
      primary_model_id: 7,
      fallback_model_ids: [],
      timeout_seconds: 200,
      fallback_timeout_seconds: 40,
      max_attempts: 1,
      policy_version: 1,
      enabled: true,
    }])
    render(<AIConfigurationSection />)

    const row = (await screen.findByText('项目立项方案 AI 分析')).closest('.rounded-lg')
    expect(row).not.toBeNull()
    fireEvent.click(within(row as HTMLElement).getByRole('button', { name: '保存顺序' }))

    await waitFor(() => expect(api.saveAICapabilityPolicy).toHaveBeenCalledWith('project.init.analysis', {
      primary_model_id: 7,
      fallback_model_ids: [],
      timeout_seconds: 200,
      fallback_timeout_seconds: 40,
      max_attempts: 1,
      enabled: true,
    }))
  })

  it('shows the routing-console health strip, resource pool, and module route', async () => {
    api.listAIModels.mockResolvedValue([
      { id: 7, enabled: true, model_type: 'chat', display_name: 'DeepSeek', provider: 'deepseek', model_name: 'deepseek-chat', credential_configured: true },
      { id: 8, enabled: true, model_type: 'asr', display_name: '语音模型', provider: 'local', model_name: 'asr-main', credential_configured: true },
    ])
    api.listAICapabilityPolicies.mockResolvedValue([{
      id: 1,
      capability_key: 'meeting.analysis',
      primary_model_id: 7,
      fallback_model_ids: [],
      timeout_seconds: 30,
      fallback_timeout_seconds: 25,
      max_attempts: 1,
      policy_version: 1,
      enabled: true,
    }])

    render(<AIConfigurationSection />)

    expect(await screen.findByText('AI 能力路由台')).toBeTruthy()
    expect(screen.getByText('模块就绪度')).toBeTruthy()
    expect(screen.getByText('模型资源池')).toBeTruthy()
    expect(screen.getByText('会议纪要 AI 分析')).toBeTruthy()
    expect(screen.getAllByText('DeepSeek')).toHaveLength(2)
    expect(screen.getByText('主')).toBeTruthy()
  })

  it('switches from module routes to model load view', async () => {
    render(<AIConfigurationSection />)

    fireEvent.click(await screen.findByRole('button', { name: '按模型 · 资源负载' }))

    expect(screen.getByText('各模型的负载分布')).toBeTruthy()
    expect(screen.getByText('主用于（第一顺位）')).toBeTruthy()
  })

  it('saves a changed route order from the route editor', async () => {
    api.listAIModels.mockResolvedValue([
      { id: 7, enabled: true, model_type: 'chat', display_name: '主模型', provider: 'deepseek', model_name: 'deepseek-chat', credential_configured: true },
      { id: 9, enabled: true, model_type: 'chat', display_name: '备用模型', provider: 'deepseek', model_name: 'deepseek-fallback', credential_configured: true },
    ])
    api.listAICapabilityPolicies.mockResolvedValue([{
      id: 1,
      capability_key: 'meeting.analysis',
      primary_model_id: 7,
      fallback_model_ids: [9],
      timeout_seconds: 30,
      fallback_timeout_seconds: 25,
      max_attempts: 2,
      policy_version: 1,
      enabled: true,
    }])
    api.saveAICapabilityPolicy.mockResolvedValue({})

    render(<AIConfigurationSection />)
    fireEvent.click(await screen.findByRole('button', { name: '编辑链路' }))
    fireEvent.click(screen.getByRole('button', { name: '移除备用模型' }))
    fireEvent.click(screen.getByRole('button', { name: '保存路由' }))

    await waitFor(() => expect(api.saveAICapabilityPolicy).toHaveBeenCalledWith('meeting.analysis', {
      primary_model_id: 7,
      fallback_model_ids: [],
      timeout_seconds: 30,
      fallback_timeout_seconds: 25,
      max_attempts: 1,
      enabled: true,
    }))
  })
})
