import { useState } from 'react'
import { batchCreatePeople } from '../../api/people'
import type { BatchPersonItem } from '../../api/people'
import { parsePeopleText } from './settingsUtils'
import { SYSTEM_ROLE_OPTIONS } from '../../domain/roles'
import { toast } from '../../utils/toast'

export function PeopleBatchImportModal({ onClose, onDone }: {
  onClose: () => void
  onDone: () => void
}) {
  const [step, setStep] = useState<'input' | 'preview' | 'result'>('input')
  const [raw, setRaw] = useState('')
  const [rows, setRows] = useState<BatchPersonItem[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<{ created: number; skipped: number; skipped_names: string[] } | null>(null)

  function handleParse() {
    const parsed = parsePeopleText(raw)
    if (!parsed.length) return toast.warning('未识别到有效人员，请检查格式')
    setRows(parsed)
    setStep('preview')
  }

  function updateRow(i: number, field: keyof BatchPersonItem, val: string) {
    setRows(prev => prev.map((r, idx) => idx === i ? { ...r, [field]: val } : r))
  }

  function removeRow(i: number) {
    setRows(prev => prev.filter((_, idx) => idx !== i))
  }

  async function handleSubmit() {
    if (!rows.length) return
    setSubmitting(true)
    try {
      const res = await batchCreatePeople(rows)
      setResult(res)
      setStep('result')
      onDone()
    } catch { toast.error('批量导入失败，请重试') }
    finally { setSubmitting(false) }
  }

  const inputCls = 'w-full border border-slate-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-indigo-400'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(15,23,42,0.45)' }}>
      <div className="bg-white rounded-2xl shadow-2xl flex flex-col" style={{ width: 680, maxWidth: '95vw', maxHeight: '88vh' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
          <div>
            <h2 className="text-base font-bold text-slate-800">批量导入人员</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {step === 'input' && '粘贴表格或每行一个姓名'}
              {step === 'preview' && `已解析 ${rows.length} 条，确认后导入`}
              {step === 'result' && '导入完成'}
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
            <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {step === 'input' && (
            <div className="space-y-4">
              <div className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 text-xs text-slate-500 space-y-1">
                <p className="font-semibold text-slate-600">支持两种格式：</p>
                <p>① 从 Excel/WPS 直接复制粘贴表格（含"姓名"列即可，可选列：职务、部门、系统角色、联系方式）</p>
                <p>② 每行输入一个姓名，默认角色为"普通成员"</p>
              </div>
              <textarea
                autoFocus
                rows={12}
                value={raw}
                onChange={e => setRaw(e.target.value)}
                placeholder={"示例（每行一个）：\n张三\n李四\n王五\n\n或粘贴 Excel 表格"}
                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:border-indigo-400"
              />
            </div>
          )}

          {step === 'preview' && (
            <div className="space-y-2">
              <div className="grid text-xs font-semibold text-slate-500 px-2 pb-1" style={{ gridTemplateColumns: '1fr 90px 110px 110px 32px' }}>
                <span>姓名</span><span>职务</span><span>部门</span><span>系统角色</span><span />
              </div>
              {rows.map((row, i) => (
                <div key={i} className="grid items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50" style={{ gridTemplateColumns: '1fr 90px 110px 110px 32px' }}>
                  <input value={row.name} onChange={e => updateRow(i, 'name', e.target.value)} className={inputCls} placeholder="姓名" />
                  <input value={row.role} onChange={e => updateRow(i, 'role', e.target.value)} className={inputCls} placeholder="职务" />
                  <input value={row.department} onChange={e => updateRow(i, 'department', e.target.value)} className={inputCls} placeholder="部门" />
                  <select value={row.system_role} onChange={e => updateRow(i, 'system_role', e.target.value)}
                    className="border border-slate-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-indigo-400 bg-white">
                    {SYSTEM_ROLE_OPTIONS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
                  </select>
                  <button onClick={() => removeRow(i)} className="text-slate-300 hover:text-red-400 flex items-center justify-center">
                    <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
              ))}
            </div>
          )}

          {step === 'result' && result && (
            <div className="py-8 text-center space-y-4">
              <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto" style={{ background: '#F0FDF4' }}>
                <svg style={{ width: 28, height: 28, color: '#16A34A' }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              </div>
              <p className="text-lg font-bold text-slate-800">导入完成</p>
              <div className="flex items-center justify-center gap-6 text-sm">
                <span className="text-emerald-600 font-semibold">✓ 新增 {result.created} 人</span>
                {result.skipped > 0 && <span className="text-slate-400">跳过 {result.skipped} 人（已存在）</span>}
              </div>
              {result.skipped_names.length > 0 && (
                <p className="text-xs text-slate-400">已跳过：{result.skipped_names.join('、')}</p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
          <button onClick={step === 'preview' ? () => setStep('input') : onClose}
            className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm hover:bg-slate-50 cursor-pointer">
            {step === 'preview' ? '返回修改' : '关闭'}
          </button>
          {step === 'input' && (
            <button onClick={handleParse} disabled={!raw.trim()}
              className="px-5 py-2 rounded-lg text-white text-sm font-semibold disabled:opacity-40 cursor-pointer"
              style={{ background: 'linear-gradient(135deg,#4F46E5,#7C3AED)' }}>
              解析预览
            </button>
          )}
          {step === 'preview' && (
            <button onClick={handleSubmit} disabled={submitting || !rows.length}
              className="px-5 py-2 rounded-lg text-white text-sm font-semibold disabled:opacity-40 cursor-pointer"
              style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
              {submitting ? '导入中…' : `确认导入 ${rows.length} 人`}
            </button>
          )}
          {step === 'result' && (
            <button onClick={onClose}
              className="px-5 py-2 rounded-lg text-white text-sm font-semibold cursor-pointer"
              style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
              完成
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
