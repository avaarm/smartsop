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
    .document-list { padding: 24px; }
    .list-header {
      display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;
      h1 { margin: 0; font-size: 28px; color: #1a237e; }
    }
    .templates-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
    }
    .template-card {
      .type-icon { font-size: 32px; width: 40px; height: 40px; color: #1a237e;
        display: flex; align-items: center; justify-content: center; }
    }
    .empty-state {
      text-align: center; padding: 48px; color: #999;
      mat-icon { font-size: 48px; width: 48px; height: 48px; margin-bottom: 16px; }
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
