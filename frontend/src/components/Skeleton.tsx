const shimmer: React.CSSProperties = {
  background: 'linear-gradient(90deg, var(--bg-page) 25%, #E8EDF3 50%, var(--bg-page) 75%)',
  backgroundSize: '200% 100%',
  animation: 'skeleton-shimmer 1.4s ease infinite',
}

export function Skel({
  width = '100%',
  height = 14,
  radius = 6,
  style,
}: {
  width?: string | number
  height?: number
  radius?: number
  style?: React.CSSProperties
}) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: radius,
        flexShrink: 0,
        ...shimmer,
        ...style,
      }}
    />
  )
}

export function SkeletonStatCard() {
  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 14,
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <Skel width={32} height={32} radius={8} />
      <Skel width="60%" height={22} radius={5} style={{ marginTop: 4 }} />
      <Skel width="45%" height={11} />
    </div>
  )
}

export function SkeletonRow({ lines = 1 }: { lines?: number }) {
  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 10,
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 7,
      }}
    >
      {Array.from({ length: lines }).map((_, i) => (
        <Skel key={i} width={i === 0 ? '75%' : '45%'} height={12} />
      ))}
    </div>
  )
}

export function SkeletonTableRows({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r}>
          {Array.from({ length: cols }).map((_, c) => (
            <td key={c} style={{ padding: '10px 12px' }}>
              <Skel width={c === 0 ? '80%' : c === cols - 1 ? '40%' : '60%'} height={12} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}
