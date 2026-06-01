import { GeoPoint } from '../domain/models';

/** Discriminated union — mirrors Android's sealed class UiState exactly. */
export type UiState =
  | { kind: 'Connecting' }
  | { kind: 'ShowMessage';    text: string }
  | { kind: 'Listening';      questionIndex: number; remaining: number }
  | { kind: 'ShowTranscript'; text: string; isFinal: boolean }
  | { kind: 'ConfirmAnswer';    text: string; remaining: number; geo: GeoPoint | null }
  | { kind: 'ConsentRequest';   message: string }
  | { kind: 'ConsentProcessing' }
  | { kind: 'Countdown';        remaining: number; prompt: string }
  | { kind: 'CaptureNow';     isSelfie: boolean; index: number; prompt: string }
  | { kind: 'ReviewPhoto';    blob: Blob; prompt: string; isSelfie: boolean; index: number; geo: GeoPoint | null }
  | { kind: 'UploadingPhoto'; index: number }
  | { kind: 'ReadyToSubmit';  caseId: string; photoCount: number; hasRecording: boolean }
  | { kind: 'Uploading' }
  | { kind: 'Done';           caseId: string; mobileNumber: string }
  | { kind: 'Error';          message: string; showRetry: boolean };
