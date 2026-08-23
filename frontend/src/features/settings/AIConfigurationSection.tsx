import { useEffect, useMemo, useState } from 'react'
import { listAIModels, setAIModelEnabled, testAIModel, type AIModel } from '../../api/aiConfig'
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
      setModels(await listAIModels())
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

      {loading && models.length === 0 ? <p className="py-14 text-center text-sm text-slate-400">正在加载模型…</p> : <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibleModels.map((model) => <AIModelCard key={model.id} model={model} busy={busyModelId === model.id} onEdit={openEditDrawer} onTest={(target) => void runTest(target)} onToggle={(target) => void toggleModel(target)} />)}
        <button type="button" onClick={openAddDrawer} className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 text-sky-700 transition hover:border-sky-400 hover:bg-sky-50"><span className="text-3xl font-light">＋</span><span className="text-sm font-semibold">添加模型</span></button>
      </div>}

      <AIModelDrawer open={drawerOpen} model={editingModel} onClose={() => setDrawerOpen(false)} onSaved={reload} />
    </section>
  )
}
