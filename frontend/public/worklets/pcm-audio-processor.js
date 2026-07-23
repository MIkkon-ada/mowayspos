/**
 * AudioWorklet 处理器：在独立线程中完成降采样、PCM 编码、VAD 静音检测。
 *
 * 输入：浏览器原生采样率（通常 44.1k/48k）的单声道 Float32
 * 输出：通过 MessagePort 回传主线程
 *   - { type: "pcm", buffer: ArrayBuffer }  → Int16 PCM @ 16kHz（发送给后端）
 *   - { type: "silence", duration: number }  → 连续静音时长（秒），主线程决定是否停止录音
 */

const TARGET_SAMPLE_RATE = 16000;
const SILENCE_THRESHOLD = 0.015; // RMS 阈值，低于此值视为静音
const SILENCE_DURATION_LIMIT = 2.0; // 连续静音超过此值通知主线程
const FRAMES_PER_NOTIFY = 5; // 每 N 帧检测一次静音状态，避免过于频繁

class PcmAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._silenceFrames = 0;
    this._frameCount = 0;
    this._inputSampleRate = sampleRate; // AudioWorklet 全局变量
    this._ratio = this._inputSampleRate / TARGET_SAMPLE_RATE;

    // 监听主线程消息（目前仅用于优雅关闭）
    this.port.onmessage = (e) => {
      if (e.data?.type === "stop") {
        this._stopped = true;
      }
    };
  }

  /**
   * 降采样：简单取平均（对语音识别够用，AudioWorklet 内必须高效）
   */
  _downsample(input) {
    const inLen = input.length;
    const outLen = Math.round(inLen / this._ratio);
    const out = new Float32Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const start = Math.round(i * this._ratio);
      const end = Math.min(Math.round((i + 1) * this._ratio), inLen);
      let sum = 0;
      const count = end - start;
      if (count > 0) {
        for (let j = start; j < end; j++) sum += input[j];
        out[i] = sum / count;
      }
    }
    return out;
  }

  /**
   * Float32 → Int16 PCM
   */
  _toPcm(samples) {
    const out = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out.buffer;
  }

  /**
   * 计算 RMS 能量
   */
  _rms(samples) {
    let sum = 0;
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i] * samples[i];
    }
    return Math.sqrt(sum / samples.length);
  }

  process(inputs, outputs, parameters) {
    if (this._stopped) return false;

    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) {
      return true; // 继续等待
    }

    const channelData = input[0]; // Float32Array，浏览器原生采样率

    // 降采样到 16kHz
    const resampled = this._downsample(channelData);

    // VAD 静音检测
    const energy = this._rms(resampled);
    if (energy < SILENCE_THRESHOLD) {
      this._silenceFrames++;
    } else {
      this._silenceFrames = 0;
    }

    this._frameCount++;

    // 每 N 帧通知主线程一次静音状态
    if (this._frameCount % FRAMES_PER_NOTIFY === 0) {
      const silenceDuration =
        (this._silenceFrames * resampled.length) / TARGET_SAMPLE_RATE;
      if (silenceDuration >= SILENCE_DURATION_LIMIT) {
        this.port.postMessage({
          type: "silence",
          duration: Math.round(silenceDuration * 10) / 10,
        });
      }
    }

    // 编码为 PCM 并发送给主线程
    const pcmBuffer = this._toPcm(resampled);
    this.port.postMessage(
      { type: "pcm", buffer: pcmBuffer },
      [pcmBuffer] // transfer，零拷贝
    );

    return true; // 继续处理
  }
}

registerProcessor("pcm-audio-processor", PcmAudioProcessor);
