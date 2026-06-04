export interface FiConfig {
  readonly serverUrl:        string;
  readonly sttTimeoutMs:     number;
  readonly uploadTimeoutMs:  number;
  readonly blurThreshold:    number;   // Laplacian RMS below this → retake
}

let _blurThreshold = 40;

export const FiConfig: FiConfig = {
  serverUrl:       `${location.protocol}//${location.host}`,
  sttTimeoutMs:    5_000,
  uploadTimeoutMs: 120_000,
  get blurThreshold() { return _blurThreshold; },
};
