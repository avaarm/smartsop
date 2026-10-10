import { Injectable, PLATFORM_ID, inject } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, BehaviorSubject, catchError, throwError, tap, timeout, map, of } from 'rxjs';

export interface Membership {
  id: number;
  user_id: number;
  account_id: number;
  role: 'owner' | 'admin' | 'member';
  account_name: string | null;
  account_slug: string | null;
}

export interface AuthUser {
  id: number;
  email: string;
  name: string;
  is_superadmin: boolean;
  is_active: boolean;
  created_at: string;
  memberships: Membership[];
}

interface AuthResponse {
  success: boolean;
  token: string;
  user: AuthUser;
}

const TOKEN_KEY = 'smartsop_token';
const USER_KEY = 'smartsop_user';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private baseUrl = '/api/auth';
  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  currentUser$ = new BehaviorSubject<AuthUser | null>(null);

  constructor(private http: HttpClient) {
    // Restore a cached session on startup so the UI doesn't flicker; /me
    // refreshes it against the server.
    if (this.isBrowser) {
      const cached = this.readUser();
      if (cached && this.token) {
        this.currentUser$.next(cached);
        this.refreshUser();
      }
    }
  }

  get token(): string | null {
    return this.isBrowser ? localStorage.getItem(TOKEN_KEY) : null;
  }

  ssoConfig(): Observable<{ enabled: boolean; provider: string }> {
    return this.http.get<{ enabled: boolean; provider: string }>(`${this.baseUrl}/sso/config`)
      .pipe(catchError(() => of({ enabled: false, provider: 'SSO' })));
  }

  /** Complete an SSO login: store the JWT handed back in the URL fragment, load the user. */
  completeSsoLogin(token: string): Observable<AuthUser> {
    if (this.isBrowser) localStorage.setItem(TOKEN_KEY, token);
    return this.http.get<{ user: AuthUser }>(`${this.baseUrl}/me`).pipe(
      map(res => res.user),
      tap(user => {
        this.currentUser$.next(user);
        if (this.isBrowser) localStorage.setItem(USER_KEY, JSON.stringify(user));
      }),
    );
  }

  isAuthenticated(): boolean {
    return !!this.token;
  }

  login(email: string, password: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.baseUrl}/login`, { email, password })
      .pipe(timeout(15000), tap(res => this.storeSession(res)), catchError(this.handleError));
  }

  register(data: { email: string; password: string; name?: string; account_name?: string }):
    Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.baseUrl}/register`, data)
      .pipe(timeout(15000), tap(res => this.storeSession(res)), catchError(this.handleError));
  }

  /** Begin a password reset. The server never reveals whether the email exists. */
  forgotPassword(email: string):
    Observable<{ success: boolean; message: string; reset_link?: string; dev_note?: string }> {
    return this.http.post<any>(`${this.baseUrl}/forgot-password`, { email })
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** Complete a password reset with a token; signs the user in on success. */
  resetPassword(token: string, password: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.baseUrl}/reset-password`, { token, password })
      .pipe(timeout(15000), tap(res => this.storeSession(res)), catchError(this.handleError));
  }

  /** Change the signed-in user's password (requires their current password). */
  changePassword(currentPassword: string, newPassword: string): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(`${this.baseUrl}/change-password`,
      { current_password: currentPassword, new_password: newPassword })
      .pipe(timeout(15000), catchError(this.handleError));
  }

  /** Re-fetch the current user from the server (e.g. after membership changes). */
  refreshUser(): void {
    this.http.get<{ success: boolean; user: AuthUser }>(`${this.baseUrl}/me`)
      .pipe(timeout(15000))
      .subscribe({
        next: res => {
          this.currentUser$.next(res.user);
          if (this.isBrowser) localStorage.setItem(USER_KEY, JSON.stringify(res.user));
        },
        error: (err) => {
          // Only drop the session if the token was actually rejected. Transient
          // failures (offline, 5xx, or a request cancelled during navigation/
          // hydration) must NOT log out a user who has a valid cached session.
          if (err?.status === 401 || err?.status === 403) {
            this.clearSession();
          }
        },
      });
  }

  logout(): void {
    this.clearSession();
  }

  /** Clear all client-side auth state. Does not navigate. */
  clearSession(): void {
    if (this.isBrowser) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    }
    this.currentUser$.next(null);
  }

  private storeSession(res: AuthResponse): void {
    if (this.isBrowser) {
      localStorage.setItem(TOKEN_KEY, res.token);
      localStorage.setItem(USER_KEY, JSON.stringify(res.user));
    }
    this.currentUser$.next(res.user);
  }

  private readUser(): AuthUser | null {
    if (!this.isBrowser) return null;
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      return null;
    }
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An error occurred';
    if (error.status === 0) {
      message = 'Cannot connect to server. Is the backend running?';
    } else if (error.error?.error) {
      message = error.error.error;
    }
    return throwError(() => new Error(message));
  }
}
