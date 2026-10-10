import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { Router, RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { AuthService } from '../../services/auth.service';
import { AccountService, Account } from '../../services/account.service';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="layout">
      <header class="topbar">
        <div class="topbar-inner">
          <!-- Brand -->
          <a class="brand" routerLink="/protocols">
            <span class="logo-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
            </span>
            <span class="brand-name">SmartSOP</span>
          </a>

          <!-- Primary navigation -->
          <nav class="topnav">
            <a routerLink="/gmp" routerLinkActive="active" ariaCurrentWhenActive="page" [routerLinkActiveOptions]="{exact: true}">Document Builder</a>
            <a routerLink="/protocols" routerLinkActive="active" ariaCurrentWhenActive="page">Protocols</a>
            <a routerLink="/register" routerLinkActive="active" ariaCurrentWhenActive="page">Controlled Docs</a>
            <a routerLink="/schedule" routerLinkActive="active" ariaCurrentWhenActive="page">Schedule</a>
            <a routerLink="/assets" routerLinkActive="active" ariaCurrentWhenActive="page">Assets</a>
            <a routerLink="/deviations" routerLinkActive="active" ariaCurrentWhenActive="page">Deviations</a>
            <a routerLink="/competency" routerLinkActive="active" ariaCurrentWhenActive="page">Competency</a>
            <a routerLink="/analytics" routerLinkActive="active" ariaCurrentWhenActive="page">Analytics</a>
            <a routerLink="/audit" routerLinkActive="active" ariaCurrentWhenActive="page">Audit</a>
            <a routerLink="/account" routerLinkActive="active" ariaCurrentWhenActive="page">Account</a>
          </nav>

          <!-- Right cluster: workspace switcher + user -->
          <div class="topbar-right">
            <form class="topsearch" (submit)="runSearch(); $event.preventDefault()">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input type="search" [(ngModel)]="globalSearch" name="globalSearch"
                     placeholder="Search SOPs…" aria-label="Search protocols" />
            </form>
            <div class="switcher" *ngIf="activeAccount">
              <button class="switcher-btn" type="button" (click)="switcherOpen = !switcherOpen; userMenuOpen = false">
                <span class="ws-avatar">{{ initial(activeAccount.name) }}</span>
                <span class="ws-name">{{ activeAccount.name }}</span>
                <svg class="ws-chev" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </button>

              <div class="menu ws-menu" *ngIf="switcherOpen">
                <div class="menu-label">Switch workspace</div>
                <button class="ws-item" *ngFor="let a of accounts" (click)="switchTo(a)">
                  <span class="ws-avatar sm">{{ initial(a.name) }}</span>
                  <span class="ws-item-name">{{ a.name }}</span>
                  <span class="ws-check" *ngIf="a.id === activeAccount.id">✓</span>
                </button>
                <div class="menu-sep"></div>
                <div class="ws-create" *ngIf="creatingWorkspace; else createBtn">
                  <input type="text" [(ngModel)]="newWorkspaceName" name="ws-new"
                         placeholder="Workspace name" (keyup.enter)="createWorkspace()" />
                  <button class="ws-create-go" (click)="createWorkspace()" [disabled]="!newWorkspaceName.trim() || busy">
                    {{ busy ? '…' : 'Create' }}
                  </button>
                </div>
                <ng-template #createBtn>
                  <button class="ws-item add" (click)="creatingWorkspace = true">
                    <span class="ws-plus">＋</span> New workspace
                  </button>
                </ng-template>
              </div>
            </div>

            <div class="user" *ngIf="auth.currentUser$ | async as user">
              <button class="user-btn" type="button" (click)="userMenuOpen = !userMenuOpen; switcherOpen = false"
                      [title]="user.email">
                <span class="user-avatar">{{ (user.name || user.email).charAt(0).toUpperCase() }}</span>
              </button>
              <div class="menu user-menu" *ngIf="userMenuOpen">
                <div class="user-head">
                  <div class="user-avatar lg">{{ (user.name || user.email).charAt(0).toUpperCase() }}</div>
                  <div class="user-meta">
                    <div class="user-name">{{ user.name || user.email }}</div>
                    <div class="user-email" *ngIf="user.name">{{ user.email }}</div>
                  </div>
                </div>
                <div class="menu-sep"></div>
                <a class="menu-item" routerLink="/account" (click)="userMenuOpen = false">Account &amp; Training</a>
                <button class="menu-item" type="button" (click)="openChangePassword()">Change password</button>
                <button class="menu-item danger" type="button" (click)="logout()">Sign out</button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- click-away for any open menu -->
      <div class="menu-backdrop" *ngIf="switcherOpen || userMenuOpen"
           (click)="switcherOpen = false; userMenuOpen = false"></div>

      <!-- Change-password modal -->
      <div class="pw-overlay" *ngIf="showChangePw" (click)="closeChangePassword()">
        <div class="pw-modal" (click)="$event.stopPropagation()">
          <h3>Change password</h3>
          <form (ngSubmit)="submitChangePassword()">
            <label><span>Current password</span>
              <input type="password" name="pwCurrent" [(ngModel)]="pwCurrent" autocomplete="current-password" /></label>
            <label><span>New password</span>
              <input type="password" name="pwNew" [(ngModel)]="pwNew" autocomplete="new-password" />
              <small class="pw-hint">At least 8 characters.</small></label>
            <label><span>Confirm new password</span>
              <input type="password" name="pwConfirm" [(ngModel)]="pwConfirm" autocomplete="new-password" /></label>
            <div class="pw-error" *ngIf="pwError">{{ pwError }}</div>
            <div class="pw-success" *ngIf="pwSuccess">✓ Your password has been updated.</div>
            <div class="pw-actions">
              <button type="button" class="pw-cancel" (click)="closeChangePassword()">{{ pwSuccess ? 'Close' : 'Cancel' }}</button>
              <button type="submit" class="pw-save" *ngIf="!pwSuccess" [disabled]="pwBusy">{{ pwBusy ? 'Saving…' : 'Update password' }}</button>
            </div>
          </form>
        </div>
      </div>

      <main class="main-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: [`
    :host {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --bar-bg: hsl(0 0% 100%);
      --bar-border: hsl(240 6% 90%);
      --text: hsl(240 6% 12%);
      --muted: hsl(240 4% 46%);
      --faint: hsl(240 4% 60%);
      --accent: hsl(243 75% 59%);
      --accent-soft: hsl(243 90% 96%);
    }

    .layout { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

    /* ── Top bar ── */
    .topbar {
      flex-shrink: 0; background: var(--bar-bg); border-bottom: 1px solid var(--bar-border);
      box-shadow: 0 1px 2px hsl(240 20% 12% / 0.03), 0 1px 3px hsl(240 20% 12% / 0.04);
      z-index: 40;
    }
    .topbar-inner { display: flex; align-items: center; height: 58px; padding: 0 20px; gap: 18px; }

    .brand { display: flex; align-items: center; gap: 9px; text-decoration: none; flex-shrink: 0;
      color: var(--text); font-size: 15px; font-weight: 700; letter-spacing: -0.02em; }
    .logo-icon {
      width: 30px; height: 30px; border-radius: 8px; flex-shrink: 0;
      background: linear-gradient(135deg, hsl(263 75% 62%) 0%, hsl(230 85% 60%) 100%);
      display: flex; align-items: center; justify-content: center; color: #fff;
      box-shadow: 0 3px 10px hsl(243 75% 50% / 0.35);
    }

    /* Nav tabs */
    .topnav {
      flex: 1; display: flex; align-items: stretch; gap: 1px; height: 58px;
      overflow-x: auto; overflow-y: hidden; scrollbar-width: none;
    }
    .topnav::-webkit-scrollbar { display: none; }
    .topnav a {
      position: relative; display: flex; align-items: center; height: 58px; padding: 0 13px;
      font-size: 13.5px; font-weight: 500; color: var(--muted); text-decoration: none; white-space: nowrap;
      transition: color 0.14s ease, background 0.14s ease;
    }
    .topnav a:hover { color: var(--text); background: hsl(240 6% 97%); }
    .topnav a.active { color: var(--accent); font-weight: 600; }
    .topnav a.active::after {
      content: ''; position: absolute; left: 10px; right: 10px; bottom: 0; height: 2.5px;
      border-radius: 3px 3px 0 0; background: var(--accent);
    }

    /* Right cluster */
    .topbar-right { flex-shrink: 0; display: flex; align-items: center; gap: 8px; }

    .topsearch {
      display: flex; align-items: center; gap: 6px; height: 34px; padding: 0 10px;
      background: hsl(240 8% 97.5%); border: 1px solid var(--bar-border); border-radius: 9px;
      transition: border-color 0.14s ease, box-shadow 0.14s ease, background 0.14s ease;
    }
    .topsearch:focus-within { border-color: var(--accent); background: #fff; box-shadow: 0 0 0 3px var(--accent-soft); }
    .topsearch svg { color: var(--faint); flex-shrink: 0; }
    .topsearch input {
      border: none; background: none; outline: none; font-family: inherit;
      font-size: 13px; width: 150px; color: var(--text);
    }
    .topsearch input::placeholder { color: var(--faint); }
    @media (max-width: 1040px) { .topsearch { display: none; } }

    .switcher { position: relative; }
    .switcher-btn {
      display: flex; align-items: center; gap: 8px; padding: 6px 10px 6px 6px; border-radius: 9px; cursor: pointer;
      background: hsl(240 8% 97.5%); border: 1px solid var(--bar-border); color: var(--text); font-family: inherit;
      transition: background 0.14s ease, border-color 0.14s ease;
    }
    .switcher-btn:hover { background: hsl(240 8% 95%); border-color: hsl(240 6% 85%); }
    .ws-avatar {
      width: 24px; height: 24px; flex-shrink: 0; border-radius: 6px;
      background: linear-gradient(135deg, hsl(263 65% 55%) 0%, hsl(230 80% 55%) 100%);
      color: #fff; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center;
      &.sm { width: 22px; height: 22px; }
    }
    .ws-name { font-size: 13px; font-weight: 600; max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ws-chev { color: var(--faint); flex-shrink: 0; }

    /* Dropdown menus */
    .menu {
      position: absolute; top: calc(100% + 6px); right: 0; z-index: 70; min-width: 240px;
      background: #fff; border: 1px solid var(--bar-border); border-radius: 12px; padding: 6px;
      box-shadow: 0 12px 40px hsl(240 30% 12% / 0.14);
    }
    .menu-label { font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--faint); padding: 6px 8px 4px; }
    .menu-sep { height: 1px; background: var(--bar-border); margin: 5px 4px; }
    .menu-item {
      display: block; width: 100%; text-align: left; padding: 8px 10px; border: none; background: none;
      border-radius: 8px; cursor: pointer; color: var(--text); font-family: inherit; font-size: 13px; text-decoration: none;
      &:hover { background: hsl(240 6% 96%); }
      &.danger { color: hsl(0 70% 45%); &:hover { background: hsl(0 75% 97%); } }
    }
    .ws-item {
      width: 100%; display: flex; align-items: center; gap: 9px; padding: 7px 8px;
      background: none; border: none; border-radius: 8px; cursor: pointer; color: var(--text);
      font-family: inherit; font-size: 13px; text-align: left;
      &:hover { background: hsl(240 6% 96%); }
      &.add { color: var(--accent); font-weight: 500; }
    }
    .ws-item-name { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ws-check { color: var(--accent); font-weight: 700; }
    .ws-plus { font-size: 15px; line-height: 1; width: 22px; text-align: center; }
    .ws-create { display: flex; gap: 6px; padding: 4px; }
    .ws-create input {
      flex: 1; min-width: 0; font-size: 12.5px; font-family: inherit; padding: 7px 9px;
      border-radius: 7px; border: 1px solid var(--bar-border); background: #fff; color: var(--text);
      &:focus { outline: none; border-color: var(--accent); }
    }
    .ws-create-go {
      font-size: 12px; font-weight: 600; padding: 0 12px; border-radius: 7px; cursor: pointer;
      background: var(--accent); color: #fff; border: none;
      &:disabled { opacity: 0.5; cursor: default; }
    }

    /* User */
    .user { position: relative; }
    .user-btn { padding: 0; border: none; background: none; cursor: pointer; border-radius: 50%; }
    .user-avatar {
      width: 32px; height: 32px; flex-shrink: 0; border-radius: 50%;
      background: linear-gradient(135deg, hsl(263 65% 58%) 0%, hsl(230 80% 58%) 100%);
      color: #fff; font-size: 13px; font-weight: 650; display: flex; align-items: center; justify-content: center;
      &.lg { width: 38px; height: 38px; font-size: 15px; }
    }
    .user-head { display: flex; align-items: center; gap: 10px; padding: 8px; }
    .user-meta { min-width: 0; }
    .user-name { font-size: 13px; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .user-email { font-size: 11.5px; color: var(--faint); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .menu-backdrop { position: fixed; inset: 0; z-index: 60; }

    /* Change-password modal */
    .pw-overlay { position: fixed; inset: 0; z-index: 80; background: hsl(240 30% 10% / 0.35);
      display: flex; align-items: center; justify-content: center; padding: 20px; }
    .pw-modal { width: 100%; max-width: 380px; background: #fff; border-radius: 14px; padding: 22px 22px 18px;
      box-shadow: 0 16px 48px hsl(240 30% 12% / 0.22); }
    .pw-modal h3 { margin: 0 0 16px; font-size: 16px; font-weight: 650; letter-spacing: -0.01em; color: var(--text); }
    .pw-modal form { display: flex; flex-direction: column; gap: 12px; }
    .pw-modal label { display: flex; flex-direction: column; gap: 5px; }
    .pw-modal label > span { font-size: 12px; font-weight: 500; color: var(--muted); }
    .pw-modal input { width: 100%; box-sizing: border-box; padding: 8px 11px; font-size: 13px; font-family: inherit;
      border: 1px solid var(--bar-border); border-radius: 7px; outline: none; }
    .pw-modal input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
    .pw-hint { font-size: 11px; color: var(--faint); }
    .pw-error { font-size: 12.5px; color: hsl(0 72% 45%); background: hsl(0 80% 97%); border: 1px solid hsl(0 70% 90%); border-radius: 7px; padding: 7px 10px; }
    .pw-success { font-size: 12.5px; color: hsl(143 65% 30%); background: hsl(143 60% 96%); border: 1px solid hsl(143 50% 85%); border-radius: 7px; padding: 7px 10px; }
    .pw-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
    .pw-cancel { padding: 8px 13px; font-size: 13px; background: #fff; border: 1px solid var(--bar-border); border-radius: 8px; cursor: pointer; color: var(--text); }
    .pw-cancel:hover { background: hsl(240 6% 97%); }
    .pw-save { padding: 8px 15px; font-size: 13px; font-weight: 600; color: #fff; border: none; border-radius: 8px; cursor: pointer;
      background: linear-gradient(135deg, hsl(243 75% 60%) 0%, hsl(230 82% 56%) 100%); }
    .pw-save:disabled { opacity: 0.6; cursor: default; }

    /* Content */
    .main-content {
      flex: 1; overflow-y: auto;
      background:
        radial-gradient(120% 80% at 100% 0%, hsl(243 60% 97.5%) 0%, transparent 45%),
        hsl(240 24% 97.6%);
    }

    /* Narrow screens: nav scrolls, brand name + workspace name hide */
    @media (max-width: 820px) {
      .topbar-inner { gap: 10px; padding: 0 12px; }
      .brand-name { display: none; }
      .ws-name { display: none; }
      .switcher-btn { padding: 6px; }
    }
  `]
})
export class MainLayoutComponent implements OnInit {
  accounts: Account[] = [];
  activeAccount: Account | null = null;
  switcherOpen = false;
  userMenuOpen = false;
  creatingWorkspace = false;
  newWorkspaceName = '';
  busy = false;
  globalSearch = '';

  // Change-password modal
  showChangePw = false;
  pwCurrent = '';
  pwNew = '';
  pwConfirm = '';
  pwError = '';
  pwSuccess = false;
  pwBusy = false;

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    public auth: AuthService,
    private accountService: AccountService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.accountService.activeAccount$.subscribe(a => (this.activeAccount = a));
    if (this.isBrowser) {
      this.accountService.loadSavedAccount();
      this.accountService.listAccounts().subscribe({
        next: (res) => (this.accounts = res.accounts),
        error: () => {},
      });
    }
  }

  initial(name: string): string {
    return (name || '?').trim().charAt(0).toUpperCase();
  }

  /** Global search → the Protocols SOP Finder (works from any page). */
  runSearch(): void {
    const q = this.globalSearch.trim();
    this.router.navigate(['/protocols'], { queryParams: { q: q || null } });
  }

  switchTo(a: Account): void {
    this.switcherOpen = false;
    if (this.activeAccount && a.id === this.activeAccount.id) return;
    this.accountService.setActiveAccount(a);
    // Land on a safe list view; the previous page may reference the old account.
    this.router.navigate(['/protocols']);
  }

  createWorkspace(): void {
    const name = this.newWorkspaceName.trim();
    if (!name || this.busy) return;
    this.busy = true;
    this.accountService.createAccount({ name }).subscribe({
      next: (res) => {
        this.accounts = [...this.accounts, res.account];
        this.newWorkspaceName = '';
        this.creatingWorkspace = false;
        this.busy = false;
        this.switchTo(res.account);
      },
      error: () => { this.busy = false; },
    });
  }

  logout(): void {
    this.userMenuOpen = false;
    this.auth.logout();
    this.router.navigate(['/login']);
  }

  openChangePassword(): void {
    this.userMenuOpen = false;
    this.showChangePw = true;
    this.pwCurrent = this.pwNew = this.pwConfirm = this.pwError = '';
    this.pwSuccess = false;
    this.pwBusy = false;
  }

  closeChangePassword(): void {
    this.showChangePw = false;
  }

  submitChangePassword(): void {
    this.pwError = '';
    if (!this.pwCurrent) { this.pwError = 'Enter your current password.'; return; }
    if (this.pwNew.length < 8) { this.pwError = 'New password must be at least 8 characters.'; return; }
    if (this.pwNew !== this.pwConfirm) { this.pwError = 'New passwords do not match.'; return; }
    this.pwBusy = true;
    this.auth.changePassword(this.pwCurrent, this.pwNew).subscribe({
      next: () => { this.pwBusy = false; this.pwSuccess = true; },
      error: (err) => { this.pwBusy = false; this.pwError = err.message || 'Could not change your password.'; },
    });
  }
}
