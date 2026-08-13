import type { AIModelWrite } from '../../api/aiConfig'

export type AIModelType = AIModelWrite['model_type']

export type AIModelProviderOption = {
  value: string
  label: string
  description: string
  defaultBaseUrl: string
  modelTypes: AIModelType[]
}

export const AI_MODEL_PROVIDERS: AIModelProviderOption[] = [
  {
    value: 'deepseek',
    label: 'DeepSeek',
    description: 'deepseek-v4-flash、deepseek-v4-pro',
    defaultBaseUrl: 'https://api.deepseek.com',
    modelTypes: ['chat'],
  },
  {
    value: 'dashscope',
    label: '阿里云 DashScope',
    description: '通义千问与 Paraformer 语音模型',
    defaultBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    modelTypes: ['chat', 'asr'],
  },
  {
    value: 'glm',
    label: '智谱 GLM',
    description: 'GLM 系列对话模型',
    defaultBaseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    modelTypes: ['chat'],
  },
  {
    value: 'anthropic',
    label: 'Anthropic',
    description: 'Claude 系列对话模型',
    defaultBaseUrl: 'https://api.anthropic.com',
    modelTypes: ['chat'],
  },
  {
    value: 'generic',
    label: '自定义 OpenAI 兼容接口',
    description: '接入其他兼容 OpenAI API 的模型服务',
    defaultBaseUrl: '',
    modelTypes: ['chat', 'asr'],
  },
]

export function providersForType(modelType: AIModelType): AIModelProviderOption[] {
  return AI_MODEL_PROVIDERS.filter((provider) => provider.modelTypes.includes(modelType))
}

export function providerByValue(value: string): AIModelProviderOption {
  return AI_MODEL_PROVIDERS.find((provider) => provider.value === value) ?? AI_MODEL_PROVIDERS.at(-1)!
}

export function buildModelCode(provider: string, modelName: string): string {
  const normalized = `${provider}-${modelName}`
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return normalized || 'custom-model'
}
