import { FiLog } from '../services/FiLog';

export interface PhotoUploadResponse {
  status:   string;
  filename: string;
}

export interface UploadResponse {
  session_id:     string;
  status:         string;
  session_folder: string;
  files_saved:    string[];
  message:        string;
}

export interface DocumentUploadResponse {
  status:        string;
  filename:      string;
  document_type: string;
}

/**
 * Thin HTTP client for the FI Agent REST API.
 * All methods delegate to the private _post helper to avoid duplicating
 * the fetch → error-check → JSON-parse pattern.
 */
export class FiApiClient {
  constructor(private readonly baseUrl: string) {}

  /** POST /fi/api/fi-session/{caseId}/photo */
  async uploadPhoto(
    caseId:   string,
    blob:     Blob,
    filename: string,
    metaJson: string,
  ): Promise<PhotoUploadResponse> {
    const form = new FormData();
    form.append('photo',     blob,    filename);
    form.append('meta_json', metaJson);
    FiLog.i('Api', `uploadPhoto → ${filename}`);
    return this._post<PhotoUploadResponse>(`/fi/api/fi-session/${caseId}/photo`, form);
  }

  /** POST /fi/api/fi-session/{caseId}/document */
  async uploadDocument(
    caseId:       string,
    file:         File,
    documentType: string,
  ): Promise<DocumentUploadResponse> {
    const form = new FormData();
    form.append('document',      file, file.name);
    form.append('document_type', documentType);
    FiLog.i('Api', `uploadDocument → ${file.name}  type=${documentType}`);
    return this._post<DocumentUploadResponse>(`/fi/api/fi-session/${caseId}/document`, form);
  }

  /** POST /fi/api/fi-session/{caseId}/submit */
  async submitSession(
    caseId:        string,
    metadataJson:  string,
    recordingBlob: Blob | null,
    recordingName: string | null,
  ): Promise<UploadResponse> {
    const form = new FormData();
    form.append('metadata_json', metadataJson);
    if (recordingBlob && recordingName) {
      form.append('recording', recordingBlob, recordingName);
    }
    FiLog.i('Api', `submitSession → case=${caseId}  rec=${recordingName ?? 'none'}`);
    return this._post<UploadResponse>(`/fi/api/fi-session/${caseId}/submit`, form);
  }

  // ── Private helpers ────────────────────────────────────────────────────

  private async _post<T>(path: string, body: FormData): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`, { method: 'POST', body });
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      throw new Error(`HTTP ${resp.status}: ${text}`);
    }
    return resp.json() as Promise<T>;
  }
}
