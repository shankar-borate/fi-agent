import { CameraManager }       from './services/CameraManager';
import { SessionRecorder }     from './services/SessionRecorder';
import { FiApiClient }         from './data/FiApiClient';
import { FiSessionRepository } from './data/FiSessionRepository';
import { FiSessionController } from './ui/FiSessionController';
import { FiSessionUI }         from './ui/FiSessionUI';
import { FiConfig, initFiConfig } from './config/FiConfig';
import { FiLog }               from './services/FiLog';
import { BasicInfo, PropertyInfo } from './domain/models';

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

let capturedBasicInfo:    BasicInfo    | null = null;
let capturedPropertyInfo: PropertyInfo | null = null;

// ── Marketing screen ────────────────────────────────────────────────────────

// ── OTP flow ────────────────────────────────────────────────────────────────


document.getElementById('btnApply')!.addEventListener('click', () => {
  // Prime iOS location permission here — this click IS a user gesture,
  // so Safari will show the permission prompt now instead of silently
  // denying it later when GPS is requested from inside a WebSocket handler.
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      () => FiLog.i('Main', 'Location permission granted on Apply click'),
      (e) => FiLog.w('Main', `Location permission on Apply: ${e.message}`),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 },
    );
  }

  hide('screenMarketing');
  show('screenOTP');
  // Reset OTP screen to step 1
  show('otpStep1');
  hide('otpStep2');
  hide('otpStep3');
  (document.getElementById('otpMobile') as HTMLInputElement).value = '';
  (document.getElementById('otpMobileErr') as HTMLElement).classList.add('hidden');
});

document.getElementById('btnBackOTPToMarketing')!.addEventListener('click', () => {
  hide('screenOTP');
  show('screenMarketing');
});

document.getElementById('btnSendOTP')!.addEventListener('click', () => {
  const mobile = (document.getElementById('otpMobile') as HTMLInputElement).value.trim();
  const err    = document.getElementById('otpMobileErr')!;
  const btn    = document.getElementById('btnSendOTP') as HTMLButtonElement;

  if (!/^[6-9][0-9]{9}$/.test(mobile)) {
    err.textContent = 'Enter a valid 10-digit Indian mobile number.';
    err.classList.remove('hidden');
    return;
  }
  err.classList.add('hidden');
  btn.disabled    = true;
  btn.textContent = 'Sending…';

  // ── Step 1 → 2: simulate SMS dispatch (2s delay) ──────────────────────
  window.setTimeout(() => {
    hide('otpStep1');
    show('otpStep2');

    const masked = `+91 ${mobile.slice(0,3)}XXXXXXX`;
    document.getElementById('otpSentMsg')!.textContent =
      `OTP has been sent to ${masked} via SMS`;
    document.getElementById('otpFillingMsg')!.textContent = 'Waiting for OTP…';

    // Clear boxes
    for (let i = 0; i < 6; i++) {
      const box = document.getElementById(`otp${i}`) as HTMLInputElement;
      box.value = '';
      box.classList.remove('filled', 'masked');
    }

    // ── After 5s: auto-fill boxes with * one by one ────────────────────
    window.setTimeout(() => {
      document.getElementById('otpFillingMsg')!.textContent = 'OTP received — verifying…';

      for (let i = 0; i < 6; i++) {
        window.setTimeout(() => {
          const box = document.getElementById(`otp${i}`) as HTMLInputElement;
          box.value = '*';
          box.classList.add('masked');

          // After last box: show verified state, then auto-advance
          if (i === 5) {
            window.setTimeout(() => {
              document.getElementById('otpFillingMsg')!.textContent = 'OTP verified ✓';

              // ── After 1.5s: move to verified screen ───────────────────
              window.setTimeout(() => {
                hide('otpStep2');
                show('otpStep3');
                document.getElementById('otpVerifiedMsg')!.textContent =
                  `+91 ${mobile} has been verified. Proceeding to your application…`;

                // ── After 2s: open form with mobile pre-filled ─────────
                window.setTimeout(() => {
                  hide('screenOTP');
                  show('screenForm');
                  const mobileEl = document.getElementById('mobileNumber') as HTMLInputElement;
                  mobileEl.value    = mobile;
                  mobileEl.readOnly = true;
                  btn.disabled    = false;
                  btn.textContent = 'Get OTP';
                }, 2_000);

              }, 1_500);
            }, 500);
          }
        }, i * 200);   // stagger * appearance by 200ms each
      }
    }, 1_000);   // 1s wait before OTP auto-fills

  }, 1_000);   // 1s delay simulating SMS dispatch
});

