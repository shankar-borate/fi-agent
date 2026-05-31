export interface FiConfig {
  readonly serverUrl:        string;
  readonly sttTimeoutMs:     number;
  readonly uploadTimeoutMs:  number;
  readonly transcribeEngine: string;
  readonly blurThreshold:    number;   // Laplacian RMS below this → retake
}

let _transcribeEngine = 'aws';
let _blurThreshold    = 40;

export const FiConfig: FiConfig = {
  serverUrl:       `${location.protocol}//${location.host}`,
  sttTimeoutMs:    5_000,
  uploadTimeoutMs: 120_000,
  get transcribeEngine() { return _transcribeEngine; },
  get blurThreshold()    { return _blurThreshold;    },
};

/** Fetch server config once at startup to pick up transcribe_engine setting. */
export async function initFiConfig(): Promise<void> {
  try {
    const resp = await fetch(`${FiConfig.serverUrl}/fi/api/fi-session/config`);
    if (resp.ok) {
      const data = await resp.json() as { transcribe_engine?: string };
      _transcribeEngine = data.transcribe_engine ?? 'aws';
    }
  } catch {
    // keep default 'aws'
  }
}
