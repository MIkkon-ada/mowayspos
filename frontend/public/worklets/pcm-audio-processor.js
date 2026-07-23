/**
 * AudioWorklet 处理器：Float32 → Int16 PCM 编码 + VAD 静音检测。
 *
 * 不再做降采样 — 改为创建 16kHz AudioContext，让浏览器内置重采样器处理采样率转换。
 * 浏览器重采样器有专业抗混叠滤波器，质量远高于手写的简单平均。
 *
 * 输入：16kHz Float32 单声道（AudioContext 已处理重采样）
 * 输出：通过 MessagePort 回传主线程
 *   - { type: "pcm", buffer: ArrayBuffer }  → Int16 PCM @ 16kHz
 *   - { type: "silence", duration: number }  → 连续静音时长（秒）
 */

const TARGET_SAMPLE_RATE = 16000;
const SILENCE_THRESHOLD = 0.015;
const SILENCE_DURATION_LIMIT = 2.0;
/** 每 N 帧检测一次静音，减少 postMessage 开销 */
const FRAMES_PER_NOTIFY = 10;

class PcmAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._silenceFrames = 0;
    this._frameCount = 0;
    this.port.onmessage = (e) => {
      if (e.data?.type === "stop") this._stopped = true;
    };
  }

  /**
   * Float32 [-1,1] → Int16 PCM
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
   * RMS 能量计算
   */
  _rms(samples) {
    let sum = 0;
    for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
    return Math.sqrt(sum / samples.length);
  }

  process(inputs) {
    if (this._stopped) return false;

    const input = inputs[0];
    if (!input?.[0] || input[0].length === 0) return true;

    const channelData = input[0]; // Float32Array @ 16kHz（浏览器已重采样）

    // VAD 静音检测
    const energy = this._rms(channelData);
    energy < SILENCE_THRESHOLD ? this._silenceFrames++ : (this._silenceFrames = 0);

    this._frameCount++;
    if (this._frameCount % FRAMES_PER_NOTIFY === 0) {
      const silenceDuration = (this._silenceFrames * channelData.length) / TARGET_SAMPLE_RATE;
      if (silenceDuration >= SILENCE_DURATION_LIMIT) {
        this.port.postMessage({ type: "silence", duration: Math.round(silenceDuration * 10) / 10 });
      }
    }

    // Float32 → Int16 PCM，transfer 零拷贝
    const pcmBuffer = this._toPcm(channelData);
    this.port.postMessage({ type: "pcm", buffer: pcmBuffer }, [pcmBuffer]);

    return true;
  }
}

registerProcessor("pcm-audio-processor", PcmAudioProcessor);
