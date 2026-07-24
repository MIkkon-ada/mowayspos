import { useCallback, useRef, useState } from 'react'

type UseVoiceRecorderArgs = {
  setText: (updater: string | ((prev: string) => string)) => void
  setError: (value: string | null) => void
}

type WorkletMessage =
  | { type: 'pcm'; buffer: ArrayBuffer }
  | { type: 'silence'; duration: number }

export function useVoiceRecorder({ setText, setError }: UseVoiceRecorderArgs) {
  const [recording, setRecording] = useState(false)
  const [timer, setTimer] = useState(0)

  const stoppingRef = useRef(false)
  const recordingRef = useRef(false)
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const clearTimer = useCallback(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
  }, [])

  /** 上次更新 DOM 的时间戳，用于平滑渲染 */
  const lastRenderRef = useRef(0)
  /** 已完成的句子（final=true 的结果累积） */
  const finalizedTextRef = useRef('')
  /** 当前正在识别的句子（final=false 的部分结果） */
  const currentSentenceRef = useRef('')

  /** 将识别结果平滑更新到 UI：每 ~50ms 刷新一次，避免高频 setState 造成的卡顿 */
  const smoothSetText = useCallback(
    (text: string, final: boolean) => {
      if (final) {
        // 句子识别完成，累积到已完成文本
        finalizedTextRef.current = (finalizedTextRef.current + text).replace(/\s+/g, ' ').trim()
        currentSentenceRef.current = ''
      } else {
        // 部分结果，更新当前句子
        currentSentenceRef.current = text
      }

      const fullText = currentSentenceRef.current
        ? finalizedTextRef.current + currentSentenceRef.current
        : finalizedTextRef.current

      const now = performance.now()
      // final 结果立即刷新；非 final 结果节流到 50ms 一次
      if (final || now - lastRenderRef.current >= 50) {
        lastRenderRef.current = now
        setText(() => fullText)
      }
    },
    [setText],
  )

  /** 提交最后一次待渲染的文本 */
  const flushPendingText = useCallback(() => {
    const fullText = currentSentenceRef.current
      ? finalizedTextRef.current + currentSentenceRef.current
      : finalizedTextRef.current
    if (fullText) {
      setText(() => fullText)
    }
  }, [setText])

  const cleanup = useCallback(() => {
    stoppingRef.current = true
    recordingRef.current = false
    clearTimer()

    const ws = wsRef.current
    if (ws) {
      try {
        if (ws.readyState === WebSocket.OPEN) ws.send('stop')
        ws.close(1000)
      } catch {
        /* ignore */
      }
      wsRef.current = null
    }

    const ctx = audioCtxRef.current
    if (ctx && ctx.state !== 'closed') {
      try {
        ctx.close()
      } catch {
        /* ignore */
      }
      audioCtxRef.current = null
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }

    lastRenderRef.current = 0
  }, [clearTimer])

  const stopRecording = useCallback(async () => {
    if (stoppingRef.current) return
    stoppingRef.current = true
    recordingRef.current = false
    clearTimer()

    const ws = wsRef.current
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send('stop')
    }

    // 等待后端返回最后一批结果
    await new Promise((resolve) => setTimeout(resolve, 1500))

    if (ws && ws.readyState !== WebSocket.CLOSED && ws.readyState !== WebSocket.CLOSING) {
      ws.close(1000)
    }
    wsRef.current = null

    audioCtxRef.current?.close()
    audioCtxRef.current = null

    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null

    flushPendingText()
    setRecording(false)
  }, [clearTimer, flushPendingText])

  const startRecording = useCallback(async () => {
    setError(null)
    setText('')
    cleanup()
    stoppingRef.current = false
    lastRenderRef.current = 0
    finalizedTextRef.current = ''
    currentSentenceRef.current = ''

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('当前浏览器不支持录音，请使用 Chrome 或 Edge 最新版')
      return
    }

    // 16kHz AudioContext — 浏览器内置重采样器有专业抗混叠滤波
    let audioCtx: AudioContext
    try {
      audioCtx = new AudioContext({ sampleRate: 16000 })
    } catch {
      setError('当前浏览器不支持 16kHz 录音，请升级 Chrome 或 Edge 到最新版')
      return
    }
    audioCtxRef.current = audioCtx

    // 加载 AudioWorklet
    try {
      await audioCtx.audioWorklet.addModule('/worklets/pcm-audio-processor.js')
    } catch {
      audioCtx.close()
      audioCtxRef.current = null
      setError('浏览器不支持语音处理，请使用 Chrome 或 Edge 最新版')
      return
    }

    // 获取麦克风
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
      })
    } catch (err) {
      audioCtx.close()
      audioCtxRef.current = null
      if (err instanceof DOMException && err.name === 'NotAllowedError') {
        setError('麦克风权限被拒绝，请在浏览器设置中允许使用麦克风')
      } else {
        setError('启动录音失败，请重试')
      }
      return
    }
    streamRef.current = stream

    // WebSocket 连接
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/api/transcribe/stream`)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    // 等待握手完成
    let preOpenServerError = ''
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('语音服务连接超时，请重试')), 6000)

      ws.onopen = () => {
        clearTimeout(timeout)
        ws.onmessage = null
        resolve()
      }

      ws.onclose = (e) => {
        clearTimeout(timeout)
        let msg = ''
        if (preOpenServerError) {
          msg = preOpenServerError
        } else if (e.code === 4001) {
          msg = '未登录，请重新登录后重试'
        } else if (e.code === 4002) {
          msg = '未配置语音识别服务，请联系管理员配置 Dashscope API Key'
        } else if (e.code === 4003) {
          msg = '语音识别服务启动失败，请检查 Dashscope API Key 是否有效'
        } else if (e.code === 1006 || !e.wasClean) {
          msg = '语音服务连接异常，请检查网络后重试'
        }
        reject(new Error(msg || '语音服务连接失败'))
      }

      ws.onerror = () => {
        clearTimeout(timeout)
        reject(new Error('语音服务连接失败，请重试'))
      }

      ws.onmessage = (e) => {
        if (typeof e.data === 'string') {
          try {
            const msg = JSON.parse(e.data)
            if (msg.error) preOpenServerError = msg.error
          } catch {
            /* ignore */
          }
        }
      }
    })

    // 处理识别结果 — 用节流避免高频 setState 导致 UI 卡顿
    ws.onmessage = (e) => {
      if (typeof e.data !== 'string') return
      try {
        const msg = JSON.parse(e.data)
        if (!msg.text) return

        smoothSetText(msg.text, Boolean(msg.final))
      } catch {
        /* ignore */
      }
    }

    ws.onclose = () => {
      if (!stoppingRef.current && recordingRef.current) {
        setError('语音服务连接中断，请重新录音')
      }
    }

    // 连接 AudioWorklet → PCM 帧立刻转发到 WebSocket（不积攒缓冲）
    let frameCount = 0
    try {
      const workletNode = new AudioWorkletNode(audioCtx, 'pcm-audio-processor')
      workletNode.port.onmessage = (e: MessageEvent<WorkletMessage>) => {
        const msg = e.data
        if (msg.type === 'pcm') {
          frameCount++
          const w = wsRef.current
          if (w?.readyState === WebSocket.OPEN) {
            w.send(msg.buffer)
          }
        }
      }
      const source = audioCtx.createMediaStreamSource(stream)
      source.connect(workletNode)
    } catch {
      cleanup()
      setError('音频处理模块加载失败，请重试')
      return
    }

    recordingRef.current = true
    setRecording(true)
    setTimer(0)
    timerIntervalRef.current = setInterval(() => setTimer((prev) => prev + 1), 1000)
  }, [setText, setError, cleanup, smoothSetText, stopRecording])

  return { recording, transcribing: false, timer, startRecording, stopRecording }
}
