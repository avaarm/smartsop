import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError, timeout } from 'rxjs';

export interface AuditEvent {
  id: number;
  account_id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  summary: string;
  detail: any;
  actor: string;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class AuditService {
  private base(accountId: number) {
    return `/api/accounts/${accountId}/audit`;
  }

  constructor(private http: HttpClient) {}

  list(accountId: number, action = '', page = 1):
    Observable<{ success: boolean; events: AuditEvent[]; total: number; pages: number }> {
    const params = new URLSearchParams({ page: String(page), per_page: '100' });
    if (action) params.set('action', action);
    return this.http.get<any>(`${this.base(accountId)}?${params.toString()}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  exportCsv(accountId: number): Observable<Blob> {
    return this.http.get(`${this.base(accountId)}/export.csv`, { responseType: 'blob' })
      .pipe(timeout(30000), catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) message = 'Cannot connect to server';
    else if (error.error?.error) message = error.error.error;
    return throwError(() => new Error(message));
  }
}