// Live loan amount hint
document.getElementById('loanAmount')!.addEventListener('input', (e) => {
  const val   = parseInt((e.target as HTMLInputElement).value, 10);
  const hint  = document.getElementById('loanAmountHint')!;
  if (!val || val < 10_000) {
    hint.textContent = 'Minimum loan amount: ₹10,000';
    hint.className   = 'form-hint';
  } else if (val > 500_000) {
    hint.textContent = `₹ ${val.toLocaleString('en-IN')} — Video PD process (above ₹5 Lakh)`;
    hint.className   = 'form-hint warn';
  } else {
    hint.textContent = `₹ ${val.toLocaleString('en-IN')} — Field Investigation process`;
    hint.className   = 'form-hint';
  }
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
  const loanAmount   = parseInt((document.getElementById('loanAmount') as HTMLInputElement).value, 10);

  // Validate
  if (!firstName || !lastName) { showError('formError', 'Please enter your full name.'); return; }
  if (!dob)         { showError('formError', 'Please enter your date of birth.'); return; }
  if (!address)     { showError('formError', 'Please enter your address.'); return; }
  if (!city)        { showError('formError', 'Please enter your city.'); return; }
  if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(panNumber)) {
    showError('formError', 'PAN number format is invalid (e.g. ABCDE1234F).');
    return;
  }
  // Mobile is already OTP-verified — just sanity check it's present
  if (!mobileNumber || mobileNumber.length !== 10) {
    showError('formError', 'Mobile number is missing. Please restart the application.');
    return;
  }
  if (!incomeRange) { showError('formError', 'Please select your income range.'); return; }
  if (!loanAmount || loanAmount < 10_000) {
    showError('formError', 'Please enter a valid loan amount (minimum ₹10,000).');
    return;
  }

  // Property Info
  const propertyType = get('propertyType') as 'flat' | 'bungalow';
  const bedroomsRaw  = parseInt(get('bedrooms'), 10) as 1 | 2 | 3;
  const hallRaw      = parseInt((document.getElementById('hall') as HTMLSelectElement).value, 10) as 0 | 1;

  if (!propertyType) { showError('formError', 'Please select the type of property.'); return; }
  if (!bedroomsRaw)  { showError('formError', 'Please select the number of bedrooms.'); return; }

  capturedBasicInfo    = { firstName, lastName, dob, address, city, panNumber, mobileNumber, incomeRange, loanAmount };
  capturedPropertyInfo = { propertyType, bedrooms: bedroomsRaw, hall: hallRaw };

  const bedroomLabel  = `${bedroomsRaw} Bedroom${bedroomsRaw > 1 ? 's' : ''}`;
  const propTypeLabel = propertyType === 'flat' ? 'Flat / Apartment' : 'Bungalow / House';

  // Populate review table
  const pairs: [string, string][] = [
    ['Full Name',        `${firstName} ${lastName}`],
    ['Date of Birth',    dob],
    ['Address',          address],
    ['City',             city],
    ['PAN Number',       panNumber],
    ['Mobile Number',    mobileNumber],
    ['Annual Income',    incomeRange],
    ['Loan Amount',      `₹ ${loanAmount.toLocaleString('en-IN')}`],
    ['Property Type',    propTypeLabel],
    ['Bedrooms',         bedroomLabel],
    ['Hall',             hallRaw === 1 ? 'Yes' : 'No'],
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
  // Reset consent checkbox when user goes back to edit
  (document.getElementById('consentCheck') as HTMLInputElement).checked = false;
  (document.getElementById('btnStartFI') as HTMLButtonElement).disabled = true;
});

// Enable Start FI only when consent is checked
document.getElementById('consentCheck')!.addEventListener('change', (e) => {
  const checked = (e.target as HTMLInputElement).checked;
  (document.getElementById('btnStartFI') as HTMLButtonElement).disabled = !checked;
});

document.getElementById('btnStartFI')!.addEventListener('click', () => {
  if (!capturedBasicInfo || !capturedPropertyInfo) { hide('screenReview'); show('screenForm'); return; }
  clearError('reviewError');

  // Route based on loan amount
  const FIELD_INVESTIGATION_LIMIT = 500_000;   // ₹5 Lakh
  if (capturedBasicInfo.loanAmount > FIELD_INVESTIGATION_LIMIT) {
    // Show Video PD coming-soon screen
    const card = document.getElementById('vpdAmountCard')!;
    card.textContent = `₹ ${capturedBasicInfo.loanAmount.toLocaleString('en-IN')}`;
    hide('screenReview');
    show('screenVideoPD');
    return;
  }

  // ≤ ₹5 Lakh → start Field Investigation
  const btn = document.getElementById('btnStartFI') as HTMLButtonElement;
  btn.disabled    = true;
  btn.textContent = 'Starting…';
  bootFI(capturedBasicInfo, capturedPropertyInfo).catch(err => {
    btn.disabled    = false;
    btn.textContent = 'Start Field Investigation';
    showError('reviewError', (err as Error).message);
  });
});

// ── Video PD navigation ────────────────────────────────────────────────────
document.getElementById('btnBackFromVideoPD')!.addEventListener('click', () => {
  hide('screenVideoPD');
  show('screenReview');
});
document.getElementById('btnReduceAmount')!.addEventListener('click', () => {
  hide('screenVideoPD');
  hide('screenReview');
  show('screenForm');
  // Clear loan amount field so user re-enters
  (document.getElementById('loanAmount') as HTMLInputElement).value = '';
  (document.getElementById('loanAmountHint') as HTMLElement).textContent = 'Enter amount in rupees';
});

// ── FI boot ─────────────────────────────────────────────────────────────────

async function bootFI(basicInfo: BasicInfo, propertyInfo: PropertyInfo): Promise<void> {
  // Case ID: firstName_uuid8  (e.g. Ramesh_a3b4c5d6)
  const safeName = basicInfo.firstName.toLowerCase().replace(/[^a-z0-9]/g, '');
  const caseId   = `${safeName}_${crypto.randomUUID().substring(0, 8)}`;
  FiLog.i('Main', `Boot FI: case=${caseId}`);

  await initFiConfig();   // read upload_recording flag from server
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
    await camera.start('user');
  } catch (e) {
    FiLog.w('Main', `Front camera unavailable: ${(e as Error).message}`);
    try { await camera.start('environment'); } catch { FiLog.e('Main', 'Camera unavailable', e); }
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
    propertyInfo,
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
