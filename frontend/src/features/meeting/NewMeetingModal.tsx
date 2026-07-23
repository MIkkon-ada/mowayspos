import { useEffect, useMemo, useRef, useState } from 'react'
import { analyzeMeeting, createMeeting, transcribeAudio, updateMeeting, type MeetingAnalyzeResult } from '../../api/meetings'
import { getProjectMembers } from '../../api/projects'
import type { MeetingItem, ProjectMember } from '../../types'
import { ErrorBar, Field, JsonListSection, SectionTitle } from './meetingShared'
import { ReportsSection } from './MeetingReportsSection'
import { PushToTasksModal } from './PushToTasksModal'

type ModalStep = 'input' | 'analyzing' | 'review'
type MeetingMode = 'kickoff' | 'progress'

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

function emptyForm(defaultMeetingType: string): ReviewForm {
  return {
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
  }
}

export function NewMeetingModal({
  projectId,
  defaultMeetingType = '',
  editItem,
  onClose,
  onCreated,
}: {
  projectId: number
  defaultMeetingType?: string
  editItem?: MeetingItem
  onClose: () => void
  onCreated: (m: MeetingItem) => void
}) {
  const isEdit = useMemo(() => !!editItem, [editItem])

  const [step, setStep] = useState<ModalStep>(isEdit ? 'review' : 'input')
  const [meetingMode, setMeetingMode] = useState<MeetingMode | null>(null)
  const [meetingText, setMeetingText] = useState('')
  const [statusMsg, setStatusMsg] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [showPushModal, setShowPushModal] = useState(false)
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const [form, setForm] = useState<ReviewForm>(() => {
    if (editItem) {
      return {
        title: editItem.title ?? '',
        meeting_type: editItem.meeting_type ?? defaultMeetingType,
        meeting_date: editItem.meeting_date ?? '',
        host: editItem.host ?? '',
        participants: editItem.participants ?? '',
        summary: editItem.summary ?? '',
        reports_json: String((editItem as Record<string, unknown>).reports_json ?? '[]'),
        task_list_json: editItem.task_list_json ?? '[]',
        decision_items_json: editItem.decision_items_json ?? '[]',
        risk_items_json: editItem.risk_items_json ?? '[]',
        transcript_text: String((editItem as Record<string, unknown>).transcript_text ?? ''),
      }
    }
    return emptyForm(defaultMeetingType)
  })

  useEffect(() => {
    getProjectMembers(projectId).then(setMembers).catch(() => {})
  }, [projectId])

  function setField(key: keyof ReviewForm, val: string) {
    setForm((f) => ({ ...f, [key]: val }))
  }

  async function handleUploadAudio() {
    if (!audioFile) return
    setUploading(true)
    setError('')
    try {
      const result = await transcribeAudio(audioFile)
      setMeetingText(result.text)
      setAudioFile(null)
    } catch (e: unknown) {
      setError(`转录失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setUploading(false)
    }
  }

  async function handleAnalyze() {
    const text = meetingText.trim()
    if (!text) {
      setError('请输入会议讨论文字')
      return
    }
    setError('')
    setStep('analyzing')
    setStatusMsg('AI 正在分析会议内容，提取摘要和行动计划...')
    try {
      const result: MeetingAnalyzeResult = await analyzeMeeting(
        text,
        projectId,
        meetingMode ?? undefined,
        members.map(m => m.person_name_snapshot).filter(Boolean),
      )
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
      if (isEdit && editItem) {
        const item = await updateMeeting(editItem.id, { project_id: projectId, ...form })
        onCreated(item)
      } else {
        const item = await createMeeting({ project_id: projectId, ...form })
        onCreated(item)
      }
    } catch (e: unknown) {
      setError(`保存失败：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSaving(false)
    }
  }

  const steps = [
    { key: 'input' as ModalStep, label: '输入文字' },
    { key: 'analyzing' as ModalStep, label: 'AI 提取' },
    { key: 'review' as ModalStep, label: '确认保存' },
  ]
  const currentIdx = isEdit ? 2 : steps.findIndex((s) => s.key === step)

  const subtitle = isEdit
    ? '编辑并保存'
    : step === 'input'
      ? '粘贴会议讨论文字，AI 自动提取会议总结和工作计划'
      : step === 'analyzing'
        ? statusMsg
        : '检查 AI 提取结果，确认后保存'

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
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#6366F1,#0EA5E9)' }}>
                <svg style={{ width: 15, height: 15, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <div className="text-sm font-bold text-slate-800">{isEdit ? '编辑会议纪要' : '新建会议纪要'}</div>
                <div className="text-xs text-slate-400">{subtitle}</div>
              </div>
            </div>
            <button onClick={onClose} className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-slate-100 text-slate-400">
              <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Steps */}
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
                      {done ? '\u2713' : i + 1}
                    </div>
                    <span className="text-xs font-medium" style={{ color: active ? '#0369A1' : '#94A3B8' }}>
                      {s.label}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto">
            {step === 'input' && (
              <div className="p-6 space-y-4">
                {/* 会议模式选择 */}
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-2">会议类型</label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() => setMeetingMode('kickoff')}
                      className="text-left p-4 rounded-xl border-2 transition-all"
                      style={{
                        borderColor: meetingMode === 'kickoff' ? '#0EA5E9' : '#E2E8F0',
                        background: meetingMode === 'kickoff' ? '#F0F9FF' : 'white',
                      }}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <div
                          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{ background: '#DBEAFE' }}
                        >
                          <svg style={{ width: 14, height: 14, color: '#2563EB' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </div>
                        <div>
                          <div className="text-sm font-bold text-slate-700">启动会</div>
                          <div className="text-xs text-slate-400">讨论修改计划</div>
                        </div>
                      </div>
                      <div className="text-xs text-slate-500 leading-relaxed ml-9">
                        AI 提取会议讨论中确定的修改方案、调整后的工作计划和待办事项
                      </div>
                    </button>
                    <button
                      onClick={() => setMeetingMode('progress')}
                      className="text-left p-4 rounded-xl border-2 transition-all"
                      style={{
                        borderColor: meetingMode === 'progress' ? '#0EA5E9' : '#E2E8F0',
                        background: meetingMode === 'progress' ? '#F0F9FF' : 'white',
                      }}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <div
                          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{ background: '#DCFCE7' }}
                        >
                          <svg style={{ width: 14, height: 14, color: '#16A34A' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                          </svg>
                        </div>
                        <div>
                          <div className="text-sm font-bold text-slate-700">进度汇报</div>
                          <div className="text-xs text-slate-400">各成员汇报进展</div>
                        </div>
                      </div>
                      <div className="text-xs text-slate-500 leading-relaxed ml-9">
                        AI 按发言人逐人提取：已完成工作、遇到的困难、领导反馈、下一步计划
                      </div>
                    </button>
                  </div>
                </div>

                {/* 文字输入 */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-semibold text-slate-600">会议讨论文字</label>
                    <div className="flex items-center gap-1">
                      {audioFile ? (
                        <span className="flex items-center gap-1.5 text-xs">
                          <span className="text-slate-500 truncate max-w-[120px]">{audioFile.name}</span>
                          <button
                            onClick={handleUploadAudio}
                            disabled={uploading}
                            className="px-2 py-0.5 rounded text-xs font-medium text-white"
                            style={{ background: '#0EA5E9' }}
                          >
                            {uploading ? '转录中...' : '转录'}
                          </button>
                          <button onClick={() => setAudioFile(null)} className="text-slate-400 hover:text-slate-600 text-xs">移除</button>
                        </span>
                      ) : (
                        <button
                          onClick={() => fileRef.current?.click()}
                          className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors"
                          title="上传录音辅助转录为文字"
                        >
                          <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                          </svg>
                          上传录音
                        </button>
                      )}
                      <input
                        ref={fileRef}
                        type="file"
                        accept="audio/*,.mp3,.wav,.m4a,.webm,.flac,.aac,.ogg"
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0]
                          if (f) setAudioFile(f)
                        }}
                      />
                    </div>
                  </div>
                  <textarea
                    className="w-full border border-slate-200 rounded-xl p-4 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
                    rows={14}
                    placeholder={
                      '在此粘贴会议讨论文字或转写文本\n\n' +
                      '适用于：\n' +
                      '· 启动会 —— 各方讨论计划、修改方案，AI 提取调整后的工作计划\n' +
                      '· 进度汇报会 —— 成员依次汇报进展、领导点评，AI 提取总结和下一步行动\n\n' +
                      '提示：可直接粘贴会议文字，或先点右上角「上传录音」将录音转为文字后再编辑'
                    }
                    value={meetingText}
                    onChange={(e) => setMeetingText(e.target.value)}
                  />
                  <div className="flex items-center justify-between mt-1.5">
                    <span className="text-xs text-slate-400">
                      {meetingText.length} 字
                    </span>
                    {meetingText.trim() && (
                      <span className="text-xs text-slate-400">
                        AI 将自动提取：会议标题、摘要、参会人、决策事项、暂定工作计划
                      </span>
                    )}
                  </div>
                </div>
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
                  <div className="text-sm text-slate-400 mt-1">请稍候</div>
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
                <JsonListSection label="暂定工作计划" value={form.task_list_json} onChange={(v) => setField('task_list_json', v)} dotColor="#10B981" />

                {error && <ErrorBar msg={error} />}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-6 py-4 border-t" style={{ borderColor: '#E9EFF6' }}>
            {step === 'review' ? (
              <>
                <button onClick={() => (isEdit ? onClose() : setStep('input'))} className="text-sm text-slate-500 hover:text-slate-700 font-medium">
                  {isEdit ? '取消' : '返回修改'}
                </button>
                <div className="flex gap-2">
                  <button onClick={() => setShowPushModal(true)} className="px-4 py-2.5 rounded-xl border-2 border-emerald-200 text-emerald-700 text-sm font-semibold hover:bg-emerald-50 flex items-center gap-2">
                    推送到工作推进
                  </button>
                  <button onClick={handleSave} disabled={saving} className="px-6 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
                    {saving ? '保存中...' : isEdit ? '保存修改' : '保存草稿'}
                  </button>
                </div>
              </>
            ) : step === 'input' ? (
              <>
                <button onClick={onClose} className="text-sm text-slate-500 hover:text-slate-700 font-medium">
                  取消
                </button>
                <button
                  onClick={handleAnalyze}
                  disabled={!meetingText.trim() || !meetingMode}
                  className="px-6 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
                >
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
