import { FiLog } from './FiLog';

/**
 * Web Speech API TTS — used only when the server cannot supply AWS Polly audio.
 * Tries to select a female en-IN voice; falls back to any English female voice,
 * then any English voice.
 */
export class TtsHelper {
  private synth = window.speechSynthesis;
  private voice: SpeechSynthesisVoice | null = null;

  // Known female voice name fragments across browsers / OS
  private static readonly FEMALE_HINTS = [
    'veena', 'heera', 'priya', 'raveena',   // Indian English female
    'samantha', 'victoria', 'karen', 'moira', 'fiona', 'tessa',
    'female', 'woman', 'girl',
  ];

  constructor() {
    const pickVoice = () => {
      const voices = this.synth.getVoices();

      const isFemaleHint = (v: SpeechSynthesisVoice) =>
        TtsHelper.FEMALE_HINTS.some(h => v.name.toLowerCase().includes(h));

      this.voice =
        // 1. Female en-IN
        voices.find(v => v.lang.startsWith('en-IN') && isFemaleHint(v)) ??
        // 2. Any en-IN
        voices.find(v => v.lang.startsWith('en-IN'))                    ??
        // 3. Female English (any region)
        voices.find(v => v.lang.startsWith('en')   && isFemaleHint(v)) ??
        // 4. Any English
        voices.find(v => v.lang.startsWith('en'))                       ??
        voices[0] ?? null;

      FiLog.i('TTS', `Voice: ${this.voice?.name ?? 'none'} (${this.voice?.lang ?? ''})`);
    };

    pickVoice();
    this.synth.onvoiceschanged = pickVoice;
  }

  speak(text: string): Promise<void> {
    return new Promise((resolve) => {
      if (!this.synth) { resolve(); return; }
      this.synth.cancel();
      const utt    = new SpeechSynthesisUtterance(text);
      if (this.voice) utt.voice = this.voice;
      utt.lang  = 'en-IN';
      utt.rate  = 0.92;
      utt.pitch = 1.1;   // slightly higher pitch → more female-sounding on generic voices
      utt.onend   = () => resolve();
      utt.onerror = () => resolve();
      this.synth.speak(utt);
    });
  }

  stop(): void { this.synth?.cancel(); }
}
