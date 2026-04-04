import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';

interface ProcedureStep {
  number: string;
  title: string;
  instructions: StepInstruction[];
  variables: StepVariable[];
  results: StepResult[];
}

interface StepInstruction {
  text: string;
  type: string; // action, verification, record, calculation
  bsc: boolean;
  options?: string[];
}

interface StepVariable {
  name: string;
  type: string; // text, number, date, time
  format?: string;
}

interface StepResult {
  unit: string;
}

@Component({
  selector: 'app-step-builder',
  standalone: true,
  imports: [
    CommonModule, FormsModule, DragDropModule,
    MatFormFieldModule, MatInputModule, MatButtonModule,
    MatIconModule, MatExpansionModule, MatSelectModule, MatCheckboxModule,
  ],
  template: `
    <div class="step-builder">
      <div class="step-header">
        <h4>Procedure Steps</h4>
        <button mat-stroked-button (click)="addStep()">
          <mat-icon>add</mat-icon> Add Step
        </button>
      </div>

      <div cdkDropList (cdkDropListDropped)="onDrop($event)" class="steps-list">
        <mat-expansion-panel *ngFor="let step of steps; let i = index"
                             cdkDrag class="step-panel">
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon cdkDragHandle class="drag-handle">drag_indicator</mat-icon>
              <strong>{{ step.number || (i + 1) }}</strong>
              <span class="step-title-text">{{ step.title || 'Untitled Step' }}</span>
            </mat-panel-title>
            <mat-panel-description>
              {{ step.instructions.length }} instruction(s)
            </mat-panel-description>
          </mat-expansion-panel-header>

          <div class="step-detail">
            <div class="step-meta">
              <mat-form-field appearance="outline" class="step-num-field">
                <mat-label>Step #</mat-label>
                <input matInput [(ngModel)]="step.number" (ngModelChange)="emitChange()">
              </mat-form-field>
              <mat-form-field appearance="outline" class="flex-field">
                <mat-label>Step Title</mat-label>
                <input matInput [(ngModel)]="step.title" (ngModelChange)="emitChange()">
              </mat-form-field>
              <button mat-icon-button color="warn" (click)="removeStep(i)">
                <mat-icon>delete</mat-icon>
              </button>
            </div>

            <!-- Instructions -->
            <h5>Instructions</h5>
            <div *ngFor="let instr of step.instructions; let j = index" class="instruction-row">
              <mat-form-field appearance="outline" class="flex-field">
                <mat-label>Instruction {{ j + 1 }}</mat-label>
                <textarea matInput [(ngModel)]="instr.text" rows="2"
                          (ngModelChange)="emitChange()"></textarea>
              </mat-form-field>
              <mat-form-field appearance="outline" class="type-field">
                <mat-label>Type</mat-label>
                <mat-select [(ngModel)]="instr.type" (selectionChange)="emitChange()">
                  <mat-option value="action">Action</mat-option>
                  <mat-option value="verification">Verification</mat-option>
                  <mat-option value="record">Record</mat-option>
                  <mat-option value="calculation">Calculation</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-checkbox [(ngModel)]="instr.bsc" (change)="emitChange()">BSC</mat-checkbox>
              <button mat-icon-button color="warn" (click)="removeInstruction(step, j)">
                <mat-icon>close</mat-icon>
              </button>
            </div>
            <button mat-stroked-button (click)="addInstruction(step)" class="add-btn">
              <mat-icon>add</mat-icon> Add Instruction
            </button>

            <!-- Variables -->
            <h5>Variables to Record</h5>
            <div *ngFor="let v of step.variables; let k = index" class="variable-row">
              <mat-form-field appearance="outline" class="flex-field">
                <mat-label>Variable Name</mat-label>
                <input matInput [(ngModel)]="v.name" (ngModelChange)="emitChange()">
              </mat-form-field>
              <mat-form-field appearance="outline" class="type-field">
                <mat-label>Type</mat-label>
                <mat-select [(ngModel)]="v.type" (selectionChange)="emitChange()">
                  <mat-option value="text">Text</mat-option>
                  <mat-option value="number">Number</mat-option>
                  <mat-option value="date">Date</mat-option>
                  <mat-option value="time">Time</mat-option>
                </mat-select>
              </mat-form-field>
              <button mat-icon-button color="warn" (click)="removeVariable(step, k)">
                <mat-icon>close</mat-icon>
              </button>
            </div>
            <button mat-stroked-button (click)="addVariable(step)" class="add-btn">
              <mat-icon>add</mat-icon> Add Variable
            </button>
          </div>
        </mat-expansion-panel>
      </div>

      <p class="empty-state" *ngIf="steps.length === 0">
        No steps yet. Click "Add Step" or use "Fill with AI" to generate procedure steps.
      </p>
    </div>
  `,
  styles: [`
    .step-builder { padding: 8px 0; }
    .step-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .step-header h4 { margin: 0; }
    .steps-list { min-height: 40px; }
    .step-panel { margin-bottom: 8px; }
    .step-panel:last-child { margin-bottom: 0; }
    .drag-handle { cursor: grab; color: #999; margin-right: 8px; }
    .step-title-text { margin-left: 8px; }
    .step-detail { padding: 8px 0; }
    .step-detail h5 { margin: 16px 0 8px 0; font-size: 14px; color: #555; }
    .step-meta { display: flex; gap: 8px; align-items: flex-start; }
    .step-num-field { width: 100px; }
    .flex-field { flex: 1; }
    .type-field { width: 140px; }
    .instruction-row, .variable-row { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 4px; }
    .add-btn { margin-top: 4px; }
    .empty-state { color: #999; text-align: center; padding: 24px; }
    .cdk-drag-preview { box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .cdk-drag-placeholder { opacity: 0.3; }
  `],
})
export class StepBuilderComponent implements OnChanges {
  @Input() sectionId = '';
  @Input() stepConfig: any = {};
  @Input() data: any = {};
  @Output() dataChange = new EventEmitter<any>();

