/**
 * AudioWorkletProcessor: downsamples native sample rate → 16 kHz,
 * converts to Int16 little-endian, emits 100 ms chunks (~3200 bytes).
 * Runs in the AudioWorkletGlobalScope (separate thread).
 */
class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._ratio  = sampleRate / 16000;   // e.g. 48000/16000 = 3
    this._phase  = 0;
    this._buf    = [];
    this._target = 1600;                 // 100 ms × 16 000 Hz
  }

  process(inputs) {
    const ch = inputs[0]?.[0];
    if (!ch) return true;

    // Linear-interpolation downsample to 16 kHz
    while (this._phase < ch.length) {
      const i    = Math.floor(this._phase);
      const frac = this._phase - i;
      const s0   = ch[i];
      const s1   = i + 1 < ch.length ? ch[i + 1] : s0;
      const s    = s0 + frac * (s1 - s0);
      this._buf.push(Math.round(Math.max(-1, Math.min(1, s)) * 32767));
      this._phase += this._ratio;
    }
    this._phase -= ch.length;

    // Emit full 100 ms chunks
    while (this._buf.length >= this._target) {
      const chunk = new Int16Array(this._buf.splice(0, this._target));
      this.port.postMessage(chunk.buffer, [chunk.buffer]);
    }
    return true;
  }
}

registerProcessor('pcm-processor', PcmProcessor);
