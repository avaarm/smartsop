import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-equipment-list',
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatIconModule,
  ],
  template: `
    <div class="equipment-list-editor">
      <!-- Equipment List -->
      <div *ngIf="sectionType === 'equipment_list'">
        <h4>Equipment</h4>
        <div *ngFor="let item of equipment; let i = index" class="item-row">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Equipment Description</mat-label>
            <input matInput [(ngModel)]="item.description" (ngModelChange)="emitChange()">
          </mat-form-field>
          <button mat-icon-button color="warn" (click)="removeEquipment(i)">
            <mat-icon>delete</mat-icon>
          </button>
        </div>
        <button mat-stroked-button (click)="addEquipment()">
          <mat-icon>add</mat-icon> Add Equipment
        </button>
      </div>

      <!-- Materials List -->
      <div *ngIf="sectionType === 'materials_list'">
        <h4>Materials</h4>
        <div *ngFor="let item of materials; let i = index" class="material-row">
          <mat-form-field appearance="outline" class="pn-field">
            <mat-label>Part Number</mat-label>
            <input matInput [(ngModel)]="item.part_number" (ngModelChange)="emitChange()">
          </mat-form-field>
          <mat-form-field appearance="outline" class="flex-field">
            <mat-label>Description</mat-label>
            <input matInput [(ngModel)]="item.description" (ngModelChange)="emitChange()">
          </mat-form-field>
          <mat-form-field appearance="outline" class="qty-field">
            <mat-label>Qty</mat-label>
            <input matInput [(ngModel)]="item.quantity" (ngModelChange)="emitChange()">
          </mat-form-field>
          <button mat-icon-button color="warn" (click)="removeMaterial(i)">
            <mat-icon>delete</mat-icon>
          </button>
        </div>
        <button mat-stroked-button (click)="addMaterial()">
          <mat-icon>add</mat-icon> Add Material
        </button>
      </div>

      <p class="empty-state" *ngIf="isEmpty()">
        No items yet. Click the add button or use "Fill with AI" to generate a list.
      </p>
    </div>
  `,
  styles: [`
    .equipment-list-editor { padding: 8px 0; }
    h4 { margin: 0 0 12px 0; }
    .item-row, .material-row { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 4px; }
    .full-width { flex: 1; }
    .flex-field { flex: 1; }
    .pn-field { width: 160px; }
    .qty-field { width: 120px; }
    .empty-state { color: #999; text-align: center; padding: 16px; }
    button[mat-stroked-button] { margin-top: 8px; }
  `],
})
export class EquipmentListComponent implements OnChanges {
  @Input() sectionId = '';
  @Input() sectionType = '';
  @Input() data: any = {};
  @Output() dataChange = new EventEmitter<any>();

  equipment: { description: string }[] = [];
  materials: { part_number: string; description: string; quantity: string }[] = [];

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['data']) {
      this.equipment = (this.data?.equipment || []).map((e: any) =>
        typeof e === 'string' ? { description: e } : { description: e.description || '' }
      );
      this.materials = (this.data?.materials || []).map((m: any) => ({
        part_number: m.part_number || '',
        description: m.description || '',
        quantity: m.quantity || 'As Needed',
      }));
    }
  }

  isEmpty(): boolean {
    return this.sectionType === 'equipment_list'
      ? this.equipment.length === 0
      : this.materials.length === 0;
  }

  emitChange(): void {
    if (this.sectionType === 'equipment_list') {
      this.dataChange.emit({ equipment: [...this.equipment] });
    } else {
      this.dataChange.emit({ materials: [...this.materials] });
    }
  }

  addEquipment(): void {
    this.equipment.push({ description: '' });
    this.emitChange();
  }
  removeEquipment(i: number): void { this.equipment.splice(i, 1); this.emitChange(); }

  addMaterial(): void {
    this.materials.push({ part_number: '', description: '', quantity: 'As Needed' });
    this.emitChange();
  }
  removeMaterial(i: number): void { this.materials.splice(i, 1); this.emitChange(); }
}
