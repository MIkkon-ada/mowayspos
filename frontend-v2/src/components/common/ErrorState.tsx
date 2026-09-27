type ErrorStateProps = {
  message: string
  onRetry?: () => void
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="center-message">
      <div className="center-message-title">加载失败</div>
      <div className="center-message-subtitle">{message}</div>
      {onRetry ? (
        <button type="button" className="secondary-button" onClick={onRetry} style={{ marginTop: 12 }}>
          重试
        </button>
      ) : null}
    </div>
  )
}
