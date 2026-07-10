import type { VoiceUpdateEditableFieldsSectionProps } from './voiceUpdateResultTypes'
import { useVoiceUpdateEditableFields } from './useVoiceUpdateEditableFields'

export function VoiceUpdateEditableFieldsSection({
  editValues,
  editingField,
  setEditingField,
  setEditValues,
  proposedSubtasks,
  setProposedSubtasks,
  currentUserName,
  taskReports,
}: VoiceUpdateEditableFieldsSectionProps) {
  const editable = useVoiceUpdateEditableFields({ editValues, editingField, setEditingField, setEditValues })
  if (!editable) return null

  const { s, setField, arrToText, arrNames, isEditing, EditIcon, confidence, confPct, confColor, confLabel, statusColor, COORD_CHIP_COLORS } = editable

  return (
    <div className="space-y-0">
      {taskReports.length === 0 && (
        <>
          <div className="flex items-start py-3 border-b" style={{ borderColor: '#F1F5F9' }}>
            <span className="w-16 flex-shrink-0 text-xs font-semibold text-slate-400 pt-0.5">完成事项</span>
            {isEditing('completed_items') ? (
              <textarea
                autoFocus
                rows={3}
                className="flex-1 text-sm border border-blue-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-400/30 resize-none"
                defaultValue={arrToText(s.completed_items)}
                onBlur={(e) => { setField('completed_items', e.target.value.split('\n').filter(Boolean)); setEditingField(null) }}
              />
            ) : (
              <span className="flex-1 text-sm text-slate-700 leading-relaxed">{arrNames(s.completed_items).join('、') || '—'}</span>
            )}
            <EditIcon field="completed_items" />
          </div>

          <div className="flex items-start py-3 border-b" style={{ borderColor: '#F1F5F9' }}>
            <span className="w-16 flex-shrink-0 text-xs font-semibold text-slate-400 pt-0.5">成果</span>
            {isEditing('achievements') ? (
              <textarea
                autoFocus
                rows={3}
                className="flex-1 text-sm border border-blue-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-400/30 resize-none"
                defaultValue={arrToText(s.achievements)}
                onBlur={(e) => { setField('achievements', e.target.value.split('\n').filter(Boolean).map((name) => ({ name }))); setEditingField(null) }}
              />
            ) : (
              <span className="flex-1 text-sm font-semibold leading-relaxed" style={{ color: '#059669' }}>
                {arrNames(s.achievements).length > 0 ? `↑ ${arrNames(s.achievements).join('、')}` : '—'}
              </span>
            )}
            <EditIcon field="achievements" />
          </div>

          {arrNames(s.achievements).length > 0 && (
            <div className="flex items-start py-3 border-b" style={{ borderColor: '#F1F5F9' }}>
              <span className="w-16 flex-shrink-0 text-xs font-semibold text-slate-400 pt-0.5">成果链接</span>
              <div className="flex-1 space-y-1.5">
                {(s.achievements as Record<string, unknown>[]).map((ach, i) => {
                  const achName = String(ach.name || `成果${i + 1}`)
                  return (
                    <div key={i} className="space-y-1">
                      <span className="text-xs font-medium text-slate-600">{achName}</span>
                      <input
                        type="url"
                        value={String(ach.file_link || '')}
                        onChange={(e) => {
                          const updated = [...(s.achievements as Record<string, unknown>[])]
                          updated[i] = { ...updated[i], file_link: e.target.value }
                          setField('achievements', updated)
                        }}
                        placeholder="粘贴文件链接（可选）"
                        className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400/30"
                      />
                    </div>
                  )
                })}
                <p className="text-xs text-slate-400">有链接负责人入库时可直接关联，无则留空</p>
              </div>
            </div>
          )}

          <div className="flex items-start py-3 border-b" style={{ borderColor: '#F1F5F9' }}>
            <span className="w-16 flex-shrink-0 text-xs font-semibold text-slate-400 pt-0.5">问题</span>
            {isEditing('issues') ? (
              <textarea
                autoFocus
                rows={3}
                className="flex-1 text-sm border border-blue-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-400/30 resize-none"
                defaultValue={arrToText(s.issues)}
                onBlur={(e) => { setField('issues', e.target.value.split('\n').filter(Boolean).map((desc) => ({ issue_type: '问题', description: desc, owner: '', priority: '中', status: '待处理' }))); setEditingField(null) }}
              />
            ) : (
              <span className="flex-1 text-sm leading-relaxed" style={{ color: arrNames(s.issues).length > 0 ? '#DC2626' : '#94A3B8' }}>
                {arrNames(s.issues).join('、') || '—'}
              </span>
            )}
            <EditIcon field="issues" />
          </div>

          <div className="flex items-start py-3 border-b" style={{ borderColor: '#F1F5F9' }}>
            <span className="w-16 flex-shrink-0 text-xs font-semibold text-slate-400 pt-0.5">下周计划</span>
            {isEditing('next_steps') ? (
              <textarea
                autoFocus
                rows={3}
                className="flex-1 text-sm border border-blue-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-400/30 resize-none"
                defaultValue={arrToText(s.next_steps)}
                onBlur={(e) => { setField('next_steps', e.target.value.split('\n').filter(Boolean)); setEditingField(null) }}
              />
            ) : (
              <span className="flex-1 text-sm text-slate-700 leading-relaxed">{arrNames(s.next_steps).join('、') || '—'}</span>
            )}
            <EditIcon field="next_steps" />
          </div>

          {proposedSubtasks.length > 0 && (
            <div className="py-3 border-b" style={{ borderColor: '#F1F5F9' }}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-1 h-3.5 rounded-full" style={{ background: '#6366F1' }} />
                <span className="text-xs font-semibold text-indigo-600">下周草稿关键任务</span>
                <span className="text-xs text-slate-400">提交后发给负责人审批，通过后自动创建</span>
              </div>
              <div className="space-y-2">
                {proposedSubtasks.map((ps, i) => (
                  <div key={i} className="flex items-center gap-2 p-2.5 rounded-xl" style={{ background: '#F5F3FF', border: '1px solid #DDD6FE' }}>
                    <div className="flex-1 min-w-0 space-y-1">
                      <input
                        className="w-full text-xs border border-indigo-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
                        value={ps.title}
                        onChange={(e) => setProposedSubtasks((prev) => prev.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))}
                        placeholder="任务说明"
                      />
                      <div className="flex gap-1.5">
                        <input
                          className="flex-1 text-xs border border-indigo-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
                          value={ps.assignee}
                          onChange={(e) => setProposedSubtasks((prev) => prev.map((x, j) => (j === i ? { ...x, assignee: e.target.value } : x)))}
                          placeholder="执行人"
                        />
                        <input
                          className="flex-1 text-xs border border-indigo-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
                          value={ps.plan_time}
                          onChange={(e) => setProposedSubtasks((prev) => prev.map((x, j) => (j === i ? { ...x, plan_time: e.target.value } : x)))}
                          placeholder="计划时间（可选）"
                        />
                      </div>
                    </div>
                    <button onClick={() => setProposedSubtasks((prev) => prev.filter((_, j) => j !== i))} className="flex-shrink-0 p-1 rounded hover:bg-red-100 text-slate-300 hover:text-red-400">
                      <svg style={{ width: 13, height: 13 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
                <button
                  onClick={() => setProposedSubtasks((prev) => [...prev, { title: '', assignee: currentUserName ?? '', plan_time: '' }])}
                  className="text-xs text-indigo-500 hover:text-indigo-700 font-semibold"
                >
                  + 手动添加
                </button>
              </div>
            </div>
          )}

          <div className="flex items-start py-3 border-b" style={{ borderColor: '#F1F5F9' }}>
            <span className="w-16 flex-shrink-0 text-xs font-semibold text-slate-400 pt-0.5">需协调人</span>
            {isEditing('need_coordination') ? (
              <input
                autoFocus
                type="text"
                className="flex-1 text-sm border border-blue-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-400/30"
                defaultValue={(s.need_coordination as string[] ?? []).join('、')}
                onBlur={(e) => { setField('need_coordination', e.target.value.split(/[,，、]/).map((value) => value.trim()).filter(Boolean)); setEditingField(null) }}
                placeholder="用、分隔多人"
              />
            ) : (
              <div className="flex-1 flex flex-wrap gap-1.5">
                {(s.need_coordination as string[] ?? []).length > 0
                  ? (s.need_coordination as string[]).map((item, i) => {
                      const [bg, color] = COORD_CHIP_COLORS[i % COORD_CHIP_COLORS.length].split(':')
                      return (
                        <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold" style={{ background: bg, color }}>
                          <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />{item}
                        </span>
                      )
                    })
                  : <span className="text-sm text-slate-300">—</span>
                }
              </div>
            )}
            <EditIcon field="need_coordination" />
          </div>

          <div className="flex items-center py-3 border-b" style={{ borderColor: '#F1F5F9' }}>
            <span className="w-16 flex-shrink-0 text-xs font-semibold text-slate-400">状态建议</span>
            {isEditing('status_suggestion') ? (
              <select
                autoFocus
                className="flex-1 text-sm border border-blue-300 rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400/30"
                value={s.status_suggestion as string ?? '进行中'}
                onChange={(e) => setField('status_suggestion', e.target.value)}
                onBlur={() => setEditingField(null)}
              >
                {['未开始', '进行中', '已完成', '延期', '暂缓'].map((value) => <option key={value}>{value}</option>)}
              </select>
            ) : (
              <div className="flex-1 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: statusColor }} />
                <span className="text-sm font-semibold" style={{ color: statusColor }}>{s.status_suggestion as string}</span>
                <span className="text-xs text-slate-400">（建议保持当前计划）</span>
              </div>
            )}
            <EditIcon field="status_suggestion" />
          </div>

          {confidence > 0 && (
            <div className="flex items-center py-3">
              <span className="w-16 flex-shrink-0 text-xs font-semibold text-slate-400">置信度</span>
              <div className="flex-1 flex items-center gap-3">
                <span className="text-2xl font-bold" style={{ color: confColor }}>{confPct}%</span>
                <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${confPct}%`, background: confColor }} />
                </div>
                <span className="text-xs text-slate-400 flex-shrink-0">{confLabel}</span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
