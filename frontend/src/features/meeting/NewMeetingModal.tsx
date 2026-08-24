import { useEffect, useMemo, useRef, useState } from 'react'
import {
  analyzeMeeting,
  createProjectMeetingDocumentRun,
  fetchProjectMeetingDocumentRun,
  pollProjectMeetingDocumentRun,
  addMeetingSkillSnapshot,
  answerMeetingSkillQuestions,
  createMeeting,
  extractMeetingDocumentText,
  preflightMeetingSkill,
  resumeMeetingSkillRun,
  type MeetingSkillRun,
  type StandardMeetingMinutes,
  updateMeeting,
  type MeetingAnalyzeResult,
} from '../../api/meetings'
import { getProjectMembers } from '../../api/projects'
import type { MeetingItem, ProjectMember } from '../../types'
import { ErrorBar, Field, JsonListSection, SectionTitle } from './meetingShared'
import { ReportsSection } from './MeetingReportsSection'
import { MeetingChangeSetReviewModal } from './MeetingChangeSetReviewModal'

type ModalStep = 'input' | 'analyzing' | 'clarifying' | 'review'

type ReviewForm = {
  title: string
  meeting_type: string
  meeting_date: string
  location: string
  host: string
  participants: string
  organizer: string
  copied_to: string
  agenda_items_json: string
  prior_action_items_json: string
  source_mode: 'standard_minutes' | 'ai_analysis'
  summary: string
  reports_json: string
  task_list_json: string
  confirmed_items_json: string
  decision_items_json: string
  risk_items_json: string
  transcript_text: string
}

function emptyForm(): ReviewForm {
  return {
    title: '',
    meeting_type: '',
    meeting_date: '',
    location: '',
    host: '',
    participants: '',
    organizer: '',
    copied_to: '项目全体成员',
    agenda_items_json: '[]',
    prior_action_items_json: '[]',
    source_mode: 'ai_analysis',
    summary: '',
    reports_json: '[]',
    task_list_json: '[]',
    confirmed_items_json: '[]',
    decision_items_json: '[]',
    risk_items_json: '[]',
    transcript_text: '',
  }
}

export function combineAnalysisSources({
  documentText,
}: {
  documentText: string
}): string {
  return documentText.trim()
}

function SourceStatus({ text, emptyLabel }: { text: string; emptyLabel: string }) {
  return text.trim() ? (
    <span className="text-xs font-medium text-emerald-600">已就绪</span>
  ) : (
    <span className="text-xs text-slate-400">{emptyLabel}</span>
  )
}

function ParsedRows({ value }: { value: string }) {
  let rows: Record<string, string>[] = []
  try {
    const parsed: unknown = JSON.parse(value)
    if (Array.isArray(parsed)) {
      rows = parsed.flatMap((item) => {
        if (typeof item === 'string') return [{ 内容: item }]
        if (!item || typeof item !== 'object') return []
        return [Object.fromEntries(Object.entries(item as Record<string, unknown>).map(([key, itemValue]) => [key, String(itemValue ?? '')]))]
      })
    }
  } catch {
    rows = []
  }
  if (!rows.length) return <p className="mt-3 text-sm text-slate-400">暂无内容</p>
  const headers = Object.keys(rows[0])
  return <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200"><table className="min-w-full text-left text-xs"><thead><tr className="bg-slate-50 text-slate-500">{headers.map((header) => <th key={header} className="whitespace-nowrap px-3 py-2.5 font-medium">{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index} className="border-t border-slate-100 text-slate-700">{headers.map((header) => <td key={header} className="min-w-28 px-3 py-2.5 align-top leading-5">{row[header] || '—'}</td>)}</tr>)}</tbody></table></div>
}

