import { Component } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="layout-container">
      <aside class="sidebar">
        <div class="sidebar-header">
          <h2>SmartSOP Lab Platform</h2>
        </div>
        
        <nav class="sidebar-nav">
          <div class="nav-section">
            <h3 class="nav-section-title">Documents</h3>
            <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-link">
              <span class="nav-icon">💬</span>
              <span>AI Chat</span>
            </a>
            <a routerLink="/form" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">📝</span>
              <span>SOP Form</span>
            </a>
            <a routerLink="/training" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">🎓</span>
              <span>Model Training</span>
            </a>
          </div>

          <div class="nav-section">
            <h3 class="nav-section-title">GMP Documents</h3>
            <a routerLink="/gmp" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-link">
              <span class="nav-icon">📄</span>
              <span>Document Builder</span>
            </a>
            <a routerLink="/gmp/new" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">➕</span>
              <span>New Document</span>
            </a>
          </div>

          <div class="nav-section">
            <h3 class="nav-section-title">Lab Management</h3>
            <a routerLink="/eln/dashboard" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">📊</span>
              <span>Dashboard</span>
            </a>
            <a routerLink="/eln/projects" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">📁</span>
              <span>Projects</span>
            </a>
            <a routerLink="/eln/experiments" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">🔬</span>
              <span>Experiments</span>
            </a>
            <a routerLink="/eln/protocols" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">📋</span>
              <span>Protocols</span>
            </a>
            <a routerLink="/eln/inventory" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">📦</span>
              <span>Inventory</span>
            </a>
            <a routerLink="/eln/users" routerLinkActive="active" class="nav-link">
              <span class="nav-icon">👥</span>
              <span>Users</span>
            </a>
          </div>
        </nav>
      </aside>

      <main class="main-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: [`
    .layout-container {
      display: flex;
      height: 100vh;
      overflow: hidden;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .sidebar {
      width: 260px;
      background: hsl(0 0% 3%);
      color: hsl(0 0% 90%);
      display: flex;
      flex-direction: column;
      border-right: 1px solid hsl(0 0% 12%);
      overflow-y: auto;
    }

    .sidebar-header {
      padding: 20px 16px;
      border-bottom: 1px solid hsl(0 0% 12%);
    }

    .sidebar-header h2 {
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      letter-spacing: -0.02em;
      color: hsl(0 0% 98%);
    }

    .sidebar-nav {
      flex: 1;
      padding: 12px 0;
    }

    .nav-section {
      margin-bottom: 16px;
    }

    .nav-section-title {
      padding: 0 16px;
      margin: 0 0 6px 0;
      font-size: 11px;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: hsl(0 0% 45%);
    }

    .nav-link {
      display: flex;
      align-items: center;
      padding: 8px 16px;
      margin: 1px 8px;
      color: hsl(0 0% 65%);
      text-decoration: none;
      font-size: 14px;
      font-weight: 400;
      border-radius: 6px;
      transition: all 0.15s ease;
    }

    .nav-link:hover {
      background: hsl(0 0% 10%);
      color: hsl(0 0% 95%);
    }

    .nav-link.active {
      background: hsl(0 0% 12%);
      color: hsl(0 0% 98%);
      font-weight: 500;
    }

    .nav-icon {
      margin-right: 10px;
      font-size: 16px;
      width: 20px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      opacity: 0.8;
    }

    .main-content {
      flex: 1;
      overflow-y: auto;
      background: hsl(0 0% 98.5%);
    }

    .sidebar::-webkit-scrollbar { width: 4px; }
    .sidebar::-webkit-scrollbar-track { background: transparent; }
    .sidebar::-webkit-scrollbar-thumb { background: hsl(0 0% 18%); border-radius: 2px; }
  `]
})
export class MainLayoutComponent {}
