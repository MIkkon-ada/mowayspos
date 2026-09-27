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
  | {
      type: 'started'
      model: string
      session_id: string
      packet_duration_ms: number
      stop_timeout_seconds: number
    }
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
    if (Object.hasOwn(state.confirmed, event.segment_id)) return state

    // The single WebSocket writer preserves provider event order, so only the
    // current partial segment needs tracking; cross-segment reordering is out of scope.
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
  return (
    field === null
    || (typeof field === 'number' && Number.isFinite(field) && field >= 0)
  )
}

function trimmedNonBlank(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

export function parseServerMessage(raw: string): ServerMessage | null {
  try {
    const value: unknown = JSON.parse(raw)
    if (!isRecord(value) || typeof value.type !== 'string') return null

    if (value.type === 'ready') {
      return { type: 'ready' }
    }

    if (value.type === 'started') {
      const model = trimmedNonBlank(value.model)
      const sessionId = trimmedNonBlank(value.session_id)
      const packetDurationMs = value.packet_duration_ms
      const stopTimeoutSeconds = value.stop_timeout_seconds
      if (
        !model
        || !sessionId
        || typeof packetDurationMs !== 'number'
        || !Number.isInteger(packetDurationMs)
        || packetDurationMs < 40
        || packetDurationMs > 250
        || typeof stopTimeoutSeconds !== 'number'
        || !Number.isFinite(stopTimeoutSeconds)
        || stopTimeoutSeconds < 2
        || stopTimeoutSeconds > 30
      ) return null
      return {
        type: 'started',
        model,
        session_id: sessionId,
        packet_duration_ms: packetDurationMs,
        stop_timeout_seconds: stopTimeoutSeconds,
      }
    }

    if (value.type === 'transcript') {
      const segmentId = trimmedNonBlank(value.segment_id)
      if (
        !segmentId
        || typeof value.text !== 'string'
        || !value.text.trim()
        || typeof value.final !== 'boolean'
        || !isOptionalTime(value, 'begin_time')
        || !isOptionalTime(value, 'end_time')
      ) return null

      const beginTime = value.begin_time
      const endTime = value.end_time
      if (
        typeof beginTime === 'number'
        && typeof endTime === 'number'
        && endTime < beginTime
      ) return null

      const message: TranscriptMessage = {
        type: 'transcript',
        segment_id: segmentId,
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

    if (value.type === 'done') {
      const sessionId = trimmedNonBlank(value.session_id)
      if (
        !sessionId
        || typeof value.duration_ms !== 'number'
        || !Number.isFinite(value.duration_ms)
        || value.duration_ms < 0
      ) return null
      return {
        type: 'done',
        session_id: sessionId,
        duration_ms: value.duration_ms,
      }
    }

    if (value.type === 'error') {
      const code = trimmedNonBlank(value.code)
      const message = trimmedNonBlank(value.message)
      if (!code || !message || typeof value.retryable !== 'boolean') return null
      return {
        type: 'error',
        code,
        message,
        retryable: value.retryable,
      }
    }
  } catch {
    return null
  }

  return null
}
