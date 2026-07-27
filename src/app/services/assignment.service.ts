import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError, timeout } from 'rxjs';

import { ProtocolRun } from './protocol.service';

export type AssignmentStatus = 'pending' | 'completed' | 'cancelled';
export type Recurrence = 'none' | 'daily' | 'weekly' | 'monthly';

export interface Assignment {
  id: number;
  account_id: number;
  protocol_id: number;
  protocol_title: string;
  assigned_to: string;
  assigned_by: string;
  due_date: string;
  status: AssignmentStatus;
  recurrence: Recurrence;
  notes: string;
  run_id: number | null;
  is_overdue: boolean;
  created_at: string;
  completed_at: string | null;
}

export interface AssignmentInput {
  protocol_id?: number;
  assigned_to?: string;
  due_date?: string;
  recurrence?: Recurrence;
  notes?: string;
  status?: AssignmentStatus;
}

@Injectable({ providedIn: 'root' })
export class AssignmentService {
  private base(accountId: number) {
    return `/api/accounts/${accountId}/assignments`;
  }

  constructor(private http: HttpClient) {}

  list(accountId: number, status?: string):
    Observable<{ success: boolean; assignments: Assignment[] }> {
    const q = status ? `?status=${status}` : '';
    return this.http.get<any>(`${this.base(accountId)}${q}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  create(accountId: number, data: AssignmentInput):
    Observable<{ success: boolean; assignment: Assignment }> {
    return this.http.post<any>(this.base(accountId), data)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  update(accountId: number, id: number, patch: AssignmentInput):
    Observable<{ success: boolean; assignment: Assignment; next_occurrence?: Assignment }> {
    return this.http.patch<any>(`${this.base(accountId)}/${id}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  remove(accountId: number, id: number): Observable<{ success: boolean }> {
    return this.http.delete<any>(`${this.base(accountId)}/${id}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  start(accountId: number, id: number):
    Observable<{ success: boolean; run: ProtocolRun; assignment: Assignment }> {
    return this.http.post<any>(`${this.base(accountId)}/${id}/start`, {})
      .pipe(timeout(15000), catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) message = 'Cannot connect to server';
    else if (error.error?.error) message = error.error.error;
    return throwError(() => new Error(message));
  }
}
