import type { MeetingItem } from '../../types'

type Props = { meetings: MeetingItem[]; loading: boolean; onOpen: (meeting: MeetingItem) => void }

function todoCount(raw?: string) { try { const data: unknown = JSON.parse(raw || '[]'); return Array.isArray(data) ? data.length : 0 } catch { return 0 } }

export function MobileMeetingTimeline({ meetings, loading, onOpen }: Props) {
  if (loading) return <div className="px-4 py-10 text-center text-sm text-slate-400">加载中...</div>
  if (!meetings.length) return <div className="px-4 py-10 text-center text-sm text-slate-400">还没有会议纪要</div>
  return <section className="space-y-3 px-4 pb-24" aria-label="会议时间线">
    {meetings.map((meeting) => <button type="button" key={meeting.id} onClick={() => onOpen(meeting)} className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm active:bg-slate-50">
      <div className="flex items-start justify-between gap-3"><h2 className="min-w-0 text-sm font-bold leading-5 text-slate-800">{meeting.title || '未命名会议'}</h2><span className="shrink-0 rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-semibold text-sky-700">{meeting.publish_status || '草稿'}</span></div>
      <p className="mt-2 text-xs text-slate-500">{meeting.meeting_date || '时间待定'} · {meeting.related_special_project || '未关联项目'}</p>
      <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{meeting.summary || '暂无会议摘要'}</p>
      <p className="mt-3 text-xs font-semibold text-sky-700">待办 {todoCount(meeting.task_list_json)} 项 →</p>
    </button>)}
  </section>
}
