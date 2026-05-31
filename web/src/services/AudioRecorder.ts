import { FiLog } from './FiLog';

type ChunkCallback = (pcm: ArrayBuffer) => void;

/**
 * Captures microphone audio, downsamples to 16 kHz 16-bit mono PCM via
 * AudioWorklet, and emits 100 ms chunks through [onChunk].
 * Used to stream audio to the server for AWS Transcribe.
 */
export class AudioRecorder {
  private ctx:      AudioContext | null = null;
  private source:   MediaStreamAudioSourceNode | null = null;
  private worklet:  AudioWorkletNode | null = null;
  private running = false;
  private workletReady = false;

  /** Call once to initialise the AudioContext and load the worklet module. */
  async prepare(stream: MediaStream): Promise<void> {
    if (this.workletReady) return;
    this.ctx = new AudioContext();
    const workletUrl = `${import.meta.env.BASE_URL}worklets/pcm-processor.js`;
    await this.ctx.audioWorklet.addModule(workletUrl);
    this.source = this.ctx.createMediaStreamSource(stream);
    this.workletReady = true;
    FiLog.i('AudioRecorder', `Ready — ctx rate=${this.ctx.sampleRate} Hz`);
  }

  start(onChunk: ChunkCallback): void {
    if (this.running || !this.ctx || !this.source) {
      FiLog.w('AudioRecorder', 'Cannot start — not prepared or already running');
      return;
    }
    this.worklet = new AudioWorkletNode(this.ctx, 'pcm-processor');
    this.worklet.port.onmessage = (ev: MessageEvent<ArrayBuffer>) => {
      if (this.running) onChunk(ev.data);
    };
    this.source.connect(this.worklet);
    this.worklet.connect(this.ctx.destination); // needed to keep graph alive
    this.running = true;
    FiLog.i('AudioRecorder', 'Recording started');
  }

  stop(): void {
    if (!this.running) return;
    this.running = false;
    try {
      this.worklet?.disconnect();
      this.worklet?.port.close();
    } catch { /* ignore */ }
    this.worklet = null;
    FiLog.i('AudioRecorder', 'Recording stopped');
  }

  destroy(): void {
    this.stop();
    this.source?.disconnect();
    this.ctx?.close().catch(() => undefined);
    this.ctx    = null;
    this.source = null;
    this.workletReady = false;
  }
}
