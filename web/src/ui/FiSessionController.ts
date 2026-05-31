import { FiLog }              from '../services/FiLog';
import { WebSocketManager }   from '../services/WebSocketManager';
import { AudioRecorder }      from '../services/AudioRecorder';
import { AudioPlayer }        from '../services/AudioPlayer';
import { TtsHelper }          from '../services/TtsHelper';
import { LocationHelper }     from '../services/LocationHelper';
import { CameraManager }      from '../services/CameraManager';
import { SessionRecorder }    from '../services/SessionRecorder';
import { SarvamSTTService }   from '../services/SarvamSTTService';
import { FiSessionRepository } from '../data/FiSessionRepository';
import { FiConfig }           from '../config/FiConfig';
import { BasicInfo, QuestionAnswer, PhotoCapture, DocumentCapture, GeoPoint } from '../domain/models';
import { UiState }            from './UiState';

export interface ControllerOptions {
  caseId:          string;
  deviceId:        string;
  basicInfo:       BasicInfo;
  audioStream:     MediaStream;
  videoElement:    HTMLVideoElement;
  camera:          CameraManager;
  sessionRecorder: SessionRecorder;
  repo:            FiSessionRepository;
  onState:         (s: UiState) => void;
  onCapture:       () => Promise<Blob>;
}

export class FiSessionController {
  private readonly ws:       WebSocketManager;
  private readonly recorder: AudioRecorder;
  private readonly player:   AudioPlayer;
  private readonly tts:      TtsHelper;
  private readonly location: LocationHelper;
  private readonly sarvam:   SarvamSTTService;

  private readonly caseId:     string;
  private readonly deviceId:   string;
  private readonly basicInfo:  BasicInfo;
  private readonly startedAt:  string;
  private readonly repo:       FiSessionRepository;
  private readonly camera:     CameraManager;
  private readonly sessionRec: SessionRecorder;
  private readonly onCapture:  () => Promise<Blob>;
  private readonly emitState:  (s: UiState) => void;

  // Session-level collected data
  private answers:   QuestionAnswer[]   = [];
  private photos:    PhotoCapture[]     = [];
  private documents: DocumentCapture[]  = [];

  // Current document upload context
  private currentDocumentType = '';

  // Current question context
  private currentQuestion      = '';
  private currentQuestionIndex = -1;
  private lastQuestionAudio    = '';
  private pendingAnswerGeo: GeoPoint | null = null;

  // Answer confirmation
  private pendingConfirmText = '';
  private confirmTimerId: number | null = null;

  // Current photo context
  private reviewBlob:      Blob | null = null;
  private reviewPrompt     = '';
  private reviewIsSelfie   = false;
  private reviewIndex      = 0;
  private reviewTag        = '';
  private pendingPhotoGeo: GeoPoint | null = null;
  private lastPrompt       = '';

  // Timers
  private listenTimerId:   number | null = null;
  private listenTickId:    number | null = null;   // per-second recording countdown
  private reviewTimerId:   number | null = null;

  constructor(opts: ControllerOptions) {
    this.caseId     = opts.caseId;
    this.deviceId   = opts.deviceId;
    this.basicInfo  = opts.basicInfo;
    this.startedAt  = new Date().toISOString();
    this.repo       = opts.repo;
    this.camera     = opts.camera;
    this.sessionRec = opts.sessionRecorder;
    this.onCapture  = opts.onCapture;
    this.emitState  = opts.onState;

    this.recorder = new AudioRecorder();
    this.player   = new AudioPlayer();
    this.tts      = new TtsHelper();
    this.location = new LocationHelper();
    this.sarvam   = new SarvamSTTService();

    this.ws = new WebSocketManager({
      onMessage: (msg) => { this._handleMessage(msg).catch(e => FiLog.e('Controller', 'handleMessage error', e)); },
      onOpen:    () => { this._onOpen().catch(e => FiLog.e('Controller', 'onOpen error', e)); },
      onFailure: () => { this.emitAndTrack({ kind: 'Error', message: 'Connection failed.', showRetry: false }); },
      onClosed:  (code) => { if (code !== 1000) FiLog.w('Controller', `WS closed unexpectedly: ${code}`); },
    });

    // Prepare AudioRecorder with microphone stream
    this.recorder.prepare(opts.audioStream).catch(e => FiLog.e('Controller', 'AudioRecorder prepare failed', e));

    // Start session recording (video+audio when captureStream is supported)
    this.sessionRec.start(opts.audioStream, opts.videoElement);
  }

