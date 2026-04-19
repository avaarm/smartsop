import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError, timeout, BehaviorSubject } from 'rxjs';
import { tap } from 'rxjs/operators';

export interface Account {
  id: number;
  name: string;
  slug: string;
  facility_name: string;
  department: string;
  default_product: string;
  default_process: string;
  terminology: string; // JSON string
  style_notes: string;
  reference_sops: string; // JSON string
  created_at: string;
  document_count: number;
  training_example_count: number;
}

export interface AccountInput {
  name?: string;
  facility_name?: string;
  department?: string;
  default_product?: string;
  default_process?: string;
  style_notes?: string;
  terminology?: Record<string, string>;
  reference_sops?: string[];
}

export interface DocumentRecord {
  id: number;
  account_id: number;
  doc_type: string;
  title: string;
  product_name: string;
  process_type: string;
  description: string;
  doc_number: string;
  revision: string;
  filename: string;
  status: string;
  created_at: string;
}

export interface TrainingExample {
  id: number;
  account_id: number;
  document_id: number | null;
  section_type: string;
  system_prompt: string;
  user_prompt: string;
  completion: string;
  source: string;
  quality_rating: number | null;
  product_name: string;
  process_type: string;
  created_at: string;
}

export interface TrainingStats {
  total_examples: number;
  by_source: { ai: number; user_edited: number; manual: number };
  rated: number;
  documents_generated: number;
}

export interface ProtocolUpload {
  id: number;
  account_id: number;
  filename: string;
  file_type: string;
  status: string;
  error_message: string | null;
  structure_json: string;
  formatting_json: string;
  /** Template ID (matches backend templates in ml_model/gmp/templates/). Empty = unknown. */
  doc_type: string;
  /** Where the doc_type came from: 'inferred' (auto-detected) or 'user' (manually chosen). */
  doc_type_source: 'inferred' | 'user';
  created_at: string;
  knowledge: ProtocolKnowledge[];
}

/** Small summary of the consolidated account style for banner-style UI. */
export interface EffectiveStyleSummary {
  upload_count: number;
  analyzed_upload_count: number;
  has_learned_style: boolean;
  orientation: string | null;
  body_font_name: string | null;
  body_font_size_pt: number | null;
  section_header_shading: string | null;
  label_cell_shading: string | null;
  terminology_count: number;
  rules_count: number;
  table_templates_count: number;
}

export interface EffectiveStyleResponse {
  success: boolean;
  doc_type: string | null;
  summary: EffectiveStyleSummary;
  style: Record<string, unknown>;
}

