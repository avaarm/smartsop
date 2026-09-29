import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError, timeout } from 'rxjs';

export interface Reagent {
  name: string;
  amount?: string;
  vendor?: string;
}

export interface StepComponent {
  type: string;
  value: string | boolean;
}

export interface BranchOption {
  label: string;
  action: 'continue' | 'goto' | 'halt';
  target: number | null;   // 1-based step number for 'goto'
}
export interface StepBranch {
  question: string;
  options: BranchOption[];
}

/** Typed LOTO/safety component library — label, icon, and whether it's a flag. */
export const COMPONENT_LIBRARY: { type: string; label: string; icon: string; flag?: boolean }[] = [
  { type: 'ppe', label: 'PPE required', icon: '🥽' },
  { type: 'energy_source', label: 'Energy source', icon: '⚡' },
  { type: 'isolation_device', label: 'Isolation device', icon: '🔒' },
  { type: 'lockout_tag', label: 'Lockout tag ID', icon: '🏷️' },
  { type: 'authorized_person', label: 'Authorized person', icon: '👤' },
  { type: 'hazard_class', label: 'Hazard class', icon: '☣️' },
  { type: 'torque', label: 'Torque spec', icon: '🔧' },
  { type: 'pressure', label: 'Pressure spec', icon: '🎚️' },
  { type: 'temperature', label: 'Temperature', icon: '🌡️' },
  { type: 'expected_result', label: 'Expected result', icon: '✅' },
  { type: 'return_to_service', label: 'Return-to-service check', icon: '🔄' },
  { type: 'verification_photo', label: 'Verification photo required', icon: '📷', flag: true },
  { type: 'second_signature', label: 'Second signature required', icon: '✍️', flag: true },
];

export function componentMeta(type: string) {
  return COMPONENT_LIBRARY.find(c => c.type === type)
    || { type, label: type, icon: '•', flag: false };
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
  components: StepComponent[];
  branch: StepBranch | null;
  created_at: string;
}

export type ProtocolType = 'protocol' | 'sop' | 'gmp_sop';
export type ProtocolStatus = 'draft' | 'in_review' | 'approved' | 'effective' | 'retired' | 'rejected';

export interface ProtocolSignoff {
  id: number;
  role: 'reviewer' | 'approver' | 'author';
  decision: 'approved' | 'rejected';
  meaning: string;
  comment: string;
  signed_by: string;
  signed_at: string;
}

export interface Protocol {
  id: number;
  account_id: number;
  title: string;
  description: string;
  protocol_type: ProtocolType;
  status: ProtocolStatus;
  version: number;
  created_by: string;
  sop_number: string;
  department: string;
  effective_date: string;
  review_date: string;
  supersedes_id: number | null;
  is_template: boolean;
  template_category: string;
  doc_format?: 'steps' | 'document';
  has_original?: boolean;
  original_filename?: string;
  doc_category?: string;
  product_code?: string;
  created_at: string;
  updated_at: string;
  step_count: number;
  signoffs: ProtocolSignoff[];
  steps?: ProtocolStep[];
  body?: DocBlock[];
}

/** A facility document-taxonomy category (EQ, QA, TM, BR, …). */
export interface DocCategory {
  code: string;
  name: string;
  kind: 'procedure' | 'record';
  description: string;
  examples: string[];
  template_count: number;
  effective_count: number;
}

/** A built-in facility document template (the "what do you want to write?" starters). */
export interface DocTemplate {
  key: string;
  name: string;
  doc_category: string;
  protocol_type: ProtocolType;
  doc_format: 'steps' | 'document';
  description: string;
  standard: string;
}

/** One block of a document-format protocol, preserving the original layout. */
export interface DocBlock {
  type: 'heading' | 'paragraph' | 'checkbox' | 'table';
  text?: string;
  level?: number;
  checked?: boolean;
  rows?: string[][];
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
  components: StepComponent[];
  branch: StepBranch | null;
  status: RunStepStatus;
  note: string;
  completed_by: string;
  completed_at: string | null;
  verification?: string;
  witnessed_by?: string;
  witnessed_at?: string | null;
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

export interface Analytics {
  totals: {
    protocols: number; effective_sops: number; runs: number; completed_runs: number;
    deviations: number; open_deviations: number;
  };
  outcomes: { done: number; failed: number; skipped: number; pending: number };
  deviation_severity: { minor: number; major: number; critical: number };
  avg_run_duration_seconds: number;
  runs_by_week: { week_ending: string; runs: number }[];
  top_protocols: { title: string; runs: number }[];
}

export interface ProtocolVersion {
  id: number;
  version: number;
  status: ProtocolStatus;
  created_by: string;
  created_at: string;
  effective_date: string;
  step_count: number;
  is_current: boolean;
}

export interface StepDiff {
  index: number;
  change: 'unchanged' | 'added' | 'removed' | 'modified';
  title: string;
  fields?: string[];
}
export interface MetaChange {
  field: string;
  from: string;
  to: string;
}
export interface VersionDiff {
  meta_changes: MetaChange[];
  steps: StepDiff[];
}

/** A prebuilt regulatory SOP a workspace can start from. */
export interface ProtocolTemplate {
  key: string;
  name: string;
  standard: string;
  category: string;
  description: string;
  protocol_type: ProtocolType;
  step_count: number;
}

export type DeviationSeverity = 'minor' | 'major' | 'critical';
export type DeviationStatus = 'open' | 'investigating' | 'resolved' | 'closed';

export interface Deviation {
  id: number;
  account_id: number;
  protocol_id: number | null;
  run_id: number | null;
  run_step_id: number | null;
  step_title: string;
  title: string;
  description: string;
  severity: DeviationSeverity;
  status: DeviationStatus;
  corrective_action: string;
  reported_by: string;
  assigned_to: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface DeviationInput {
  title: string;
  description?: string;
  severity?: DeviationSeverity;
  run_id?: number;
  run_step_id?: number;
  protocol_id?: number;
  step_title?: string;
  assigned_to?: string;
}

export interface StepInput {
  section?: string;
  title?: string;
  description?: string;
  duration_seconds?: number | null;
  warning?: string;
  reagents?: Reagent[];
  components?: StepComponent[];
  branch?: StepBranch | null;
}

@Injectable({ providedIn: 'root' })
export class ProtocolService {
  private base(accountId: number) {
    return `/api/accounts/${accountId}/protocols`;
  }