  connect(): void {
    const wsUrl = FiConfig.serverUrl
      .replace(/^http:/, 'ws:')
      .replace(/^https:/, 'wss:')
      .replace(/\/$/, '') + `/fi/ws/fi-session/${this.caseId}`;

    FiLog.i('Controller', `Connecting → ${wsUrl}`);
    this.emitAndTrack({ kind: 'Connecting' });
    this.ws.connect(wsUrl);
  }

  // ── Handshake ─────────────────────────────────────────────────────────

  private async _onOpen(): Promise<void> {
    FiLog.i('Controller', 'WS open — sending ready');
    this.ws.sendJson({
      type:       'ready',
      session_id: this.caseId,
      device_id:  this.deviceId,
      started_at: this.startedAt,
      basic_info: {
        first_name:    this.basicInfo.firstName,
        last_name:     this.basicInfo.lastName,
        dob:           this.basicInfo.dob,
        address:       this.basicInfo.address,
        city:          this.basicInfo.city,
        pan_number:    this.basicInfo.panNumber,
        mobile_number: this.basicInfo.mobileNumber,
        income_range:  this.basicInfo.incomeRange,
      },
    });
  }

  // ── Server message dispatcher ─────────────────────────────────────────

  private async _handleMessage(msg: Record<string, unknown>): Promise<void> {
    const type = msg['type'] as string;
    FiLog.i('Controller', `Server msg: ${type}`);

    switch (type) {

      case 'question': {
        this.currentQuestion      = msg['text']  as string;
        this.currentQuestionIndex = msg['index'] as number ?? 0;
        this.lastQuestionAudio    = msg['audio'] as string ?? '';
        this.lastPrompt = this.currentQuestion;
        FiLog.i('Controller', `Q${this.currentQuestionIndex + 1}: ${this.currentQuestion}`);
        this.emitAndTrack({ kind: 'ShowMessage', text: this.currentQuestion });
        await this._speak(this.currentQuestion, this.lastQuestionAudio);
        this.ws.sendJson({ type: 'tts_done' });
        break;
      }

      case 'tts_audio': {
        // Server sends standalone AWS Polly audio frame
        const audio = msg['data'] as string ?? '';
        if (audio) await this.player.playBase64Mp3(audio);
        break;
      }

      case 'start_listening': {
        const qIdx      = msg['question_index'] as number ?? 0;
        const timeoutMs = msg['timeout_ms']     as number ?? FiConfig.sttTimeoutMs;
        FiLog.i('Controller', `Listening Q${qIdx}  engine=${FiConfig.transcribeEngine}  timeout=${timeoutMs}ms`);

        // ── Pre-recording "get ready" countdown: 3 … 2 … 1 ──────────────
        for (let i = 3; i >= 1; i--) {
          this.emitAndTrack({ kind: 'Countdown', remaining: i, prompt: this.currentQuestion });
          await new Promise<void>(r => window.setTimeout(r, 1_000));
        }

        this.pendingAnswerGeo = await this.location.getLocation();

        // ── Recording countdown ticker ────────────────────────────────────
        const totalSecs = Math.ceil(timeoutMs / 1_000);
        let remainingSecs = totalSecs;
        this.emitAndTrack({ kind: 'Listening', questionIndex: qIdx, remaining: remainingSecs });

        this._clearListenTick();
        this.listenTickId = window.setInterval(() => {
          remainingSecs = Math.max(0, remainingSecs - 1);
          this.emitAndTrack({ kind: 'Listening', questionIndex: qIdx, remaining: remainingSecs });
        }, 1_000);

        if (FiConfig.transcribeEngine === 'sarvam') {
          const text = await this.sarvam.listen(
            timeoutMs,
            (onChunk) => this.recorder.start(onChunk),
            ()        => this.recorder.stop(),
            (partial) => this.emitAndTrack({ kind: 'ShowTranscript', text: partial, isFinal: false }),
          );
          this._clearListenTick();
          this.recorder.stop();
          FiLog.i('Controller', `Sarvam transcript Q${qIdx}: '${text}'`);
          this.ws.sendJson({ type: 'transcript_result', question_index: qIdx, text });
        } else {
          // AWS path — send raw PCM to server
          this.recorder.start((chunk) => { this.ws.sendBinary(chunk); });
          this._clearListenTimer();
          this.listenTimerId = window.setTimeout(() => {
            FiLog.i('Controller', 'Listen timeout → audio_end');
            this._clearListenTick();
            this.recorder.stop();
            this.ws.sendJson({ type: 'audio_end' });
          }, timeoutMs);
        }
        break;
      }

      case 'transcript': {
        const text    = (msg['text']     as string  ?? '').trim();
        const isFinal = msg['is_final']  as boolean ?? false;
        FiLog.i('Controller', `Transcript final=${isFinal}: '${text}'`);

        if (isFinal) {
          this._clearListenTimer();
          this._clearListenTick();
          this._startConfirm(text);
        } else {
          this.emitAndTrack({ kind: 'ShowTranscript', text, isFinal: false });
        }
        break;
      }

      case 'pan_retry': {
        const message = msg['message'] as string ?? 'PAN card unclear. Please try again.';
        FiLog.w('Controller', `PAN retry: ${message}`);
        this.emitAndTrack({ kind: 'ShowMessage', text: message });
        break;
      }

      case 'request_document': {
        const prompt   = msg['prompt']        as string ?? 'Please upload bank statement (PDF)';
        const docType  = msg['document_type'] as string ?? 'bank_statement';
        this.currentDocumentType = docType;
        FiLog.i('Controller', `Document requested: type=${docType}`);
        this.emitAndTrack({ kind: 'UploadDocument', prompt, documentType: docType });
        break;
      }

      case 'announce_photo': {
        const prompt = msg['prompt']   as string ?? '';
        const audio  = msg['audio']    as string ?? '';
        this.lastPrompt = prompt;
        FiLog.i('Controller', `Announce photo: ${prompt}`);
        this.emitAndTrack({ kind: 'ShowMessage', text: prompt });
        await this._speak(prompt, audio);
        this.ws.sendJson({ type: 'tts_done' });
        break;
      }

      case 'countdown': {
        const value = msg['value'] as number;
        this.emitAndTrack({ kind: 'Countdown', remaining: value, prompt: this.lastPrompt });
        break;
      }

      case 'capture_photo': {
        const prompt     = msg['prompt']      as string  ?? '';
        const isSelfie   = msg['is_selfie']   as boolean ?? false;
        const photoIndex = msg['photo_index'] as number  ?? 0;
        FiLog.i('Controller', `Capture photo selfie=${isSelfie} idx=${photoIndex}`);

        this.pendingPhotoGeo  = await this.location.getLocation();
        this.reviewPrompt     = prompt;
        this.reviewIsSelfie   = isSelfie;
        this.reviewIndex      = photoIndex;
        this.reviewTag        = _deriveTag(prompt, isSelfie);

        await this.camera.switchCamera(isSelfie ? 'user' : 'environment');
        this.emitAndTrack({ kind: 'CaptureNow', isSelfie, index: photoIndex, prompt });

        try {
          const blob = await this.onCapture();
          this.notifyPhotoCaptured(blob);
        } catch (err) {
          FiLog.e('Controller', 'Photo capture failed', err);
          this.emitAndTrack({ kind: 'Error', message: `Camera capture failed: ${(err as Error).message}`, showRetry: true });
        }
        break;
      }

      case 'photo_ack':
        FiLog.d('Controller', `Photo ack idx=${msg['photo_index']}`);
        break;

      case 'session_done': {
        const message = msg['message'] as string ?? 'Session complete';
        FiLog.i('Controller', `Session done: ${message}`);
        this.ws.close();
        this.emitAndTrack({
          kind:         'ReadyToSubmit',
          caseId:       this.caseId,
          photoCount:   this.photos.length,
          hasRecording: true,
        });
        break;
      }

      case 'error': {
        const message = msg['message'] as string ?? 'Server error';
        FiLog.e('Controller', `Server error: ${message}`);
        this.emitAndTrack({ kind: 'Error', message, showRetry: false });
        break;
      }

      default:
        FiLog.w('Controller', `Unknown msg type: ${type}`);
    }
  }

