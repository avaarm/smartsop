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
    }

    .sidebar {
      width: 260px;
      background: linear-gradient(180deg, #1a237e 0%, #283593 100%);
      color: white;
      display: flex;
      flex-direction: column;
      box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
      overflow-y: auto;
    }

    .sidebar-header {
      padding: 24px 20px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    .sidebar-header h2 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      line-height: 1.4;
    }

    .sidebar-nav {
      flex: 1;
      padding: 16px 0;
    }

    .nav-section {
      margin-bottom: 24px;
    }

    .nav-section-title {
      padding: 0 20px;
      margin: 0 0 12px 0;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      opacity: 0.6;
    }

    .nav-link {
      display: flex;
      align-items: center;
      padding: 12px 20px;
      color: rgba(255, 255, 255, 0.8);
      text-decoration: none;
      transition: all 0.2s ease;
      border-left: 3px solid transparent;
    }

    .nav-link:hover {
      background: rgba(255, 255, 255, 0.1);
      color: white;
    }

    .nav-link.active {
      background: rgba(255, 255, 255, 0.15);
      color: white;
      border-left-color: #4CAF50;
    }

    .nav-icon {
      margin-right: 12px;
      font-size: 18px;
      width: 24px;
      display: inline-block;
    }

    .main-content {
      flex: 1;
      overflow-y: auto;
      background: #f5f5f5;
    }

    /* Scrollbar styling */
    .sidebar::-webkit-scrollbar {
      width: 6px;
    }

    .sidebar::-webkit-scrollbar-track {
      background: rgba(0, 0, 0, 0.1);
    }

    .sidebar::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.3);
      border-radius: 3px;
    }

    .sidebar::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 255, 255, 0.5);
    }
  `]
})
export class MainLayoutComponent {}
