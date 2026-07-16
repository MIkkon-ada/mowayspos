export const ARCHIVE_SECTIONS = [
  { id: 'archive-overview', label: '档案总览' },
  { id: 'archive-project-info', label: '项目基本信息' },
  { id: 'archive-progress', label: '工作推进快照' },
  { id: 'archive-assets', label: '成果与问题' },
  { id: 'archive-meetings', label: '会议与决策' },
  { id: 'archive-close-review', label: '结束复盘' },
  { id: 'archive-approvals', label: '审批记录' },
  { id: 'archive-operations', label: '操作记录' },
] as const

export function ArchiveSectionNav({ activeId, onSelect }: { activeId: string; onSelect: (id: string) => void }) {
  return (
    <nav className="archive-section-nav" aria-label="项目档案导航">
      <div className="archive-section-nav__title">项目档案导航</div>
      <div className="archive-section-nav__list">
        {ARCHIVE_SECTIONS.map((section, index) => (
          <button
            key={section.id}
            type="button"
            className={`archive-section-nav__item ${activeId === section.id ? 'is-active' : ''}`}
            aria-current={activeId === section.id ? 'location' : undefined}
            onClick={() => onSelect(section.id)}
          >
            <span>{section.label}</span>
            <span className="archive-section-nav__number">{index + 1}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}
