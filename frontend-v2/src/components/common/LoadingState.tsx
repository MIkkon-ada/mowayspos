type LoadingStateProps = {
  text?: string
}

export function LoadingState({ text = '加载中...' }: LoadingStateProps) {
  return (
    <div className="center-message">
      <div className="center-message-title">{text}</div>
    </div>
  )
}
