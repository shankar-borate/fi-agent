export interface FiConfig {
  readonly serverUrl:        string;
  readonly sttTimeoutMs:     number;
  readonly uploadTimeoutMs:  number;
  readonly blurThreshold:    number;
  readonly uploadRecording:  boolean;  // false = skip recording upload (fast demo Submit)
}

let _blurThreshold    = 40;
let _uploadRecording  = true;   // default: record + upload

export const FiConfig: FiConfig = {
  serverUrl:       `${location.protocol}//${location.host}`,
  sttTimeoutMs:    5_000,
  uploadTimeoutMs: 120_000,
  get blurThreshold()   { return _blurThreshold;   },
  get uploadRecording() { return _uploadRecording; },
};

/** Fetch server config once at startup. */
export async function initFiConfig(): Promise<void> {
  try {
    const resp = await fetch(`${FiConfig.serverUrl}/fi/api/fi-session/config`);
    if (resp.ok) {
      const data = await resp.json() as { upload_recording?: boolean };
      if (data.upload_recording === false) {
        _uploadRecording = false;
      }
    }
  } catch {
    // keep defaults
  }
}
