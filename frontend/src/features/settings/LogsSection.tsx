import { useEffect, useState } from 'react'
import { fetchGlobalLogs, type OperationLogItem } from '../../api/logs'
import { fmtLogTime } from './settingsUtils'

const TARGET_TYPE_LABEL: Record<string, string> = {
  task: '任务',
  issue: '问题',
  achievement: '成果',
  project: '项目',
  person: '人员',
  meeting: '会议',
}

const ACTION_COLOR: Record<string, string> = {
  新建任务: '#0369A1',
  修改任务: '#0891B2',
  删除任务: '#DC2626',
  新建问题: '#7C3AED',
  修改问题: '#6D28D9',
  删除问题: '#B91C1C',
  新建成果: '#059669',
  修改成果: '#047857',
  删除成果: '#B45309',
  确认入库: '#0369A1',
  退回: '#DC2626',
}

export function LogsSection() {
  const [logs, setLogs] = useState<OperationLogItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [filterOp, setFilterOp] = useState('')
  const [filterType, setFilterType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const PAGE_SIZE = 50

  function load(p = page) {
    setLoading(true)
    fetchGlobalLogs({ operator: filterOp || undefined, target_type: filterType || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined, page: p, page_size: PAGE_SIZE })
      .then((r) => { setLogs(r.items); setTotal(r.total) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(1); setPage(1) }, [filterOp, filterType, dateFrom, dateTo])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="bg-white rounded-2xl border p-4 flex items-center gap-3 flex-wrap" style={{ borderColor: '#E9EFF6' }}>
        <input value={filterOp} onChange={(e) => setFilterOp(e.target.value)} placeholder="操作人" className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" style={{ width: 120 }} />
        <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:border-blue-400 cursor-pointer">
          <option value="">全部类型</option>
          {Object.entries(TARGET_TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
        <span className="text-xs text-slate-400">至</span>
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
        <button onClick={() => load(page)} className="px-3 py-1.5 rounded-lg text-white text-sm font-semibold hover:opacity-90" style={{ background: '#0369A1' }}>查询</button>
        <span className="ml-auto text-xs text-slate-400">共 {total} 条记录</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border overflow-hidden" style={{ borderColor: '#E9EFF6' }}>
        <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#E8EDF5', borderBottom: '1px solid #C7D2E8' }}>
              {['时间', '操作人', '操作类型', '对象类型', '对象ID', '变更摘要'].map((h) => (
                <th key={h} className="text-left py-2.5 px-4 font-semibold" style={{ color: '#475569' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="py-12 text-center text-slate-400">加载中…</td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan={6} className="py-12 text-center text-slate-400">暂无日志记录</td></tr>
            ) : logs.map((log) => {
              const color = ACTION_COLOR[log.action] ?? '#64748B'
              let summary = ''
              try {
                const before = log.before_json ? JSON.parse(log.before_json) : {}
                const after  = log.after_json  ? JSON.parse(log.after_json)  : {}
                const changed = Object.keys(after).filter((k) => JSON.stringify(before[k]) !== JSON.stringify(after[k]))
                summary = changed.length ? `修改字段：${changed.slice(0, 4).join('、')}${changed.length > 4 ? '…' : ''}` : (log.before_json ? '记录已删除' : '新建记录')
              } catch { summary = '-' }
              return (
                <tr key={log.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td className="py-3 px-4 text-slate-500 whitespace-nowrap">{fmtLogTime(log.created_at)}</td>
                  <td className="py-3 px-4 font-semibold text-slate-700">{log.operator || '-'}</td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold text-white" style={{ background: color }}>{log.action || '-'}</span>
                  </td>
                  <td className="py-3 px-4 text-slate-600">{TARGET_TYPE_LABEL[log.target_type] ?? log.target_type ?? '-'}</td>
                  <td className="py-3 px-4 text-slate-400">#{log.target_id ?? '-'}</td>
                  <td className="py-3 px-4 text-slate-500">{summary}</td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 py-3 border-t" style={{ borderColor: '#E9EFF6' }}>
            <button disabled={page <= 1} onClick={() => { const p = page - 1; setPage(p); load(p) }} className="px-3 py-1 rounded-lg text-xs border border-slate-200 disabled:opacity-40 hover:bg-slate-50 cursor-pointer">上一页</button>
            <span className="text-xs text-slate-500">{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => { const p = page + 1; setPage(p); load(p) }} className="px-3 py-1 rounded-lg text-xs border border-slate-200 disabled:opacity-40 hover:bg-slate-50 cursor-pointer">下一页</button>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── 批量导入人员弹窗 ─────────────────────────────────────────
