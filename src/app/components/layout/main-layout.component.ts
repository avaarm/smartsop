import { Component } from '@angular/core';
import { Router, RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';

import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
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
            <span>GMP Docs</span>
          </div>
        </div>

        <nav class="sidebar-nav">
          <div class="nav-section">
            <div class="nav-section-title">Workspace</div>
            <a routerLink="/gmp" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <span>Document Builder</span>
            </a>
            <a routerLink="/protocols" routerLinkActive="active" class="nav-link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 11l3 3L22 4"/>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
              </svg>
              <span>Protocols</span>
            </a>
            <a routerLink="/schedule" routerLinkActive="active" class="nav-link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
              <span>Schedule</span>
            </a>
            <a routerLink="/assets" routerLinkActive="active" class="nav-link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
              </svg>
              <span>Assets</span>
            </a>
            <a routerLink="/deviations" routerLinkActive="active" class="nav-link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/>
              </svg>
              <span>Deviations</span>
            </a>
            <a routerLink="/analytics" routerLinkActive="active" class="nav-link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
              <span>Analytics</span>
            </a>
            <a routerLink="/account" routerLinkActive="active" class="nav-link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </button>
          </div>
          <div class="footer-text">Powered by Llama 3</div>
        </div>
      </aside>

      <main class="main-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: [`
    :host {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .layout {
      display: flex;
      height: 100vh;
      overflow: hidden;
    }

    .sidebar {
      width: 240px;
      background: hsl(0 0% 3.5%);
      color: hsl(0 0% 90%);
      display: flex;
      flex-direction: column;
      border-right: 1px solid hsl(0 0% 12%);
      flex-shrink: 0;
    }

    .sidebar-header {
      padding: 18px 16px;
      border-bottom: 1px solid hsl(0 0% 10%);
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 14px;
      font-weight: 600;
      letter-spacing: -0.02em;
      color: hsl(0 0% 98%);
    }

    .logo-icon {
      width: 28px;
      height: 28px;
      border-radius: 6px;
      background: linear-gradient(135deg, hsl(263 70% 60%) 0%, hsl(217 91% 60%) 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
    }

    .sidebar-nav {
      flex: 1;
      padding: 16px 8px;
      overflow-y: auto;
    }

    .nav-section-title {
      padding: 0 10px;
      margin-bottom: 6px;
      font-size: 11px;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: hsl(0 0% 45%);
    }

    .nav-link {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 7px 10px;
      margin-bottom: 2px;
      color: hsl(0 0% 68%);
      text-decoration: none;
      font-size: 13px;
      font-weight: 400;
      border-radius: 6px;
      transition: all 0.15s ease;
    }

    .nav-link svg {
      opacity: 0.7;
    }

    .nav-link:hover {
      background: hsl(0 0% 9%);
      color: hsl(0 0% 95%);
    }

    .nav-link:hover svg {
      opacity: 1;
    }

    .nav-link.active {
      background: hsl(0 0% 11%);
      color: hsl(0 0% 98%);
      font-weight: 500;
    }

    .nav-link.active svg {
      opacity: 1;
    }

    .sidebar-footer {
      padding: 12px 14px 14px;
      border-top: 1px solid hsl(0 0% 10%);
    }

    .user-box {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 8px;
      margin-bottom: 10px;
      border-radius: 7px;
      background: hsl(0 0% 8%);
    }

    .user-info {
      display: flex;
      align-items: center;
      gap: 9px;
      min-width: 0;
    }

    .user-avatar {
      width: 28px;
      height: 28px;
      flex-shrink: 0;
      border-radius: 50%;
      background: linear-gradient(135deg, hsl(263 70% 55%) 0%, hsl(217 91% 55%) 100%);
      color: #fff;
      font-size: 12px;
      font-weight: 600;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .user-meta { min-width: 0; }

    .user-name {
      font-size: 12.5px;
      font-weight: 500;
      color: hsl(0 0% 92%);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .user-email {
      font-size: 10.5px;
      color: hsl(0 0% 50%);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .logout-btn {
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      padding: 0;
      border: none;
      border-radius: 6px;
      background: transparent;
      color: hsl(0 0% 55%);
      cursor: pointer;
      transition: background 0.15s ease, color 0.15s ease;
    }

    .logout-btn:hover {
      background: hsl(0 0% 14%);
      color: hsl(0 0% 90%);
    }

    .footer-text {
      font-size: 11px;
      color: hsl(0 0% 40%);
      padding: 0 4px;
    }

    .main-content {
      flex: 1;
      overflow-y: auto;
      background: hsl(0 0% 99%);
    }

    .sidebar::-webkit-scrollbar { width: 4px; }
    .sidebar::-webkit-scrollbar-track { background: transparent; }
    .sidebar::-webkit-scrollbar-thumb { background: hsl(0 0% 15%); border-radius: 2px; }

    /* Phones: the sidebar becomes a compact top bar so the content column gets
       the full width. Field work (scanning a tag, running an SOP) happens here. */
    @media (max-width: 768px) {
      .layout { flex-direction: column; height: 100dvh; }

      .sidebar {
        width: 100%;
        flex-direction: row;
        align-items: center;
        border-right: none;
        border-bottom: 1px solid hsl(0 0% 12%);
      }

      .sidebar-header { padding: 10px 12px; border-bottom: none; flex-shrink: 0; }
      .logo span { display: none; }

      .sidebar-nav {
        padding: 8px;
        overflow-x: auto;
        overflow-y: hidden;
        -webkit-overflow-scrolling: touch;
      }
      .sidebar-nav::-webkit-scrollbar { display: none; }
      .nav-section { display: flex; gap: 4px; }
      .nav-section-title { display: none; }
      .nav-link { margin-bottom: 0; white-space: nowrap; flex-shrink: 0; }

      .sidebar-footer { padding: 8px 10px; border-top: none; flex-shrink: 0; margin-left: auto; }
      .user-box { padding: 0; background: none; border: none; }
      .user-meta, .footer-text { display: none; }
    }
  `]
})
export class MainLayoutComponent {
  constructor(public auth: AuthService, private router: Router) {}

  logout(): void {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
