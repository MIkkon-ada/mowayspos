import { useEffect, useMemo, useState } from 'react'
import {
  clearAIModelCredential,
  createAIModel,
  listAICapabilityPolicies,
  listAIModels,
  replaceAIModelCredentials,
  saveAICapabilityPolicy,
  setAIModelEnabled,
  testAIModel,
  type AICapabilityPolicy,
  type AIModel,
  type AIModelWrite,
} from '../../api/aiConfig'
import { Card, SectionTitle } from './settingsShared'

const CAPABILITY_LABELS: Record<string, string> = {
  'meeting.analysis': '会议纪要分析',
  'task.extraction': '任务提取',
  'project.init.analysis': '项目初始化分析',
  'speech.realtime': '语音实时转写',
}

const emptyModel: AIModelWrite = {
  code: '', display_name: '', provider: 'deepseek', model_name: '', model_type: 'chat',
  base_url: 'https://api.deepseek.com', config: {}, enabled: true, source: 'custom',
}

function defaultPolicy(capabilityKey: string): AICapabilityPolicy {
  return {
    id: 0,
    capability_key: capabilityKey,
    primary_model_id: null,
    fallback_model_ids: [],
    timeout_seconds: 60,
    max_attempts: 1,
    policy_version: 0,
    enabled: false,
  }
}

