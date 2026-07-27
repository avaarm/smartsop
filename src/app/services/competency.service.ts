import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError, timeout } from 'rxjs';

export type TrainingStatus = 'assigned' | 'acknowledged';

export interface TrainingRecord {
  id: number;
  account_id: number;
  protocol_id: number;
  protocol_title: string;
  protocol_version: number;
  trainee: string;
  assigned_by: string;
  status: TrainingStatus;
  acknowledgement: string;
  acknowledged_at: string | null;
  expires_at: string;
  is_expired: boolean;
  is_current: boolean;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class CompetencyService {
  private base(accountId: number) {
    return `/api/accounts/${accountId}/competency`;
  }

  constructor(private http: HttpClient) {}

  list(accountId: number): Observable<{ success: boolean; training: TrainingRecord[] }> {
    return this.http.get<any>(this.base(accountId))
      .pipe(timeout(15000), catchError(this.handleError));
  }

  assign(accountId: number, data: { protocol_id: number; trainee: string; expires_at?: string }):
    Observable<{ success: boolean; training: TrainingRecord }> {
    return this.http.post<any>(this.base(accountId), data)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  acknowledge(accountId: number, id: number, acknowledgement?: string):
    Observable<{ success: boolean; training: TrainingRecord }> {
    return this.http.post<any>(`${this.base(accountId)}/${id}/acknowledge`,
                               acknowledgement ? { acknowledgement } : {})
      .pipe(timeout(15000), catchError(this.handleError));
  }

  remove(accountId: number, id: number): Observable<{ success: boolean }> {
    return this.http.delete<any>(`${this.base(accountId)}/${id}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) message = 'Cannot connect to server';
    else if (error.error?.error) message = error.error.error;
    return throwError(() => new Error(message));
  }
}
