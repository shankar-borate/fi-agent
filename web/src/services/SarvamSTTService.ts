import { FiLog } from './FiLog';
import { FiConfig } from '../config/FiConfig';

type StartRecording = (onChunk: (chunk: ArrayBuffer) => void) => void;
type StopRecording  = () => void;
type OnPartial      = (text: string) => void;

/**
 * Streams microphone PCM directly to the server's Sarvam proxy WebSocket.
 * The proxy forwards to Sarvam AI (with auth) and relays transcripts back.
 *
 * Usage:
 *   const text = await sarvam.listen(timeoutMs, startRec, stopRec, onPartial);
 */
export class SarvamSTTService {
  private ws: WebSocket | null = null;
  private flushTimer: number | null = null;

  async listen(
    timeoutMs:      number,
    startRecording: StartRecording,
    stopRecording:  StopRecording,
    onPartial:      OnPartial,
  ): Promise<string> {
    const wsUrl = FiConfig.serverUrl
      .replace(/^http:/, 'ws:')
      .replace(/^https:/, 'wss:')
      .replace(/\/$/, '') + '/fi/ws/sarvam-stt';

    FiLog.i('SarvamSTT', `Connecting → ${wsUrl}`);

    return new Promise<string>((resolve) => {
      const ws    = new WebSocket(wsUrl);
      this.ws     = ws;
      const parts: string[] = [];
      let   done  = false;

      const finish = (reason: string) => {
        if (done) return;
        done = true;
        if (this.flushTimer !== null) { clearTimeout(this.flushTimer); this.flushTimer = null; }
        stopRecording();
        FiLog.i('SarvamSTT', `Done (${reason}) — transcript: "${parts.join(' ').trim()}"`);
        resolve(parts.join(' ').trim() || '(no answer)');
      };

      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        FiLog.i('SarvamSTT', 'Proxy connected — starting recording');
        startRecording((chunk) => {
          if (ws.readyState === WebSocket.OPEN) ws.send(chunk);
        });

        this.flushTimer = window.setTimeout(() => {
          FiLog.i('SarvamSTT', 'Timeout — flushing');
          this.flushTimer = null;
          stopRecording();
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'flush' }));
          }
        }, timeoutMs);
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as { type: string; text?: string };
          if (msg.type === 'transcript' && msg.text) {
            FiLog.i('SarvamSTT', `Segment: ${msg.text}`);
            parts.push(msg.text);
            onPartial(msg.text);
          } else if (msg.type === 'error') {
            FiLog.e('SarvamSTT', `Server error: ${(msg as Record<string, string>)['message'] ?? JSON.stringify(msg)}`);
          }
        } catch { /* ignore parse errors */ }
      };

      ws.onclose = () => finish('ws-closed');
      ws.onerror = () => {
        FiLog.e('SarvamSTT', 'WebSocket error');
        finish('ws-error');
      };
    });
  }

  triggerFlush(): void {
    if (this.flushTimer !== null) { clearTimeout(this.flushTimer); this.flushTimer = null; }
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      FiLog.i('SarvamSTT', 'Early flush — silence detected');
      this.ws.send(JSON.stringify({ type: 'flush' }));
    }
  }

  close(): void {
    if (this.flushTimer !== null) { clearTimeout(this.flushTimer); this.flushTimer = null; }
    this.ws?.close();
    this.ws = null;
  }
}
