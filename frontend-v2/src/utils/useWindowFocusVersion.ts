import { useEffect, useState } from 'react'

/** Returns a version that changes whenever the browser window regains focus. */
export function useWindowFocusVersion(): number {
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const handleFocus = () => setVersion((current) => current + 1)
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [])

  return version
}
