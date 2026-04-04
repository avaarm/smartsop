import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCheckboxModule } from '@angular/material/checkbox';

@Component({
  selector: 'app-section-editor',
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatIconModule, MatCheckboxModule,
  ],
  template: `
    <div class="section-editor">
      <!-- Approval Block -->
      <div *ngIf="sectionType === 'approval_block'" class="approval-editor">
        <div *ngFor="let approver of approvers; let i = index" class="approver-row">
          <mat-form-field appearance="outline">
            <mat-label>Role</mat-label>
            <input matInput [(ngModel)]="approver.role" (ngModelChange)="emitChange()">
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Name</mat-label>
            <input matInput [(ngModel)]="approver.name" (ngModelChange)="emitChange()">
          </mat-form-field>
          <mat-form-field appearance="outline" class="date-field">
            <mat-label>Date</mat-label>
            <input matInput [(ngModel)]="approver.date" (ngModelChange)="emitChange()">
          </mat-form-field>
          <button mat-icon-button color="warn" (click)="removeApprover(i)">
            <mat-icon>delete</mat-icon>
          </button>
        </div>
        <button mat-stroked-button (click)="addApprover()">
          <mat-icon>add</mat-icon> Add Approver
        </button>
      </div>

      <!-- References -->
      <div *ngIf="sectionType === 'references'" class="references-editor">
        <div *ngFor="let ref of references; let i = index" class="ref-row">
          <mat-form-field appearance="outline" class="doc-num-field">
            <mat-label>Doc Number</mat-label>
            <input matInput [(ngModel)]="ref.doc_number" (ngModelChange)="emitChange()">
          </mat-form-field>
          <mat-form-field appearance="outline" class="flex-field">
            <mat-label>Title</mat-label>
            <input matInput [(ngModel)]="ref.title" (ngModelChange)="emitChange()">
          </mat-form-field>
          <button mat-icon-button color="warn" (click)="removeReference(i)">
            <mat-icon>delete</mat-icon>
          </button>
        </div>
        <button mat-stroked-button (click)="addReference()">
          <mat-icon>add</mat-icon> Add Reference
        </button>
      </div>

      <!-- Attachments -->
      <div *ngIf="sectionType === 'attachments'" class="attachments-editor">
        <div *ngFor="let att of attachments; let i = index" class="att-row">
          <mat-form-field appearance="outline" class="doc-num-field">
            <mat-label>Doc Number</mat-label>
            <input matInput [(ngModel)]="att.doc_number" (ngModelChange)="emitChange()">
          </mat-form-field>
          <mat-form-field appearance="outline" class="flex-field">
            <mat-label>Title</mat-label>
            <input matInput [(ngModel)]="att.title" (ngModelChange)="emitChange()">
          </mat-form-field>
          <mat-form-field appearance="outline" class="qty-field">
            <mat-label>Qty</mat-label>
            <input matInput type="number" [(ngModel)]="att.quantity" (ngModelChange)="emitChange()">
          </mat-form-field>
          <button mat-icon-button color="warn" (click)="removeAttachment(i)">
            <mat-icon>delete</mat-icon>
          </button>
        </div>
        <button mat-stroked-button (click)="addAttachment()">
          <mat-icon>add</mat-icon> Add Attachment
        </button>
      </div>

      <!-- General Instructions -->
      <div *ngIf="sectionType === 'general_instructions'" class="instructions-editor">
        <div *ngFor="let instr of instructions; let i = index" class="instr-row">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Instruction {{ i + 1 }}</mat-label>
            <textarea matInput [(ngModel)]="instructions[i]" rows="2"
                      (ngModelChange)="emitInstructionsChange()"></textarea>
          </mat-form-field>
          <button mat-icon-button color="warn" (click)="removeInstruction(i)">
            <mat-icon>delete</mat-icon>
          </button>
        </div>
        <button mat-stroked-button (click)="addInstruction()">
          <mat-icon>add</mat-icon> Add Instruction
        </button>
      </div>

      <!-- Checklist / Review -->
      <div *ngIf="sectionType === 'checklist' || sectionType === 'review'" class="checklist-editor">
        <p class="editor-note">Review checklist items:</p>
        <div *ngFor="let item of checklistItems; let i = index" class="checklist-row">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Item {{ i + 1 }}</mat-label>
            <input matInput [(ngModel)]="checklistItems[i]" (ngModelChange)="emitChecklistChange()">
          </mat-form-field>
          <button mat-icon-button color="warn" (click)="removeChecklistItem(i)">
            <mat-icon>delete</mat-icon>
          </button>
        </div>
        <button mat-stroked-button (click)="addChecklistItem()">
          <mat-icon>add</mat-icon> Add Item
        </button>
      </div>

      <!-- Free Text / Comments / Other -->
      <div *ngIf="isGenericText()" class="text-editor">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>{{ sectionTitle }}</mat-label>
          <textarea matInput [(ngModel)]="textContent" rows="4"
                    (ngModelChange)="emitTextChange()"></textarea>
        </mat-form-field>
      </div>

      <!-- Default: show JSON data -->
      <div *ngIf="sectionType === 'label_accountability' || sectionType === 'comments'" class="info-note">
        <mat-icon>info</mat-icon>
        <span>This section uses default formatting. It will be auto-generated in the document.</span>
      </div>
    </div>
  `,
  styles: [`
    .section-editor { padding: 8px 0; }
    .approver-row, .ref-row, .att-row, .instr-row, .checklist-row {
      display: flex; gap: 8px; align-items: flex-start; margin-bottom: 4px;
    }
    .flex-field { flex: 1; }
    .doc-num-field { width: 180px; }
    .qty-field { width: 80px; }
    .date-field { width: 140px; }
    .full-width { width: 100%; }
    .editor-note { color: #666; margin-bottom: 8px; }
    .info-note {
      display: flex; align-items: center; gap: 8px;
      color: #888; font-size: 14px; padding: 12px;
      background: #f5f5f5; border-radius: 4px;
    }
    .info-note mat-icon { font-size: 18px; color: #1565c0; }
    button[mat-stroked-button] { margin-top: 8px; }
  `],
})
export class SectionEditorComponent implements OnChanges {
  @Input() sectionId = '';
  @Input() sectionType = '';
  @Input() sectionTitle = '';
  @Input() data: any = {};
  @Output() dataChange = new EventEmitter<any>();

