import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';

import { GMPDocumentService, GMPTemplate } from '../../../services/gmp-document.service';

@Component({
  selector: 'app-document-list',
  standalone: true,
  imports: [CommonModule, RouterModule, MatCardModule, MatButtonModule, MatIconModule, MatChipsModule],
  template: `
    <div class="document-list">
      <div class="list-header">
        <h1>GMP Documents</h1>
        <button mat-raised-button color="primary" routerLink="/gmp/new">
          <mat-icon>add</mat-icon> New Document
        </button>
      </div>

      <div class="templates-grid">
        <mat-card *ngFor="let t of templates" class="template-card">
          <mat-card-header>
            <mat-icon mat-card-avatar class="type-icon">{{ getIcon(t.doc_type) }}</mat-icon>
            <mat-card-title>{{ t.name }}</mat-card-title>
            <mat-card-subtitle>{{ formatType(t.doc_type) }}</mat-card-subtitle>
          </mat-card-header>
          <mat-card-actions>
            <button mat-button color="primary" [routerLink]="['/gmp/new']"
                    [queryParams]="{ type: t.id }">
              <mat-icon>edit_document</mat-icon> Create
            </button>
          </mat-card-actions>
        </mat-card>
      </div>

      <div class="empty-state" *ngIf="templates.length === 0 && !loading">
        <mat-icon>description</mat-icon>
        <p>No document templates available. Check that the backend is running.</p>
      </div>
    </div>
  `,
  styles: [`
    :host {
      --card-border: hsl(240 5.9% 90%);
      --muted-fg: hsl(240 3.8% 46.1%);
      --primary: hsl(240 5.9% 10%);
      --radius: 0.75rem;
    }
    .document-list {
      padding: 32px 40px;
      max-width: 1100px;
      margin: 0 auto;
      font-family: 'Inter', -apple-system, sans-serif;
    }
    .list-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 32px;
      h1 {
        margin: 0;
        font-size: 30px;
        font-weight: 700;
        letter-spacing: -0.03em;
        color: var(--primary);
      }
      button {
        height: 40px;
        font-size: 14px;
        font-weight: 500;
        border-radius: var(--radius);
        letter-spacing: -0.01em;
      }
    }
    .templates-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 12px;
    }
    .template-card {
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
      transition: border-color 0.15s, box-shadow 0.15s;
      &:hover {
        border-color: hsl(240 5.9% 80%);
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
      }
      .type-icon {
        font-size: 28px;
        width: 36px;
        height: 36px;
        color: var(--primary);
        display: flex;
        align-items: center;
        justify-content: center;
      }
      mat-card-title {
        font-size: 15px;
        font-weight: 600;
        letter-spacing: -0.01em;
      }
      mat-card-subtitle {
        font-size: 13px;
        color: var(--muted-fg);
      }
      button {
        font-size: 13px;
        font-weight: 500;
        letter-spacing: -0.01em;
      }
    }
    .empty-state {
      text-align: center;
      padding: 64px;
      color: var(--muted-fg);
      mat-icon {
        font-size: 40px;
        width: 40px;
        height: 40px;
        margin-bottom: 12px;
        color: hsl(0 0% 80%);
      }
      p { font-size: 14px; }
    }
  `],
})
export class DocumentListComponent implements OnInit {
  templates: GMPTemplate[] = [];
  loading = false;

  constructor(private gmpService: GMPDocumentService) {}

  ngOnInit(): void {
    this.loading = true;
    this.gmpService.getTemplates().subscribe({
      next: (res) => { this.templates = res.templates || []; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  getIcon(type: string): string {
    const icons: Record<string, string> = {
      batch_record: 'science',
      sop: 'description',
      deviation_report: 'report_problem',
      capa: 'build',
      change_control: 'swap_horiz',
    };
    return icons[type] || 'description';
  }

  formatType(type: string): string {
    return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
}
