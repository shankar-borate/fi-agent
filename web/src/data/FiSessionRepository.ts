import { FiApiClient, DocumentUploadResponse, UploadResponse } from './FiApiClient';
import { FiSession, PhotoCapture } from '../domain/models';
import { DeviceDetector } from '../services/DeviceDetector';

export class FiSessionRepository {
  constructor(private readonly api: FiApiClient) {}

  async uploadPhoto(caseId: string, photo: PhotoCapture): Promise<void> {
    const meta = JSON.stringify({
      prompt:    photo.prompt,
      is_selfie: photo.isSelfie,
      geo:       photo.geo,
    });
    await this.api.uploadPhoto(caseId, photo.blob, photo.filename, meta);
  }

  async uploadDocument(
    caseId: string, file: File, documentType: string,
  ): Promise<DocumentUploadResponse> {
    return this.api.uploadDocument(caseId, file, documentType);
  }

  async submitSession(session: FiSession): Promise<UploadResponse> {
    const dev = DeviceDetector.detect();
    const metadata = JSON.stringify({
      session_id:  session.sessionId,
      device_id:   session.deviceId,
      device_info: {
        user_agent:  dev.userAgent,
        browser:     dev.browser,
        os:          dev.os,
        device_type: dev.deviceType,
        screen_size: dev.screenSize,
        language:    dev.language,
      },
      started_at:  session.startedAt,
      ended_at:    session.endedAt,
      basic_info: {
        first_name:    session.basicInfo.firstName,
        last_name:     session.basicInfo.lastName,
        dob:           session.basicInfo.dob,
        address:       session.basicInfo.address,
        city:          session.basicInfo.city,
        pan_number:    session.basicInfo.panNumber,
        mobile_number: session.basicInfo.mobileNumber,
        income_range:  session.basicInfo.incomeRange,
        loan_amount:   session.basicInfo.loanAmount,
      },
      property_info: session.propertyInfo ? {
        property_type: session.propertyInfo.propertyType,
        bedrooms:      session.propertyInfo.bedrooms,
        hall:          session.propertyInfo.hall,
      } : null,
      questions:   session.answers.map(a => ({
        question: a.question,
        answer:   a.answer,
        geo:      a.geo,
      })),
      photos:      session.photos.map(p => ({
        prompt:     p.prompt,
        tag:        p.tag,
        filename:   p.filename,
        is_selfie:  p.isSelfie,
        geo:        p.geo,
        blur_score: p.blurScore,
      })),
      documents:   session.documents.map(d => ({
        document_type: d.documentType,
        filename:      d.filename,
        uploaded_at:   d.uploadedAt,
      })),
      recording_filename: session.recordingName ?? null,
    });

    return this.api.submitSession(
      session.sessionId,
      metadata,
      session.recordingBlob,
      session.recordingName,
    );
  }
}