  // ── TTS: AWS Polly preferred, Web Speech fallback ─────────────────────

  private async _speak(text: string, base64Audio = ''): Promise<void> {
    if (base64Audio) {
      await this.player.playBase64Mp3(base64Audio);
    } else {
      await this.tts.speak(text);
    }
  }

  // ── Photo review (5-second countdown) ────────────────────────────────

  notifyPhotoCaptured(blob: Blob): void {
    this.reviewBlob = blob;
    this._startReview();
  }

  private _startReview(): void {
    if (this.reviewTimerId !== null) { clearTimeout(this.reviewTimerId); this.reviewTimerId = null; }
    const blob = this.reviewBlob;
    if (!blob) return;

    this.emitAndTrack({
      kind:     'ReviewPhoto',
      blob,
      prompt:   this.reviewPrompt,
      isSelfie: this.reviewIsSelfie,
      index:    this.reviewIndex,
      geo:      this.pendingPhotoGeo,
    });

    this.reviewTimerId = window.setTimeout(() => {
      FiLog.i('Controller', 'Review auto-save');
      this._commitPhoto().catch(e => {
        this.emitAndTrack({ kind: 'Error', message: `Photo upload failed: ${(e as Error).message}`, showRetry: true });
      });
    }, 5_000);
  }

  // ── Document upload ───────────────────────────────────────────────────

