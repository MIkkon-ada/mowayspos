import { useCallback, useEffect, useRef, useState } from 'react'
import {
  composeTranscript,
  emptyTranscript,
  mergeTranscript,
  parseServerMessage,
  type RecorderState,
  type ServerMessage,
  type TranscriptState,
} from './voiceRecorderProtocol'

type UseVoiceRecorderArgs = {
  projectId: number | null
  selectedTaskId: number | null
  canRecord: boolean
  initialText: string
  setText: (updater: string | ((prev: string) => string)) => void
  setError: (value: string | null) => void
}

type WorkletMessage =
  | { type: 'pcm'; buffer: ArrayBuffer }
  | { type: 'flushed' }

type Waiter = {
  attempt: number
  types: Set<ServerMessage['type']>
  resolve: (message: ServerMessage | null) => void
  timer: ReturnType<typeof setTimeout>
}

const SOCKET_TIMEOUT_MS = 6000
const DONE_TIMEOUT_MS = 8000
const FLUSH_TIMEOUT_MS = 1000

async function releaseLocalMedia(
  context: AudioContext | null,
  stream: MediaStream | null,
  source: MediaStreamAudioSourceNode | null,
  node: AudioWorkletNode | null,
) {
  try {
    source?.disconnect()
  } catch {
    // A partially-created graph may already be disconnected.
  }
  try {
    node?.disconnect()
  } catch {
    // A partially-created graph may already be disconnected.
  }
  if (node) node.port.onmessage = null
  stream?.getTracks().forEach((track) => track.stop())
  if (context && context.state !== 'closed') {
    try {
      await context.close()
    } catch {
      // Cleanup is best-effort and idempotent.
    }
  }
}

