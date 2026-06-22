import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
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

        <h1>{{ mode === 'login' ? 'Sign in' : 'Create your account' }}</h1>
        <p class="subtitle">
          {{ mode === 'login'
            ? 'Access your organization\\'s GMP document workspace.'
            : 'Set up a workspace for your organization.' }}
        </p>

        <form (ngSubmit)="submit()">
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

          <label>
            <span>Password</span>
            <input type="password" name="password" [(ngModel)]="password" required
                   placeholder="••••••••"
                   [attr.autocomplete]="mode === 'login' ? 'current-password' : 'new-password'" />
            <small *ngIf="mode === 'register'" class="hint">At least 8 characters.</small>
          </label>

          <div class="error" *ngIf="error">{{ error }}</div>

          <button type="submit" class="btn-primary" [disabled]="loading">
            {{ loading ? 'Please wait…' : (mode === 'login' ? 'Sign in' : 'Create account') }}
          </button>
        </form>

        <div class="switch">
          <ng-container *ngIf="mode === 'login'; else toLogin">
            New here?
            <button type="button" class="link" (click)="setMode('register')">Create an account</button>
          </ng-container>
          <ng-template #toLogin>
            Already have an account?
            <button type="button" class="link" (click)="setMode('login')">Sign in</button>
          </ng-template>
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
      background: hsl(0 0% 97%);
    }

    .auth-card {
      width: 100%;
      max-width: 380px;
      background: #fff;
      border: 1px solid hsl(0 0% 90%);
      border-radius: 12px;
      padding: 32px 28px;
      box-shadow: 0 1px 3px hsl(0 0% 0% / 0.04), 0 8px 24px hsl(0 0% 0% / 0.04);
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
      width: 30px;
      height: 30px;
      border-radius: 7px;
      background: linear-gradient(135deg, hsl(263 70% 60%) 0%, hsl(217 91% 60%) 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
    }

    h1 {
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.02em;
      color: hsl(0 0% 10%);
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
      border-color: hsl(217 91% 60%);
      box-shadow: 0 0 0 3px hsl(217 91% 60% / 0.12);
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
      margin-top: 4px;
      padding: 10px 14px;
      font-size: 13px;
      font-weight: 500;
      color: #fff;
      background: hsl(0 0% 10%);
      border: none;
      border-radius: 7px;
      cursor: pointer;
      transition: background 0.15s ease, opacity 0.15s ease;
    }

    .btn-primary:hover:not(:disabled) { background: hsl(0 0% 0%); }
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
      color: hsl(217 91% 50%);
      font-weight: 500;
      cursor: pointer;
    }

    .link:hover { text-decoration: underline; }
  `]
})
export class LoginComponent implements OnInit {
  mode: 'login' | 'register' = 'login';
  email = '';
  password = '';
  name = '';
  accountName = '';
  loading = false;
  error = '';

  private returnUrl = '/gmp';

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
  }

  setMode(mode: 'login' | 'register'): void {
    this.mode = mode;
    this.error = '';
  }

  submit(): void {
    this.error = '';
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
}
