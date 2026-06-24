import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import {
  Observable, catchError, throwError, timeout, of, timer,
  switchMap, map, takeWhile, last, shareReplay,
} from 'rxjs';

export interface GMPTemplate {
  id: string;
  name: string;
  doc_type: string;
}

export interface GMPTemplateSchema {
  id: string;
  name: string;
  doc_type: string;
  orientation: string;
  sections: GMPSectionSchema[];
}

export interface GMPSectionSchema {
  id: string;
  title: string;
  type: string;
  required: boolean;
  llm_prompt?: string;
  step_config?: any;
  columns?: any[];
  default_data?: any;
}

export interface GMPDocumentRequest {
  doc_type: string;
  title: string;
  product_name: string;
  process_type: string;
  description: string;
  doc_number?: string;
  revision?: string;
  sections?: Record<string, any>;
  account_id?: number;
}

export interface GMPDocumentResponse {
  success: boolean;
  doc_id?: string;
  filename?: string;
  download_url?: string;
  preview_sections?: PreviewSection[];
  error?: string;
}

export interface PreviewSection {
  id: string;
  title: string;
  type: string;
  has_content: boolean;
}

export interface OllamaStatus {
  success: boolean;
  available: boolean;
  model: string;
  models: string[];
}

export interface SectionPreviewRequest {
  doc_type: string;
  section_id: string;
  context: Record<string, any>;
}

export interface Paper {
  pmcid: string;
  pmid?: string;
  title: string;
  authors: string[];
  journal: string;
  year: string;
  abstract?: string;
  doi?: string;
  url?: string;
}

export interface PaperMethods {
  paper: Paper;
  methods_text: string;
  sections: { heading: string; text: string }[];
}

export interface PaperAutofillResponse {
  paper: Paper;
  section_data: Record<string, any>;
  notes?: string;
}

@Injectable({
  providedIn: 'root'
})
export class GMPDocumentService {
  private baseUrl = '/api/gmp';

  // Whether the backend runs LLM calls on a worker (enqueue + poll). Fetched
  // once and shared; falls back to false (synchronous) if the call fails.
  private readonly asyncEnabled$: Observable<boolean>;

  constructor(private http: HttpClient) {
    this.asyncEnabled$ = this.http
      .get<{ success: boolean; async_tasks: boolean }>(`${this.baseUrl}/config`)
      .pipe(
        map(r => !!r.async_tasks),
        catchError(() => of(false)),
        shareReplay(1),
      );
  }

  /** Enqueue a task, then poll until it finishes; emits the task result. */
  private enqueueAndPoll(url: string, body: any): Observable<any> {
    return this.http.post<{ task_id: string }>(url, body).pipe(
      switchMap(res => timer(0, 1500).pipe(
        switchMap(() => this.http.get<{ state: string; result?: any; error?: string }>(
          `${this.baseUrl}/tasks/${res.task_id}`)),
        takeWhile(t => t.state === 'PENDING' || t.state === 'STARTED' || t.state === 'RETRY', true),
        last(),
        switchMap(t => t.state === 'SUCCESS'
          ? of(t.result)
          : throwError(() => new Error(t.error || 'Generation failed'))),
      )),
      timeout(180000),
    );
  }

  getTemplates(): Observable<{ success: boolean; templates: GMPTemplate[] }> {
    return this.http.get<{ success: boolean; templates: GMPTemplate[] }>(
      `${this.baseUrl}/templates`
    ).pipe(timeout(30000), catchError(this.handleError));
  }

  getTemplateSchema(templateId: string): Observable<{ success: boolean; template: GMPTemplateSchema }> {
    return this.http.get<{ success: boolean; template: GMPTemplateSchema }>(
      `${this.baseUrl}/templates/${templateId}`
    ).pipe(timeout(30000), catchError(this.handleError));
  }

  generateDocument(request: GMPDocumentRequest): Observable<GMPDocumentResponse> {
    // Generate no longer calls the LLM implicitly, so it completes in <1s
    return this.http.post<GMPDocumentResponse>(
      `${this.baseUrl}/generate`, request
    ).pipe(timeout(30000), catchError(this.handleError));
  }

  previewSection(request: SectionPreviewRequest): Observable<{ success: boolean; data: any }> {
    // When the backend offloads LLM work to a worker, enqueue + poll so the
    // request doesn't hang for 10-90s; otherwise call the synchronous endpoint.
    return this.asyncEnabled$.pipe(
      switchMap(async => async
        ? this.enqueueAndPoll(`${this.baseUrl}/preview/async`, request)
            .pipe(map(result => ({ success: true, data: result })))
        : this.http.post<{ success: boolean; data: any }>(`${this.baseUrl}/preview`, request)
            .pipe(timeout(90000))),
      catchError(this.handleError),
    );
  }

  getOllamaStatus(): Observable<OllamaStatus> {
    return this.http.get<OllamaStatus>(
      `${this.baseUrl}/ollama/status`
    ).pipe(timeout(10000), catchError(this.handleError));
  }

  // ── Paper Scraping ──

  searchPapers(query: string, limit = 10): Observable<{ success: boolean; papers: Paper[] }> {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    return this.http.get<{ success: boolean; papers: Paper[] }>(
      `${this.baseUrl}/papers/search?${params}`
    ).pipe(timeout(45000), catchError(this.handleError));
  }

  getPaperMethods(pmcid: string): Observable<{ success: boolean } & PaperMethods> {
    return this.http.get<{ success: boolean } & PaperMethods>(
      `${this.baseUrl}/papers/${pmcid}/methods`
    ).pipe(timeout(60000), catchError(this.handleError));
  }

  autofillFromPaper(pmcid: string, context: Record<string, any>):
    Observable<{ success: boolean } & PaperAutofillResponse> {
    return this.asyncEnabled$.pipe(
      switchMap(async => async
        ? this.enqueueAndPoll(`${this.baseUrl}/papers/autofill/async`, { pmcid, context })
            .pipe(map(result => ({ success: true, ...(result as PaperAutofillResponse) })))
        : this.http.post<{ success: boolean } & PaperAutofillResponse>(
            `${this.baseUrl}/papers/autofill`, { pmcid, context }).pipe(timeout(120000))),
      catchError(this.handleError),
    );
  }

  getDownloadUrl(filename: string): string {
    return `/api/download/${filename}`;
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) {
      message = 'Cannot connect to server. Is the backend running?';
    } else if (error.status === 503) {
      message = 'Ollama LLM is not available. Start it with: ollama serve';
    } else if (error.error?.error) {
      message = error.error.error;
    }
    return throwError(() => new Error(message));
  }
}