export function AIConfigurationSection() {
  const [models, setModels] = useState<AIModel[]>([])
  const [policies, setPolicies] = useState<AICapabilityPolicy[]>([])
  const [typeFilter, setTypeFilter] = useState<'all' | 'chat' | 'asr'>('all')
  const [form, setForm] = useState<AIModelWrite | null>(null)
  const [credentialModelId, setCredentialModelId] = useState<number | null>(null)
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  async function reload() {
    const [nextModels, nextPolicies] = await Promise.all([listAIModels(), listAICapabilityPolicies()])
    setModels(nextModels)
    setPolicies(nextPolicies)
  }

  useEffect(() => { void reload().catch(() => setMessage('加载 AI 能力配置失败')) }, [])

  const visibleModels = useMemo(
    () => models.filter(model => typeFilter === 'all' || model.model_type === typeFilter),
    [models, typeFilter],
  )

  async function saveModel() {
    if (!form) return
    setSaving(true); setMessage('')
    try {
      await createAIModel(form)
      setForm(null)
      await reload()
      setMessage('模型已创建')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '保存模型失败')
    } finally { setSaving(false) }
  }

  async function saveCredential() {
    if (!credentialModelId || !apiKeyInput) return
    setSaving(true); setMessage('')
    try {
      await replaceAIModelCredentials(credentialModelId, apiKeyInput)
      setApiKeyInput(''); setCredentialModelId(null)
      await reload()
      setMessage('凭证已加密保存')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '保存凭证失败')
    } finally { setSaving(false) }
  }

  async function toggleModel(model: AIModel) {
    try {
      await setAIModelEnabled(model.id, !model.enabled)
      await reload()
    } catch (error) { setMessage(error instanceof Error ? error.message : '更新模型失败') }
  }

  async function runModelTest(model: AIModel) {
    try {
      const result = await testAIModel(model.id)
      setMessage(result.ok ? '连接成功' : result.message)
    } catch { setMessage('连接测试失败') }
  }

  async function savePolicy(policy: AICapabilityPolicy, primaryModelId: number | null) {
    try {
      await saveAICapabilityPolicy(policy.capability_key, {
        primary_model_id: primaryModelId,
        fallback_model_ids: policy.fallback_model_ids,
        timeout_seconds: policy.timeout_seconds,
        max_attempts: policy.max_attempts,
        enabled: primaryModelId !== null,
      })
      await reload()
    } catch (error) { setMessage(error instanceof Error ? error.message : '保存策略失败') }
  }

  return (
    <>
      <Card>
        <div className="flex items-center justify-between gap-3">
          <SectionTitle>AI能力配置</SectionTitle>
          <button type="button" onClick={() => setForm({ ...emptyModel })} className="rounded-lg bg-sky-700 px-3 py-1.5 text-xs font-semibold text-white">添加模型</button>
        </div>
        <p className="mb-4 text-xs text-slate-500">模型、凭证和调用策略均由数据库管理；页面只显示“已配置凭证”状态。</p>
        {message && <p className="mb-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">{message}</p>}
        <div className="mb-3 flex gap-2">
          {([['all', '全部'], ['chat', '对话'], ['asr', '语音']] as const).map(([key, label]) => <button key={key} type="button" onClick={() => setTypeFilter(key)} className="rounded-lg border px-3 py-1 text-xs" style={{ borderColor: typeFilter === key ? '#0369A1' : '#E2E8F0', color: typeFilter === key ? '#0369A1' : '#64748B' }}>{label}</button>)}
        </div>
        <div className="space-y-2">
          {visibleModels.map(model => <div key={model.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-100 p-3">
            <div className="min-w-48 flex-1"><p className="text-sm font-semibold text-slate-800">{model.display_name}</p><p className="text-xs text-slate-500">{model.provider} · {model.model_name} · {model.model_type} · v{model.revision}</p></div>
            <span className={`rounded-full px-2 py-0.5 text-xs ${model.credential_configured ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{model.credential_configured ? '已配置凭证' : '未配置凭证'}</span>
            <button type="button" onClick={() => { setCredentialModelId(model.id); setApiKeyInput('') }} className="text-xs text-sky-700">凭证</button>
            <button type="button" onClick={() => void runModelTest(model)} className="text-xs text-sky-700">测试</button>
            <button type="button" onClick={() => void toggleModel(model)} className="text-xs text-slate-600">{model.enabled ? '停用' : '启用'}</button>
          </div>)}
          {!visibleModels.length && <p className="py-3 text-center text-xs text-slate-400">暂无模型</p>}
        </div>
      </Card>

      <Card>
        <SectionTitle>能力策略</SectionTitle>
        <p className="mb-3 text-xs text-slate-500">每项能力绑定一个同类型主模型；尚未绑定的能力保持禁用。</p>
        <div className="space-y-3">
          {Object.keys(CAPABILITY_LABELS).map(key => {
            const policy = policies.find(item => item.capability_key === key) ?? defaultPolicy(key)
            const requiredType = key === 'speech.realtime' ? 'asr' : 'chat'
            const options = models.filter(model => model.enabled && model.model_type === requiredType && model.credential_configured)
            return <div key={key} className="grid gap-2 rounded-xl border border-slate-100 p-3 sm:grid-cols-[1fr_220px]">
              <div><p className="text-sm font-semibold text-slate-800">{CAPABILITY_LABELS[key]}</p><p className="text-xs text-slate-500">{key}{policy?.enabled ? ` · 策略版本 ${policy.policy_version}` : ' · 未启用'}</p></div>
              <select value={policy.primary_model_id ?? ''} onChange={event => void savePolicy(policy, event.target.value ? Number(event.target.value) : null)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs">
                <option value="">未绑定</option>{options.map(model => <option key={model.id} value={model.id}>{model.display_name}</option>)}
              </select>
            </div>
          })}
        </div>
      </Card>

      {form && <Card><SectionTitle>添加模型</SectionTitle><div className="grid gap-2 sm:grid-cols-2">
        {(['code', 'display_name', 'provider', 'model_name', 'base_url'] as const).map(field => <input key={field} value={form[field]} onChange={event => setForm({ ...form, [field]: event.target.value })} placeholder={field} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" />)}
        <select value={form.model_type} onChange={event => setForm({ ...form, model_type: event.target.value as 'chat' | 'asr' })} className="rounded-lg border border-slate-200 px-3 py-2 text-sm"><option value="chat">对话</option><option value="asr">语音</option></select>
      </div><div className="mt-3 flex gap-2"><button type="button" disabled={saving} onClick={() => void saveModel()} className="rounded-lg bg-sky-700 px-3 py-1.5 text-xs font-semibold text-white">保存</button><button type="button" onClick={() => setForm(null)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs">取消</button></div></Card>}

      {credentialModelId && <Card><SectionTitle>更新凭证</SectionTitle><p className="mb-2 text-xs text-slate-500">输入框始终为空；保存后不会回显 API Key。</p><input type="password" value={apiKeyInput} onChange={event => setApiKeyInput(event.target.value)} placeholder="输入 API Key" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" /><div className="mt-3 flex gap-2"><button type="button" disabled={saving || !apiKeyInput} onClick={() => void saveCredential()} className="rounded-lg bg-sky-700 px-3 py-1.5 text-xs font-semibold text-white">加密保存</button><button type="button" onClick={() => void clearAIModelCredential(credentialModelId).then(reload)} className="rounded-lg border border-red-200 px-3 py-1.5 text-xs text-red-600">清除</button><button type="button" onClick={() => setCredentialModelId(null)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs">取消</button></div></Card>}
    </>
  )
}
