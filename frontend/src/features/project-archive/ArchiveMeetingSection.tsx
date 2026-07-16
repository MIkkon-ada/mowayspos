import { Link } from 'react-router-dom'
import type { MeetingItem } from '../../types'
import { formatArchiveDate, parseMeetingDecisions } from './projectArchiveViewModel'

export function ArchiveMeetingSection({ projectId, meetings, error }: { projectId: number; meetings: MeetingItem[]; error?: string }) {
  return (
    <section id="archive-meetings" className="archive-section">
      <div className="archive-section-title-row">
        <div><span className="archive-section-eyebrow">MEETINGS & DECISIONS</span><h2>会议与决策</h2></div>
        <Link className="archive-text-link archive-print-hidden" to={`/work/meetings?projectId=${projectId}`}>查看会议纪要 <span>›</span></Link>
      </div>
      <article className="archive-card archive-meetings-card">
        {error ? <div className="archive-module-error">{error}</div> : meetings.length === 0 ? (
          <div className="archive-empty archive-empty--meeting">暂无会议与决策记录</div>
        ) : (
          <div className="archive-meeting-list">
            {meetings.map((meeting) => {
              const decisions = parseMeetingDecisions(meeting)
              return (
                <article key={meeting.id} className="archive-meeting-row">
                  <div className="archive-meeting-row__date"><strong>{formatArchiveDate(meeting.meeting_date)}</strong><span>{meeting.meeting_type || '项目会议'}</span></div>
                  <div className="archive-meeting-row__main">
                    <div className="archive-meeting-row__heading"><h3>{meeting.title || `会议 #${meeting.id}`}</h3><span>{meeting.publish_status || '未发布'}</span></div>
                    <p><strong>主持人：</strong>{meeting.host || '未记录'}</p>
                    <p>{meeting.summary || '暂无会议摘要'}</p>
                    <div className="archive-decision-box">
                      <strong>决策事项</strong>
                      {decisions.length > 0 ? <ul>{decisions.map((decision, index) => <li key={`${meeting.id}-${index}`}>{decision}</li>)}</ul> : <span>{meeting.summary ? '暂无结构化决策' : '暂无结构化决策'}</span>}
                    </div>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </article>
    </section>
  )
}
