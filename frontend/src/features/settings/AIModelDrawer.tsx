import { useEffect, useMemo, useState } from 'react'
import {
  createAIModel,
  replaceAIModelCredentials,
  testAIModel,
  updateAIModel,
  type AIModel,
  type AIModelWrite,
} from '../../api/aiConfig'
import {
  AI_MODEL_PROVIDERS,
  buildModelCode,
  providerByValue,
  providersForType,
  type AIModelType,
} from './aiModelProviders'

type Props = {
  open: boolean
  model: AIModel | null
  onClose: () => void
  onSaved: () => Promise<void>
}

const emptyForm: AIModelWrite = {
  code: '',
  display_name: '',
  provider: 'deepseek',
  model_name: '',
  model_type: 'chat',
  base_url: 'https://api.deepseek.com',
  config: {},
  enabled: true,
  source: 'custom',
}

function Chevron() {
  return <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M3.5 6.25 8 10.75l4.5-4.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
}

export function AIModelDrawer({ open, model, onClose, onSaved }: Props) {
  const [form, setForm] = useState<AIModelWrite>({ ...emptyForm })
  const [apiKey, setApiKey] = useState('')
  const [persistedModelId, setPersistedModelId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [message, setMessage] = useState('')
  const [fieldError, setFieldError] = useState('')

  useEffect(() => {
    if (!open) return
    setForm(model ? {
      code: model.code,
      display_name: model.display_name,
      provider: model.provider,
      model_name: model.model_name,
      model_type: model.model_type,
      base_url: model.base_url,
      config: model.config,
      enabled: model.enabled,
      source: model.source,
    } : { ...emptyForm })
    setPersistedModelId(model?.id ?? null)
    setApiKey('')
    setMessage('')
    setFieldError('')
  }, [model, open])

  const providerOptions = useMemo(() => providersForType(form.model_type), [form.model_type])
  const credentialConfigured = Boolean(model?.credential_configured)

  if (!open) return null

  function validate(): boolean {
    if (!form.provider || !form.model_name.trim() || !form.base_url.trim()) {
      setFieldError('请填写服务商、模型名称和 Base URL')
      return false
    }
    try {
      new URL(form.base_url)
    } catch {
      setFieldError('Base URL 格式不正确')
      return false
    }
    setFieldError('')
    return true
  }

  function payload(): AIModelWrite {
    return {
      ...form,
      code: form.code || buildModelCode(form.provider, form.model_name),
      display_name: form.display_name.trim(),
      model_name: form.model_name.trim(),
      base_url: form.base_url.trim(),
    }
  }

  async function ensureModelExists(): Promise<number | null> {
    if (!validate()) return null
    if (persistedModelId !== null) {
      const { code: _code, source: _source, ...updatePayload } = payload()
      await updateAIModel(persistedModelId, updatePayload)
      return persistedModelId
    }
    const created = await createAIModel(payload())
    setPersistedModelId(created.id)
    await onSaved()
    return created.id
  }

  async function handleTest() {
    if (form.model_type !== 'chat') return
    if (!apiKey && !model?.credential_configured) {
      setFieldError('请填写 API Key 后再测试')
      return
    }
    setTesting(true)
    setMessage('')
    try {
      const modelId = await ensureModelExists()
      if (modelId === null) return
      const result = await testAIModel(modelId, apiKey || undefined)
      setMessage(result.message)
    } catch {
      setMessage('连接测试请求未完成，请检查本地服务后重试')
    } finally {
      setTesting(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    setMessage('')
    try {
      const modelId = await ensureModelExists()
      if (modelId === null) return
      if (apiKey) await replaceAIModelCredentials(modelId, apiKey)
      await onSaved()
      onClose()
    } catch (error) {
      await onSaved()
      setMessage(error instanceof Error ? error.message : '保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  function changeModelType(nextType: AIModelType) {
    const options = providersForType(nextType)
    const nextProvider = options.find((option) => option.value === form.provider) ?? options[0]
    setForm({ ...form, model_type: nextType, provider: nextProvider.value, base_url: nextProvider.defaultBaseUrl })
    setMessage('')
    setFieldError('')
  }

  function changeProvider(value: string) {
    const provider = providerByValue(value)
    setForm({ ...form, provider: value, base_url: provider.defaultBaseUrl })
    setMessage('')
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/25" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <aside className="absolute right-0 top-0 flex h-full w-full max-w-[500px] flex-col bg-white shadow-2xl">
        <header className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
          <div><h2 className="text-xl font-bold text-slate-800">{model || persistedModelId ? '编辑模型' : '添加模型'}</h2><p className="mt-1 text-xs text-slate-500">配置系统可调用的 AI 模型</p></div>
          <button type="button" onClick={onClose} aria-label="关闭" className="grid h-8 w-8 place-items-center rounded-lg text-xl text-slate-500 hover:bg-slate-100">×</button>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <section className="border-b border-slate-100 pb-6">
            <h3 className="mb-3 text-sm font-bold text-slate-700">模型类型</h3>
            <div className="grid grid-cols-2 gap-3">
              {([['chat', '对话模型'], ['asr', '语音模型']] as const).map(([value, label]) => <button key={value} type="button" disabled={Boolean(model || persistedModelId)} onClick={() => changeModelType(value)} className={`rounded-xl border px-4 py-3 text-sm font-semibold ${form.model_type === value ? 'border-sky-500 bg-sky-50 text-sky-700' : 'border-slate-200 text-slate-500'} disabled:cursor-not-allowed`}>{label}</button>)}
            </div>
          </section>

          <section className="pt-6">
            <h3 className="mb-4 text-sm font-bold text-slate-700">接入配置</h3>
            <label className="block text-sm font-semibold text-slate-700">服务商 <span className="text-rose-600">*</span><div className="relative mt-2"><select value={form.provider} onChange={(event) => changeProvider(event.target.value)} className="w-full appearance-none rounded-lg border border-slate-200 bg-white px-3 py-2.5 pr-9 text-sm font-normal">{providerOptions.map((provider) => <option key={provider.value} value={provider.value}>{provider.label}</option>)}</select><span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-slate-500"><Chevron /></span></div></label>
            <p className="mt-1.5 text-xs text-slate-400">{providerByValue(form.provider).description}</p>

            <label className="mt-5 block text-sm font-semibold text-slate-700">模型名称 <span className="text-rose-600">*</span><input value={form.model_name} onChange={(event) => setForm({ ...form, model_name: event.target.value })} placeholder="例如：deepseek-v4-pro" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-normal" /></label>
            <label className="mt-5 block text-sm font-semibold text-slate-700">显示名称<input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} placeholder="例如：DeepSeek V4 Pro" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-normal" /></label>
            <label className="mt-5 block text-sm font-semibold text-slate-700">Base URL <span className="text-rose-600">*</span><input value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} placeholder="https://api.example.com/v1" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-normal" /></label>
            <label className="mt-5 block text-sm font-semibold text-slate-700">API Key <span className="text-rose-600">*</span><input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={credentialConfigured ? '已配置 API Key；仅在输入新密钥时替换' : '请输入 API Key'} autoComplete="new-password" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-normal" /></label>
            {credentialConfigured && <p className="mt-1.5 text-xs text-emerald-700">已配置 API Key，保存时不会覆盖现有密钥。</p>}
            {fieldError && <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{fieldError}</p>}
          </section>
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-slate-200 px-6 py-4">
          <div className="flex min-w-0 items-center gap-3"><button type="button" title={form.model_type === 'asr' ? '语音模型暂不支持连接测试' : undefined} disabled={testing || saving || form.model_type !== 'chat'} onClick={() => void handleTest()} className="shrink-0 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-40">{testing ? '测试中…' : '测试连接'}</button>{message && <span className={`truncate text-xs ${message === '连接成功' ? 'text-emerald-700' : 'text-rose-700'}`}>{message}</span>}</div>
          <div className="flex shrink-0 gap-2"><button type="button" onClick={onClose} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600">取消</button><button type="button" disabled={saving || testing} onClick={() => void handleSave()} className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? '保存中…' : '保存'}</button></div>
        </footer>
      </aside>
    </div>
  )
}
