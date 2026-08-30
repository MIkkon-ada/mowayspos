import { useEffect, useMemo, useState } from 'react'
import {
  listAICapabilityPolicies,
  listAIModels,
  saveAICapabilityPolicy,
  setAIModelEnabled,
  testAIModel,
  type AICapabilityPolicy,
  type AIModel,
} from '../../api/aiConfig'
import { AIModelCard } from './AIModelCard'
import { AIModelDrawer } from './AIModelDrawer'

type ModelFilter = 'all' | AIModel['model_type']

function friendlyLoadError(error: unknown): string {
  const text = error instanceof Error ? error.message : ''
  if (text.includes('403')) return '仅技术管理员可以管理模型。'
  if (text.includes('503')) return 'AI 配置服务暂不可用，请联系系统管理员。'
  return '模型加载失败，请重试。'
}

export function AIConfigurationSection() {
  const [models, setModels] = useState<AIModel[]>([])
  const [policies, setPolicies] = useState<AICapabilityPolicy[]>([])
  const [policyOrders, setPolicyOrders] = useState<Record<string, number[]>>({})
  const [filter, setFilter] = useState<ModelFilter>('all')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [message, setMessage] = useState('')
  const [busyModelId, setBusyModelId] = useState<number | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editingModel, setEditingModel] = useState<AIModel | null>(null)

  async function reload() {
    setLoading(true)
    try {
      const [nextModels, nextPolicies] = await Promise.all([listAIModels(), listAICapabilityPolicies()])
      setModels(nextModels)
      setPolicies(nextPolicies)
      setPolicyOrders(Object.fromEntries(nextPolicies.map((policy) => [
        policy.capability_key,
        [policy.primary_model_id, ...policy.fallback_model_ids].filter((id): id is number => id !== null),
      ])))
      setLoadError('')
    } catch (error) {
      setLoadError(friendlyLoadError(error))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void reload() }, [])

  const visibleModels = useMemo(
    () => models.filter((model) => filter === 'all' || model.model_type === filter),
    [filter, models],
  )

  const counts = useMemo(() => ({
    all: models.length,
    chat: models.filter((model) => model.model_type === 'chat').length,
    asr: models.filter((model) => model.model_type === 'asr').length,
  }), [models])

  function openAddDrawer() {
    setEditingModel(null)
    setDrawerOpen(true)
    setMessage('')
  }

  function openEditDrawer(model: AIModel) {
    setEditingModel(model)
    setDrawerOpen(true)
    setMessage('')
  }

  async function runTest(model: AIModel) {
    setBusyModelId(model.id)
    setMessage('')
    try {
      const result = await testAIModel(model.id)
      setMessage(result.ok ? `${model.display_name || model.model_name} 连接成功` : '连接失败，请检查模型名称、Base URL 和 API Key')
    } catch {
      setMessage('连接失败，请检查模型名称、Base URL 和 API Key')
    } finally {
      setBusyModelId(null)
    }
  }

  async function toggleModel(model: AIModel) {
    setBusyModelId(model.id)
    setMessage('')
    try {
      await setAIModelEnabled(model.id, !model.enabled)
      await reload()
    } catch {
      setMessage('更新模型状态失败，请重试。')
    } finally {
      setBusyModelId(null)
    }
  }

  function eligibleModels(policy: AICapabilityPolicy) {
    const requiredType = policy.capability_key === 'speech.realtime' ? 'asr' : 'chat'
    return models.filter((model) => model.enabled && model.model_type === requiredType)
  }

  function moveModel(key: string, index: number, direction: -1 | 1) {
    setPolicyOrders((current) => {
      const next = [...(current[key] ?? [])]
      const target = index + direction
      if (target < 0 || target >= next.length) return current
      ;[next[index], next[target]] = [next[target], next[index]]
      return { ...current, [key]: next }
    })
  }

  function addModel(key: string, id: number) {
    setPolicyOrders((current) => ({ ...current, [key]: [...(current[key] ?? []), id] }))
  }

  function removeModel(key: string, id: number) {
    setPolicyOrders((current) => ({ ...current, [key]: (current[key] ?? []).filter((item) => item !== id) }))
  }

  async function savePolicy(policy: AICapabilityPolicy) {
    const ids = policyOrders[policy.capability_key] ?? []
    if (ids.length === 0) {
      setMessage('每个启用的 AI 能力至少需要一个模型。')
      return
    }

    setMessage('')
    try {
      await saveAICapabilityPolicy(policy.capability_key, {
        primary_model_id: ids[0],
        fallback_model_ids: ids.slice(1),
        timeout_seconds: policy.timeout_seconds,
        max_attempts: ids.length,
        enabled: policy.enabled,
      })
      await reload()
      setMessage('模型优先级已保存。')
    } catch {
      setMessage('模型优先级保存失败，请重试。')
    }
  }

  const tabs: Array<{ key: ModelFilter; label: string; count: number }> = [
    { key: 'all', label: '全部', count: counts.all },
    { key: 'chat', label: '对话模型', count: counts.chat },
    { key: 'asr', label: '语音模型', count: counts.asr },
  ]

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div><h2 className="text-xl font-bold text-slate-800">模型管理</h2><p className="mt-1 text-sm text-slate-500">统一配置系统中可使用的 AI 模型。</p></div>
      </header>

      <nav className="mt-6 flex gap-7 border-b border-slate-200" aria-label="模型类型筛选">
        {tabs.map((tab) => <button key={tab.key} type="button" onClick={() => setFilter(tab.key)} className={`border-b-2 px-0.5 pb-3 text-sm ${filter === tab.key ? 'border-sky-700 font-semibold text-sky-700' : 'border-transparent text-slate-500'}`}>{tab.label}（{tab.count}）</button>)}
      </nav>

      {loadError && <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"><span>{loadError}</span><button type="button" onClick={() => void reload()} className="font-semibold underline">重新加载</button></div>}
      {message && <p className={`mt-5 rounded-xl px-4 py-3 text-sm ${message.includes('成功') ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>{message}</p>}

      <section className="mt-6 rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold text-slate-800">AI 能力策略</h3>
        <p className="mt-1 text-xs text-slate-500">技术管理员设置主模型和备用模型的调用顺序。</p>
        <div className="mt-4 space-y-4">
          {policies.map((policy) => {
            const order = policyOrders[policy.capability_key] ?? []
            const available = eligibleModels(policy)
            return <div key={policy.capability_key} className="rounded-lg bg-slate-50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <strong className="text-sm text-slate-700">{policy.capability_key}</strong>
                <button type="button" onClick={() => void savePolicy(policy)} className="rounded-md bg-sky-700 px-3 py-1.5 text-xs font-semibold text-white">保存顺序</button>
              </div>
              <ol className="mt-2 space-y-1">
                {order.map((id, index) => {
                  const model = models.find((item) => item.id === id)
                  return <li key={id} className="flex items-center gap-2 text-xs">
                    <span className="w-4 font-semibold text-slate-400">{index + 1}</span>
                    <span className="flex-1">{model?.display_name || model?.model_name || `模型 ${id}`}</span>
                    <button type="button" disabled={index === 0} onClick={() => moveModel(policy.capability_key, index, -1)}>↑</button>
                    <button type="button" disabled={index === order.length - 1} onClick={() => moveModel(policy.capability_key, index, 1)}>↓</button>
                    <button type="button" onClick={() => removeModel(policy.capability_key, id)}>移除</button>
                  </li>
                })}
              </ol>
              <select
                className="mt-2 rounded border border-slate-200 px-2 py-1 text-xs"
                defaultValue=""
                onChange={(event) => {
                  const id = Number(event.target.value)
                  if (id) addModel(policy.capability_key, id)
                  event.currentTarget.value = ''
                }}
              >
                <option value="">添加模型</option>
                {available.filter((model) => !order.includes(model.id)).map((model) => <option key={model.id} value={model.id}>{model.display_name || model.model_name}</option>)}
              </select>
            </div>
          })}
        </div>
      </section>

      {loading && models.length === 0 ? <p className="py-14 text-center text-sm text-slate-400">正在加载模型…</p> : <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibleModels.map((model) => <AIModelCard key={model.id} model={model} busy={busyModelId === model.id} onEdit={openEditDrawer} onTest={(target) => void runTest(target)} onToggle={(target) => void toggleModel(target)} />)}
        <button type="button" onClick={openAddDrawer} className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 text-sky-700 transition hover:border-sky-400 hover:bg-sky-50"><span className="text-3xl font-light">＋</span><span className="text-sm font-semibold">添加模型</span></button>
      </div>}

      <AIModelDrawer open={drawerOpen} model={editingModel} onClose={() => setDrawerOpen(false)} onSaved={reload} />
    </section>
  )
}
