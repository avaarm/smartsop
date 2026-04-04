import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatStepperModule } from '@angular/material/stepper';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatSnackBarModule, MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';

import {
  GMPDocumentService,
  GMPTemplate,
  GMPTemplateSchema,
  GMPSectionSchema,
  GMPDocumentRequest,
  OllamaStatus,
} from '../../../services/gmp-document.service';
import { SectionEditorComponent } from '../section-editor/section-editor.component';
import { StepBuilderComponent } from '../step-builder/step-builder.component';
import { EquipmentListComponent } from '../equipment-list/equipment-list.component';

@Component({
  selector: 'app-document-builder',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatStepperModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatCardModule,
    MatChipsModule,
    MatExpansionModule,
    MatSnackBarModule,
    MatTooltipModule,
    MatDividerModule,
    SectionEditorComponent,
    StepBuilderComponent,
    EquipmentListComponent,
  ],
  templateUrl: './document-builder.component.html',
  styleUrl: './document-builder.component.scss',
})
export class DocumentBuilderComponent implements OnInit {
  // Step 1: Template selection
  templates: GMPTemplate[] = [];
  selectedTemplateId: string = '';
  templateSchema: GMPTemplateSchema | null = null;

  // Step 2: Basic info
  docTitle: string = '';
  productName: string = '';
  processType: string = '';
  description: string = '';
  docNumber: string = '';
  revision: string = '01';

  // Step 3: Section data
  sectionData: Record<string, any> = {};

  // Status
  loading = false;
  generating = false;
  ollamaStatus: OllamaStatus | null = null;
  generatedDocUrl: string = '';
  generatedFilename: string = '';
  generatedPreview: any[] = [];

  // Section AI generation tracking
  sectionGenerating: Record<string, boolean> = {};

  constructor(
    private gmpService: GMPDocumentService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadTemplates();
    this.checkOllamaStatus();
  }

  loadTemplates(): void {
    this.loading = true;
    this.gmpService.getTemplates().subscribe({
      next: (res) => {
        this.templates = res.templates || [];
        this.loading = false;
      },
      error: (err) => {
        this.snackBar.open(err.message, 'Close', { duration: 5000 });
        this.loading = false;
      },
    });
  }

  checkOllamaStatus(): void {
    this.gmpService.getOllamaStatus().subscribe({
      next: (status) => {
        this.ollamaStatus = status;
      },
      error: () => {
        this.ollamaStatus = { success: false, available: false, model: '', models: [] };
      },
    });
  }

  onTemplateSelect(): void {
    if (!this.selectedTemplateId) return;
    this.loading = true;
    this.gmpService.getTemplateSchema(this.selectedTemplateId).subscribe({
      next: (res) => {
        this.templateSchema = res.template;
        // Initialize section data with defaults
        this.sectionData = {};
        for (const section of this.templateSchema.sections) {
          if (section.default_data) {
            this.sectionData[section.id] = { ...section.default_data };
          }
        }
        this.loading = false;
      },
      error: (err) => {
        this.snackBar.open(err.message, 'Close', { duration: 5000 });
        this.loading = false;
      },
    });
  }

  fillSectionWithAI(section: GMPSectionSchema): void {
    this.sectionGenerating[section.id] = true;
    this.gmpService.previewSection({
      doc_type: this.selectedTemplateId,
      section_id: section.id,
      context: {
        product_name: this.productName,
        process_type: this.processType,
        description: this.description,
      },
    }).subscribe({
      next: (res) => {
        if (res.data) {
          this.sectionData[section.id] = res.data;
        }
        this.sectionGenerating[section.id] = false;
        this.snackBar.open(`${section.title} generated with AI`, 'OK', { duration: 3000 });
      },
      error: (err) => {
        this.sectionGenerating[section.id] = false;
        this.snackBar.open(`Failed to generate ${section.title}: ${err.message}`, 'Close', { duration: 5000 });
      },
    });
  }

  onSectionDataChange(sectionId: string, data: any): void {
    this.sectionData[sectionId] = data;
  }

  generateDocument(): void {
    this.generating = true;
    const request: GMPDocumentRequest = {
      doc_type: this.selectedTemplateId,
      title: this.docTitle,
      product_name: this.productName,
      process_type: this.processType,
      description: this.description,
      doc_number: this.docNumber || undefined,
      revision: this.revision,
      sections: this.sectionData,
    };

    this.gmpService.generateDocument(request).subscribe({
      next: (res) => {
        this.generating = false;
        if (res.success) {
          this.generatedDocUrl = this.gmpService.getDownloadUrl(res.filename!);
          this.generatedFilename = res.filename!;
          this.generatedPreview = res.preview_sections || [];
          this.snackBar.open('Document generated successfully!', 'Download', {
            duration: 10000,
          }).onAction().subscribe(() => {
            window.open(this.generatedDocUrl, '_blank');
          });
        }
      },
      error: (err) => {
        this.generating = false;
        this.snackBar.open(err.message, 'Close', { duration: 5000 });
      },
    });
  }

  downloadDocument(): void {
    if (this.generatedDocUrl) {
      window.open(this.generatedDocUrl, '_blank');
    }
  }

  getSectionIcon(type: string): string {
    const icons: Record<string, string> = {
      approval_block: 'verified',
      references: 'menu_book',
      attachments: 'attach_file',
      general_instructions: 'info',
      step_procedure: 'format_list_numbered',
      equipment_list: 'build',
      materials_list: 'science',
      flowchart: 'account_tree',
      checklist: 'checklist',
      comments: 'comment',
      review: 'rate_review',
      label_accountability: 'label',
      free_text: 'notes',
    };
    return icons[type] || 'description';
  }

  isStepProcedure(type: string): boolean {
    return type === 'step_procedure';
  }

  isEquipmentOrMaterials(type: string): boolean {
    return type === 'equipment_list' || type === 'materials_list';
  }
}
