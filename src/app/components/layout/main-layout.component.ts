import { Component } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';

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
            <div class="nav-section-title">Primary</div>
            <a routerLink="/protocols" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-link nav-link-primary">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              <span>Protocol Knowledge</span>
            </a>
          </div>

          <div class="nav-section">
            <div class="nav-section-title">Use</div>
            <a routerLink="/gmp" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <span>Document Builder</span>
            </a>
            <a routerLink="/account" routerLinkActive="active" class="nav-link">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              <span>Account &amp; Training</span>
            </a>
          </div>
        </nav>

        <div class="sidebar-footer">
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

    .nav-section {
      margin-bottom: 14px;
    }

    .nav-section-title {
      padding: 0 10px;
      margin-bottom: 6px;
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
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

    .nav-link-primary {
      font-weight: 500;
      color: hsl(0 0% 85%);
    }

    .nav-link-primary svg {
      opacity: 0.9;
      color: hsl(221 83% 65%);
    }

    .nav-link-primary.active {
      background: linear-gradient(135deg, hsl(221 83% 25% / 0.6), hsl(263 70% 25% / 0.6));
      color: hsl(0 0% 100%);
    }

    .nav-link-primary.active svg {
      color: hsl(221 83% 75%);
    }

    .sidebar-footer {
      padding: 14px 18px;
      border-top: 1px solid hsl(0 0% 10%);
    }

    .footer-text {
      font-size: 11px;
      color: hsl(0 0% 40%);
    }

    .main-content {
      flex: 1;
      overflow-y: auto;
      background: hsl(0 0% 99%);
    }

    .sidebar::-webkit-scrollbar { width: 4px; }
    .sidebar::-webkit-scrollbar-track { background: transparent; }
    .sidebar::-webkit-scrollbar-thumb { background: hsl(0 0% 15%); border-radius: 2px; }
  `]
})
export class MainLayoutComponent {}
