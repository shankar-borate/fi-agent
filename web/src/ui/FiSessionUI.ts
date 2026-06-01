import { UiState }            from './UiState';
import { FiSessionController } from './FiSessionController';
import { FiLog }               from '../services/FiLog';

export class FiSessionUI {
  private readonly controller: FiSessionController;

  private readonly videoPreview:   HTMLVideoElement;
  private readonly photoPreview:   HTMLImageElement;
  private readonly tvMessage:      HTMLElement;
  private readonly tvTranscript:   HTMLElement;
  private readonly tvCountdown:    HTMLElement;
  private readonly ivMicIndicator: HTMLElement;
  private readonly layoutReview:   HTMLElement;
  private readonly btnSave:        HTMLButtonElement;
  private readonly btnDiscard:     HTMLButtonElement;
  private readonly btnSubmit:      HTMLButtonElement;
  private readonly progressBar:      HTMLElement;
  private readonly thankyou:         HTMLElement;
  private readonly thankyouBody:     HTMLElement;
  private readonly thankyouRef:      HTMLElement;
  private readonly photoReviewPopup: HTMLElement;
  private readonly popupHeader:      HTMLElement;
  private readonly popupImage:       HTMLImageElement;
  private readonly popupGeo:         HTMLElement;
  private popupPhotoUrl:             string | null = null;

  private readonly consentScreen: HTMLElement;
  private readonly consentBody:   HTMLElement;

  private currentPhotoUrl: string | null = null;

  constructor(controller: FiSessionController) {
    this.controller = controller;

    this.videoPreview   = document.getElementById('videoPreview')   as HTMLVideoElement;
    this.photoPreview   = document.getElementById('photoPreview')   as HTMLImageElement;
    this.tvMessage      = document.getElementById('tvMessage')      as HTMLElement;
    this.tvTranscript   = document.getElementById('tvTranscript')   as HTMLElement;
    this.tvCountdown    = document.getElementById('tvCountdown')    as HTMLElement;
    this.ivMicIndicator = document.getElementById('ivMicIndicator') as HTMLElement;
    this.layoutReview   = document.getElementById('layoutReview')   as HTMLElement;
    this.btnSave        = document.getElementById('btnSave')        as HTMLButtonElement;
    this.btnDiscard     = document.getElementById('btnDiscard')     as HTMLButtonElement;
    this.btnSubmit      = document.getElementById('btnSubmit')      as HTMLButtonElement;
    this.progressBar    = document.getElementById('progressBar')    as HTMLElement;
    this.thankyou         = document.getElementById('thankyou')         as HTMLElement;
    this.thankyouBody     = document.getElementById('thankyouBody')     as HTMLElement;
    this.thankyouRef      = document.getElementById('thankyouRef')      as HTMLElement;
    this.photoReviewPopup = document.getElementById('photoReviewPopup') as HTMLElement;
    this.popupHeader      = document.getElementById('popupHeader')      as HTMLElement;
    this.popupImage       = document.getElementById('popupImage')       as HTMLImageElement;
    this.popupGeo         = document.getElementById('popupGeo')         as HTMLElement;

    this.consentScreen = document.getElementById('consentScreen') as HTMLElement;
    this.consentBody   = document.getElementById('consentBody')   as HTMLElement;

    // Popup buttons wire to same controller methods
    document.getElementById('btnPopupSave')!.addEventListener('click',    () => this.controller.onSave());
    document.getElementById('btnPopupDiscard')!.addEventListener('click', () => this.controller.onDiscard());

    // Consent buttons
    document.getElementById('btnConsentAgree')!.addEventListener('click',   () => this.controller.onSave());
    document.getElementById('btnConsentDecline')!.addEventListener('click', () => this.controller.onDiscard());

    this.btnSave.addEventListener('click', () => this.controller.onSave());
    this.btnDiscard.addEventListener('click', () => this.controller.onDiscard());
    this.btnSubmit.addEventListener('click',  () => {
      this.controller.submitSession().catch(e => FiLog.e('UI', 'Submit error', e));
    });
  }

