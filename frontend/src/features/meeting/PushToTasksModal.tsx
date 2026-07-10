import { useState } from 'react'
import { apiPatch, apiPost } from '../../api/client'
import { generateTaskCards } from '../../api/meetings'
import type { TaskCard } from '../../api/meetings'
import type { ProjectMember } from '../../types'
import { ErrorBar } from './meetingShared'

type CardWithState = TaskCard & { approved: boolean; executing?: boolean; done?: boolean; error?: string }

type Step = 'map' | 'loading' | 'review' | 'executing' | 'done'

export function PushToTasksModal({
  projectId,
  reportsJson,
  transcriptText,
  members,
  onClose,
  onDone,
}: {
  projectId: number
  reportsJson: string
  transcriptText: string
  members: ProjectMember[]
  onClose: () => void
  onDone: () => void
}) {
  const [step, setStep] = useState<Step>('map')
  const [speakerMap, setSpeakerMap] = useState<Record<string, string>>({})
  const [customNames, setCustomNames] = useState<Record<string, string>>({})
  const [cards, setCards] = useState<CardWithState[]>([])
  const [error, setError] = useState('')
  const [doneCount, setDoneCount] = useState(0)
  const [failCount, setFailCount] = useState(0)

  let reports: { member: string }[] = []
  try {
    reports = JSON.parse(reportsJson)
  } catch {
    reports = []
  }

  const speakerSet = new Set<string>()
  reports.forEach((r) => {
    if (r.member) speakerSet.add(r.member)
  })
  const speakers = [...speakerSet]
  const uniqueMembers = [...new Map(members.map((m) => [m.person_name_snapshot, m])).values()]

  const resolveName = (label: string) => {
    if (label in customNames) return customNames[label] || label
    return speakerMap[label] || label
  }

  async function handleGenerate() {
    setError('')
    setStep('loading')

    const finalMap: Record<string, string> = {}
    speakers.forEach((s) => {
      finalMap[s] = resolveName(s)
    })

    try {
      const result = await generateTaskCards(projectId, transcriptText, finalMap)
      const loaded: CardWithState[] = (result.task_cards || []).map((c) => ({ ...c, approved: true }))
      setCards(loaded)
      setStep('review')
    } catch (e: unknown) {
      setError(`AI 分析失败：${e instanceof Error ? e.message : String(e)}`)
      setStep('map')
    }
  }

  async function handleExecute() {
    setStep('executing')
    setDoneCount(0)
    setFailCount(0)

    const approved = cards.filter((c) => c.approved)
    let ok = 0
    let fail = 0

    for (let i = 0; i < cards.length; i++) {
      if (!cards[i].approved) continue
      setCards((prev) => prev.map((c, idx) => (idx === i ? { ...c, executing: true } : c)))

      try {
        const card = cards[i]
        if (card.action === 'create') {
          await apiPost(`/api/tasks/${card.parent_task_id}/subtasks`, {
            title: card.title,
            assignee: card.assignee || '',
            plan_time: card.plan_time || '',
            status: '未开始',
            notes: card.notes || '',
          })
        } else if (card.action === 'update_status') {
          const base = card.current_payload ?? { title: card.subtask_title, assignee: '', plan_time: '', status: '', completion_criteria: '', notes: '' }
          await apiPatch(`/api/subtasks/${card.subtask_id}`, {
            ...base,
            status: card.new_status,
            notes: card.notes ? (base.notes ? base.notes + '\n' + card.notes : card.notes) : base.notes,
          })
        } else if (card.action === 'add_note') {
          const base = card.current_payload ?? { title: card.subtask_title, assignee: '', plan_time: '', status: '', completion_criteria: '', notes: '' }
          const appendedNote = base.notes ? base.notes + '\n【会议备注】' + card.note : '【会议备注】' + card.note
          await apiPatch(`/api/subtasks/${card.subtask_id}`, {
            ...base,
            notes: appendedNote,
          })
        }
        ok++
        setCards((prev) => prev.map((c, idx) => (idx === i ? { ...c, executing: false, done: true } : c)))
      } catch (e: unknown) {
        fail++
        const msg = e instanceof Error ? e.message : String(e)
        setCards((prev) => prev.map((c, idx) => (idx === i ? { ...c, executing: false, error: msg } : c)))
      }
      setDoneCount(ok)
      setFailCount(fail)
    }

    if (approved.length === 0 || ok > 0) {
      setStep('done')
    } else {
      setStep('executing')
    }
  }

  const approvedCount = cards.filter((c) => c.approved).length

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center"
      style={{ background: 'rgba(15,23,42,0.6)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden" style={{ width: 640, maxHeight: '88vh' }}>

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
          <div>
            <div className="text-sm font-bold text-slate-800">推送到工作推进</div>
            <div className="text-xs text-slate-400 mt-0.5">
              {step === 'map' && '映射发言人 → 生成 AI 任务建议卡片'}
              {step === 'loading' && 'AI 正在分析会议内容，生成任务建议…'}
              {step === 'review' && `共生成 ${cards.length} 张卡片，请逐一确认后执行`}
              {step === 'executing' && '正在执行已批准的卡片…'}
              {step === 'done' && `执行完毕：成功 ${doneCount} 张，失败 ${failCount} 张`}
            </div>
          </div>
          <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-slate-100 text-slate-400">
            <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">

          {/* Step: map */}
          {step === 'map' && (
            <div className="space-y-5">
              {speakers.length > 0 ? (
                <div>
                  <div className="text-xs font-bold text-slate-700 mb-3">发言人映射</div>
                  <div className="space-y-2">
                    {speakers.map((speaker) => (
                      <div key={speaker} className="grid items-center gap-3" style={{ gridTemplateColumns: '120px 1fr' }}>
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-bold flex-shrink-0">
                            {speaker.slice(0, 1)}
                          </div>
                          <span className="text-xs font-semibold text-slate-600 truncate">{speaker}</span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <select
                            className="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-300"
                            value={speaker in customNames ? '__custom__' : speakerMap[speaker] ?? ''}
                            onChange={(e) => {
                              const val = e.target.value
                              if (val === '__custom__') {
                                setCustomNames((c) => ({ ...c, [speaker]: speakerMap[speaker] ?? '' }))
                              } else {
                                setCustomNames((c) => { const n = { ...c }; delete n[speaker]; return n })
                                setSpeakerMap((m) => ({ ...m, [speaker]: val }))
                              }
                            }}
                          >
                            <option value="">保持原标签</option>
                            {uniqueMembers.length > 0 && (
                              <optgroup label="本项目成员">
                                {uniqueMembers.map((m) => (
                                  <option key={m.id} value={m.person_name_snapshot}>
                                    {m.person_name_snapshot} ({m.role})
                                  </option>
                                ))}
                              </optgroup>
                            )}
                            <option value="__custom__">手动填写</option>
                          </select>
                          {speaker in customNames && (
                            <input
                              autoFocus
                              type="text"
                              className="w-full border border-blue-300 rounded-lg px-2.5 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
                              placeholder="输入姓名"
                              value={customNames[speaker]}
                              onChange={(e) => {
                                const v = e.target.value
                                setCustomNames((c) => ({ ...c, [speaker]: v }))
                                setSpeakerMap((m) => ({ ...m, [speaker]: v }))
                              }}
                            />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-slate-400 text-center py-4">
                  未检测到说话人标签（如"说话人1："），请确认转录文本格式
                </div>
              )}
              {error && <ErrorBar msg={error} />}
            </div>
          )}

          {/* Step: loading */}
          {step === 'loading' && (
            <div className="flex flex-col items-center justify-center py-16 gap-4">
              <div className="w-10 h-10 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin" />
              <div className="text-sm text-slate-500">AI 正在对照任务清单生成建议卡片…</div>
            </div>
          )}

          {/* Step: review */}
          {(step === 'review' || step === 'executing' || step === 'done') && (
            <div className="space-y-3">
              {cards.length === 0 && (
                <div className="text-xs text-slate-400 text-center py-8">AI 未生成任何卡片，可能会议内容与现有任务无明显交集</div>
              )}
              {cards.map((card, i) => (
                <TaskCardItem
                  key={i}
                  card={card}
                  readonly={step !== 'review'}
                  onToggle={() => {
                    setCards((prev) => prev.map((c, idx) => idx === i ? { ...c, approved: !c.approved } : c))
                  }}
                  onEditField={(field, value) => {
                    setCards((prev) => prev.map((c, idx) => idx === i ? { ...c, [field]: value } : c))
                  }}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t" style={{ borderColor: '#E9EFF6' }}>
          <button onClick={onClose} className="text-sm text-slate-500 hover:text-slate-700">
            {step === 'done' ? '关闭' : '取消'}
          </button>
          <div className="flex items-center gap-3">
            {step === 'map' && (
              <button
                onClick={handleGenerate}
                disabled={speakers.length === 0}
                className="px-6 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-40"
                style={{ background: 'linear-gradient(135deg,#3B82F6,#6366F1)' }}
              >
                AI 生成任务卡片
              </button>
            )}
            {step === 'review' && (
              <button
                onClick={handleExecute}
                disabled={approvedCount === 0}
                className="px-6 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-40"
                style={{ background: 'linear-gradient(135deg,#059669,#10B981)' }}
              >
                执行 {approvedCount} 张已批准的卡片
              </button>
            )}
            {step === 'done' && (
              <button
                onClick={onDone}
                className="px-6 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90"
                style={{ background: 'linear-gradient(135deg,#059669,#10B981)' }}
              >
                完成
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


function TaskCardItem({
  card,
  readonly,
  onToggle,
  onEditField,
}: {
  card: CardWithState
  readonly: boolean
  onToggle: () => void
  onEditField: (field: string, value: string) => void
}) {
  const [showEvidence, setShowEvidence] = useState(false)

  const actionMeta = {
    create: { label: '新建关键任务', color: '#059669', bg: '#ECFDF5', border: '#A7F3D0' },
    update_status: { label: '更新状态', color: '#2563EB', bg: '#EFF6FF', border: '#BFDBFE' },
    add_note: { label: '追加备注', color: '#D97706', bg: '#FFFBEB', border: '#FDE68A' },
  }[card.action]

  const isCompleted = card.done
  const isFailed = !!card.error
  const isRunning = card.executing

  let borderColor = actionMeta.border
  if (isCompleted) borderColor = '#86EFAC'
  if (isFailed) borderColor = '#FCA5A5'

  return (
    <div
      className="rounded-xl border p-4 transition-all"
      style={{
        borderColor,
        background: card.approved ? actionMeta.bg : '#F8FAFC',
        opacity: card.approved ? 1 : 0.55,
      }}
    >
      {/* Card header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-xs font-bold px-2 py-0.5 rounded-full"
            style={{ color: actionMeta.color, background: 'white', border: `1px solid ${actionMeta.border}` }}
          >
            {actionMeta.label}
          </span>
          {isRunning && <span className="text-xs text-slate-400">执行中…</span>}
          {isCompleted && <span className="text-xs text-green-600 font-medium">已完成</span>}
          {isFailed && <span className="text-xs text-red-500 font-medium">失败：{card.error}</span>}
        </div>
        {!readonly && (
          <button
            onClick={onToggle}
            className="flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors"
            style={{
              borderColor: card.approved ? actionMeta.color : '#CBD5E1',
              background: card.approved ? actionMeta.color : 'white',
            }}
            title={card.approved ? '点击跳过此卡片' : '点击批准此卡片'}
          >
            {card.approved && (
              <svg style={{ width: 10, height: 10 }} fill="none" stroke="white" strokeWidth="3" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            )}
          </button>
        )}
      </div>

      {/* Card body */}
      <div className="mt-3 space-y-1.5 text-xs text-slate-700">
        {card.action === 'create' && (
          <>
            <div><span className="text-slate-400">关键任务：</span>
              {!readonly ? (
                <input
                  className="ml-1 border-b border-slate-300 bg-transparent focus:outline-none focus:border-blue-400 font-medium"
                  value={card.title}
                  onChange={(e) => onEditField('title', e.target.value)}
                />
              ) : (
                <span className="font-medium">{card.title}</span>
              )}
            </div>
            <div><span className="text-slate-400">负责人：</span><span>{card.assignee || '—'}</span></div>
            <div><span className="text-slate-400">计划时间：</span><span>{card.plan_time || '—'}</span></div>
            <div><span className="text-slate-400">重点工作：</span><span className="text-slate-500">{card.parent_key_task}</span></div>
            {card.notes && <div><span className="text-slate-400">备注：</span><span>{card.notes}</span></div>}
          </>
        )}
        {card.action === 'update_status' && (
          <>
            <div><span className="text-slate-400">关键任务：</span><span className="font-medium">{card.subtask_title}</span></div>
            <div>
              <span className="text-slate-400">状态改为：</span>
              {!readonly ? (
                <select
                  className="ml-1 border-b border-slate-300 bg-transparent focus:outline-none focus:border-blue-400 font-medium text-xs"
                  value={card.new_status}
                  onChange={(e) => onEditField('new_status', e.target.value)}
                >
                  {['未开始', '进行中', '已完成', '暂停', '已取消'].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              ) : (
                <span className="font-medium" style={{ color: actionMeta.color }}>{card.new_status}</span>
              )}
            </div>
            {card.notes && <div><span className="text-slate-400">附加备注：</span><span>{card.notes}</span></div>}
          </>
        )}
        {card.action === 'add_note' && (
          <>
            <div><span className="text-slate-400">关键任务：</span><span className="font-medium">{card.subtask_title}</span></div>
            <div>
              <span className="text-slate-400">追加备注：</span>
              {!readonly ? (
                <input
                  className="ml-1 border-b border-slate-300 bg-transparent focus:outline-none focus:border-blue-400 w-56"
                  value={card.note}
                  onChange={(e) => onEditField('note', e.target.value)}
                />
              ) : (
                <span>{card.note}</span>
              )}
            </div>
          </>
        )}
      </div>

      {/* Evidence */}
      {card.evidence && (
        <div className="mt-2.5">
          <button
            className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1"
            onClick={() => setShowEvidence((v) => !v)}
          >
            <svg style={{ width: 10, height: 10, transform: showEvidence ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
            </svg>
            会议依据
          </button>
          {showEvidence && (
            <div className="mt-1.5 pl-3 border-l-2 border-slate-200 text-xs text-slate-500 italic leading-relaxed">
              {card.evidence}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
