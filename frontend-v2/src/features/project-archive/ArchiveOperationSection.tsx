import type { ArchiveTimelineEvent } from './projectArchiveViewModel'
import { ArchiveTimeline } from './ArchiveTimeline'

export function ArchiveOperationSection({ events, error, administratorView }: { events: ArchiveTimelineEvent[]; error?: string; administratorView: boolean }) {
  return (
    <section id="archive-operations" className="archive-section archive-section--last">
      <div className="archive-section-title-row">
        <div><span className="archive-section-eyebrow">OPERATION HISTORY</span><h2>操作记录</h2></div>
        <span className="archive-section-note">{administratorView ? '管理员审计日志' : '项目生命周期聚合记录'}</span>
      </div>
      <article className="archive-card archive-operation-card">
        {error ? <div className="archive-module-error">{error}</div> : <ArchiveTimeline events={events} compact={false} />}
      </article>
    </section>
  )
}
