import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface DocumentRequest {
  steps: string;
  roles: string;
  notes?: string;
  type: 'sop' | 'batch';
}

export interface WordDocumentInfo {
  available: boolean;
  filename: string;
  download_url: string;
}

export interface DocumentResponse {
  success: boolean;
  content: string;
  type: string;
  doc_id: string;
  word_document?: WordDocumentInfo;
  error?: string;
}

export interface FeedbackRequest {
  doc_id: string;
  score: number;
  text?: string;
}

export interface FeedbackResponse {
  success: boolean;
  error?: string;
}

export interface ModelStats {
  total_documents: number;
  documents_with_feedback: number;
  average_feedback_score: number;
  sops: {
    total: number;
    with_feedback: number;
  };
  batch_records: {
    total: number;
    with_feedback: number;
  };
}

export interface StatsResponse {
  success: boolean;
  stats: ModelStats;
  error?: string;
}

@Injectable({
  providedIn: 'root'
})
export class AIService {
  private apiUrl = 'http://localhost:5000';

  constructor(private http: HttpClient) { }

  generateDocument(data: DocumentRequest): Observable<DocumentResponse> {
    return this.http.post<DocumentResponse>(`${this.apiUrl}/api/generate_document`, data);
  }

  submitFeedback(feedback: FeedbackRequest): Observable<FeedbackResponse> {
    return this.http.post<FeedbackResponse>(`${this.apiUrl}/api/feedback`, feedback);
  }

  getModelStats(): Observable<StatsResponse> {
    return this.http.get<StatsResponse>(`${this.apiUrl}/api/stats`);
  }

  triggerTraining(): Observable<FeedbackResponse> {
    return this.http.post<FeedbackResponse>(`${this.apiUrl}/api/train`, {});
  }
}
