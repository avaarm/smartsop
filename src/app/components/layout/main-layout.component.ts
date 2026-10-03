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
                <button class="menu-item danger" type="button" (click)="logout()">Sign out</button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- click-away for any open menu -->
      <div class="menu-backdrop" *ngIf="switcherOpen || userMenuOpen"
           (click)="switcherOpen = false; userMenuOpen = false"></div>

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
}
