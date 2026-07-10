import { useEffect, useRef, useState } from 'react'
import { analyzeMeeting, createMeeting, transcribeAudio, type MeetingAnalyzeResult } from '../../api/meetings'
import { getProjectMembers } from '../../api/projects'
import type { MeetingItem, ProjectMember } from '../../types'
import { ErrorBar, Field, JsonListSection, SectionTitle } from './meetingShared'
import { ReportsSection } from './MeetingReportsSection'
import { PushToTasksModal } from './PushToTasksModal'

type ModalStep = 'input' | 'analyzing' | 'review'
type InputTab = 'text' | 'audio'

type ReviewForm = {
  title: string
  meeting_type: string
  meeting_date: string
  host: string
  participants: string
  summary: string
  reports_json: string
  task_list_json: string
  decision_items_json: string
  risk_items_json: string
  transcript_text: string
}

export function NewMeetingModal({
  projectId,
  defaultMeetingType = '',
  onClose,
  onCreated,
}: {
  projectId: number
  defaultMeetingType?: string
  onClose: () => void
  onCreated: (m: MeetingItem) => void
}) {
  const [tab, setTab] = useState<InputTab>('text')
  const [step, setStep] = useState<ModalStep>('input')
  const [pastedText, setPastedText] = useState('')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [statusMsg, setStatusMsg] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [showPushModal, setShowPushModal] = useState(false)
  const [members, setMembers] = useState<ProjectMember[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  const [form, setForm] = useState<ReviewForm>({
    title: '',
    meeting_type: defaultMeetingType,
    meeting_date: '',
    host: '',
    participants: '',
    summary: '',
    reports_json: '[]',
    task_list_json: '[]',
    decision_items_json: '[]',
    risk_items_json: '[]',
    transcript_text: '',
  })

  useEffect(() => {
    getProjectMembers(projectId).then(setMembers).catch(() => {})
  }, [projectId])

  function setField(key: keyof ReviewForm, val: string) {
    setForm((f) => ({ ...f, [key]: val }))
  }

  async function handleAnalyze() {
    setError('')
    let text = ''

    if (tab === 'audio') {
      if (!audioFile) {
        setError('请先选择音频文件')
        return
      }
      setStep('analyzing')
      setStatusMsg('正在转录音频...')
      try {
        text = (await transcribeAudio(audioFile)).text
      } catch (e: unknown) {
        setError(`转录失败：${e instanceof Error ? e.message : String(e)}`)
        setStep('input')
        return
      }
    } else {
      if (!pastedText.trim()) {
        setError('请粘贴会议记录文本')
        return
      }
      text = pastedText
    }

    setStep('analyzing')
    setStatusMsg('AI 正在分析会议内容...')
    try {
      const result: MeetingAnalyzeResult = await analyzeMeeting(text, projectId)
      setForm({
        title: result.title,
        meeting_type: result.meeting_type,
        meeting_date: result.meeting_date,
        host: result.host,
        participants: result.participants,
        summary: result.summary,
        reports_json: result.reports_json ?? '[]',
        task_list_json: result.task_list_json,
        decision_items_json: result.decision_items_json,
        risk_items_json: result.risk_items_json,
        transcript_text: text,
      })
      setStep('review')
    } catch (e: unknown) {
      setError(`AI 分析失败：${e instanceof Error ? e.message : String(e)}`)
      setStep('input')
    }
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const item = await createMeeting({ project_id: projectId, ...form })
      onCreated(item)
    } catch (e: unknown) {
      setError(`保存失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSaving(false)
    }
  }

  const steps = [
    { key: 'input' as ModalStep, label: '输入' },
    { key: 'analyzing' as ModalStep, label: '分析' },
    { key: 'review' as ModalStep, label: '确认' },
  ]
  const currentIdx = steps.findIndex((s) => s.key === step)

  return (
    <>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center"
        style={{ background: 'rgba(15,23,42,0.5)' }}
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose()
        }}
      >
        <div className="bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden" style={{ width: 700, maxHeight: '92vh' }}>
          <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#6366F1,#0EA5E9)' }}>
                <svg style={{ width: 15, height: 15, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <div className="text-sm font-bold text-slate-800">新建会议纪要</div>
                <div className="text-xs text-slate-400">{step === 'input' ? '选择输入方式' : step === 'analyzing' ? statusMsg : '确认并保存'}</div>
              </div>
            </div>
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-slate-100 text-slate-400">
              <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="flex items-center gap-1 px-6 py-3 border-b" style={{ borderColor: '#F1F5F9', background: '#FAFBFC' }}>
            {steps.map((s, i) => {
              const done = currentIdx > i
              const active = currentIdx === i
              return (
                <div key={s.key} className="flex items-center gap-1">
                  {i > 0 && <div className="w-8 h-px mx-1" style={{ background: done ? '#0EA5E9' : '#E2E8F0' }} />}
                  <div className="flex items-center gap-1.5">
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                      style={{
                        background: done ? '#0EA5E9' : active ? '#EFF6FF' : '#F1F5F9',
                        color: done ? 'white' : active ? '#0369A1' : '#94A3B8',
                        border: active ? '1.5px solid #0EA5E9' : '1.5px solid transparent',
                      }}
                    >
                      {done ? '✓' : i + 1}
                    </div>
                    <span className="text-xs font-medium" style={{ color: active ? '#0369A1' : '#94A3B8' }}>
                      {s.label}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="flex-1 overflow-y-auto">
            {step === 'input' && (
              <div className="p-6 space-y-4">
                <div className="flex gap-1 p-1 rounded-xl" style={{ background: '#F1F5F9' }}>
                  {(['text', 'audio'] as InputTab[]).map((t) => (
                    <button
                      key={t}
                      onClick={() => setTab(t)}
                      className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all"
                      style={{
                        background: tab === t ? 'white' : 'transparent',
                        color: tab === t ? '#0369A1' : '#64748B',
                        boxShadow: tab === t ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                      }}
                    >
                      {t === 'text' ? '文本' : '音频'}
                    </button>
                  ))}
                </div>

                {tab === 'text' ? (
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-2">粘贴会议记录文本</label>
                    <textarea
                      className="w-full border border-slate-200 rounded-xl p-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
                      rows={12}
                      placeholder="请在这里粘贴会议记录"
                      value={pastedText}
                      onChange={(e) => setPastedText(e.target.value)}
                    />
                    <div className="text-xs text-slate-400 mt-1 text-right">{pastedText.length} 字</div>
                  </div>
                ) : (
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-2">上传会议录音</label>
                    <div
                      className="border-2 border-dashed rounded-xl p-8 flex flex-col items-center gap-3 cursor-pointer transition-colors"
                      style={{ borderColor: audioFile ? '#0EA5E9' : '#E2E8F0', background: audioFile ? '#F0F9FF' : '#FAFBFC' }}
                      onClick={() => fileRef.current?.click()}
                    >
                      <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ background: audioFile ? '#DBEAFE' : '#F1F5F9' }}>
                        <svg style={{ width: 22, height: 22, color: audioFile ? '#0369A1' : '#94A3B8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                      </div>
                      {audioFile ? (
                        <div className="text-center">
                          <div className="text-sm font-semibold text-slate-700">{audioFile.name}</div>
                          <div className="text-xs text-slate-400 mt-0.5">{(audioFile.size / 1024 / 1024).toFixed(1)} MB</div>
                        </div>
                      ) : (
                        <div className="text-center">
                          <div className="text-sm font-semibold text-slate-600">点击选择音频文件</div>
                          <div className="text-xs text-slate-400 mt-1">支持 MP3、WAV、M4A、WEBM、FLAC、AAC、OGG</div>
                        </div>
                      )}
                    </div>
                    <input
                      ref={fileRef}
                      type="file"
                      accept="audio/*,.mp3,.wav,.m4a,.webm,.flac,.aac,.ogg"
                      className="hidden"
                      onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
                    />
                  </div>
                )}
                {error && <ErrorBar msg={error} />}
              </div>
            )}

            {step === 'analyzing' && (
              <div className="p-12 flex flex-col items-center gap-5">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#EFF6FF,#DBEAFE)' }}>
                  <svg className="animate-spin" style={{ width: 28, height: 28, color: '#0369A1' }} fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                </div>
                <div className="text-center">
                  <div className="text-base font-bold text-slate-700">{statusMsg}</div>
                  <div className="text-sm text-slate-400 mt-1">请稍候，可能需要一点时间</div>
                </div>
              </div>
            )}

            {step === 'review' && (
              <div className="p-6 space-y-5">
                <div>
                  <SectionTitle>基本信息</SectionTitle>
                  <div className="grid grid-cols-2 gap-3 mt-2">
                    <Field label="标题" value={form.title} onChange={(v) => setField('title', v)} />
                    <div>
                      <label className="block text-xs font-semibold text-slate-500 mb-1">会议类型</label>
                      <select
                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-300"
                        value={form.meeting_type}
                        onChange={(e) => setField('meeting_type', e.target.value)}
                      >
                        <option value="">请选择</option>
                        <option value="kickoff">启动会</option>
                        <option value="weekly">周会</option>
                        <option value="monthly">月会</option>
                        <option value="review">评审会</option>
                        <option value="special">专项会</option>
                        <option value="discuss">讨论会</option>
                      </select>
                    </div>
                    <Field label="日期" value={form.meeting_date} onChange={(v) => setField('meeting_date', v)} placeholder="YYYY-MM-DD" />
                    <Field label="主持人" value={form.host} onChange={(v) => setField('host', v)} />
                    <div className="col-span-2">
                      <Field label="参会人" value={form.participants} onChange={(v) => setField('participants', v)} placeholder="多个姓名用逗号分隔" />
                    </div>
                  </div>
                </div>

                <div>
                  <SectionTitle>会议摘要</SectionTitle>
                  <textarea
                    className="w-full mt-2 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-300 resize-none"
                    rows={3}
                    value={form.summary}
                    onChange={(e) => setField('summary', e.target.value)}
                  />
                </div>

                <ReportsSection reportsJson={form.reports_json} />
                <JsonListSection label="决策事项" value={form.decision_items_json} onChange={(v) => setField('decision_items_json', v)} dotColor="#3B82F6" />
                <JsonListSection label="行动清单" value={form.task_list_json} onChange={(v) => setField('task_list_json', v)} dotColor="#10B981" />

                {error && <ErrorBar msg={error} />}
              </div>
            )}
          </div>

          <div className="flex items-center justify-between px-6 py-4 border-t" style={{ borderColor: '#E9EFF6' }}>
            {step === 'review' ? (
              <>
                <button onClick={() => setStep('input')} className="text-sm text-slate-500 hover:text-slate-700 font-medium">
                  返回
                </button>
                <div className="flex gap-2">
                  <button onClick={() => setShowPushModal(true)} className="px-4 py-2.5 rounded-xl border-2 border-emerald-200 text-emerald-700 text-sm font-semibold hover:bg-emerald-50 flex items-center gap-2">
                    推送到工作推进
                  </button>
                  <button onClick={handleSave} disabled={saving} className="px-6 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
                    {saving ? '保存中...' : '保存草稿'}
                  </button>
                </div>
              </>
            ) : step === 'input' ? (
              <>
                <button onClick={onClose} className="text-sm text-slate-500 hover:text-slate-700 font-medium">
                  取消
                </button>
                <button onClick={handleAnalyze} className="px-6 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90" style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
                  AI 分析
                </button>
              </>
            ) : (
              <div />
            )}
          </div>
        </div>
      </div>

      {showPushModal && (
        <PushToTasksModal
          projectId={projectId}
          reportsJson={form.reports_json}
          transcriptText={form.transcript_text}
          members={members}
          onClose={() => setShowPushModal(false)}
          onDone={() => {
            setShowPushModal(false)
            handleSave()
          }}
        />
      )}
    </>
  )
}
