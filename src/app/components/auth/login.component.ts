import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';

import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
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

        <h1>{{ titleText }}</h1>
        <p class="subtitle">{{ subtitleText }}</p>

        <!-- Confirmation shown after a reset link is requested -->
        <div class="sent" *ngIf="forgotSent">
          <div class="sent-icon">✓</div>
          <p class="sent-msg">{{ forgotMessage }}</p>
          <p class="dev-link" *ngIf="forgotDevLink">
            <small>No email is configured on this server — use this link to reset:</small>
            <a [href]="forgotDevLink">Continue to reset your password →</a>
          </p>
          <button type="button" class="link back" (click)="setMode('login')">← Back to sign in</button>
        </div>

        <form (ngSubmit)="submit()" *ngIf="!forgotSent">
          <ng-container *ngIf="mode === 'register'">
            <label>
              <span>Your name</span>
              <input type="text" name="name" [(ngModel)]="name" placeholder="Jane Doe" autocomplete="name" />
            </label>
            <label>
              <span>Organization / account name</span>
              <input type="text" name="account_name" [(ngModel)]="accountName"
                     placeholder="Acme Pharma" autocomplete="organization" />
            </label>
          </ng-container>

          <label>
            <span>Email</span>
            <input type="email" name="email" [(ngModel)]="email" required
                   placeholder="you@company.com" autocomplete="email" />
          </label>

          <label *ngIf="mode !== 'forgot'">
            <span>Password</span>
            <input type="password" name="password" [(ngModel)]="password" required
                   placeholder="••••••••"
                   [attr.autocomplete]="mode === 'login' ? 'current-password' : 'new-password'" />
            <small *ngIf="mode === 'register'" class="hint">At least 8 characters.</small>
          </label>

          <div class="forgot-link" *ngIf="mode === 'login'">
            <button type="button" class="link" (click)="setMode('forgot')">Forgot password?</button>
          </div>

          <div class="error" *ngIf="error">{{ error }}</div>

          <button type="submit" class="btn-primary" [disabled]="loading">
            {{ loading ? 'Please wait…' : submitText }}
          </button>
        </form>

        <div class="sso" *ngIf="ssoEnabled && mode === 'login' && !forgotSent">
          <div class="divider"><span>or</span></div>
          <button type="button" class="btn-sso" (click)="ssoLogin()">Sign in with {{ ssoProvider }}</button>
        </div>

        <div class="switch" *ngIf="!forgotSent">
          <ng-container *ngIf="mode === 'login'">
            New here?
            <button type="button" class="link" (click)="setMode('register')">Create an account</button>
          </ng-container>
          <ng-container *ngIf="mode === 'register'">
            Already have an account?
            <button type="button" class="link" (click)="setMode('login')">Sign in</button>
          </ng-container>
          <ng-container *ngIf="mode === 'forgot'">
            Remembered it?
            <button type="button" class="link" (click)="setMode('login')">Back to sign in</button>
          </ng-container>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    .auth-page {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background:
        radial-gradient(60% 55% at 50% 0%, hsl(243 80% 96%) 0%, hsl(240 25% 98%) 55%, hsl(240 20% 97%) 100%);
    }

    .auth-card {
      width: 100%;
      max-width: 400px;
      background: #fff;
      border: 1px solid hsl(240 12% 92%);
      border-radius: 18px;
      padding: 36px 32px;
      box-shadow:
        0 1px 2px hsl(240 30% 20% / 0.04),
        0 12px 32px hsl(240 40% 20% / 0.10),
        0 40px 80px hsl(243 50% 30% / 0.06);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 9px;
      font-size: 14px;
      font-weight: 600;
      color: hsl(0 0% 12%);
      margin-bottom: 22px;
    }

    .brand-icon {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: linear-gradient(135deg, hsl(263 75% 62%) 0%, hsl(230 85% 60%) 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      box-shadow: 0 4px 14px hsl(243 75% 50% / 0.35);
    }

    h1 {
      font-size: 23px;
      font-weight: 680;
      letter-spacing: -0.03em;
      color: hsl(240 10% 8%);
      margin: 0 0 6px;
    }

    .subtitle {
      font-size: 13px;
      color: hsl(0 0% 45%);
      margin: 0 0 22px;
      line-height: 1.5;
    }

    form { display: flex; flex-direction: column; gap: 14px; }

    label { display: flex; flex-direction: column; gap: 6px; }

    label > span {
      font-size: 12px;
      font-weight: 500;
      color: hsl(0 0% 30%);
    }

    input {
      width: 100%;
      box-sizing: border-box;
      padding: 9px 11px;
      font-size: 13px;
      border: 1px solid hsl(0 0% 85%);
      border-radius: 7px;
      outline: none;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }

    input:focus {
      border-color: hsl(243 75% 62%);
      box-shadow: 0 0 0 3px hsl(243 75% 62% / 0.15);
    }

    .hint { font-size: 11px; color: hsl(0 0% 55%); }

    .error {
      font-size: 12.5px;
      color: hsl(0 72% 45%);
      background: hsl(0 80% 97%);
      border: 1px solid hsl(0 70% 90%);
      border-radius: 7px;
      padding: 8px 10px;
    }

    .btn-primary {
      margin-top: 6px;
      padding: 11px 14px;
      font-size: 13.5px;
      font-weight: 600;
      color: #fff;
      background: linear-gradient(135deg, hsl(243 75% 60%) 0%, hsl(230 82% 56%) 100%);
      border: none;
      border-radius: 9px;
      cursor: pointer;
      box-shadow: 0 1px 2px hsl(243 60% 40% / 0.3), 0 6px 18px hsl(243 70% 50% / 0.28);
      transition: transform 0.12s ease, box-shadow 0.15s ease, opacity 0.15s ease;
    }

    .btn-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 3px 6px hsl(243 60% 40% / 0.32), 0 10px 26px hsl(243 70% 50% / 0.32); }
    .btn-primary:disabled { opacity: 0.6; cursor: default; }

    .switch {
      margin-top: 20px;
      font-size: 12.5px;
      color: hsl(0 0% 45%);
      text-align: center;
    }

    .link {
      background: none;
      border: none;
      padding: 0;
      font: inherit;
      color: hsl(243 75% 55%);
      font-weight: 550;
      cursor: pointer;
    }

    .link:hover { text-decoration: underline; }

    .sso { margin-top: 16px; }
    .divider { display: flex; align-items: center; gap: 10px; margin: 4px 0 14px; color: hsl(0 0% 60%); font-size: 12px;
      &::before, &::after { content: ''; flex: 1; height: 1px; background: hsl(0 0% 90%); } }
    .btn-sso {
      width: 100%; padding: 10px 14px; font-size: 13px; font-weight: 500;
      color: hsl(0 0% 12%); background: #fff; border: 1px solid hsl(0 0% 85%);
      border-radius: 7px; cursor: pointer;
      &:hover { background: hsl(0 0% 97%); border-color: hsl(0 0% 75%); }
    }

    .forgot-link { text-align: right; margin-top: -6px; }
    .forgot-link .link { font-size: 12px; color: hsl(0 0% 45%); }
    .forgot-link .link:hover { color: hsl(243 75% 55%); }

    .sent { display: flex; flex-direction: column; align-items: center; gap: 14px; text-align: center; padding: 6px 0 2px; }
    .sent-icon {
      width: 44px; height: 44px; border-radius: 50%;
      background: hsl(143 60% 94%); color: hsl(143 65% 32%);
      display: flex; align-items: center; justify-content: center; font-size: 22px;
    }
    .sent-msg { font-size: 13.5px; color: hsl(0 0% 32%); line-height: 1.55; margin: 0; }
    .dev-link {
      font-size: 12.5px; background: hsl(45 92% 96%); border: 1px solid hsl(45 80% 85%);
      border-radius: 8px; padding: 10px 12px; margin: 0; display: flex; flex-direction: column; gap: 6px; text-align: left;
      small { color: hsl(38 60% 35%); }
      a { color: hsl(243 75% 52%); font-weight: 600; text-decoration: none; word-break: break-all; }
      a:hover { text-decoration: underline; }
    }
    .back { margin-top: 2px; }
  `]
})
export class LoginComponent implements OnInit {
  mode: 'login' | 'register' | 'forgot' = 'login';
  email = '';
  password = '';
  name = '';
  accountName = '';
  loading = false;
  error = '';

  // Forgot-password state
  forgotSent = false;
  forgotMessage = '';
  forgotDevLink = '';

  ssoEnabled = false;
  ssoProvider = 'SSO';

  get titleText(): string {
    return this.mode === 'login' ? 'Sign in'
      : this.mode === 'register' ? 'Create your account'
      : 'Reset your password';
  }

  get subtitleText(): string {
    return this.mode === 'login' ? "Access your organization's GMP document workspace."
      : this.mode === 'register' ? 'Set up a workspace for your organization.'
      : "Enter your email and we'll send you a link to reset your password.";
  }

  get submitText(): string {
    return this.mode === 'login' ? 'Sign in'
      : this.mode === 'register' ? 'Create account'
      : 'Send reset link';
  }

  private returnUrl = '/gmp';
  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute,
  ) {}

  ngOnInit(): void {
    this.returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || '/gmp';
    if (this.route.snapshot.queryParamMap.get('mode') === 'register') {
      this.mode = 'register';
    }
    if (!this.isBrowser) return;

    // The SSO callback redirects back here with the JWT in the URL fragment.
    const hash = window.location.hash || '';
    const match = hash.match(/sso_token=([^&]+)/);
    if (match) {
      this.loading = true;
      this.auth.completeSsoLogin(decodeURIComponent(match[1])).subscribe({
        next: () => { window.location.hash = ''; this.router.navigateByUrl(this.returnUrl); },
        error: () => { this.loading = false; this.error = 'SSO sign-in failed.'; },
      });
      return;
    }

    this.auth.ssoConfig().subscribe(cfg => {
      this.ssoEnabled = cfg.enabled;
      this.ssoProvider = cfg.provider || 'SSO';
    });
  }

  ssoLogin(): void {
    if (this.isBrowser) window.location.href = '/api/auth/sso/login';
  }

  setMode(mode: 'login' | 'register' | 'forgot'): void {
    this.mode = mode;
    this.error = '';
    this.forgotSent = false;
    this.forgotDevLink = '';
  }

  submit(): void {
    this.error = '';
    if (this.mode === 'forgot') { this.forgotSubmit(); return; }
    if (!this.email || !this.password) {
      this.error = 'Email and password are required.';
      return;
    }
    this.loading = true;
    const request$ = this.mode === 'login'
      ? this.auth.login(this.email, this.password)
      : this.auth.register({
          email: this.email,
          password: this.password,
          name: this.name,
          account_name: this.accountName,
        });

    request$.subscribe({
      next: () => {
        this.loading = false;
        this.router.navigateByUrl(this.returnUrl);
      },
      error: (err) => {
        this.loading = false;
        this.error = err.message || 'Something went wrong.';
      },
    });
  }

  private forgotSubmit(): void {
    if (!this.email) { this.error = 'Enter your email address.'; return; }
    this.loading = true;
    this.auth.forgotPassword(this.email).subscribe({
      next: (res) => {
        this.loading = false;
        this.forgotSent = true;
        this.forgotMessage = res.message;
        this.forgotDevLink = res.reset_link || '';   // dev-only fallback when no SMTP
      },
      error: (err) => {
        this.loading = false;
        this.error = err.message || 'Something went wrong.';
      },
    });
  }
}
