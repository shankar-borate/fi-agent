export interface GeoPoint {
  latitude:  number;
  longitude: number;
  timestamp: string;
}

export interface PropertyInfo {
  propertyType: 'flat' | 'bungalow';
  bedrooms:     1 | 2 | 3;
  hall:         0 | 1;
}

export interface BasicInfo {
  firstName:    string;
  lastName:     string;
  dob:          string;   // ISO date "YYYY-MM-DD"
  address:      string;
  city:         string;
  panNumber:    string;
  mobileNumber: string;
  incomeRange:  string;
  loanAmount:   number;   // in INR
}

export interface QuestionAnswer {
  question: string;
  answer:   string;
  geo:      GeoPoint | null;
}

export interface PhotoCapture {
  prompt:    string;
  tag:       string;     // "selfie" | "kitchen" | "nameplate" | "pan" | …
  isSelfie:  boolean;
  blob:      Blob;
  filename:  string;
  geo:       GeoPoint | null;
  blurScore: number;     // Laplacian variance — higher = sharper
}

export interface DocumentCapture {
  documentType: string;
  filename:     string;
  uploadedAt:   string;
}

export interface FiSession {
  sessionId:     string;
  deviceId:      string;
  startedAt:     string;
  endedAt:       string;
  basicInfo:     BasicInfo;
  propertyInfo:  PropertyInfo | null;
  answers:       QuestionAnswer[];
  photos:        PhotoCapture[];
  documents:     DocumentCapture[];
  recordingBlob: Blob | null;
  recordingName: string | null;
}