  approvers: any[] = [];
  references: any[] = [];
  attachments: any[] = [];
  instructions: string[] = [];
  checklistItems: string[] = [];
  textContent = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['data']) {
      this.loadData();
    }
  }

  loadData(): void {
    if (!this.data) return;
    this.approvers = this.data.approvers || [];
    this.references = this.data.references || [];
    this.attachments = this.data.attachments || [];
    this.instructions = this.data.instructions || [];
    this.checklistItems = this.data.checklist_items || [];
    this.textContent = this.data.text || '';
  }

  isGenericText(): boolean {
    return this.sectionType === 'free_text' ||
      (this.sectionType !== 'approval_block' &&
       this.sectionType !== 'references' &&
       this.sectionType !== 'attachments' &&
       this.sectionType !== 'general_instructions' &&
       this.sectionType !== 'checklist' &&
       this.sectionType !== 'review' &&
       this.sectionType !== 'label_accountability' &&
       this.sectionType !== 'comments' &&
       this.sectionType !== 'flowchart');
  }

  emitChange(): void {
    if (this.sectionType === 'approval_block') {
      this.dataChange.emit({ approvers: [...this.approvers] });
    } else if (this.sectionType === 'references') {
      this.dataChange.emit({ references: [...this.references] });
    } else if (this.sectionType === 'attachments') {
      this.dataChange.emit({ attachments: [...this.attachments] });
    }
  }

  emitInstructionsChange(): void {
    this.dataChange.emit({ instructions: [...this.instructions] });
  }

  emitChecklistChange(): void {
    this.dataChange.emit({ ...this.data, checklist_items: [...this.checklistItems] });
  }

  emitTextChange(): void {
    this.dataChange.emit({ text: this.textContent });
  }

  addApprover(): void {
    this.approvers.push({ role: '', name: '', date: '' });
    this.emitChange();
  }
  removeApprover(i: number): void { this.approvers.splice(i, 1); this.emitChange(); }

  addReference(): void {
    this.references.push({ doc_number: '', title: '' });
    this.emitChange();
  }
  removeReference(i: number): void { this.references.splice(i, 1); this.emitChange(); }

  addAttachment(): void {
    this.attachments.push({ doc_number: '', title: '', quantity: 1 });
    this.emitChange();
  }
  removeAttachment(i: number): void { this.attachments.splice(i, 1); this.emitChange(); }

  addInstruction(): void { this.instructions.push(''); this.emitInstructionsChange(); }
  removeInstruction(i: number): void { this.instructions.splice(i, 1); this.emitInstructionsChange(); }

  addChecklistItem(): void { this.checklistItems.push(''); this.emitChecklistChange(); }
  removeChecklistItem(i: number): void { this.checklistItems.splice(i, 1); this.emitChecklistChange(); }
}
