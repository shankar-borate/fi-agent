import { FiLog } from './FiLog';

/**
 * Records the full session as a WebM file.
 *
 * When a <video> element is supplied, captures its rendered frames (15 fps)
 * combined with the microphone audio, producing a video/webm.
 * Falls back to audio-only webm when captureStream() is unavailable.
 *
 * Camera switches handled automatically — captureStream() tracks the video
 * element's rendered output, so it follows srcObject changes seamlessly.
 */
export class SessionRecorder {
  private recorder:  MediaRecorder | null = null;
  private chunks:    Blob[] = [];
  private _mimeType  = '';

  // ── Start ──────────────────────────────────────────────────────────────

  start(audioStream: MediaStream, videoEl?: HTMLVideoElement): void {
    if (this.recorder && this.recorder.state !== 'inactive') {
      this.recorder.stop();
    }
    this.chunks    = [];
    this._mimeType = '';

    // Attempt video + audio capture
    let stream   = audioStream;
    let hasVideo = false;

    if (videoEl) {
      const capture: ((fps: number) => MediaStream) | undefined =
        (videoEl as any).captureStream ?? (videoEl as any).mozCaptureStream;
      if (capture) {
        try {
          const vidStream: MediaStream = capture.call(videoEl, 15);
          stream = new MediaStream([
            ...vidStream.getVideoTracks(),
            ...audioStream.getAudioTracks(),
          ]);
          hasVideo = true;
          FiLog.i('SessionRecorder', 'Recording video+audio at 15 fps');
        } catch (e) {
          FiLog.w('SessionRecorder', `captureStream failed — audio only: ${e}`);
        }
      } else {
        FiLog.w('SessionRecorder', 'captureStream not supported — audio only');
      }
    }

    // Pick MIME type matching stream content
    const candidates = hasVideo
      ? ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']
      : ['audio/webm;codecs=opus',     'audio/webm',
         'audio/ogg;codecs=opus',      'audio/mp4'];

    this._mimeType = candidates.find(t => MediaRecorder.isTypeSupported(t)) ?? '';

    const opts: MediaRecorderOptions = this._mimeType ? { mimeType: this._mimeType } : {};
    this.recorder = new MediaRecorder(stream, opts);
    this.recorder.ondataavailable = (e) => { if (e.data.size > 0) this.chunks.push(e.data); };
    this.recorder.onerror = (e) => { FiLog.e('SessionRecorder', 'MediaRecorder error', e); };

    this.recorder.start(2_000); // 2-second timeslice keeps memory footprint low
    FiLog.i('SessionRecorder', `Started — mimeType="${this._mimeType || 'browser default'}"  video=${hasVideo}`);
  }

  // ── Stop ───────────────────────────────────────────────────────────────

  stop(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (!this.recorder) {
        reject(new Error('Recorder not initialized'));
        return;
      }

      // Already stopped but we still have chunks — return what we collected
      if (this.recorder.state === 'inactive') {
        if (this.chunks.length > 0) {
          const blob = this._makeBlob();
          FiLog.i('SessionRecorder', `Already inactive — returning ${blob.size} bytes`);
          resolve(blob);
        } else {
          reject(new Error('No recording data available'));
        }
        return;
      }

      this.recorder.onstop = () => {
        if (this.chunks.length === 0) {
          reject(new Error('Recording produced no data'));
          return;
        }
        const blob = this._makeBlob();
        FiLog.i('SessionRecorder', `Stopped — ${blob.size} bytes  mimeType="${blob.type}"`);
        resolve(blob);
      };

      this.recorder.stop();
    });
  }

  // ── Helpers ────────────────────────────────────────────────────────────

  private _makeBlob(): Blob {
    const type = this.recorder?.mimeType || this._mimeType || 'video/webm';
    return new Blob(this.chunks, { type });
  }

  /** File extension for the recorded blob. */
  get extension(): string {
    if (this._mimeType.includes('mp4')) return '.mp4';
    if (this._mimeType.includes('ogg')) return '.ogg';
    return '.webm';
  }

  get mimeType(): string { return this._mimeType; }

  get isRecording(): boolean {
    return this.recorder?.state === 'recording' || this.recorder?.state === 'paused';
  }
}