  /** Called by UI when the user selects a PDF file. */
  async onDocumentSelected(file: File): Promise<void> {
    const docType = this.currentDocumentType || 'bank_statement';
    FiLog.i('Controller', `Uploading document: ${file.name}  type=${docType}`);
    this.emitAndTrack({ kind: 'UploadingDocument', documentType: docType });

    // Capture GPS at time of document upload
    const docGeo = await this.location.getLocation();

    try {
      const result = await this.repo.uploadDocument(this.caseId, file, docType);
      const doc: DocumentCapture = {
        documentType: docType,
        filename:     result.filename,
        uploadedAt:   new Date().toISOString(),
      };
      this.documents.push(doc);
      FiLog.i('Controller', `Document uploaded: ${result.filename}`);
      const geoStr = docGeo
        ? `\n📍 Lat: ${docGeo.latitude.toFixed(5)},  Long: ${docGeo.longitude.toFixed(5)}`
        : '';
      this.emitAndTrack({ kind: 'ShowMessage', text: `Bank statement uploaded.\n${result.filename}${geoStr}` });
      this.ws.sendJson({ type: 'document_ready', document_type: docType, filename: result.filename });
    } catch (err) {
      FiLog.e('Controller', 'Document upload failed', err);
      this.emitAndTrack({
        kind: 'UploadDocument',
        prompt: `Upload failed: ${(err as Error).message}. Tap Upload to retry or Skip to continue.`,
        documentType: docType,
      });
    }
  }

  // ── Answer confirmation (8-second auto-confirm countdown) ────────────