export function useVoiceRecorder(args: UseVoiceRecorderArgs) {
  const [recorderState, setRecorderState] = useState<RecorderState>('idle')
  const [timer, setTimer] = useState(0)

  const argsRef = useRef(args)
  argsRef.current = args
  const stateRef = useRef<RecorderState>('idle')
  const mountedRef = useRef(true)
  const mediaActiveRef = useRef(false)
  const startInFlightRef = useRef(false)
  const startOwnerRef = useRef<number | null>(null)
  const terminalRef = useRef(false)
  const attemptGenerationRef = useRef(0)
  const stoppingRef = useRef(false)
  const intentionalCloseSocketsRef = useRef(new WeakSet<WebSocket>())
  const backpressureRef = useRef(false)
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const flushWaiterRef = useRef<(() => void) | null>(null)
  const transcriptRef = useRef<TranscriptState>(emptyTranscript(''))
  const waitersRef = useRef(new Set<Waiter>())

  const updateState = useCallback((next: RecorderState) => {
    stateRef.current = next
    mediaActiveRef.current = ['connecting', 'starting', 'recording', 'stopping'].includes(next)
    if (mountedRef.current) setRecorderState(next)
  }, [])

  const clearTimer = useCallback(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
  }, [])

  const resolveWaiters = useCallback((message: ServerMessage | null, attempt: number) => {
    for (const waiter of [...waitersRef.current]) {
      if (waiter.attempt !== attempt) continue
      if (message && !waiter.types.has(message.type) && message.type !== 'error') continue
      clearTimeout(waiter.timer)
      waitersRef.current.delete(waiter)
      waiter.resolve(message)
    }
  }, [])

  const waitForMessage = useCallback((
    expected: ServerMessage['type'] | ServerMessage['type'][],
    attempt: number,
    timeoutMs = SOCKET_TIMEOUT_MS,
  ) => {
    const types = new Set(Array.isArray(expected) ? expected : [expected])
    return new Promise<ServerMessage | null>((resolve) => {
      const waiter: Waiter = {
        attempt,
        types,
        resolve,
        timer: setTimeout(() => {
          waitersRef.current.delete(waiter)
          resolve(null)
        }, timeoutMs),
      }
      waitersRef.current.add(waiter)
    })
  }, [])

  const releaseAttachedMedia = useCallback(async () => {
    const context = audioCtxRef.current
    const stream = streamRef.current
    const source = sourceRef.current
    const node = workletRef.current
    const flushWaiter = flushWaiterRef.current
    audioCtxRef.current = null
    streamRef.current = null
    sourceRef.current = null
    workletRef.current = null
    flushWaiterRef.current = null
    flushWaiter?.()
    await releaseLocalMedia(context, stream, source, node)
  }, [])

  const cleanup = useCallback(async (options?: {
    invalidateAttempt?: boolean
    preserveAttempt?: number
  }) => {
    const invalidateAttempt = options?.invalidateAttempt ?? true
    const preserveAttempt = options?.preserveAttempt

    // Atomically detach every owned resource before the first await.
    const socket = wsRef.current
    const context = audioCtxRef.current
    const stream = streamRef.current
    const source = sourceRef.current
    const node = workletRef.current
    const flushWaiter = flushWaiterRef.current
    wsRef.current = null
    audioCtxRef.current = null
    streamRef.current = null
    sourceRef.current = null
    workletRef.current = null
    flushWaiterRef.current = null

    if (invalidateAttempt) attemptGenerationRef.current += 1
    if (socket) intentionalCloseSocketsRef.current.add(socket)
    clearTimer()
    flushWaiter?.()

    const capturedWaiters = [...waitersRef.current].filter(
      (waiter) => waiter.attempt !== preserveAttempt,
    )
    for (const waiter of capturedWaiters) {
      clearTimeout(waiter.timer)
      waitersRef.current.delete(waiter)
      waiter.resolve(null)
    }

    await releaseLocalMedia(context, stream, source, node)
    if (socket && socket.readyState < WebSocket.CLOSING) {
      try {
        socket.close(1000)
      } catch {
        // Cleanup must stay idempotent.
      }
    }
  }, [clearTimer])

  const finishTerminal = useCallback(async (
    next: Extract<RecorderState, 'completed' | 'failed'>,
    message?: string,
    socket?: WebSocket,
    attempt = attemptGenerationRef.current,
  ) => {
    if (!mountedRef.current) return
    if (attemptGenerationRef.current !== attempt) return
    if (socket && wsRef.current !== socket) return
    if (terminalRef.current) return
    if (next === 'completed' && stateRef.current === 'failed') return

    terminalRef.current = true
    clearTimer()
    updateState(next)
    if (message) argsRef.current.setError(message)
    await cleanup({ invalidateAttempt: true })
  }, [cleanup, clearTimer, updateState])

  const ownsAttempt = useCallback((ws: WebSocket, attempt: number) => (
    mountedRef.current
    && wsRef.current === ws
    && attemptGenerationRef.current === attempt
  ), [])

  const installSocketHandlers = useCallback((ws: WebSocket, attempt: number) => {
    ws.onmessage = (event) => {
      if (!ownsAttempt(ws, attempt)) return
      if (typeof event.data !== 'string') return
      const message = parseServerMessage(event.data)
      if (!message) return

      // Wake protocol waiters before applying terminal UI state.
      resolveWaiters(message, attempt)

      if (message.type === 'transcript' && !terminalRef.current) {
        transcriptRef.current = mergeTranscript(transcriptRef.current, message)
        argsRef.current.setText(() => composeTranscript(transcriptRef.current))
        return
      }
      if (message.type === 'error') {
        void finishTerminal('failed', message.message, ws, attempt)
        return
      }
      if (message.type === 'done' && stateRef.current !== 'failed') {
        void finishTerminal('completed', undefined, ws, attempt)
      }
    }

    const handleTransportFailure = () => {
      if (!ownsAttempt(ws, attempt)) return
      if (intentionalCloseSocketsRef.current.has(ws)) return
      resolveWaiters(null, attempt)
      if (
        ['connecting', 'starting', 'recording', 'stopping'].includes(stateRef.current)
      ) {
        void finishTerminal(
          'failed',
          '语音服务连接中断，请检查已识别文字后重试',
          ws,
          attempt,
        )
      }
    }
    ws.onerror = handleTransportFailure
    ws.onclose = handleTransportFailure
  }, [finishTerminal, ownsAttempt, resolveWaiters])

  const openSocket = useCallback((ws: WebSocket) => new Promise<boolean>((resolve) => {
    if (ws.readyState === WebSocket.OPEN) {
      resolve(true)
      return
    }
    let settled = false
    const cleanupListeners = () => {
      clearTimeout(timeout)
      ws.removeEventListener('open', finishWithSuccess)
      ws.removeEventListener('close', finishWithFailure)
      ws.removeEventListener('error', finishWithFailure)
    }
    const finishWithSuccess = () => {
      if (settled) return
      settled = true
      cleanupListeners()
      resolve(true)
    }
    const finishWithFailure = () => {
      if (settled) return
      settled = true
      cleanupListeners()
      resolve(false)
    }
    const timeout = setTimeout(finishWithFailure, SOCKET_TIMEOUT_MS)
    ws.addEventListener('open', finishWithSuccess)
    ws.addEventListener('close', finishWithFailure)
    ws.addEventListener('error', finishWithFailure)
  }), [])

  const isCurrentAttempt = useCallback((attempt: number, ws: WebSocket) => (
    ownsAttempt(ws, attempt)
    && ws.readyState === WebSocket.OPEN
    && !terminalRef.current
    && stateRef.current !== 'failed'
    && stateRef.current !== 'completed'
  ), [ownsAttempt])

  const ownsStartAttempt = useCallback((attempt: number, ws?: WebSocket) => (
    mountedRef.current
    && startInFlightRef.current
    && startOwnerRef.current === attempt
    && attemptGenerationRef.current === attempt
    && (!ws || isCurrentAttempt(attempt, ws))
  ), [isCurrentAttempt])

  const startMicrophone = useCallback(async (ws: WebSocket, attempt: number) => {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('当前浏览器不支持录音，请使用最新版 Chrome 或 Edge')
    }

    let context: AudioContext | null = null
    let stream: MediaStream | null = null
    let node: AudioWorkletNode | null = null
    let source: MediaStreamAudioSourceNode | null = null
    try {
      context = new AudioContext({ sampleRate: 16000 })
      await context.audioWorklet.addModule('/worklets/pcm-audio-processor.js')
      if (!ownsStartAttempt(attempt, ws)) {
        await releaseLocalMedia(context, stream, source, node)
        return false
      }

      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      if (!ownsStartAttempt(attempt, ws)) {
        await releaseLocalMedia(context, stream, source, node)
        return false
      }

      node = new AudioWorkletNode(context, 'pcm-audio-processor')
      source = context.createMediaStreamSource(stream)

      node.port.onmessage = (event: MessageEvent<WorkletMessage>) => {
        if (!isCurrentAttempt(attempt, ws)) return
        const message = event.data
        if (message.type === 'flushed') {
          flushWaiterRef.current?.()
          flushWaiterRef.current = null
          return
        }
        if (message.type !== 'pcm' || ws.readyState !== WebSocket.OPEN) return
        if (ws.bufferedAmount > 512 * 1024) {
          if (!backpressureRef.current) {
            backpressureRef.current = true
            void finishTerminal(
              'failed',
              '网络发送积压过高，录音已停止，请检查已识别文字后重试',
              ws,
              attempt,
            )
          }
          return
        }
        ws.send(message.buffer)
      }
      source.connect(node)
      node.connect(context.destination)
      if (!ownsStartAttempt(attempt, ws)) {
        await releaseLocalMedia(context, stream, source, node)
        return false
      }

      audioCtxRef.current = context
      streamRef.current = stream
      workletRef.current = node
      sourceRef.current = source
      return true
    } catch (error) {
      await releaseLocalMedia(context, stream, source, node)
      if (error instanceof DOMException && error.name === 'NotAllowedError') {
        throw new Error('麦克风权限被拒绝，请在浏览器设置中允许使用麦克风')
      }
      throw error instanceof Error ? error : new Error('启动录音失败，请重试')
    }
  }, [finishTerminal, isCurrentAttempt, ownsStartAttempt])

  const stopRecording = useCallback(async () => {
    if (stoppingRef.current || stateRef.current !== 'recording') return
    const attempt = attemptGenerationRef.current
    stoppingRef.current = true
    clearTimer()
    updateState('stopping')

    const node = workletRef.current
    let tailWasFlushed = true
    if (node) {
      const flushed = new Promise<void>((resolve) => {
        flushWaiterRef.current = resolve
      })
      node.port.postMessage({ type: 'stop' })
      tailWasFlushed = await Promise.race([
        flushed.then(() => true),
        new Promise<false>((resolve) => setTimeout(() => resolve(false), FLUSH_TIMEOUT_MS)),
      ])
    }

    if (terminalRef.current || attemptGenerationRef.current !== attempt) return
    await releaseAttachedMedia()
    if (terminalRef.current || attemptGenerationRef.current !== attempt) return
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      await finishTerminal(
        'failed',
        '语音服务连接已断开，请检查已识别文字后重试',
        undefined,
        attempt,
      )
      return
    }

    // Register before sending because the server may answer immediately.
    const terminal = waitForMessage(['done', 'error'], attempt, DONE_TIMEOUT_MS)
    ws.send(JSON.stringify({ type: 'stop' }))
    const result = await terminal
    if (!result) {
      await finishTerminal('failed', '语音收尾超时，请检查最后一句是否完整', ws, attempt)
      return
    }
    if (result.type === 'error') return
    if (!tailWasFlushed) {
      argsRef.current.setError('录音已完成，但尾帧确认超时，请检查最后一句是否完整')
    }
  }, [clearTimer, finishTerminal, releaseAttachedMedia, updateState, waitForMessage])

  const startRecording = useCallback(async () => {
    if (!mountedRef.current) return
    if (startInFlightRef.current || mediaActiveRef.current) return
    startInFlightRef.current = true
    const attempt = attemptGenerationRef.current + 1
    attemptGenerationRef.current = attempt
    startOwnerRef.current = attempt
    terminalRef.current = false
    stoppingRef.current = false
    backpressureRef.current = false
    setTimer(0)
    updateState('connecting')

    try {
      argsRef.current.setError(null)

      // Dispose a previous terminal session without invalidating this claimed attempt.
      await cleanup({ invalidateAttempt: false, preserveAttempt: attempt })
      if (!ownsStartAttempt(attempt)) return

      const { projectId, selectedTaskId, canRecord, initialText, setError } = argsRef.current
      if (!canRecord || !projectId || !selectedTaskId) {
        terminalRef.current = true
        updateState('failed')
        setError('请先选择执行中的项目和关键任务')
        return
      }

      transcriptRef.current = emptyTranscript(initialText)
      if (!ownsStartAttempt(attempt)) return
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/api/transcribe/stream`)
      if (!ownsStartAttempt(attempt)) {
        intentionalCloseSocketsRef.current.add(ws)
        ws.close(1000)
        return
      }
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws
      installSocketHandlers(ws, attempt)

      // Waiters are installed before the socket can deliver the corresponding event.
      const ready = waitForMessage('ready', attempt)
      const opened = await openSocket(ws)
      const readyResult = await ready
      if (!opened || readyResult?.type !== 'ready' || !ownsStartAttempt(attempt, ws)) {
        if (ownsAttempt(ws, attempt) && !terminalRef.current) {
          await finishTerminal('failed', '语音服务连接超时，请重试', ws, attempt)
        }
        return
      }

      updateState('starting')
      const started = waitForMessage('started', attempt)
      ws.send(JSON.stringify({
        type: 'start',
        scene: 'work_report',
        project_id: projectId,
        selected_task_id: selectedTaskId,
        sample_rate: 16000,
        format: 'pcm',
      }))
      const startResult = await started
      if (startResult?.type !== 'started' || !ownsStartAttempt(attempt, ws)) {
        if (ownsAttempt(ws, attempt) && !terminalRef.current) {
          await finishTerminal('failed', '语音识别启动超时，请重试', ws, attempt)
        }
        return
      }

      const attached = await startMicrophone(ws, attempt)
      if (!attached || !ownsStartAttempt(attempt, ws)) return
      updateState('recording')
      if (!ownsStartAttempt(attempt, ws)) return
      timerIntervalRef.current = setInterval(() => {
        if (mountedRef.current && attemptGenerationRef.current === attempt) {
          setTimer((value) => value + 1)
        }
      }, 1000)
    } catch (error) {
      const ws = wsRef.current
      if (ownsStartAttempt(attempt) && (!ws || ownsAttempt(ws, attempt))) {
        await finishTerminal(
          'failed',
          error instanceof Error ? error.message : '启动录音失败，请重试',
          ws ?? undefined,
          attempt,
        )
      }
    } finally {
      if (startOwnerRef.current === attempt) {
        startOwnerRef.current = null
        startInFlightRef.current = false
      }
    }
  }, [
    cleanup,
    finishTerminal,
    installSocketHandlers,
    openSocket,
    ownsAttempt,
    ownsStartAttempt,
    startMicrophone,
    updateState,
    waitForMessage,
  ])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      stoppingRef.current = true
      terminalRef.current = true
      startInFlightRef.current = false
      startOwnerRef.current = null
      attemptGenerationRef.current += 1
      void cleanup({ invalidateAttempt: false })
    }
  }, [cleanup])

  const recording = recorderState === 'recording'
  const transcribing = recorderState === 'connecting'
    || recorderState === 'starting'
    || recorderState === 'stopping'

  return {
    recorderState,
    recording,
    transcribing,
    timer,
    startRecording,
    stopRecording,
  }
}
