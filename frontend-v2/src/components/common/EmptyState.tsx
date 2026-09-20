type EmptyStateProps = {
  title?: string
  description?: string
}

export function EmptyState({ title = '暂无数据', description }: EmptyStateProps) {
  return (
    <div className="center-message">
      <div className="center-message-title">{title}</div>
      {description ? <div className="center-message-subtitle">{description}</div> : null}
    </div>
  )
}
