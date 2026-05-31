import { FiLog } from './FiLog';

/** Web Speech API TTS — fallback when server doesn't send AWS Polly audio. */
export class TtsHelper {
  private synth = window.speechSynthesis;
  private voice: SpeechSynthesisVoice | null = null;

  constructor() {
    const pickVoice = () => {
      const voices = this.synth.getVoices();
      this.voice =
        voices.find(v => v.lang.startsWith('en-IN')) ??
        voices.find(v => v.lang.startsWith('en'))    ??
        voices[0]                                     ??
        null;
      FiLog.i('TTS', `Voice selected: ${this.voice?.name ?? 'none'}`);
    };
    pickVoice();
    // voices may load asynchronously
    this.synth.onvoiceschanged = pickVoice;
  }

  speak(text: string): Promise<void> {
    return new Promise((resolve) => {
      if (!this.synth) { resolve(); return; }
      this.synth.cancel();
      const utt = new SpeechSynthesisUtterance(text);
      if (this.voice) utt.voice = this.voice;
      utt.lang = 'en-IN';
      utt.rate = 0.95;
      utt.onend   = () => resolve();
      utt.onerror = () => resolve();
      this.synth.speak(utt);
    });
  }

  stop(): void {
    this.synth?.cancel();
  }
}
