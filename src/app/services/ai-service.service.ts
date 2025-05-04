import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface DocumentRequest {
  steps: string;
  roles: string;
  notes?: string;
  type: 'sop' | 'batch';
}

export interface DocumentResponse {
  success: boolean;
  content: string;
  type: string;
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
}
