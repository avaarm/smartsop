import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';

import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="auth-page">
      <div class="auth-card">
        <div class="brand">
          <div class="brand-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <span>SmartSOP</span>
        </div>

        <h1>Choose a new password</h1>
        <p class="subtitle">Set a new password for your account, then you'll be signed in.</p>

        <div class="error" *ngIf="!token">
          This reset link is missing its token. Request a new link from the sign-in page.
        </div>

        <form (ngSubmit)="submit()" *ngIf="token">
          <label>
            <span>New password</span>
            <input type="password" name="password" [(ngModel)]="password" required
                   placeholder="••••••••" autocomplete="new-password" />
            <small class="hint">At least 8 characters.</small>
          </label>
          <label>
            <span>Confirm new password</span>
            <input type="password" name="confirm" [(ngModel)]="confirm" required
                   placeholder="••••••••" autocomplete="new-password" />
          </label>

          <div class="error" *ngIf="error">{{ error }}</div>

          <button type="submit" class="btn-primary" [disabled]="loading">
            {{ loading ? 'Please wait…' : 'Reset password & sign in' }}
          </button>
        </form>

        <div class="switch">
          <button type="button" class="link" (click)="goToLogin()">← Back to sign in</button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    .auth-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px;
      background: radial-gradient(60% 55% at 50% 0%, hsl(243 80% 96%) 0%, hsl(240 25% 98%) 55%, hsl(240 20% 97%) 100%); }
    .auth-card { width: 100%; max-width: 400px; background: #fff; border: 1px solid hsl(240 12% 92%); border-radius: 18px;
      padding: 36px 32px; box-shadow: 0 1px 2px hsl(240 30% 20% / 0.04), 0 12px 32px hsl(240 40% 20% / 0.10), 0 40px 80px hsl(243 50% 30% / 0.06); }
    .brand { display: flex; align-items: center; gap: 9px; font-size: 14px; font-weight: 600; color: hsl(0 0% 12%); margin-bottom: 22px; }
    .brand-icon { width: 32px; height: 32px; border-radius: 8px; background: linear-gradient(135deg, hsl(263 75% 62%) 0%, hsl(230 85% 60%) 100%);
      display: flex; align-items: center; justify-content: center; color: #fff; box-shadow: 0 4px 14px hsl(243 75% 50% / 0.35); }
    h1 { font-size: 23px; font-weight: 680; letter-spacing: -0.03em; color: hsl(240 10% 8%); margin: 0 0 6px; }
    .subtitle { font-size: 13px; color: hsl(0 0% 45%); margin: 0 0 22px; line-height: 1.5; }
    form { display: flex; flex-direction: column; gap: 14px; }
    label { display: flex; flex-direction: column; gap: 6px; }
    label > span { font-size: 12px; font-weight: 500; color: hsl(0 0% 30%); }
    input { width: 100%; box-sizing: border-box; padding: 9px 11px; font-size: 13px; border: 1px solid hsl(0 0% 85%);
      border-radius: 7px; outline: none; transition: border-color 0.15s ease, box-shadow 0.15s ease; }
    input:focus { border-color: hsl(243 75% 62%); box-shadow: 0 0 0 3px hsl(243 75% 62% / 0.15); }
    .hint { font-size: 11px; color: hsl(0 0% 55%); }
    .error { font-size: 12.5px; color: hsl(0 72% 45%); background: hsl(0 80% 97%); border: 1px solid hsl(0 70% 90%); border-radius: 7px; padding: 8px 10px; }
    .btn-primary { margin-top: 6px; padding: 11px 14px; font-size: 13.5px; font-weight: 600; color: #fff;
      background: linear-gradient(135deg, hsl(243 75% 60%) 0%, hsl(230 82% 56%) 100%); border: none; border-radius: 9px; cursor: pointer;
      box-shadow: 0 1px 2px hsl(243 60% 40% / 0.3), 0 6px 18px hsl(243 70% 50% / 0.28); transition: transform 0.12s ease, box-shadow 0.15s ease, opacity 0.15s ease; }
    .btn-primary:hover:not(:disabled) { transform: translateY(-1px); }
    .btn-primary:disabled { opacity: 0.6; cursor: default; }
    .switch { margin-top: 20px; font-size: 12.5px; color: hsl(0 0% 45%); text-align: center; }
    .link { background: none; border: none; padding: 0; font: inherit; color: hsl(243 75% 55%); font-weight: 550; cursor: pointer; }
    .link:hover { text-decoration: underline; }
  `]
})
export class ResetPasswordComponent implements OnInit {
  token = '';
  password = '';
  confirm = '';
  loading = false;
  error = '';

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute,
  ) {}

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') || '';
  }

  submit(): void {
    this.error = '';
    if (this.password.length < 8) { this.error = 'Password must be at least 8 characters.'; return; }
    if (this.password !== this.confirm) { this.error = 'Passwords do not match.'; return; }
    this.loading = true;
    this.auth.resetPassword(this.token, this.password).subscribe({
      next: () => { this.loading = false; this.router.navigateByUrl('/gmp'); },
      error: (err) => { this.loading = false; this.error = err.message || 'Could not reset your password.'; },
    });
  }

  goToLogin(): void {
    this.router.navigate(['/login']);
  }
}
