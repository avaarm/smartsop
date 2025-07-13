import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, timeout, catchError, throwError, retry } from 'rxjs';

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
  private apiUrl = 'http://localhost:5001';

  constructor(private http: HttpClient) { }

  // Timeout after 60 seconds
  private requestTimeout = 60000;
  
  // Handle HTTP errors
  private handleError(error: HttpErrorResponse | Error) {
    if (error.name === 'TimeoutError') {
      return throwError(() => new Error('Request timed out. The server is taking too long to respond.'));
    }
    
    if (error instanceof HttpErrorResponse) {
      if (error.status === 0) {
        // A client-side or network error occurred
        return throwError(() => new Error('Unable to connect to the server. Please check your connection and make sure the server is running.'));
      } else {
        // The backend returned an unsuccessful response code
        const message = error.error instanceof Object ? error.error.error || 'Server error' : 'Server error';
        return throwError(() => new Error(`Server error: ${message}`));
      }
    }
    
    // For any other type of error
    return throwError(() => error);
  }

  generateDocument(data: DocumentRequest): Observable<DocumentResponse> {
    return this.http.post<DocumentResponse>(`${this.apiUrl}/api/generate_document`, data, {
      // Add withCredentials to ensure cookies are sent with the request
      withCredentials: true
    })
    .pipe(
      retry(1), // Retry the request once before failing
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  submitFeedback(feedback: FeedbackRequest): Observable<FeedbackResponse> {
    return this.http.post<FeedbackResponse>(`${this.apiUrl}/api/feedback`, feedback, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getModelStats(): Observable<StatsResponse> {
    return this.http.get<StatsResponse>(`${this.apiUrl}/api/stats`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  triggerTraining(): Observable<FeedbackResponse> {
    return this.http.post<FeedbackResponse>(`${this.apiUrl}/api/train`, {}, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }
}
