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
  types: Set<ServerMessage['type']>
  resolve: (message: ServerMessage | null) => void
  timer: ReturnType<typeof setTimeout>
}

const SOCKET_TIMEOUT_MS = 6000
const DONE_TIMEOUT_MS = 8000
const FLUSH_TIMEOUT_MS = 1000

export function useVoiceRecorder(args: UseVoiceRecorderArgs) {
  const [recorderState, setRecorderState] = useState<RecorderState>('idle')
  const [timer, setTimer] = useState(0)

  const argsRef = useRef(args)
  argsRef.current = args
  const stateRef = useRef<RecorderState>('idle')
  const stoppingRef = useRef(false)
  const intentionalCloseRef = useRef(false)
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
  const stopRef = useRef<() => Promise<void>>(async () => {})

  const updateState = useCallback((next: RecorderState) => {
    stateRef.current = next
    setRecorderState(next)
  }, [])

  const clearTimer = useCallback(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
  }, [])

  const resolveWaiters = useCallback((message: ServerMessage | null) => {
    for (const waiter of [...waitersRef.current]) {
      if (message && !waiter.types.has(message.type) && message.type !== 'error') continue
      clearTimeout(waiter.timer)
      waitersRef.current.delete(waiter)
      waiter.resolve(message)
    }
  }, [])

  const waitForMessage = useCallback((
    expected: ServerMessage['type'] | ServerMessage['type'][],
    timeoutMs = SOCKET_TIMEOUT_MS,
  ) => {
    const types = new Set(Array.isArray(expected) ? expected : [expected])
    return new Promise<ServerMessage | null>((resolve) => {
      const waiter: Waiter = {
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

  const fail = useCallback((message: string) => {
    clearTimer()
    if (stateRef.current !== 'completed' && stateRef.current !== 'failed') {
      updateState('failed')
    }
    argsRef.current.setError(message)
  }, [clearTimer, updateState])

  const releaseMedia = useCallback(async () => {
    flushWaiterRef.current = null
    try {
      sourceRef.current?.disconnect()
    } catch {
      // The graph may already be disconnected.
    }
    sourceRef.current = null
    try {
      workletRef.current?.disconnect()
    } catch {
      // The graph may already be disconnected.
    }
    if (workletRef.current) workletRef.current.port.onmessage = null
    workletRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    const context = audioCtxRef.current
    audioCtxRef.current = null
    if (context && context.state !== 'closed') {
      try {
        await context.close()
      } catch {
        // Cleanup must stay idempotent.
      }
    }
  }, [])

  const cleanup = useCallback(async (closeSocket = true) => {
    clearTimer()
    resolveWaiters(null)
    await releaseMedia()
    const socket = wsRef.current
    wsRef.current = null
    if (closeSocket && socket && socket.readyState < WebSocket.CLOSING) {
      intentionalCloseRef.current = true
      try {
        socket.close(1000)
      } catch {
        // Cleanup must stay idempotent.
      }
    }
  }, [clearTimer, releaseMedia, resolveWaiters])

  const installSocketHandlers = useCallback((ws: WebSocket) => {
    ws.onmessage = (event) => {
      if (typeof event.data !== 'string') return
      const message = parseServerMessage(event.data)
      if (!message) return

      // Wake protocol waiters before applying terminal UI state.
      resolveWaiters(message)

      if (message.type === 'transcript' && stateRef.current !== 'failed') {
        transcriptRef.current = mergeTranscript(transcriptRef.current, message)
        argsRef.current.setText(() => composeTranscript(transcriptRef.current))
        return
      }
      if (message.type === 'error') {
        fail(message.message)
        return
      }
      if (message.type === 'done' && stateRef.current !== 'failed') {
        clearTimer()
        updateState('completed')
      }
    }

    const handleTransportFailure = () => {
      if (wsRef.current !== ws) return
      resolveWaiters(null)
      if (
        !intentionalCloseRef.current
        && ['connecting', 'starting', 'recording', 'stopping'].includes(stateRef.current)
      ) {
        fail('语音服务连接中断，请检查已识别文字后重试')
      }
    }
    ws.onerror = handleTransportFailure
    ws.onclose = handleTransportFailure
  }, [clearTimer, fail, resolveWaiters, updateState])

  const openSocket = useCallback((ws: WebSocket) => new Promise<boolean>((resolve) => {
    if (ws.readyState === WebSocket.OPEN) {
      resolve(true)
      return
    }
    const timeout = setTimeout(() => resolve(false), SOCKET_TIMEOUT_MS)
    ws.addEventListener('open', () => {
      clearTimeout(timeout)
      resolve(true)
    }, { once: true })
    ws.addEventListener('close', () => {
      clearTimeout(timeout)
      resolve(false)
    }, { once: true })
  }), [])

  const startMicrophone = useCallback(async (ws: WebSocket) => {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('当前浏览器不支持录音，请使用最新版 Chrome 或 Edge')
    }

    let context: AudioContext | null = null
    let stream: MediaStream | null = null
    let node: AudioWorkletNode | null = null
    let source: MediaStreamAudioSourceNode | null = null
    try {
      context = new AudioContext({ sampleRate: 16000 })
      audioCtxRef.current = context
      await context.audioWorklet.addModule('/worklets/pcm-audio-processor.js')

      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      streamRef.current = stream
      node = new AudioWorkletNode(context, 'pcm-audio-processor')
      workletRef.current = node
      source = context.createMediaStreamSource(stream)
      sourceRef.current = source

      node.port.onmessage = (event: MessageEvent<WorkletMessage>) => {
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
            fail('网络发送积压过高，录音已停止，请检查已识别文字后重试')
            void stopRef.current()
          }
          return
        }
        ws.send(message.buffer)
      }
      source.connect(node)
      node.connect(context.destination)
    } catch (error) {
      await releaseMedia()
      if (error instanceof DOMException && error.name === 'NotAllowedError') {
        throw new Error('麦克风权限被拒绝，请在浏览器设置中允许使用麦克风')
      }
      throw error instanceof Error ? error : new Error('启动录音失败，请重试')
    }
  }, [fail, releaseMedia])

  const stopRecording = useCallback(async () => {
    if (stoppingRef.current || !['recording', 'failed'].includes(stateRef.current)) return
    stoppingRef.current = true
    clearTimer()
    if (stateRef.current !== 'failed') updateState('stopping')

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

    await releaseMedia()
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fail('语音服务连接已断开，请检查已识别文字后重试')
      await cleanup()
      return
    }

    // Register before sending because the server may answer immediately.
    const terminal = waitForMessage(['done', 'error'], DONE_TIMEOUT_MS)
    ws.send(JSON.stringify({ type: 'stop' }))
    const result = await terminal
    if (!result) {
      fail('语音收尾超时，请检查最后一句是否完整')
      await cleanup()
      return
    }
    if (result.type === 'error') {
      await cleanup()
      return
    }
    if (!tailWasFlushed) {
      argsRef.current.setError('录音已完成，但尾帧确认超时，请检查最后一句是否完整')
    }
    await cleanup()
  }, [cleanup, clearTimer, fail, releaseMedia, updateState, waitForMessage])
  stopRef.current = stopRecording

  const startRecording = useCallback(async () => {
    if (!['idle', 'completed', 'failed'].includes(stateRef.current)) return
    const { projectId, selectedTaskId, canRecord, initialText, setError } = argsRef.current
    setError(null)
    if (!canRecord || !projectId || !selectedTaskId) {
      fail('请先选择执行中的项目和关键任务')
      return
    }

    await cleanup()
    stoppingRef.current = false
    intentionalCloseRef.current = false
    backpressureRef.current = false
    transcriptRef.current = emptyTranscript(initialText)
    setTimer(0)
    updateState('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/transcribe/stream`)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws
    installSocketHandlers(ws)

    // Waiters are installed before the socket can deliver the corresponding event.
    const ready = waitForMessage('ready')
    if (!await openSocket(ws) || (await ready)?.type !== 'ready') {
      if (stateRef.current !== 'failed') fail('语音服务连接超时，请重试')
      await cleanup()
      return
    }

    updateState('starting')
    const started = waitForMessage('started')
    ws.send(JSON.stringify({
      type: 'start',
      scene: 'work_report',
      project_id: projectId,
      selected_task_id: selectedTaskId,
      sample_rate: 16000,
      format: 'pcm',
    }))
    const startResult = await started
    if (startResult?.type !== 'started') {
      if (stateRef.current !== 'failed') fail('语音识别启动超时，请重试')
      await cleanup()
      return
    }

    try {
      await startMicrophone(ws)
    } catch (error) {
      fail(error instanceof Error ? error.message : '启动录音失败，请重试')
      await cleanup()
      return
    }

    updateState('recording')
    timerIntervalRef.current = setInterval(() => setTimer((value) => value + 1), 1000)
  }, [cleanup, fail, installSocketHandlers, openSocket, startMicrophone, updateState, waitForMessage])

  useEffect(() => () => {
    stoppingRef.current = true
    intentionalCloseRef.current = true
    void cleanup()
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
