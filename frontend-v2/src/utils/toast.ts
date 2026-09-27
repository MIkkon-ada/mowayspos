type ToastType = 'success' | 'error' | 'info' | 'warning'

export type ToastItem = {
  id: number
  type: ToastType
  message: string
}

type Listener = (toasts: ToastItem[]) => void

let items: ToastItem[] = []
let nextId = 1
const listeners = new Set<Listener>()

function broadcast() {
  const snapshot = [...items]
  listeners.forEach((l) => l(snapshot))
}

function add(type: ToastType, message: string, duration = 3500) {
  const id = nextId++
  items = [...items, { id, type, message }]
  broadcast()
  setTimeout(() => {
    items = items.filter((t) => t.id !== id)
    broadcast()
  }, duration)
}

export function subscribeToasts(listener: Listener): () => void {
  listeners.add(listener)
  listener([...items])
  return () => listeners.delete(listener)
}

export const toast = {
  success: (msg: string) => add('success', msg),
  error:   (msg: string) => add('error', msg),
  info:    (msg: string) => add('info', msg),
  warning: (msg: string) => add('warning', msg),
}
