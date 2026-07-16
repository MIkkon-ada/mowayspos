import type { ArchiveTimelineEvent } from './projectArchiveViewModel'
import { formatArchiveDateTime } from './projectArchiveViewModel'

export function ArchiveTimeline({ events, compact = true, onMore }: { events: ArchiveTimelineEvent[]; compact?: boolean; onMore?: () => void }) {
  const visible = compact ? events.slice(0, 8) : events
  return (
    <div className={`archive-timeline ${compact ? 'archive-timeline--compact' : ''}`}>
      <div className="archive-card-heading">
        <div>
          <span className="archive-card-kicker">LIFECYCLE</span>
          <h2>关键时间线</h2>
        </div>
        <span className="archive-card-count">{events.length}</span>
      </div>
      {visible.length === 0 ? (
        <div className="archive-empty archive-empty--timeline">暂无时间线记录</div>
      ) : (
        <ol className="archive-timeline__list">
          {visible.map((event) => (
            <li key={event.id} className={`archive-timeline__event tone-${event.tone}`}>
              <span className="archive-timeline__dot" aria-hidden="true" />
              <div>
                <strong>{event.title}</strong>
                <time>{formatArchiveDateTime(event.at)}</time>
                <p>{event.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
      {compact && events.length > 0 && (
        <button type="button" className="archive-text-link archive-print-hidden" onClick={onMore}>查看更多时间线 <span>›</span></button>
      )}
    </div>
  )
}
