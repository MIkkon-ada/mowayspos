export type RecorderState =
  | 'idle'
  | 'connecting'
  | 'starting'
  | 'recording'
  | 'stopping'
  | 'completed'
  | 'failed'

export type ServerMessage =
  | { type: 'ready' }
  | { type: 'started'; model: string; session_id: string }
  | {
      type: 'transcript'
      segment_id: string
      text: string
      final: boolean
      begin_time?: number | null
      end_time?: number | null
    }
  | { type: 'done'; session_id: string; duration_ms: number }
  | { type: 'error'; code: string; message: string; retryable: boolean }

export type TranscriptState = {
  baseText: string
  order: string[]
  confirmed: Record<string, string>
  partial: { segmentId: string; text: string } | null
}

type TranscriptMessage = Extract<ServerMessage, { type: 'transcript' }>

export function emptyTranscript(baseText: string): TranscriptState {
  return {
    baseText: baseText.trim(),
    order: [],
    confirmed: {},
    partial: null,
  }
}

export function mergeTranscript(
  state: TranscriptState,
  event: TranscriptMessage,
): TranscriptState {
  if (!event.final) {
    return {
      ...state,
      partial: { segmentId: event.segment_id, text: event.text },
    }
  }

  const alreadyConfirmed = Object.hasOwn(state.confirmed, event.segment_id)
  return {
    ...state,
    order: alreadyConfirmed ? state.order : [...state.order, event.segment_id],
    confirmed: { ...state.confirmed, [event.segment_id]: event.text },
    partial: state.partial?.segmentId === event.segment_id ? null : state.partial,
  }
}

export function composeTranscript(state: TranscriptState): string {
  const recognized = [
    ...state.order.map((segmentId) => state.confirmed[segmentId]),
    state.partial?.text ?? '',
  ]
    .filter(Boolean)
    .join('')

  return [state.baseText, recognized].filter(Boolean).join('\n')
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isOptionalTime(value: Record<string, unknown>, key: string): boolean {
  if (!Object.hasOwn(value, key)) return true
  const field = value[key]
  return field === null || (typeof field === 'number' && Number.isFinite(field))
}

export function parseServerMessage(raw: string): ServerMessage | null {
  try {
    const value: unknown = JSON.parse(raw)
    if (!isRecord(value) || typeof value.type !== 'string') return null

    if (value.type === 'ready') {
      return { type: 'ready' }
    }

    if (
      value.type === 'started'
      && typeof value.model === 'string'
      && typeof value.session_id === 'string'
    ) {
      return {
        type: 'started',
        model: value.model,
        session_id: value.session_id,
      }
    }

    if (
      value.type === 'transcript'
      && typeof value.segment_id === 'string'
      && typeof value.text === 'string'
      && typeof value.final === 'boolean'
      && isOptionalTime(value, 'begin_time')
      && isOptionalTime(value, 'end_time')
    ) {
      const message: TranscriptMessage = {
        type: 'transcript',
        segment_id: value.segment_id,
        text: value.text,
        final: value.final,
      }
      if (Object.hasOwn(value, 'begin_time')) {
        message.begin_time = value.begin_time as number | null
      }
      if (Object.hasOwn(value, 'end_time')) {
        message.end_time = value.end_time as number | null
      }
      return message
    }

    if (
      value.type === 'done'
      && typeof value.session_id === 'string'
      && typeof value.duration_ms === 'number'
      && Number.isFinite(value.duration_ms)
    ) {
      return {
        type: 'done',
        session_id: value.session_id,
        duration_ms: value.duration_ms,
      }
    }

    if (
      value.type === 'error'
      && typeof value.code === 'string'
      && typeof value.message === 'string'
      && typeof value.retryable === 'boolean'
    ) {
      return {
        type: 'error',
        code: value.code,
        message: value.message,
        retryable: value.retryable,
      }
    }
  } catch {
    return null
  }

  return null
}