  constructor(private http: HttpClient) {}

  listProtocols(accountId: number, page = 1, q = ''):
    Observable<{ success: boolean; protocols: Protocol[]; total: number; page: number; pages: number }> {
    const query = q ? `&q=${encodeURIComponent(q)}` : '';
    return this.http.get<any>(`${this.base(accountId)}?page=${page}&per_page=50${query}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** The org's own reusable template library (documents saved as templates). */
  listTemplateLibrary(accountId: number):
    Observable<{ success: boolean; protocols: Protocol[]; total: number }> {
    return this.http.get<any>(`${this.base(accountId)}?templates=true&per_page=100`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** Save a copy of a document into the org template library under a category. */
  saveAsTemplate(accountId: number, id: number, category: string, title?: string):
    Observable<{ success: boolean; template: Protocol }> {
    return this.http.post<any>(`${this.base(accountId)}/${id}/save-as-template`, { category, title })
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

  listTemplates(accountId: number): Observable<{ success: boolean; templates: ProtocolTemplate[] }> {
    return this.http.get<any>(`${this.base(accountId)}/templates`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  createFromTemplate(accountId: number, key: string, title?: string):
    Observable<{ success: boolean; protocol: Protocol }> {
    return this.http.post<any>(`${this.base(accountId)}/from-template`, { key, title })
      .pipe(timeout(20000), catchError(this.handleError));
  }

  /** The facility document taxonomy with per-category template & effective counts. */
  docCategories(accountId: number): Observable<{ success: boolean; categories: DocCategory[] }> {
    return this.http.get<any>(`${this.base(accountId)}/doc-categories`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** Built-in facility document templates (optionally for one category). */
  docTemplates(accountId: number, category?: string):
    Observable<{ success: boolean; templates: DocTemplate[] }> {
    const q = category ? `?category=${encodeURIComponent(category)}` : '';
    return this.http.get<any>(`${this.base(accountId)}/doc-templates${q}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** Start a new document from a built-in template, filling any {{variables}}. */
  createFromDocTemplate(accountId: number, key: string,
                        opts?: { title?: string; variables?: Record<string, string> }):
    Observable<{ success: boolean; protocol: Protocol }> {
    return this.http.post<any>(`${this.base(accountId)}/from-doc-template`, { key, ...(opts || {}) })
      .pipe(timeout(20000), catchError(this.handleError));
  }

  importFromText(accountId: number,
                 body: { title?: string; text: string; mode: string; as_template?: boolean; category?: string }):
    Observable<{ success: boolean; protocol: Protocol; mode: string; step_count: number }> {
    return this.http.post<any>(`${this.base(accountId)}/import`, body)
      .pipe(timeout(90000), catchError(this.handleError));
  }

  importFromFile(accountId: number, form: FormData):
    Observable<{ success: boolean; protocol: Protocol; mode: string; step_count: number }> {
    return this.http.post<any>(`${this.base(accountId)}/import`, form)
      .pipe(timeout(90000), catchError(this.handleError));
  }

  updateProtocol(accountId: number, id: number,
                 patch: Partial<Pick<Protocol, 'title' | 'description' | 'protocol_type' | 'sop_number' | 'department' | 'review_date'>>
                   & { body?: DocBlock[] }):
    Observable<{ success: boolean; protocol: Protocol }> {
    return this.http.put<any>(`${this.base(accountId)}/${id}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** Download the exact file that was uploaded (byte-faithful). */
  downloadOriginal(accountId: number, id: number): Observable<Blob> {
    return this.http.get(`${this.base(accountId)}/${id}/original`, { responseType: 'blob' })
      .pipe(timeout(30000), catchError(this.handleError));
  }

  /** Fill {{variables}} into the document and download a matching .docx. */
  renderDocx(accountId: number, id: number, variables: Record<string, string>): Observable<Blob> {
    return this.http.post(`${this.base(accountId)}/${id}/render.docx`, { variables }, { responseType: 'blob' })
      .pipe(timeout(30000), catchError(this.handleError));
  }

  // ── Controlled-document lifecycle ──

  private lifecycle(accountId: number, id: number, action: string, body: any = {}):
    Observable<{ success: boolean; protocol: Protocol }> {
    return this.http.post<any>(`${this.base(accountId)}/${id}/${action}`, body)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  submitProtocol(accountId: number, id: number) { return this.lifecycle(accountId, id, 'submit'); }

  signProtocol(accountId: number, id: number,
               body: { role: 'reviewer' | 'approver'; decision: 'approved' | 'rejected'; password: string; meaning?: string; comment?: string }) {
    return this.lifecycle(accountId, id, 'sign', body);
  }

  makeEffective(accountId: number, id: number, body: { review_date?: string } = {}) {
    return this.lifecycle(accountId, id, 'make-effective', body);
  }

  retireProtocol(accountId: number, id: number) { return this.lifecycle(accountId, id, 'retire'); }

  newVersion(accountId: number, id: number) { return this.lifecycle(accountId, id, 'new-version'); }

  /** Fork a protocol into a new independent draft (its own version-1 lineage).
      Optionally fill {{placeholders}} and set a title when starting from a template. */
  copyProtocol(accountId: number, id: number,
               opts?: { title?: string; variables?: Record<string, string> }):
    Observable<{ success: boolean; protocol: Protocol }> {
    return this.http.post<any>(`${this.base(accountId)}/${id}/copy`, opts || {})
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** The {{placeholders}} a template defines, so 'use' can prompt to fill them. */
  templateVariables(accountId: number, id: number):
    Observable<{ success: boolean; variables: string[] }> {
    return this.http.get<any>(`${this.base(accountId)}/${id}/template-variables`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** Download an export (json|pdf) as a Blob; the interceptor adds auth. */
  exportProtocol(accountId: number, id: number, format: 'json' | 'pdf'): Observable<Blob> {
    return this.http.get(`${this.base(accountId)}/${id}/export.${format}`, { responseType: 'blob' })
      .pipe(timeout(30000), catchError(this.handleError));
  }

  // ── Version history / diff / rollback ──

  listVersions(accountId: number, id: number):
    Observable<{ success: boolean; versions: ProtocolVersion[] }> {
    return this.http.get<any>(`${this.base(accountId)}/${id}/versions`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  diffVersions(accountId: number, id: number, fromId?: number, toId?: number):
    Observable<{ success: boolean; from: ProtocolVersion; to: ProtocolVersion; diff: VersionDiff }> {
    const params = new URLSearchParams();
    if (fromId) params.set('from', String(fromId));
    if (toId) params.set('to', String(toId));
    const q = params.toString() ? `?${params.toString()}` : '';
    return this.http.get<any>(`${this.base(accountId)}/${id}/diff${q}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  restoreVersion(accountId: number, id: number, sourceId: number):
    Observable<{ success: boolean; protocol: Protocol; restored_from: number }> {
    return this.http.post<any>(`${this.base(accountId)}/${id}/restore`, { source_id: sourceId })
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
             patch: { status?: RunStepStatus; note?: string; verification?: string;
                      witness_email?: string; witness_password?: string }):
    Observable<{ success: boolean; step: ProtocolRunStep }> {
    return this.http.patch<any>(`/api/accounts/${accountId}/runs/${runId}/steps/${runStepId}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  finishRun(accountId: number, runId: number): Observable<{ success: boolean; run: ProtocolRun }> {
    return this.http.post<any>(`/api/accounts/${accountId}/runs/${runId}/finish`, {})
      .pipe(timeout(15000), catchError(this.handleError));
  }

  getAnalytics(accountId: number): Observable<{ success: boolean } & Analytics> {
    return this.http.get<any>(`/api/accounts/${accountId}/analytics`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  // ── Deviations / corrective actions (CAPA) ──

  listDeviations(accountId: number, filters: { status?: string; severity?: string; run_id?: number } = {}):
    Observable<{ success: boolean; deviations: Deviation[]; total: number }> {
    const params = new URLSearchParams({ per_page: '100' });
    if (filters.status) params.set('status', filters.status);
    if (filters.severity) params.set('severity', filters.severity);
    if (filters.run_id) params.set('run_id', String(filters.run_id));
    return this.http.get<any>(`/api/accounts/${accountId}/deviations?${params.toString()}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  flagDeviation(accountId: number, body: DeviationInput):
    Observable<{ success: boolean; deviation: Deviation }> {
    return this.http.post<any>(`/api/accounts/${accountId}/deviations`, body)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  updateDeviation(accountId: number, id: number,
                  patch: Partial<Pick<Deviation, 'status' | 'severity' | 'corrective_action' | 'assigned_to' | 'title' | 'description'>>):
    Observable<{ success: boolean; deviation: Deviation }> {
    return this.http.patch<any>(`/api/accounts/${accountId}/deviations/${id}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) message = 'Cannot connect to server';
    else if (error.error?.error) message = error.error.error;
    return throwError(() => new Error(message));
  }
}
