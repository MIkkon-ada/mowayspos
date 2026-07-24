import { useEffect, useState } from 'react'
import { getLLMConfigs, saveLLMConfig, type LLMProviderConfig } from '../../api/llmConfig'
import { Card, SectionTitle } from './settingsShared'

export function LLMConfigSection() {
  const [configs, setConfigs] = useState<LLMProviderConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ api_key: '', base_url: '', model: '' })
  const [saving, setSaving] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getLLMConfigs().then(setConfigs).catch(() => setConfigs([])).finally(() => setLoading(false))
  }, [])

  async function handleToggle(cfg: LLMProviderConfig) {
    setSaving(cfg.provider)
    setError('')
    try {
      await saveLLMConfig(cfg.provider, { enabled: !cfg.enabled, model: cfg.model, base_url: cfg.base_url })
      setConfigs(prev => prev.map(c => c.provider === cfg.provider ? { ...c, enabled: !cfg.enabled } : c))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '操作失败')
    } finally { setSaving(null) }
  }

  function startEdit(cfg: LLMProviderConfig) {
    setEditingProvider(cfg.provider)
    setEditForm({ api_key: '', base_url: cfg.base_url, model: cfg.model })
    setError('')
  }

  async function handleSaveEdit(cfg: LLMProviderConfig) {
    setSaving(cfg.provider)
    setError('')
    try {
      await saveLLMConfig(cfg.provider, {
        enabled: cfg.enabled,
        model: editForm.model || cfg.default_model,
        base_url: editForm.base_url || cfg.default_base_url,
        ...(editForm.api_key ? { api_key: editForm.api_key } : {}),
      })
      setConfigs(prev => prev.map(c => c.provider === cfg.provider
        ? { ...c, model: editForm.model || c.default_model, base_url: editForm.base_url || c.default_base_url, api_key_set: editForm.api_key ? true : c.api_key_set }
        : c))
      setEditingProvider(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally { setSaving(null) }
  }

  return (
    <Card>
      <SectionTitle>大模型配置</SectionTitle>
      {error && (
        <div className="mb-3 px-3 py-2 rounded-lg text-xs font-medium" style={{ background: '#FEF2F2', color: '#DC2626', border: '1px solid #FECACA' }}>
          {error}
        </div>
      )}
      {loading
        ? <p className="text-sm text-slate-400 py-4 text-center">加载中…</p>
        : configs.map(cfg => (
          <div key={cfg.provider} style={{ borderBottom: '1px solid #F1F5F9', paddingBottom: 16, marginBottom: 16 }}>
            <div className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-800">{cfg.display_name}</span>
                  {cfg.enabled && (
                    <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: '#D1FAE5', color: '#065F46' }}>启用中</span>
                  )}
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  模型：<span className="font-medium text-slate-600">{cfg.model}</span>
                  {' · '}API Key：{cfg.api_key_set ? <span className="text-emerald-600">已配置</span> : <span className="text-red-500">未配置</span>}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button type="button" onClick={() => startEdit(cfg)}
                  className="cursor-pointer px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 text-xs font-semibold hover:bg-slate-50 transition-colors">
                  配置
                </button>
                <button type="button" onClick={() => handleToggle(cfg)} disabled={saving === cfg.provider}
                  className="cursor-pointer px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
                  style={cfg.enabled
                    ? { background: '#FEF2F2', color: '#DC2626', border: '1px solid #FECACA' }
                    : { background: '#EFF6FF', color: '#1D4ED8', border: '1px solid #BFDBFE' }}>
                  {saving === cfg.provider ? '处理中…' : cfg.enabled ? '停用' : '启用'}
                </button>
              </div>
            </div>

            {editingProvider === cfg.provider && (
              <div className="mt-3 p-3 rounded-xl space-y-2" style={{ background: '#F8FAFC', border: '1px solid #E2E8F0' }}>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-xs text-slate-500 mb-1">模型名称</p>
                    <input value={editForm.model} onChange={e => setEditForm(f => ({ ...f, model: e.target.value }))}
                      placeholder={cfg.default_model}
                      className="w-full border border-slate-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-400/30" />
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 mb-1">API Key {cfg.api_key_set ? '（已设置，留空保留）' : '（未设置）'}</p>
                    <input type="password" value={editForm.api_key} onChange={e => setEditForm(f => ({ ...f, api_key: e.target.value }))}
                      placeholder={cfg.api_key_set ? '••••••••' : '输入 API Key'}
                      className="w-full border border-slate-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-400/30" />
                  </div>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Base URL</p>
                  <input value={editForm.base_url} onChange={e => setEditForm(f => ({ ...f, base_url: e.target.value }))}
                    placeholder={cfg.default_base_url}
                    className="w-full border border-slate-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-400/30" />
                </div>
                <div className="flex gap-2 pt-1">
                  <button type="button" onClick={() => handleSaveEdit(cfg)} disabled={saving === cfg.provider}
                    className="cursor-pointer px-3 py-1.5 rounded-lg text-white text-xs font-semibold disabled:opacity-50" style={{ background: '#0369A1' }}>
                    {saving === cfg.provider ? '保存中…' : '保存'}
                  </button>
                  <button type="button" onClick={() => setEditingProvider(null)}
                    className="cursor-pointer px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-xs">取消</button>
                </div>
              </div>
            )}
          </div>
        ))
      }
    </Card>
  )
}

