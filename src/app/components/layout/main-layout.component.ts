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
      <aside class="sidebar">
        <div class="sidebar-header">
          <div class="logo">
            <div class="logo-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
            </div>
            <span>SmartSOP</span>
          </div>
        </div>

        <!-- Workspace switcher -->
        <div class="switcher" *ngIf="activeAccount">
          <button class="switcher-btn" type="button" (click)="switcherOpen = !switcherOpen">
            <span class="ws-avatar">{{ initial(activeAccount.name) }}</span>
            <span class="ws-meta">
              <span class="ws-name">{{ activeAccount.name }}</span>
              <span class="ws-sub">Workspace</span>
            </span>
            <svg class="ws-chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>

          <div class="ws-menu" *ngIf="switcherOpen">
            <div class="ws-menu-label">Switch workspace</div>
            <button class="ws-item" *ngFor="let a of accounts" (click)="switchTo(a)">
              <span class="ws-avatar sm">{{ initial(a.name) }}</span>
              <span class="ws-item-name">{{ a.name }}</span>
              <span class="ws-check" *ngIf="a.id === activeAccount.id">✓</span>
            </button>

            <div class="ws-sep"></div>
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

        <nav class="sidebar-nav">
          <div class="nav-section">
            <div class="nav-section-title">Workspace</div>
            <a routerLink="/gmp" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <span>Document Builder</span>
            </a>
            <a routerLink="/protocols" routerLinkActive="active" class="nav-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 11l3 3L22 4"/>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
              </svg>
              <span>Protocols</span>
            </a>
            <a routerLink="/schedule" routerLinkActive="active" class="nav-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
              <span>Schedule</span>
            </a>
            <a routerLink="/assets" routerLinkActive="active" class="nav-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
              </svg>
              <span>Assets</span>
            </a>
            <a routerLink="/deviations" routerLinkActive="active" class="nav-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/>
              </svg>
              <span>Deviations</span>
            </a>
            <a routerLink="/competency" routerLinkActive="active" class="nav-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>
              </svg>
              <span>Competency</span>
            </a>
            <a routerLink="/analytics" routerLinkActive="active" class="nav-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
              <span>Analytics</span>
            </a>
            <a routerLink="/account" routerLinkActive="active" class="nav-link">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 20h9"/>
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
              </svg>
              <span>Account &amp; Training</span>
            </a>
          </div>
        </nav>

        <div class="sidebar-footer">
          <div class="user-box" *ngIf="auth.currentUser$ | async as user">
            <div class="user-info">
              <div class="user-avatar">{{ (user.name || user.email).charAt(0).toUpperCase() }}</div>
              <div class="user-meta">
                <div class="user-name">{{ user.name || user.email }}</div>
                <div class="user-email" *ngIf="user.name">{{ user.email }}</div>
              </div>
            </div>
            <button class="logout-btn" type="button" (click)="logout()" title="Sign out">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </button>
          </div>
        </div>
      </aside>

      <!-- click-away for the switcher -->
      <div class="switcher-backdrop" *ngIf="switcherOpen" (click)="switcherOpen = false"></div>

      <main class="main-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: [`
    :host {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;

      /* High-end dark sidebar palette */
      --sb-bg: hsl(240 14% 6%);
      --sb-panel: hsl(240 10% 11%);
      --sb-border: hsl(240 8% 16%);
      --sb-text: hsl(240 6% 90%);
      --sb-muted: hsl(240 5% 55%);
      --sb-faint: hsl(240 5% 42%);
      --accent: hsl(243 75% 66%);
      --accent-soft: hsl(243 75% 66% / 0.14);
    }

    .layout { display: flex; height: 100vh; overflow: hidden; }

    .sidebar {
      width: 256px;
      background: linear-gradient(180deg, hsl(240 15% 7%) 0%, var(--sb-bg) 100%);
      color: var(--sb-text);
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--sb-border);
      flex-shrink: 0;
    }

    .sidebar-header { padding: 18px 18px 8px; }
    .logo { display: flex; align-items: center; gap: 10px; font-size: 15px; font-weight: 650; letter-spacing: -0.02em; color: hsl(0 0% 100%); }
    .logo-icon {
      width: 30px; height: 30px; border-radius: 8px;
      background: linear-gradient(135deg, hsl(263 75% 62%) 0%, hsl(230 85% 60%) 100%);
      display: flex; align-items: center; justify-content: center; color: white;
      box-shadow: 0 4px 14px hsl(243 75% 50% / 0.4);
    }

    /* Workspace switcher */
    .switcher { position: relative; padding: 8px 12px 4px; }
    .switcher-btn {
      width: 100%; display: flex; align-items: center; gap: 10px;
      padding: 8px 10px; border-radius: 10px; cursor: pointer;
      background: var(--sb-panel); border: 1px solid var(--sb-border); color: var(--sb-text);
      font-family: inherit; transition: background 0.15s ease, border-color 0.15s ease;
    }
    .switcher-btn:hover { background: hsl(240 10% 13%); border-color: hsl(240 8% 22%); }
    .ws-avatar {
      width: 28px; height: 28px; flex-shrink: 0; border-radius: 7px;
      background: linear-gradient(135deg, hsl(263 65% 55%) 0%, hsl(230 80% 55%) 100%);
      color: #fff; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center;
      &.sm { width: 24px; height: 24px; font-size: 11px; border-radius: 6px; }
    }
    .ws-meta { flex: 1; min-width: 0; text-align: left; display: flex; flex-direction: column; }
    .ws-name { font-size: 13px; font-weight: 600; color: hsl(0 0% 96%); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ws-sub { font-size: 10.5px; color: var(--sb-faint); letter-spacing: 0.02em; }
    .ws-chev { color: var(--sb-muted); flex-shrink: 0; }

    .ws-menu {
      position: absolute; top: calc(100% - 2px); left: 12px; right: 12px; z-index: 70;
      background: hsl(240 12% 10%); border: 1px solid var(--sb-border); border-radius: 12px;
      padding: 6px; box-shadow: 0 16px 40px hsl(240 40% 2% / 0.6);
    }
    .ws-menu-label { font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--sb-faint); padding: 6px 8px 4px; }
    .ws-item {
      width: 100%; display: flex; align-items: center; gap: 9px; padding: 7px 8px;
      background: none; border: none; border-radius: 8px; cursor: pointer; color: var(--sb-text);
      font-family: inherit; font-size: 13px; text-align: left;
      &:hover { background: hsl(240 10% 14%); }
      &.add { color: var(--accent); font-weight: 500; }
    }
    .ws-item-name { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ws-check { color: var(--accent); font-weight: 700; }
    .ws-plus { font-size: 15px; line-height: 1; width: 24px; text-align: center; }
    .ws-sep { height: 1px; background: var(--sb-border); margin: 5px 4px; }
    .ws-create { display: flex; gap: 6px; padding: 4px; }
    .ws-create input {
      flex: 1; min-width: 0; font-size: 12.5px; font-family: inherit; padding: 7px 9px;
      border-radius: 7px; border: 1px solid var(--sb-border); background: hsl(240 10% 8%); color: var(--sb-text);
      &:focus { outline: none; border-color: var(--accent); }
    }
    .ws-create-go {
      font-size: 12px; font-weight: 600; padding: 0 12px; border-radius: 7px; cursor: pointer;
      background: var(--accent); color: #fff; border: none;
      &:disabled { opacity: 0.5; cursor: default; }
    }
    .switcher-backdrop { position: fixed; inset: 0; z-index: 60; }

    .sidebar-nav { flex: 1; padding: 12px 10px; overflow-y: auto; }
    .nav-section-title { padding: 8px 10px 6px; font-size: 10.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--sb-faint); }

    .nav-link {
      position: relative; display: flex; align-items: center; gap: 11px;
      padding: 9px 11px; margin-bottom: 2px; color: var(--sb-muted);
      text-decoration: none; font-size: 13.5px; font-weight: 450; border-radius: 9px;
      transition: background 0.15s ease, color 0.15s ease;
    }
    .nav-link svg { opacity: 0.75; flex-shrink: 0; }
    .nav-link:hover { background: hsl(240 10% 12%); color: hsl(0 0% 96%); }
    .nav-link:hover svg { opacity: 1; }
    .nav-link.active { background: var(--accent-soft); color: hsl(0 0% 100%); font-weight: 550; }
    .nav-link.active svg { opacity: 1; color: var(--accent); }
    .nav-link.active::before {
      content: ''; position: absolute; left: -10px; top: 50%; transform: translateY(-50%);
      width: 3px; height: 20px; border-radius: 0 3px 3px 0; background: var(--accent);
    }

    .sidebar-footer { padding: 12px; border-top: 1px solid var(--sb-border); }
    .user-box { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px; border-radius: 10px; background: var(--sb-panel); }
    .user-info { display: flex; align-items: center; gap: 9px; min-width: 0; }
    .user-avatar {
      width: 30px; height: 30px; flex-shrink: 0; border-radius: 50%;
      background: linear-gradient(135deg, hsl(263 65% 58%) 0%, hsl(230 80% 58%) 100%);
      color: #fff; font-size: 12.5px; font-weight: 650; display: flex; align-items: center; justify-content: center;
    }
    .user-meta { min-width: 0; }
    .user-name { font-size: 12.5px; font-weight: 550; color: hsl(0 0% 94%); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .user-email { font-size: 10.5px; color: var(--sb-faint); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .logout-btn {
      flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 30px; height: 30px;
      padding: 0; border: none; border-radius: 8px; background: transparent; color: var(--sb-muted); cursor: pointer;
      transition: background 0.15s ease, color 0.15s ease;
      &:hover { background: hsl(0 0% 100% / 0.08); color: hsl(0 0% 95%); }
    }

    .main-content { flex: 1; overflow-y: auto; background: hsl(240 20% 99%); }

    .sidebar::-webkit-scrollbar { width: 4px; }
    .sidebar::-webkit-scrollbar-track { background: transparent; }
    .sidebar::-webkit-scrollbar-thumb { background: hsl(240 8% 20%); border-radius: 2px; }

    /* Phones: sidebar becomes a compact top bar */
    @media (max-width: 768px) {
      .layout { flex-direction: column; height: 100dvh; }
      .sidebar { width: 100%; flex-direction: row; align-items: center; border-right: none; border-bottom: 1px solid var(--sb-border); }
      .sidebar-header { padding: 10px 12px; flex-shrink: 0; }
      .logo span { display: none; }
      .switcher { display: none; }
      .sidebar-nav { padding: 8px; overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch; }
      .sidebar-nav::-webkit-scrollbar { display: none; }
      .nav-section { display: flex; gap: 4px; }
      .nav-section-title { display: none; }
      .nav-link { margin-bottom: 0; white-space: nowrap; flex-shrink: 0; }
      .nav-link span { display: none; }
      .nav-link.active::before { display: none; }
      .sidebar-footer { padding: 8px 10px; border-top: none; flex-shrink: 0; margin-left: auto; }
      .user-box { padding: 0; background: none; }
      .user-meta { display: none; }
    }
  `]
})
export class MainLayoutComponent implements OnInit {
  accounts: Account[] = [];
  activeAccount: Account | null = null;
  switcherOpen = false;
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
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
