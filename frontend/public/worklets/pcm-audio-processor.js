/**
 * AudioWorklet processor for 16kHz mono Float32 audio.
 *
 * Audio is converted to signed Int16 PCM and sent in 100ms packets. RMS-based
 * silence messages are diagnostics only: silent samples are never discarded
 * and silence never stops the processor.
 */

const TARGET_SAMPLE_RATE = 16000;
const DEFAULT_PACKET_SAMPLES = TARGET_SAMPLE_RATE / 10;
const MIN_PACKET_SAMPLES = 640;
const MAX_PACKET_SAMPLES = 4000;
const SILENCE_THRESHOLD = 0.015;
const SILENCE_DURATION_LIMIT = 2.0;
const FRAMES_PER_NOTIFY = 10;

class PcmAudioProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const configuredPacketSamples = options?.processorOptions?.packetSamples;
    this._packetSamples = Number.isInteger(configuredPacketSamples)
      && configuredPacketSamples >= MIN_PACKET_SAMPLES
      && configuredPacketSamples <= MAX_PACKET_SAMPLES
      ? configuredPacketSamples
      : DEFAULT_PACKET_SAMPLES;
    this._packet = new Float32Array(this._packetSamples);
    this._packetLength = 0;
    this._silentSampleCount = 0;
    this._frameCount = 0;
    this._stopped = false;
    this._flushed = false;
    this.port.onmessage = (event) => {
      if (event.data?.type === "stop") this._stop();
    };
  }

  _toPcm(samples) {
    const output = new Int16Array(samples.length);
    for (let index = 0; index < samples.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, samples[index]));
      output[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
    return output.buffer;
  }

  _rms(samples) {
    let sum = 0;
    for (let index = 0; index < samples.length; index += 1) {
      sum += samples[index] * samples[index];
    }
    return Math.sqrt(sum / samples.length);
  }

  _emitPcm(samples) {
    const buffer = this._toPcm(samples);
    this.port.postMessage({ type: "pcm", buffer }, [buffer]);
  }

  _recordRms(channelData) {
    const energy = this._rms(channelData);
    if (energy < SILENCE_THRESHOLD) {
      this._silentSampleCount += channelData.length;
    } else {
      this._silentSampleCount = 0;
    }

    this._frameCount += 1;
    if (this._frameCount % FRAMES_PER_NOTIFY !== 0) return;

    const silenceDuration = this._silentSampleCount / TARGET_SAMPLE_RATE;
    if (silenceDuration >= SILENCE_DURATION_LIMIT) {
      this.port.postMessage({
        type: "silence",
        duration: Math.round(silenceDuration * 10) / 10,
      });
    }
  }

  _append(channelData) {
    let sourceOffset = 0;
    while (sourceOffset < channelData.length) {
      const copyLength = Math.min(
        this._packetSamples - this._packetLength,
        channelData.length - sourceOffset,
      );
      this._packet.set(
        channelData.subarray(sourceOffset, sourceOffset + copyLength),
        this._packetLength,
      );
      this._packetLength += copyLength;
      sourceOffset += copyLength;

      if (this._packetLength === this._packetSamples) {
        this._emitPcm(this._packet);
        this._packetLength = 0;
      }
    }
  }

  _stop() {
    if (this._flushed) return;

    this._stopped = true;
    if (this._packetLength > 0) {
      this._emitPcm(this._packet.subarray(0, this._packetLength));
      this._packetLength = 0;
    }
    this.port.postMessage({ type: "flushed" });
    this._flushed = true;
  }

  process(inputs) {
    if (this._stopped) return false;

    const channelData = inputs[0]?.[0];
    if (!channelData || channelData.length === 0) return true;

    this._recordRms(channelData);
    this._append(channelData);
    return true;
  }
}

registerProcessor("pcm-audio-processor", PcmAudioProcessor);
