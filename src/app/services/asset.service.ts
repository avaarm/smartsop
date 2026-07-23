import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError, timeout } from 'rxjs';

/** A protocol summary as returned alongside an asset. */
export interface LinkedProtocol {
  id: number;
  title: string;
  status: string;
  protocol_type: string;
  version: number;
  sop_number: string;
}

export interface Asset {
  id: number;
  account_id: number;
  name: string;
  asset_tag: string;
  qr_slug: string;
  location: string;
  manufacturer: string;
  model: string;
  hazard_class: string;
  energy_sources: string[];
  protocol_ids: number[];
  notes: string;
  created_at: string;
  updated_at: string;
  protocols?: LinkedProtocol[];
}

export interface AssetInput {
  name?: string;
  asset_tag?: string;
  location?: string;
  manufacturer?: string;
  model?: string;
  hazard_class?: string;
  energy_sources?: string[];
  protocol_ids?: number[];
  notes?: string;
}

@Injectable({ providedIn: 'root' })
export class AssetService {
  private base(accountId: number) {
    return `/api/accounts/${accountId}/assets`;
  }

  constructor(private http: HttpClient) {}

  listAssets(accountId: number, q = ''):
    Observable<{ success: boolean; assets: Asset[]; total: number }> {
    const query = q ? `?q=${encodeURIComponent(q)}` : '';
    return this.http.get<any>(`${this.base(accountId)}${query}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  getAsset(accountId: number, id: number): Observable<{ success: boolean; asset: Asset }> {
    return this.http.get<any>(`${this.base(accountId)}/${id}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  createAsset(accountId: number, data: AssetInput): Observable<{ success: boolean; asset: Asset }> {
    return this.http.post<any>(this.base(accountId), data)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  updateAsset(accountId: number, id: number, patch: AssetInput):
    Observable<{ success: boolean; asset: Asset }> {
    return this.http.put<any>(`${this.base(accountId)}/${id}`, patch)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  deleteAsset(accountId: number, id: number): Observable<{ success: boolean }> {
    return this.http.delete<any>(`${this.base(accountId)}/${id}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** The printable QR tag, as inline SVG. */
  qrSvg(accountId: number, id: number, base: string): Observable<string> {
    return this.http.get(`${this.base(accountId)}/${id}/qr.svg?base=${encodeURIComponent(base)}`,
                         { responseType: 'text' })
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** Resolve a scanned QR slug to its asset + applicable SOPs. */
  scan(slug: string): Observable<{ success: boolean; asset: Asset }> {
    return this.http.get<any>(`/api/assets/scan/${encodeURIComponent(slug)}`)
      .pipe(timeout(15000), catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) message = 'Cannot connect to server';
    else if (error.error?.error) message = error.error.error;
    return throwError(() => new Error(message));
  }
}