  private _startConfirm(text: string): void {
    this._clearConfirmTimer();
    this.pendingConfirmText = text;
    const CONFIRM_MS = 8_000;
    const TICK_MS    = 1_000;
    let remaining = CONFIRM_MS / TICK_MS;

    const geo = this.pendingAnswerGeo;
    const tick = () => {
      this.emitAndTrack({ kind: 'ConfirmAnswer', text, remaining, geo });
      if (remaining <= 0) {
        FiLog.i('Controller', 'Confirm auto-timeout → confirming');
        this._doConfirm();
        return;
      }
      remaining--;
      this.confirmTimerId = window.setTimeout(tick, TICK_MS);
    };
    tick();
  }

  private _doConfirm(): void {
    this._clearConfirmTimer();
    const text = this.pendingConfirmText;
    this.answers.push({
      question: this.currentQuestion,
      answer:   text,
      geo:      this.pendingAnswerGeo,
    });
    this.pendingAnswerGeo = null;
    FiLog.i('Controller', `Answer confirmed [${this.answers.length}]: ${text}`);
    this.emitAndTrack({ kind: 'ShowTranscript', text, isFinal: true });
    this.ws.sendJson({ type: 'answer_confirm' });
  }

  private _clearConfirmTimer(): void {
    if (this.confirmTimerId !== null) { clearTimeout(this.confirmTimerId); this.confirmTimerId = null; }
  }

  /** Save button pressed during photo review (or retry after upload failure). */
  onSave(): void {
    switch (this.currentUiKind()) {
      case 'ConfirmAnswer':
        this._doConfirm();
        break;
      case 'ReviewPhoto':
      case 'Error':
        if (this.reviewTimerId !== null) { clearTimeout(this.reviewTimerId); this.reviewTimerId = null; }
        this._commitPhoto().catch(e => {
          this.emitAndTrack({ kind: 'Error', message: `Photo upload failed: ${(e as Error).message}`, showRetry: true });
        });
        break;
    }
  }

  /** Discard button pressed during photo review — retake the same photo. */
  onDiscard(): void {
    switch (this.currentUiKind()) {
      case 'UploadDocument':
        FiLog.i('Controller', 'Document upload skipped by officer');
        this.emitAndTrack({ kind: 'ShowMessage', text: 'Bank statement skipped.' });
        this.ws.sendJson({ type: 'document_skipped', document_type: this.currentDocumentType });
        break;

      case 'ConfirmAnswer':
        this._clearConfirmTimer();
        FiLog.i('Controller', 'User requested re-record');
        this.pendingAnswerGeo = null;
        this.ws.sendJson({ type: 'answer_retry' });
        break;
      case 'ReviewPhoto':
        if (this.reviewTimerId !== null) { clearTimeout(this.reviewTimerId); this.reviewTimerId = null; }
        this._retakePhoto();
        break;
      case 'Error':
        FiLog.w('Controller', 'Photo skipped by user');
        this.ws.sendJson({ type: 'photo_taken', photo_index: this.reviewIndex, filename: '' });
        break;
    }
  }

  private _retakePhoto(): void {
    FiLog.i('Controller', 'Retaking photo');
    this.emitAndTrack({ kind: 'ShowMessage', text: 'Retaking photo…' });
    window.setTimeout(async () => {
      this.emitAndTrack({ kind: 'CaptureNow', isSelfie: this.reviewIsSelfie, index: this.reviewIndex, prompt: this.reviewPrompt });
      const [geo, blob] = await Promise.all([
        this.location.getLocation(),
        this.onCapture().catch(() => null as Blob | null),
      ]);
      this.pendingPhotoGeo = geo;
      if (blob) {
        this.notifyPhotoCaptured(blob);
      } else {
        FiLog.e('Controller', 'Retake capture failed');
        this.emitAndTrack({ kind: 'Error', message: 'Camera capture failed. Please try again.', showRetry: true });
      }
    }, 400);
  }

