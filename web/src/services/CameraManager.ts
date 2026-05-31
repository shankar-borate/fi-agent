import { FiLog } from './FiLog';

export type FacingMode = 'user' | 'environment';

export class CameraManager {
  private stream:  MediaStream | null = null;
  private facing:  FacingMode = 'user';

  constructor(private readonly videoEl: HTMLVideoElement) {}

  async start(facingMode: FacingMode = 'user'): Promise<void> {
    this.facing = facingMode;
    await this._acquireStream(facingMode);
    FiLog.i('Camera', `Started facing=${facingMode}`);
  }

  async switchCamera(facingMode: FacingMode): Promise<void> {
    if (facingMode === this.facing) return;
    FiLog.i('Camera', `Switching to facing=${facingMode}`);
    this._stopTracks();
    this.facing = facingMode;
    await this._acquireStream(facingMode);
  }

  /** Capture current video frame as a JPEG Blob. */
  capturePhoto(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      const video = this.videoEl;
      if (!video.videoWidth) { reject(new Error('Video not ready')); return; }

      const canvas = document.createElement('canvas');
      canvas.width  = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d')!.drawImage(video, 0, 0);
      canvas.toBlob(
        (blob) => blob ? resolve(blob) : reject(new Error('Canvas toBlob failed')),
        'image/jpeg',
        0.92,
      );
    });
  }

  stop(): void {
    this._stopTracks();
    this.videoEl.srcObject = null;
    FiLog.i('Camera', 'Stopped');
  }

  private async _acquireStream(facingMode: FacingMode): Promise<void> {
    const constraints: MediaStreamConstraints = {
      video: { facingMode, width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    };
    this.stream = await navigator.mediaDevices.getUserMedia(constraints);
    this.videoEl.srcObject = this.stream;
    await this.videoEl.play().catch(() => undefined);
  }

  private _stopTracks(): void {
    this.stream?.getTracks().forEach(t => t.stop());
    this.stream = null;
  }

  getVideoStream(): MediaStream | null { return this.stream; }
}