  steps: ProcedureStep[] = [];

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['data'] && this.data?.steps) {
      this.steps = this.data.steps.map((s: any) => ({
        number: s.number || '',
        title: s.title || '',
        instructions: (s.instructions || []).map((instr: any) => ({
          text: typeof instr === 'string' ? instr : (instr.text || ''),
          type: instr.type || 'action',
          bsc: instr.bsc || false,
          options: instr.options || [],
        })),
        variables: (s.variables || []).map((v: any) => ({
          name: typeof v === 'string' ? v : (v.name || ''),
          type: v.type || 'text',
          format: v.format || '',
        })),
        results: s.results || [],
      }));
    }
  }

  emitChange(): void {
    this.dataChange.emit({
      ...this.data,
      title: this.data?.title || this.sectionId,
      steps: this.steps,
    });
  }

  addStep(): void {
    const num = this.steps.length + 1;
    this.steps.push({
      number: `${num}`,
      title: '',
      instructions: [{ text: '', type: 'action', bsc: false }],
      variables: [],
      results: [],
    });
    this.emitChange();
  }

  removeStep(i: number): void {
    this.steps.splice(i, 1);
    this.emitChange();
  }

  addInstruction(step: ProcedureStep): void {
    step.instructions.push({ text: '', type: 'action', bsc: false });
    this.emitChange();
  }

  removeInstruction(step: ProcedureStep, i: number): void {
    step.instructions.splice(i, 1);
    this.emitChange();
  }

  addVariable(step: ProcedureStep): void {
    step.variables.push({ name: '', type: 'text' });
    this.emitChange();
  }

  removeVariable(step: ProcedureStep, i: number): void {
    step.variables.splice(i, 1);
    this.emitChange();
  }

  onDrop(event: CdkDragDrop<ProcedureStep[]>): void {
    moveItemInArray(this.steps, event.previousIndex, event.currentIndex);
    this.emitChange();
  }
}