export interface ProtocolKnowledge {
  id: number;
  account_id: number;
  upload_id: number;
  category: string;
  knowledge_json: string;
  summary: string;
  confidence: number | null;
  is_active: boolean;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class AccountService {
  private baseUrl = '/api/accounts';

  activeAccount$ = new BehaviorSubject<Account | null>(null);

  constructor(private http: HttpClient) {}

  // ── Account CRUD ──

  listAccounts(): Observable<{ success: boolean; accounts: Account[] }> {
    return this.http.get<{ success: boolean; accounts: Account[] }>(
      this.baseUrl
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  createAccount(data: AccountInput): Observable<{ success: boolean; account: Account }> {
    return this.http.post<{ success: boolean; account: Account }>(
      this.baseUrl, data
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  getAccount(id: number): Observable<{ success: boolean; account: Account }> {
    return this.http.get<{ success: boolean; account: Account }>(
      `${this.baseUrl}/${id}`
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  updateAccount(id: number, data: AccountInput): Observable<{ success: boolean; account: Account }> {
    return this.http.put<{ success: boolean; account: Account }>(
      `${this.baseUrl}/${id}`, data
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  setActiveAccount(account: Account | null): void {
    this.activeAccount$.next(account);
    if (account) {
      localStorage.setItem('active_account_id', String(account.id));
    } else {
      localStorage.removeItem('active_account_id');
    }
  }

  loadSavedAccount(): void {
    const savedId = localStorage.getItem('active_account_id');
    if (savedId) {
      this.getAccount(Number(savedId)).subscribe({
        next: (res) => this.activeAccount$.next(res.account),
        error: () => localStorage.removeItem('active_account_id'),
      });
    }
  }

  // ── Documents ──

  listDocuments(accountId: number): Observable<{ success: boolean; documents: DocumentRecord[] }> {
    return this.http.get<{ success: boolean; documents: DocumentRecord[] }>(
      `${this.baseUrl}/${accountId}/documents`
    ).pipe(timeout(15000), catchError(this.handleError));
  }

  // ── Training Data ──

  listTrainingExamples(accountId: number, page = 1, source?: string):
    Observable<{ success: boolean; examples: TrainingExample[]; total: number; page: number; pages: number }> {
    let url = `${this.baseUrl}/${accountId}/training?page=${page}&per_page=20`;
    if (source) url += `&source=${source}`;
    return this.http.get<any>(url).pipe(timeout(15000), catchError(this.handleError));
  }

  addTrainingExample(accountId: number, data: { prompt: string; completion: string; section_type?: string }):
    Observable<{ success: boolean; example: TrainingExample }> {
    return this.http.post<{ success: boolean; example: TrainingExample }>(
      `${this.baseUrl}/${accountId}/training`, data
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  recordEdit(accountId: number, exampleId: number, editedContent: string):
    Observable<{ success: boolean; example: TrainingExample }> {
    return this.http.post<{ success: boolean; example: TrainingExample }>(
      `${this.baseUrl}/${accountId}/training/${exampleId}/edit`,
      { edited_content: editedContent }
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  rateExample(accountId: number, exampleId: number, rating: number): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(
      `${this.baseUrl}/${accountId}/training/${exampleId}/rate`,
      { rating }
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  getTrainingStats(accountId: number): Observable<{ success: boolean } & TrainingStats> {
    return this.http.get<{ success: boolean } & TrainingStats>(
      `${this.baseUrl}/${accountId}/training/stats`
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  // ── Export URLs (direct download) ──

  getExportJsonlUrl(accountId: number, minRating?: number, source?: string): string {
    let url = `${this.baseUrl}/${accountId}/export/jsonl`;
    const params: string[] = [];
    if (minRating) params.push(`min_rating=${minRating}`);
    if (source) params.push(`source=${source}`);
    if (params.length) url += '?' + params.join('&');
    return url;
  }

  getExportFullUrl(accountId: number): string {
    return `${this.baseUrl}/${accountId}/export/full`;
  }

  generateModelfile(accountId: number, baseModel = 'llama3'):
    Observable<{ success: boolean; model_name: string; instructions: string; filename: string }> {
    return this.http.get<any>(
      `${this.baseUrl}/${accountId}/export/modelfile?base_model=${baseModel}`
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  // ── Protocol Upload & Knowledge ──

  uploadProtocol(accountId: number, file: File):
    Observable<{ success: boolean; upload: ProtocolUpload; metadata: any }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<{ success: boolean; upload: ProtocolUpload; metadata: any }>(
      `${this.baseUrl}/${accountId}/protocols/upload`, formData
    ).pipe(timeout(30000), catchError(this.handleError));
  }

  listProtocols(accountId: number):
    Observable<{ success: boolean; uploads: ProtocolUpload[] }> {
    return this.http.get<{ success: boolean; uploads: ProtocolUpload[] }>(
      `${this.baseUrl}/${accountId}/protocols`
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  analyzeProtocol(accountId: number, uploadId: number):
    Observable<{ success: boolean; upload: ProtocolUpload }> {
    return this.http.post<{ success: boolean; upload: ProtocolUpload }>(
      `${this.baseUrl}/${accountId}/protocols/${uploadId}/analyze`, {}
    ).pipe(timeout(300000), catchError(this.handleError));
  }

  listProtocolKnowledge(accountId: number):
    Observable<{ success: boolean; knowledge: ProtocolKnowledge[] }> {
    return this.http.get<{ success: boolean; knowledge: ProtocolKnowledge[] }>(
      `${this.baseUrl}/${accountId}/protocols/knowledge`
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  updateKnowledge(accountId: number, knowledgeId: number, data: { is_active?: boolean }):
    Observable<{ success: boolean; knowledge: ProtocolKnowledge }> {
    return this.http.put<{ success: boolean; knowledge: ProtocolKnowledge }>(
      `${this.baseUrl}/${accountId}/protocols/knowledge/${knowledgeId}`, data
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  deleteProtocol(accountId: number, uploadId: number):
    Observable<{ success: boolean }> {
    return this.http.delete<{ success: boolean }>(
      `${this.baseUrl}/${accountId}/protocols/${uploadId}`
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  /** Update mutable fields on an upload (currently just doc_type). */
  updateProtocol(accountId: number, uploadId: number, data: { doc_type?: string }):
    Observable<{ success: boolean; upload: ProtocolUpload }> {
    return this.http.patch<{ success: boolean; upload: ProtocolUpload }>(
      `${this.baseUrl}/${accountId}/protocols/${uploadId}`, data
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  /**
   * Preview the consolidated style SmartSOP will use when generating a
   * document of the given type for this account. Returns both a small
   * ``summary`` suitable for a banner and the full ``style`` spec.
   */
  getEffectiveStyle(accountId: number, docType?: string):
    Observable<EffectiveStyleResponse> {
    const qs = docType ? `?doc_type=${encodeURIComponent(docType)}` : '';
    return this.http.get<EffectiveStyleResponse>(
      `${this.baseUrl}/${accountId}/effective-style${qs}`
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) {
      message = 'Cannot connect to server';
    } else if (error.error?.error) {
      message = error.error.error;
    }
    return throwError(() => new Error(message));
  }
}
