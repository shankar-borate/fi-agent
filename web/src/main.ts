import { CameraManager }       from './services/CameraManager';
import { SessionRecorder }     from './services/SessionRecorder';
import { FiApiClient }         from './data/FiApiClient';
import { FiSessionRepository } from './data/FiSessionRepository';
import { FiSessionController } from './ui/FiSessionController';
import { FiSessionUI }         from './ui/FiSessionUI';
import { FiConfig, initFiConfig } from './config/FiConfig';
import { FiLog }               from './services/FiLog';
import { BasicInfo }           from './domain/models';

// ── Screen helpers ─────────────────────────────────────────────────────────

function show(id: string) { document.getElementById(id)!.classList.remove('hidden'); }
function hide(id: string) { document.getElementById(id)!.classList.add('hidden'); }
function showError(id: string, msg: string) {
  const el = document.getElementById(id)!;
  el.textContent = msg;
  el.classList.remove('hidden');
}
function clearError(id: string) {
  const el = document.getElementById(id)!;
  el.textContent = '';
  el.classList.add('hidden');
}

// ── Device identity ────────────────────────────────────────────────────────

function getDeviceId(): string {
  let id = localStorage.getItem('fi_device_id');
  if (!id) { id = crypto.randomUUID(); localStorage.setItem('fi_device_id', id); }
  return id;
}

// ── Form state ─────────────────────────────────────────────────────────────

let capturedBasicInfo: BasicInfo | null = null;

// ── Marketing screen ────────────────────────────────────────────────────────

document.getElementById('btnApply')!.addEventListener('click', () => {
  hide('screenMarketing');
  show('screenForm');
});

// ── Application form ────────────────────────────────────────────────────────

document.getElementById('btnBackToMarketing')!.addEventListener('click', () => {
  hide('screenForm');
  show('screenMarketing');
});

document.getElementById('loanForm')!.addEventListener('submit', (e) => {
  e.preventDefault();
  clearError('formError');

  const get = (id: string) => (document.getElementById(id) as HTMLInputElement).value.trim();

  const firstName    = get('firstName');
  const lastName     = get('lastName');
  const dob          = get('dob');
  const address      = get('address');
  const city         = get('city');
  const panNumber    = get('panNumber').toUpperCase();
  const mobileNumber = get('mobileNumber');
  const incomeRange  = get('incomeRange');

  // Validate
  if (!firstName || !lastName) { showError('formError', 'Please enter your full name.'); return; }
  if (!dob)         { showError('formError', 'Please enter your date of birth.'); return; }
  if (!address)     { showError('formError', 'Please enter your address.'); return; }
  if (!city)        { showError('formError', 'Please enter your city.'); return; }
  if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(panNumber)) {
    showError('formError', 'PAN number format is invalid (e.g. ABCDE1234F).');
    return;
  }
  if (!/^[6-9][0-9]{9}$/.test(mobileNumber)) {
    showError('formError', 'Mobile number must be a valid 10-digit Indian number.');
    return;
  }
  if (!incomeRange) { showError('formError', 'Please select your income range.'); return; }

  capturedBasicInfo = { firstName, lastName, dob, address, city, panNumber, mobileNumber, incomeRange };

  // Populate review table
  const pairs: [string, string][] = [
    ['Full Name',       `${firstName} ${lastName}`],
    ['Date of Birth',   dob],
    ['Address',         address],
    ['City',            city],
    ['PAN Number',      panNumber],
    ['Mobile Number',   mobileNumber],
    ['Annual Income',   incomeRange],
  ];
  const table = document.getElementById('reviewTable')!;
  table.innerHTML = pairs.map(([k, v]) =>
    `<div class="review-row">
       <span class="review-key">${k}</span>
       <span class="review-val">${v}</span>
     </div>`
  ).join('');

  hide('screenForm');
  show('screenReview');
});

// ── Review screen ───────────────────────────────────────────────────────────

document.getElementById('btnBackToForm')!.addEventListener('click', () => {
  hide('screenReview');
  show('screenForm');
});

document.getElementById('btnStartFI')!.addEventListener('click', () => {
  if (!capturedBasicInfo) { hide('screenReview'); show('screenForm'); return; }
  clearError('reviewError');
  const btn = document.getElementById('btnStartFI') as HTMLButtonElement;
  btn.disabled    = true;
  btn.textContent = 'Starting…';
  bootFI(capturedBasicInfo).catch(err => {
    btn.disabled    = false;
    btn.textContent = 'Start Field Investigation';
    showError('reviewError', (err as Error).message);
  });
});

// ── FI boot ─────────────────────────────────────────────────────────────────

async function bootFI(basicInfo: BasicInfo): Promise<void> {
  // Case ID: firstName_uuid8  (e.g. Ramesh_a3b4c5d6)
  const safeName = basicInfo.firstName.toLowerCase().replace(/[^a-z0-9]/g, '');
  const caseId   = `${safeName}_${crypto.randomUUID().substring(0, 8)}`;
  FiLog.i('Main', `Boot FI: case=${caseId}`);

  await initFiConfig();
  FiLog.i('Main', `Transcribe engine: ${FiConfig.transcribeEngine}`);

  hide('screenReview');
  show('session');

  // Microphone stream (audio-only for STT + recording)
  let audioStream: MediaStream;
  try {
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, sampleRate: { ideal: 48000 } },
      video: false,
    });
  } catch (e) {
    hide('session');
    show('screenReview');
    showError('reviewError', `Microphone access denied: ${(e as Error).message}`);
    return;
  }

  // Camera
  const videoEl = document.getElementById('videoPreview') as HTMLVideoElement;
  const camera  = new CameraManager(videoEl);
  try {
    await camera.start('environment');
  } catch (e) {
    FiLog.w('Main', `Back camera unavailable: ${(e as Error).message}`);
    try { await camera.start('user'); } catch { FiLog.e('Main', 'Camera unavailable', e); }
  }

  const sessionRecorder = new SessionRecorder();
  const api             = new FiApiClient(FiConfig.serverUrl);
  const repo            = new FiSessionRepository(api);
  const deviceId        = getDeviceId();

  let ui!: FiSessionUI;

  const controller = new FiSessionController({
    caseId,
    deviceId,
    basicInfo,
    audioStream,
    videoElement: videoEl,
    camera,
    sessionRecorder,
    repo,
    onState:   (state) => ui.render(state),
    onCapture: ()      => camera.capturePhoto(),
  });

  ui = new FiSessionUI(controller);
  controller.connect();
}
