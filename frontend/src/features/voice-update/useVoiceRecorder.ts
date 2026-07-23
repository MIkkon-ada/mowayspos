import { useCallback, useEffect, useRef, useState } from 'react'

type UseVoiceRecorderArgs = {
  setText: (updater: string | ((prev: string) => string)) => void
  setError: (value: string | null) => void
}

/** AudioWorklet 返回消息类型 */
type WorkletMessage =
  | { type: 'pcm'; buffer: ArrayBuffer }
  | { type: 'silence'; duration: number }

export function useVoiceRecorder({ setText, setError }: UseVoiceRecorderArgs) {
  const [recording, setRecording] = useState(false)
  const [timer, setTimer] = useState(0)

  const timerRef = useRef<number | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const committedRef = useRef('')
  const partialRef = useRef('')
  /** 防止 stopRecording 和 VAD 自动停止并发调用 */
  const stoppingRef = useRef(false)

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      cleanup()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const cleanup = useCallback(() => {
    stoppingRef.current = true
    // 先通知 worklet 停止
    if (workletRef.current) {
      try { workletRef.current.port.postMessage({ type: 'stop' }) } catch { /* ignore */ }
      workletRef.current.disconnect()
      workletRef.current = null
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {})
      audioCtxRef.current = null
    }
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    const ws = wsRef.current
    wsRef.current = null
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('stop')
      // 给服务端时间发送最后结果
      setTimeout(() => {
        if (ws.readyState !== WebSocket.CLOSED) ws.close()
      }, 3000)
    }
  }, [])

  const startRecording = useCallback(async () => {
    setError(null)
    stoppingRef.current = false

    // 1. 获取麦克风权限
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setError('麦克风权限被拒绝，请在浏览器地址栏左侧点击锁形图标允许麦克风访问')
      return
    }
    streamRef.current = stream

    committedRef.current = ''
    partialRef.current = ''

    // 2. 建立 WebSocket 连接
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/api/transcribe/stream`)
    wsRef.current = ws

    let serverError: string | null = null
    const opened = await new Promise<boolean>((resolve) => {
      const t = setTimeout(() => resolve(false), 6000)
      ws.addEventListener('open', () => { clearTimeout(t); resolve(true) }, { once: true })
      ws.addEventListener('close', (e) => {
        clearTimeout(t)
        if (!serverError) {
          if (e.code === 4001) serverError = '未登录，请重新登录后重试'
          else if (e.code === 4002) serverError = '未配置语音识别服务，请联系管理员配置 Dashscope API Key'
          else if (e.code === 1006) serverError = '语音服务连接异常，请检查网络后重试'
          else if (!e.wasClean) serverError = '语音服务连接异常，请重试'
        }
        resolve(false)
      }, { once: true })
      ws.addEventListener('error', () => { clearTimeout(t); resolve(false) }, { once: true })
    })

    // 收第一条消息，判断是否为错误
    if (opened && ws.readyState === WebSocket.OPEN) {
      const firstMsg = await new Promise<string | null>((resolve) => {
        const t = setTimeout(() => resolve(null), 3000)
        ws.addEventListener('message', (e) => { clearTimeout(t); resolve(e.data as string) }, { once: true })
        ws.addEventListener('close', () => { clearTimeout(t); resolve(null) }, { once: true })
      })
      if (firstMsg) {
        try {
          const parsed = JSON.parse(firstMsg) as { text?: string; final?: boolean; error?: string }
          if (parsed.error) {
            serverError = parsed.error
            ws.close()
          }
          if (parsed.text && parsed.final) {
            committedRef.current += parsed.text
            setText(committedRef.current)
          } else if (parsed.text) {
            partialRef.current = parsed.text
            setText(committedRef.current + partialRef.current)
          }
        } catch { /* ignore */ }
      }
    }

    if (serverError || !opened || ws.readyState !== WebSocket.OPEN) {
      setError(serverError || '实时转写连接失败，请检查网络')
      stream.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      try { ws.close() } catch { /* ignore */ }
      wsRef.current = null
      return
    }

    // 3. 设置 WebSocket 消息处理
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as { text?: string; final?: boolean; error?: string }
        if (data.error) { setError(data.error); return }
        if (data.text) {
          if (data.final) {
            committedRef.current += data.text
            partialRef.current = ''
          } else {
            partialRef.current = data.text
          }
          setText(committedRef.current + partialRef.current)
        }
      } catch { /* ignore */ }
    }

    ws.onclose = () => {
      // 连接断开时如果不是主动停止，提示用户
      if (!stoppingRef.current && recording) {
        setError('语音服务连接中断，请重新录音')
      }
    }

    ws.onerror = () => {
      if (!stoppingRef.current) setError('实时转写出错，请重试')
    }

    // 4. 创建 AudioContext + AudioWorklet（替代废弃的 ScriptProcessorNode）
    const audioCtx = new AudioContext()
    audioCtxRef.current = audioCtx

    try {
      await audioCtx.audioWorklet.addModule('/worklets/pcm-audio-processor.js')
    } catch (err) {
      setError('浏览器不支持语音处理，请使用 Chrome 或 Edge 最新版')
      cleanup()
      return
    }

    const workletNode = new AudioWorkletNode(audioCtx, 'pcm-audio-processor')
    workletRef.current = workletNode

    // 接收 worklet 消息：PCM 数据 → 发送 WebSocket；静音检测 → 自动停止
    workletNode.port.onmessage = (e: MessageEvent<WorkletMessage>) => {
      const msg = e.data
      if (msg.type === 'pcm') {
        // 发送 PCM 数据到后端
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(msg.buffer)
        }
      } else if (msg.type === 'silence') {
        // 连续静音超过阈值，自动停止录音
        if (!stoppingRef.current) {
          setError(null) // 静音停止不是错误
          stopRecording()
        }
      }
    }

    // 连接音频管线：source → worklet（不需要 connect 到 destination，不需要监听）
    const source = audioCtx.createMediaStreamSource(stream)
    source.connect(workletNode)
    // AudioWorklet 不需要 connect 到 destination（我们不做本地回放）

    // 5. 开始录音
    setRecording(true)
    setTimer(0)
    timerRef.current = window.setInterval(() => setTimer((t) => t + 1), 1000)
  }, [setText, setError, cleanup])

  const stopRecording = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    cleanup()
    setRecording(false)
  }, [cleanup])

  return {
    recording,
    timer,
    startRecording,
    stopRecording,
  }
}