  render(state: UiState): void {
    FiLog.d('UI', `render: ${state.kind}`);

    // Reset button labels before per-state overrides
    this.btnSave.textContent    = 'Save';
    this.btnDiscard.textContent = 'Discard';

    switch (state.kind) {

      case 'Connecting':
        this._showLive();
        this._showMessage('Connecting…');
        this._hideAll();
        break;

      case 'ShowMessage':
        this._showLive();
        this._showMessage(state.text);
        this._hideAll();
        break;

      case 'Listening':
        this._showLive();
        this._hideAll();
        // Question stays in tvMessage. Show recording status in transcript slot.
        this.tvTranscript.textContent = '🔴  Recording — please speak now';
        this.tvTranscript.classList.remove('final');
        this._show(this.tvTranscript);
        this._show(this.ivMicIndicator);
        this.tvCountdown.textContent = `${state.remaining}s`;
        this.tvCountdown.classList.add('countdown-recording');
        this._show(this.tvCountdown);
        break;

      case 'ShowTranscript':
        this._showLive();
        this._hideAll();
        this._show(this.ivMicIndicator);
        // Show partial text; prefix with mic icon so it's clear words are being heard
        this.tvTranscript.textContent = state.isFinal
          ? state.text
          : (state.text ? `🎙 ${state.text}` : '🔴  Recording — please speak now');
        this.tvTranscript.classList.toggle('final', state.isFinal);
        this._show(this.tvTranscript);
        break;

      case 'ConfirmAnswer': {
        this._showLive();
        this._showMessage(`Did you say:\n"${state.text}"`);
        this._hideAll();
        // No countdown — show GPS only if available
        if (state.geo) {
          this.tvTranscript.textContent =
            `📍 Lat: ${state.geo.latitude.toFixed(5)},  Long: ${state.geo.longitude.toFixed(5)}`;
          this.tvTranscript.classList.remove('final');
          this._show(this.tvTranscript);
        }
        this.btnSave.textContent    = 'Confirm';
        this.btnDiscard.textContent = 'Re-record';
        this._show(this.layoutReview);
        break;
      }

      case 'ConsentRequest':
        // Full-screen consent — hide camera, show dedicated consent card
        this.videoPreview.classList.add('hidden');
        this._hideAll();
        this._showConsent(state.message);
        break;

      case 'ConsentProcessing':
        this._hideConsent();
        this.videoPreview.classList.remove('hidden');
        this._showMessage('Retrieving your bank statement securely…');
        this._hideAll();
        this._show(this.progressBar);
        break;

      case 'Countdown':
        this._showLive();
        this._showMessage(state.prompt);
        this._hideAll();
        this.tvCountdown.textContent = String(state.remaining);
        this.tvCountdown.classList.remove('countdown-recording');
        this._show(this.tvCountdown);
        break;

      case 'CaptureNow':
        this._showLive();
        this._showMessage(state.prompt);
        this._hideAll();
        break;

      case 'ReviewPhoto': {
        this._showLive();
        this._hideAll();
        this._revokePopupUrl();
        this.popupPhotoUrl  = URL.createObjectURL(state.blob);
        this.popupImage.src = this.popupPhotoUrl;
        this.popupHeader.textContent =
          (state.isSelfie ? 'Selfie' : state.prompt.slice(0, 55)) +
          '  —  Review before saving';
        this.popupGeo.textContent = state.geo
          ? `📍 Lat: ${state.geo.latitude.toFixed(5)},  Long: ${state.geo.longitude.toFixed(5)}`
          : '';
        this.btnSave.textContent    = '✓ Save Photo';
        this.btnDiscard.textContent = '✗ Retake';
        this._show(this.photoReviewPopup);
        break;
      }

      case 'UploadingPhoto':
        this._showLive();
        this._showMessage('Uploading photo…');
        this._hideAll();
        this._show(this.progressBar);
        break;

      case 'ReadyToSubmit':
        this._showLive();
        this._showMessage(`Session complete\n${state.photoCount} photo(s) captured`);
        this._hideAll();
        this._show(this.btnSubmit);
        break;

      case 'Uploading':
        this._showLive();
        this._showMessage('Submitting FI report…');
        this._hideAll();
        this._show(this.progressBar);
        break;

      case 'Done':
        this._showLive();
        this._hideAll();
        // Show dedicated thank-you screen over the camera
        this.thankyouBody.textContent =
          'Your Field Investigation has been successfully submitted. ' +
          'Your case is currently under review. ' +
          'ABC Bank will contact you on your registered mobile number with the decision.';
        this.thankyouRef.innerHTML =
          `<strong>Case Reference:</strong> ${state.caseId}<br>` +
          `<strong>Registered Mobile:</strong> +91 ${state.mobileNumber}`;
        this._show(this.thankyou);
        break;

      case 'Error':
        this._showLive();
        this._showMessage(`Error: ${state.message}`);
        this._hideAll();
        if (state.showRetry) {
          this.btnSave.textContent    = 'Retry';
          this.btnDiscard.textContent = 'Skip';
          this._show(this.layoutReview);
        }
        break;
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────

  private _showMessage(text: string): void {
    this.tvMessage.textContent = text;
  }

  /** Hide all dynamic elements so each state only reveals what it needs. */
  private _hideAll(): void {
    this._hide(this.tvTranscript);
    this._hide(this.tvCountdown);
    this._hide(this.ivMicIndicator);
    this._hide(this.layoutReview);
    this._hide(this.btnSubmit);
    this._hide(this.progressBar);
    this._hide(this.thankyou);
    this._hide(this.photoReviewPopup);
    this._revokePopupUrl();
    this._hideConsent();
  }

  private _showConsent(message: string): void {
    this.consentBody.textContent = message;
    this._show(this.consentScreen);
  }

  private _hideConsent(): void {
    this._hide(this.consentScreen);
  }

  private _revokePopupUrl(): void {
    if (this.popupPhotoUrl) { URL.revokeObjectURL(this.popupPhotoUrl); this.popupPhotoUrl = null; }
  }

  private _showLive(): void {
    this._revokePhotoUrl();
    this.videoPreview.classList.remove('hidden');
    this.photoPreview.classList.add('hidden');
    this.photoPreview.src = '';
  }

  private _revokePhotoUrl(): void {
    if (this.currentPhotoUrl) {
      URL.revokeObjectURL(this.currentPhotoUrl);
      this.currentPhotoUrl = null;
    }
  }

  private _show(el: HTMLElement): void { el.classList.remove('hidden'); }
  private _hide(el: HTMLElement): void { el.classList.add('hidden'); }
}
