import { useLocation, Outlet } from 'react-router-dom'

export function PageTransition() {
  const { pathname } = useLocation()
  return (
    <div
      key={pathname}
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        animation: 'page-enter 0.16s ease-out',
      }}
    >
      <Outlet />
    </div>
  )
}
