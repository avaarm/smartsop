import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError, timeout } from 'rxjs';

export interface Comment {
  id: number;
  account_id: number;
  protocol_id: number;
  step_id: number | null;
  parent_id: number | null;
  body: string;
  author: string;
  author_user_id: number | null;
  is_pinned: boolean;
  resolved: boolean;
  resolved_by: string;
  resolved_at: string | null;
  level: 'step' | 'protocol';
  created_at: string;
  updated_at: string;
}

@Injectable({ providedIn: 'root' })
export class CommentService {
  private base(accountId: number, protocolId: number) {
    return `/api/accounts/${accountId}/protocols/${protocolId}/comments`;
  }

  constructor(private http: HttpClient) {}

  list(accountId: number, protocolId: number):
    Observable<{ success: boolean; comments: Comment[] }> {
    return this.http.get<any>(this.base(accountId, protocolId))
      .pipe(timeout(15000), catchError(this.handleError));
  }

  create(accountId: number, protocolId: number,
         data: { body: string; step_id?: number | null; parent_id?: number }):
    Observable<{ success: boolean; comment: Comment }> {
    return this.http.post<any>(this.base(accountId, protocolId), data)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  update(accountId: number, protocolId: number, id: number,
         patch: { body?: string; is_pinned?: boolean; resolved?: boolean }):
    Observable<{ success: boolean; comment: Comment }> {
    return this.http.patch<any>(`${this.base(accountId, protocolId)}/${id}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  remove(accountId: number, protocolId: number, id: number): Observable<{ success: boolean }> {
    return this.http.delete<any>(`${this.base(accountId, protocolId)}/${id}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) message = 'Cannot connect to server';
    else if (error.error?.error) message = error.error.error;
    return throwError(() => new Error(message));
  }
}
