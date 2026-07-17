import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError, timeout } from 'rxjs';

export interface Reagent {
  name: string;
  amount?: string;
  vendor?: string;
}

export interface ProtocolStep {
  id: number;
  protocol_id: number;
  order_index: number;
  section: string;
  title: string;
  description: string;
  duration_seconds: number | null;
  warning: string;
  reagents: Reagent[];
  created_at: string;
}

export interface Protocol {
  id: number;
  account_id: number;
  title: string;
  description: string;
  status: 'draft' | 'published';
  version: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  step_count: number;
  steps?: ProtocolStep[];
}

export type RunStepStatus = 'pending' | 'done' | 'failed' | 'skipped';

export interface ProtocolRunStep {
  id: number;
  run_id: number;
  step_id: number | null;
  order_index: number;
  title: string;
  description: string;
  duration_seconds: number | null;
  warning: string;
  reagents: Reagent[];
  status: RunStepStatus;
  note: string;
  completed_by: string;
  completed_at: string | null;
}

export interface ProtocolRun {
  id: number;
  account_id: number;
  protocol_id: number;
  protocol_title: string;
  protocol_version: number;
  experiment_id: string;
  status: 'running' | 'completed';
  started_by: string;
  started_at: string;
  completed_at: string | null;
  completed_steps: number;
  total_steps: number;
  steps?: ProtocolRunStep[];
}

export interface StepInput {
  section?: string;
  title?: string;
  description?: string;
  duration_seconds?: number | null;
  warning?: string;
  reagents?: Reagent[];
}

@Injectable({ providedIn: 'root' })
export class ProtocolService {
  private base(accountId: number) {
    return `/api/accounts/${accountId}/protocols`;
  }

  constructor(private http: HttpClient) {}

  listProtocols(accountId: number, page = 1):
    Observable<{ success: boolean; protocols: Protocol[]; total: number; page: number; pages: number }> {
    return this.http.get<any>(`${this.base(accountId)}?page=${page}&per_page=50`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  createProtocol(accountId: number, data: { title: string; description?: string }):
    Observable<{ success: boolean; protocol: Protocol }> {
    return this.http.post<any>(this.base(accountId), data)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  getProtocol(accountId: number, id: number): Observable<{ success: boolean; protocol: Protocol }> {
    return this.http.get<any>(`${this.base(accountId)}/${id}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  updateProtocol(accountId: number, id: number, patch: Partial<Pick<Protocol, 'title' | 'description' | 'status'>>):
    Observable<{ success: boolean; protocol: Protocol }> {
    return this.http.put<any>(`${this.base(accountId)}/${id}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  deleteProtocol(accountId: number, id: number): Observable<{ success: boolean }> {
    return this.http.delete<any>(`${this.base(accountId)}/${id}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  addStep(accountId: number, protocolId: number, step: StepInput):
    Observable<{ success: boolean; step: ProtocolStep }> {
    return this.http.post<any>(`${this.base(accountId)}/${protocolId}/steps`, step)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  updateStep(accountId: number, protocolId: number, stepId: number, patch: StepInput):
    Observable<{ success: boolean; step: ProtocolStep }> {
    return this.http.put<any>(`${this.base(accountId)}/${protocolId}/steps/${stepId}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  deleteStep(accountId: number, protocolId: number, stepId: number): Observable<{ success: boolean }> {
    return this.http.delete<any>(`${this.base(accountId)}/${protocolId}/steps/${stepId}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  reorderSteps(accountId: number, protocolId: number, order: number[]): Observable<{ success: boolean }> {
    return this.http.post<any>(`${this.base(accountId)}/${protocolId}/steps/reorder`, { order })
      .pipe(timeout(15000), catchError(this.handleError));
  }

  // ── Runs ──

  startRun(accountId: number, protocolId: number, experimentId = ''):
    Observable<{ success: boolean; run: ProtocolRun }> {
    return this.http.post<any>(`${this.base(accountId)}/${protocolId}/runs`, { experiment_id: experimentId })
      .pipe(timeout(15000), catchError(this.handleError));
  }

  listRuns(accountId: number, protocolId?: number):
    Observable<{ success: boolean; runs: ProtocolRun[]; total: number }> {
    const q = protocolId ? `?protocol_id=${protocolId}` : '';
    return this.http.get<any>(`/api/accounts/${accountId}/runs${q}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  getRun(accountId: number, runId: number): Observable<{ success: boolean; run: ProtocolRun }> {
    return this.http.get<any>(`/api/accounts/${accountId}/runs/${runId}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  updateRun(accountId: number, runId: number, patch: { experiment_id?: string }):
    Observable<{ success: boolean; run: ProtocolRun }> {
    return this.http.put<any>(`/api/accounts/${accountId}/runs/${runId}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  setRunStep(accountId: number, runId: number, runStepId: number,
             patch: { status?: RunStepStatus; note?: string }):
    Observable<{ success: boolean; step: ProtocolRunStep }> {
    return this.http.patch<any>(`/api/accounts/${accountId}/runs/${runId}/steps/${runStepId}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  finishRun(accountId: number, runId: number): Observable<{ success: boolean; run: ProtocolRun }> {
    return this.http.post<any>(`/api/accounts/${accountId}/runs/${runId}/finish`, {})
      .pipe(timeout(15000), catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) message = 'Cannot connect to server';
    else if (error.error?.error) message = error.error.error;
    return throwError(() => new Error(message));
  }
}
