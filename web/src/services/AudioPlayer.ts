import { FiLog } from './FiLog';

export class AudioPlayer {
  private current: HTMLAudioElement | null = null;

  /** Play base64-encoded MP3 audio (AWS Polly output). Resolves when done. */
  async playBase64Mp3(base64: string): Promise<void> {
    this.stop();
    FiLog.i('AudioPlayer', `Decoding b64 audio (len=${base64.length})`);

    try {
      const binary = atob(base64);
      const bytes  = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: 'audio/mpeg' });
      const url  = URL.createObjectURL(blob);

      await new Promise<void>((resolve) => {
        const audio = new Audio(url);
        this.current = audio;
        audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
        audio.onerror = () => { URL.revokeObjectURL(url); resolve(); };
        audio.play().catch(() => resolve());
      });
    } catch (err) {
      FiLog.e('AudioPlayer', 'Playback failed', err);
    }
  }

  stop(): void {
    if (this.current) {
      this.current.pause();
      this.current = null;
    }
  }
}