  private async _commitPhoto(): Promise<void> {
    const blob = this.reviewBlob;
    if (!blob) return;

    const ts       = _timestamp();
    const ext      = blob.type.includes('png') ? '.png' : '.jpg';
    const filename = `photo_${ts}${ext}`;

    this.emitAndTrack({ kind: 'UploadingPhoto', index: this.reviewIndex });

    const photo: PhotoCapture = {
      prompt:    this.reviewPrompt,
      tag:       this.reviewTag,
      isSelfie:  this.reviewIsSelfie,
      blob,
      filename,
      geo:       this.pendingPhotoGeo,
      blurScore: 0,
    };

    await this.repo.uploadPhoto(this.caseId, photo);

    this.photos.push(photo);
    this.pendingPhotoGeo = null;
    FiLog.i('Controller', `Photo uploaded [${this.photos.length}]: ${filename}`);

    // Notify server to advance the session
    this.ws.sendJson({ type: 'photo_taken', photo_index: this.reviewIndex, filename });
  }

  // ── Submit (recording + metadata) ─────────────────────────────────────

  async submitSession(): Promise<void> {
    FiLog.i('Controller', `Submit: case=${this.caseId}`);
    this.emitAndTrack({ kind: 'Uploading' });
    try {
      // Stop session recording
      const recBlob = await this.sessionRec.stop().catch(() => null);
      const recName = recBlob
        ? `recording_${this.caseId}_${_timestamp()}${this.sessionRec.extension}`
        : null;

      const resp = await this.repo.submitSession({
        sessionId:     this.caseId,
        deviceId:      this.deviceId,
        startedAt:     this.startedAt,
        endedAt:       new Date().toISOString(),
        basicInfo:     this.basicInfo,
        answers:       this.answers,
        photos:        this.photos,
        documents:     this.documents,
        recordingBlob: recBlob,
        recordingName: recName,
      });

      FiLog.i('Controller', `Submit success: ${resp.message}`);
      this.emitAndTrack({ kind: 'Done', caseId: this.caseId, mobileNumber: this.basicInfo.mobileNumber });
    } catch (e) {
      FiLog.e('Controller', 'Submit failed', e);
      this.emitAndTrack({ kind: 'Error', message: `Submit failed: ${(e as Error).message}`, showRetry: false });
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────

  private _lastKind: UiState['kind'] = 'Connecting';

  private currentUiKind(): UiState['kind'] { return this._lastKind; }

  /** Wrap emitState to track current kind for Save/Discard dispatch. */
  private emitAndTrack(state: UiState): void {
    this._lastKind = state.kind;
    this.emitState(state);
  }

  private _clearListenTimer(): void {
    if (this.listenTimerId !== null) { clearTimeout(this.listenTimerId); this.listenTimerId = null; }
  }

  private _clearListenTick(): void {
    if (this.listenTickId !== null) { clearInterval(this.listenTickId); this.listenTickId = null; }
  }

  destroy(): void {
    this._clearListenTimer();
    this._clearListenTick();
    this._clearConfirmTimer();
    if (this.reviewTimerId !== null) { clearTimeout(this.reviewTimerId); this.reviewTimerId = null; }
    this.sarvam.close();
    this.recorder.destroy();
    this.player.stop();
    this.tts.stop();
    this.ws.close();
  }
}

function _timestamp(): string {
  return new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 15);
}

function _deriveTag(prompt: string, isSelfie: boolean): string {
  if (isSelfie) return 'selfie';
  const p = prompt.toLowerCase();
  if (p.includes('pan'))                         return 'pan';
  if (p.includes('kitchen'))                     return 'kitchen';
  if (p.includes('bedroom 1') || p.includes('bedroom1')) return 'bedroom1';
  if (p.includes('bedroom 2') || p.includes('bedroom2')) return 'bedroom2';
  if (p.includes('bedroom'))                     return 'bedroom';
  if (p.includes('hall') || p.includes('living')) return 'hall';
  if (p.includes('nameplate') || p.includes('signage') || p.includes('door')) return 'nameplate';
  if (p.includes('outside') || p.includes('front') || p.includes('exterior')) return 'outside';
  return 'photo';
}