function StandardMinutesReview({ form }: { form: ReviewForm }) {
  let agenda: string[] = []
  try {
    const parsed: unknown = JSON.parse(form.agenda_items_json)
    agenda = Array.isArray(parsed) ? parsed.map((item) => String(item).trim()).filter(Boolean) : []
  } catch {
    agenda = []
  }
  return <section className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
    <div><SectionTitle>会议议程</SectionTitle>{agenda.length ? <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-700">{agenda.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ol> : <p className="mt-3 text-sm text-slate-400">暂无议程</p>}</div>
    <div className="border-t border-slate-100 pt-6"><SectionTitle>本周新增待办事项</SectionTitle><ParsedRows value={form.task_list_json} /></div>
    <div className="border-t border-slate-100 pt-6"><SectionTitle>上周待办追踪</SectionTitle><ParsedRows value={form.prior_action_items_json} /></div>
  </section>
}

export function NewMeetingModal({
  projectId,
  editItem,
  onClose,
  onCreated,
}: {
  projectId: number
  editItem?: MeetingItem
  onClose: () => void
  onCreated: (m: MeetingItem) => void
}) {
  const isEdit = useMemo(() => !!editItem, [editItem])
  const [step, setStep] = useState<ModalStep>(isEdit ? 'review' : 'input')
  const [statusMsg, setStatusMsg] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [analysisId, setAnalysisId] = useState<number | null>(null)
  const [savedMeeting, setSavedMeeting] = useState<MeetingItem | null>(null)
  const [reviewMeetingId, setReviewMeetingId] = useState<number | null>(null)
  const [documentName, setDocumentName] = useState('')
  const [documentFile, setDocumentFile] = useState<File | null>(null)
  const [documentText, setDocumentText] = useState('')
  const [documentReferenceKind, setDocumentReferenceKind] = useState('meeting_document')
  const [skillRun, setSkillRun] = useState<MeetingSkillRun | null>(null)
  const [clarificationValues, setClarificationValues] = useState<Record<number, string>>({})
  const [documentUploading, setDocumentUploading] = useState(false)
  const [projectMembers, setProjectMembers] = useState<ProjectMember[]>([])
  const [membersLoadFailed, setMembersLoadFailed] = useState(false)
  const documentRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<ReviewForm>(() => {
    if (editItem) {
      return {
        title: editItem.title ?? '',
        meeting_type: editItem.meeting_type ?? '',
        meeting_date: editItem.meeting_date ?? '',
        location: editItem.location ?? '',
        host: editItem.host ?? '',
        participants: editItem.participants ?? '',
        organizer: editItem.organizer ?? '',
        copied_to: editItem.copied_to ?? '',
        agenda_items_json: editItem.agenda_items_json ?? '[]',
        prior_action_items_json: editItem.prior_action_items_json ?? '[]',
        source_mode: editItem.source_mode ?? 'ai_analysis',
        summary: editItem.summary ?? '',
        reports_json: String((editItem as Record<string, unknown>).reports_json ?? '[]'),
        task_list_json: editItem.task_list_json ?? '[]',
        confirmed_items_json: editItem.risk_items_json ?? '[]',
        decision_items_json: editItem.decision_items_json ?? '[]',
        risk_items_json: editItem.risk_items_json ?? '[]',
        transcript_text: String((editItem as Record<string, unknown>).transcript_text ?? ''),
      }
    }
    return emptyForm()
  })

  useEffect(() => {
    let active = true
    setProjectMembers([])
    setMembersLoadFailed(false)
    void getProjectMembers(projectId)
      .then((members) => {
        if (active) setProjectMembers(members)
      })
      .catch(() => {
        if (active) setMembersLoadFailed(true)
      })
    return () => {
      active = false
    }
  }, [projectId])

  const analysisText = useMemo(
    () => combineAnalysisSources({ documentText }),
    [documentText],
  )
  const sourceCount = Number(Boolean(documentText.trim()))
  const skillReferenceFiles = useMemo(() => [
    ...(documentText.trim() ? [{ source_id: `document:${documentName || 'uploaded'}`, kind: documentReferenceKind, filename: documentName }] : []),
  ], [documentName, documentReferenceKind, documentText])

  function setField(key: keyof ReviewForm, value: string) {
    setForm((previous) => ({ ...previous, [key]: value }))
  }

  async function handleDocumentSelected(file: File) {
    setDocumentUploading(true)
    setError('')
    try {
      const result = await extractMeetingDocumentText(projectId, file)
      setDocumentFile(file)
      setDocumentName(result.filename)
      setDocumentText(result.text)
      if (result.standard_minutes?.is_standard_minutes) {
        const minutes = result.standard_minutes
        setForm((previous) => ({
          ...previous,
          title: minutes.title || previous.title,
          meeting_type: minutes.meeting_type || previous.meeting_type,
          meeting_date: minutes.meeting_date || previous.meeting_date,
          location: minutes.location || previous.location,
          host: minutes.host || previous.host,
          participants: minutes.participants || previous.participants,
          organizer: minutes.organizer || previous.organizer,
          copied_to: minutes.copied_to || previous.copied_to,
          summary: minutes.summary || previous.summary,
          agenda_items_json: JSON.stringify(minutes.agenda_items ?? []),
          task_list_json: JSON.stringify(minutes.current_action_items ?? []),
          prior_action_items_json: JSON.stringify(minutes.prior_action_items ?? []),
          source_mode: 'standard_minutes',
          transcript_text: `【会议文档】\n${result.text}`,
        }))
      }
    } catch (cause: unknown) {
      setError(`文档读取失败：${cause instanceof Error ? cause.message : String(cause)}`)
    } finally {
      setDocumentUploading(false)
    }
  }

  async function generateAfterPreflight(run: MeetingSkillRun) {
    setStep('analyzing')
    setStatusMsg('材料已完成预检，正在生成会议纪要草稿…')
    const readyRun = run.status === 'ready_for_review' ? run : await resumeMeetingSkillRun(run.id)
    setSkillRun(readyRun)
    const result: MeetingAnalyzeResult = await analyzeMeeting(analysisText, projectId, undefined, undefined, readyRun.id)
    setAnalysisId(result.analysis_id)
    setForm((previous) => ({
      ...previous,
      title: previous.title || result.title,
      meeting_date: previous.meeting_date || result.meeting_date,
      host: previous.host || result.host,
      summary: result.summary,
      reports_json: result.reports_json ?? '[]',
      task_list_json: result.task_list_json,
      confirmed_items_json: result.confirmed_items_json ?? '[]',
      decision_items_json: result.decision_items_json,
      risk_items_json: result.risk_items_json,
      transcript_text: analysisText,
      source_mode: 'ai_analysis',
    }))
    setStep('review')
  }

  async function handleAnalyze() {
    if (!documentText.trim() || !documentName) {
      setError('请先上传一份会议纪要 Word 文档')
      return
    }
    setError('')
    setStep('analyzing')
    setStatusMsg('正在结合项目工作推进表分析会议纪要，并生成待审核草稿…')
    try {
      if (!documentFile) {
        setError('请重新选择会议纪要 Word 文档')
        setStep('input')
        return
      }
      const run = await createProjectMeetingDocumentRun(projectId, documentFile)
      setStatusMsg(`Agent 正在分析（${run.stage || 'reading'}）…`)
      const status = await pollProjectMeetingDocumentRun(run.id, {
        onStatus: (next) => {
          setStatusMsg(`Agent 正在${next.stage || next.status}，已完成 ${next.step_count} 步项目上下文查询…`)
        },
      })
      if (status.status === 'failed') {
        setError(`会议纪要 Agent 分析失败${status.error_code ? `（${status.error_code}）` : ''}：${status.error_message || '请检查模型配置后重试'}`)
        setStep('input')
        return
      }
      const completedRun = await fetchProjectMeetingDocumentRun(run.id)
      if (!completedRun.meeting) {
        setError('会议纪要 Agent 已完成，但未生成可审核的会议草稿')
        setStep('input')
        return
      }
      onCreated(completedRun.meeting)
    } catch (cause: unknown) {
      setError(`会议纪要分析失败：${cause instanceof Error ? cause.message : String(cause)}`)
      setStep('input')
    }
  }

  async function handleClarificationContinue() {
    if (!skillRun) return
    setError('')
    const unresolvedMaterials = skillRun.questions.filter((item) => item.action === 'material_upload' && !item.resolved_at)
    try {
      if (unresolvedMaterials.length) {
        if (!documentText.trim()) {
          setError('请先为缺失材料上传 Word、Excel 或 TXT 文件')
          return
        }
        const refreshed = await addMeetingSkillSnapshot(skillRun.id, {
          transcript_text: analysisText,
          reference_files: skillReferenceFiles,
        })
        setSkillRun(refreshed)
        if (refreshed.status === 'waiting_for_answers') return
        await generateAfterPreflight(refreshed)
        return
      }

      const answers = skillRun.questions
        .filter((item) => item.action === 'answer' && !item.resolved_at)
        .map((item) => ({ question_id: item.id, value: clarificationValues[item.id] || undefined }))
      if (answers.some((item) => !item.value)) {
        setError('请明确处置所有阻断问题后再继续')
        return
      }
      const updated = await answerMeetingSkillQuestions(skillRun.id, answers)
      setSkillRun(updated)
      await generateAfterPreflight(updated)
    } catch (cause: unknown) {
      setError(`澄清处理失败：${cause instanceof Error ? cause.message : String(cause)}`)
    }
  }

  function chooseMissingMaterial(questionCode: string) {
    setDocumentReferenceKind(questionCode.replace(/_missing$/, ''))
    documentRef.current?.click()
  }

  async function handleLegacyAnalyze() {
    if (!analysisText.trim()) {
      setError('请至少添加一份会议材料后再生成草稿')
      return
    }
    setError('')
    setStep('analyzing')
    setStatusMsg('AI 正在整理会议材料并生成通用会议纪要草稿…')
    try {
      const result: MeetingAnalyzeResult = await analyzeMeeting(analysisText, projectId)
      setAnalysisId(result.analysis_id)
      setForm((previous) => ({
        ...previous,
        title: previous.title || result.title,
        meeting_date: previous.meeting_date || result.meeting_date,
        host: previous.host || result.host,
        summary: result.summary,
        reports_json: result.reports_json ?? '[]',
        task_list_json: result.task_list_json,
        confirmed_items_json: result.confirmed_items_json ?? '[]',
        decision_items_json: result.decision_items_json,
        risk_items_json: result.risk_items_json,
        transcript_text: analysisText,
        source_mode: 'ai_analysis',
      }))
      setStep('review')
    } catch (cause: unknown) {
      setError(`AI 分析失败：${cause instanceof Error ? cause.message : String(cause)}`)
      setStep('input')
    }
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const { confirmed_items_json, reports_json: _reportsJson, ...meetingForm } = form
      const payload = { project_id: projectId, ...meetingForm, risk_items_json: confirmed_items_json, skill_run_id: skillRun?.id, analysis_id: analysisId }
      const item = isEdit && editItem
        ? await updateMeeting(editItem.id, payload)
        : await createMeeting(payload)
      if (isEdit || analysisId === null) {
        onCreated(item)
      } else {
        setSavedMeeting(item)
        setReviewMeetingId(item.id)
      }
    } catch (cause: unknown) {
      setError(`保存失败：${cause instanceof Error ? cause.message : String(cause)}`)
    } finally {
      setSaving(false)
    }
  }

  const steps = [
    { key: 'input' as ModalStep, label: '会议设置与材料' },
    { key: 'analyzing' as ModalStep, label: 'AI 生成草稿' },
    { key: 'clarifying' as ModalStep, label: '确认待核事实' },
    { key: 'review' as ModalStep, label: '确认保存' },
  ]
  const currentIdx = isEdit ? 2 : steps.findIndex((item) => item.key === step)
  const memberNames = Array.from(new Set(
    projectMembers
      .map((member) => member.person_name_snapshot.trim())
      .filter(Boolean),
  ))

  const singleMemberField = (
    label: '主持人' | '整理人',
    key: 'host' | 'organizer',
    placeholder: string,
  ) => (
    <div>
      <label className="mb-1 block text-xs font-semibold text-slate-700">{label}</label>
      {membersLoadFailed ? (
        <input
          aria-label={label}
          type="text"
          value={form[key]}
          onChange={(event) => setField(key, event.target.value)}
          placeholder={placeholder}
          className="w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-sky-500"
        />
      ) : (
        <select
          aria-label={label}
          value={form[key]}
          onChange={(event) => setField(key, event.target.value)}
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-sky-500"
        >
          <option value="">{memberNames.length ? placeholder : '暂无可选成员'}</option>
          {memberNames.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      )}
    </div>
  )

  if (reviewMeetingId !== null && savedMeeting) {
    const finishReview = () => onCreated(savedMeeting)
    return <MeetingChangeSetReviewModal meetingId={reviewMeetingId} onClose={finishReview} onDone={finishReview} />
  }

  return (
    <>
          <div className="meeting-workbench-shell flex min-h-0 flex-1 flex-col overflow-hidden bg-[#F5F8FC]" style={{ fontFamily: 'Inter, sans-serif' }}>
            <header className="flex min-h-[80px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-5 py-3 lg:px-7">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#0069b4] text-lg text-white">▤</div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">{isEdit ? '编辑会议纪要' : '新建会议纪要'}</h1>
              <p className="mt-0.5 text-sm text-slate-500">上传会议纪要 Word，AI 将结合项目上下文生成草稿</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg px-3 py-2 text-sm text-slate-500 transition hover:bg-slate-100 hover:text-slate-800">关闭</button>
        </header>

            <div className="shrink-0 border-b border-slate-200 bg-white px-5 lg:px-7">
              <div className="mx-auto flex max-w-[1280px] items-center gap-2 py-2.5">
            {steps.map((item, index) => {
              const active = currentIdx === index
              const done = currentIdx > index
              return (
                <div key={item.key} className="flex items-center gap-2">
                  {index > 0 && <span className="mx-2 h-px w-10 bg-slate-200" />}
                  <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${done || active ? 'bg-sky-600 text-white' : 'bg-slate-100 text-slate-400'}`}>{done ? '✓' : index + 1}</span>
                  <span className={`text-sm ${active ? 'font-medium text-sky-700' : 'text-slate-400'}`}>{item.label}</span>
                </div>
              )
            })}
          </div>
        </div>

            <main className="meeting-workbench-main min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
          {step === 'input' && (
            <div className="mx-auto max-w-[1280px] space-y-8 px-5 py-7 pb-32 lg:px-7">
              <section className="meeting-new-information-card rounded-2xl border border-slate-300 bg-white p-6 shadow-sm">
                <SectionTitle>会议信息</SectionTitle>
                <div className="mt-5 grid gap-x-5 gap-y-4 lg:grid-cols-3">
                  <Field label="会议主题" value={form.title} onChange={(value) => setField('title', value)} placeholder="例如：项目推进周例会" />
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-slate-700">会议日期</label>
                    <input type="date" value={form.meeting_date} onChange={(event) => setField('meeting_date', event.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-sky-500" />
                  </div>
                  <Field label="会议地点" value={form.location} onChange={(value) => setField('location', value)} placeholder="线上会议或具体地点" />
                  {singleMemberField('主持人', 'host', '请选择主持人')}
                  <Field label="参会人员" value={form.participants} onChange={(value) => setField('participants', value)} placeholder="可选，多人用顿号或逗号分隔" />
                  {singleMemberField('整理人', 'organizer', '请选择整理人')}
                  <div className="lg:col-span-3">
                    <Field label="抄送" value={form.copied_to} onChange={(value) => setField('copied_to', value)} placeholder="项目全体成员" />
                  </div>
                </div>
              </section>

              <section className="meeting-new-material-card rounded-2xl border border-slate-300 bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <SectionTitle>会议材料</SectionTitle>
                    <p className="mt-1 text-sm text-slate-400">材料可以同时添加，AI 会合并分析；暂不支持 PDF。</p>
                  </div>
                  <span className="text-sm text-slate-400">已添加 {sourceCount} 份材料</span>
                </div>
                <div className="mt-5 grid gap-4 lg:grid-cols-3">
                  <div className="rounded-xl border border-dashed border-sky-200 bg-sky-50/50 p-4">
                    <div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-slate-800">上传会议纪要 Word</h3><p className="mt-1 text-xs leading-5 text-slate-500">仅支持已整理的 Word（.docx）会议纪要；本流程只读取文档内容。</p></div><SourceStatus text={documentText} emptyLabel="未上传" /></div>
                    {documentName && <p className="mt-3 truncate text-xs text-slate-600">{documentName}</p>}
                    <button type="button" onClick={() => documentRef.current?.click()} disabled={documentUploading} className="mt-4 rounded-lg border border-sky-200 bg-white px-3 py-2 text-sm font-medium text-sky-700 hover:bg-sky-50 disabled:opacity-50">{documentUploading ? '读取中…' : documentText ? '更换文档' : '选择 Word'}</button>
                    <input ref={documentRef} type="file" accept=".docx" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void handleDocumentSelected(file); event.currentTarget.value = '' }} />
                  </div>

                </div>
              </section>
              {error && <ErrorBar msg={error} />}
            </div>
          )}

          {step === 'analyzing' && (
            <div className="mx-auto flex max-w-[1180px] flex-col items-center py-28 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-100 text-2xl text-sky-600 animate-pulse">✦</div>
              <h2 className="mt-5 text-lg font-semibold text-slate-800">{statusMsg}</h2>
              <p className="mt-2 text-sm text-slate-400">已汇总 {sourceCount} 份材料，请稍候。</p>
            </div>
          )}

          {step === 'clarifying' && skillRun && (
            <div className="mx-auto max-w-[920px] space-y-5 px-8 py-10 pb-32">
              <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
                <p className="text-sm font-semibold text-amber-900">生成已暂停，需先完成以下核对</p>
                <p className="mt-2 text-sm leading-6 text-amber-800">这些问题来自当前材料快照。完成后系统会以新的答案版本或材料快照继续运行，不会在预检阶段生成纪要草稿。</p>
              </section>
              {skillRun.questions.filter((item) => !item.resolved_at).map((question) => (
                <section key={question.id} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-base font-semibold text-slate-900">{question.question}</h2>
                      <p className="mt-1 text-xs text-slate-500">{question.blocking ? '阻断项：明确处置后才能开始生成' : '非阻断项'}</p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">{question.question_kind}</span>
                  </div>
                  {question.evidence.length > 0 && <div className="mt-4 rounded-xl bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-600">{question.evidence.map((item, index) => <p key={`${item.source_id}-${index}`}>{item.locator}{item.quote ? `：${item.quote}` : ''}</p>)}</div>}
                  {question.action === 'material_upload' ? (
                    <div className="mt-5 flex flex-wrap items-center gap-3"><button type="button" onClick={() => chooseMissingMaterial(question.code)} className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-2 text-sm font-medium text-sky-700 hover:bg-sky-100">补充文件</button><span className="text-xs text-slate-500">支持 Word、Excel、TXT；补充后会创建新的材料快照并重新预检。</span></div>
                  ) : question.answer_mode === 'single_choice' && question.options.length ? (
                    <div className="mt-5 flex flex-wrap gap-2">{question.options.map((option) => <button key={option.value} type="button" onClick={() => setClarificationValues((previous) => ({ ...previous, [question.id]: option.value }))} className={`rounded-lg border px-3 py-2 text-sm ${clarificationValues[question.id] === option.value ? 'border-sky-500 bg-sky-50 text-sky-700' : 'border-slate-200 text-slate-700 hover:bg-slate-50'}`}>{option.label || option.value}</button>)}</div>
                  ) : <textarea value={clarificationValues[question.id] || ''} onChange={(event) => setClarificationValues((previous) => ({ ...previous, [question.id]: event.target.value }))} placeholder="填写确认后的事实" className="mt-5 min-h-28 w-full resize-y rounded-lg border border-slate-200 p-3 text-sm leading-6 outline-none focus:border-sky-400" />}
                </section>
              ))}
              {error && <ErrorBar msg={error} />}
            </div>
          )}

          {step === 'review' && (
            <div className="mx-auto max-w-[1180px] px-8 py-8 pb-32">
              <div className="space-y-6">
                {form.source_mode === 'standard_minutes' && <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">已按标准会议纪要读取：原文中的议程、决议、本周待办和上周追踪将直接保留，不经过 AI 改写。</div>}
                <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <SectionTitle>确认会议信息</SectionTitle>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <Field label="会议主题" value={form.title} onChange={(value) => setField('title', value)} />
                    <Field label="会议类型" value={form.meeting_type} onChange={(value) => setField('meeting_type', value)} />
                    <Field label="会议日期" value={form.meeting_date} onChange={(value) => setField('meeting_date', value)} />
                    <Field label="会议地点" value={form.location} onChange={(value) => setField('location', value)} />
                    <Field label="主持人" value={form.host} onChange={(value) => setField('host', value)} />
                    <Field label="参会人员" value={form.participants} onChange={(value) => setField('participants', value)} />
                    <Field label="整理人" value={form.organizer} onChange={(value) => setField('organizer', value)} />
                    <Field label="抄送" value={form.copied_to} onChange={(value) => setField('copied_to', value)} />
                  </div>
                </section>
                <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><SectionTitle>会议小结与决议</SectionTitle><textarea className="mt-3 min-h-28 w-full resize-y rounded-lg border border-slate-200 p-3 text-sm leading-7 text-slate-700 outline-none focus:border-sky-400" value={form.summary} onChange={(event) => setField('summary', event.target.value)} /></section>
                {form.source_mode === 'standard_minutes' ? <StandardMinutesReview form={form} /> : <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><ReportsSection reportsJson={form.reports_json} /><div className="space-y-5"><JsonListSection label="会议议程" value={form.agenda_items_json} onChange={(value) => setField('agenda_items_json', value)} dotColor="#0EA5E9" /><JsonListSection label="已确认事项" value={form.confirmed_items_json} onChange={(value) => setField('confirmed_items_json', value)} dotColor="#10B981" /><JsonListSection label="待决策事项" value={form.decision_items_json} onChange={(value) => setField('decision_items_json', value)} dotColor="#F59E0B" /><JsonListSection label="本周待办" value={form.task_list_json} onChange={(value) => setField('task_list_json', value)} dotColor="#0EA5E9" /><JsonListSection label="上周待办追踪" value={form.prior_action_items_json} onChange={(value) => setField('prior_action_items_json', value)} dotColor="#8B5CF6" /></div></section>}
                {error && <ErrorBar msg={error} />}
              </div>
            </div>
          )}
        </main>

        {step === 'clarifying' && (
          <footer className="meeting-new-footer flex shrink-0 items-center justify-between border-t border-slate-200 bg-white px-5 py-4 shadow-[0_-6px_18px_rgba(15,23,42,0.04)] lg:px-7">
            <button onClick={() => setStep('input')} className="rounded-lg px-3 py-2 text-sm text-slate-500 hover:bg-slate-100">返回修改材料</button>
            <button onClick={() => void handleClarificationContinue()} disabled={documentUploading} className="rounded-lg bg-sky-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40">确认并继续</button>
          </footer>
        )}

        {step !== 'analyzing' && step !== 'clarifying' && (
          <footer className="meeting-new-footer flex shrink-0 items-center justify-between border-t border-slate-200 bg-white px-5 py-4 shadow-[0_-6px_18px_rgba(15,23,42,0.04)] lg:px-7">
            {step === 'review' ? <button onClick={() => (isEdit ? onClose() : setStep('input'))} className="rounded-lg px-3 py-2 text-sm text-slate-500 hover:bg-slate-100">{isEdit ? '取消' : '返回修改'}</button> : <button onClick={onClose} className="rounded-lg px-3 py-2 text-sm text-slate-500 hover:bg-slate-100">取消</button>}
            {step === 'input' ? <button onClick={() => void handleAnalyze()} disabled={!analysisText.trim() || documentUploading} className="rounded-lg bg-sky-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40">AI 生成草稿</button> : <button onClick={() => void handleSave()} disabled={saving} className="rounded-lg bg-sky-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50">{saving ? '保存中…' : isEdit ? '保存修改' : '保存草稿'}</button>}
          </footer>
        )}
      </div>

    </>
  )
}
