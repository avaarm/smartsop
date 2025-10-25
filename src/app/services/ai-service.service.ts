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
  message?: string;
  num_examples?: number;
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

export interface TrainingMetrics {
  training_loss: number;
  eval_results: any;
  num_examples: number;
  timestamp: string;
  model_save_path: string;
  training_time_seconds?: number;
  training_hyperparameters?: {
    learning_rate: number;
    batch_size: number;
    num_epochs: number;
    use_gradient_checkpointing: boolean;
    weight_decay: number;
    warmup_ratio?: number;
    max_length?: number;
    fp16?: boolean;
  };
}

export interface TrainingStatusResponse {
  success: boolean;
  training_history: TrainingMetrics[];
  is_training_in_progress: boolean;
  latest_model: string | null;
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

  triggerTraining(options: { 
    min_feedback_score?: number, 
    min_examples?: number,
    advanced_options?: {
      num_epochs?: number;
      learning_rate?: number;
      batch_size?: number;
      use_gradient_checkpointing?: boolean;
      early_stopping_patience?: number;
    }
  } = {}): Observable<FeedbackResponse> {
    return this.http.post<FeedbackResponse>(`${this.apiUrl}/api/train`, options, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }
  
  getTrainingStatus(): Observable<TrainingStatusResponse> {
    return this.http.get<TrainingStatusResponse>(`${this.apiUrl}/api/training/status`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Document export methods
  exportDocument(content: string, format: string, title?: string, docId?: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/api/export/${format}`, {
      content,
      title,
      doc_id: docId
    }, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getExportFormats(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/api/export/formats`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  downloadDocument(filename: string): string {
    return `${this.apiUrl}/api/download/${filename}`;
  }
}
