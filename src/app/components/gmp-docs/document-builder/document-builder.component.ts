import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import {
  GMPDocumentService,
  GMPTemplate,
  GMPTemplateSchema,
  GMPSectionSchema,
  GMPDocumentRequest,
  OllamaStatus,
} from '../../../services/gmp-document.service';

@Component({
  selector: 'app-document-builder',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './document-builder.component.html',
  styleUrl: './document-builder.component.scss',
})
export class DocumentBuilderComponent implements OnInit {
  // Stepper state
  currentStep = 1;
  totalSteps = 4;

  // Template
  templates: GMPTemplate[] = [];
  selectedTemplateId = '';
  templateSchema: GMPTemplateSchema | null = null;

  // Basic info
  docTitle = '';
  productName = '';
  processType = '';
  description = '';
  docNumber = '';
  revision = '01';

  // Section data
  sectionData: Record<string, any> = {};
  expandedSections: Record<string, boolean> = {};

  // Status
  loading = false;
  generating = false;
  ollamaStatus: OllamaStatus | null = null;

  // Generated result
  generatedDocUrl = '';
  generatedFilename = '';
  generatedPreview: any[] = [];
  errorMessage = '';
  successMessage = '';

  // Per-section AI loading
  sectionGenerating: Record<string, boolean> = {};
  fillAllInProgress = false;
  fillAllProgress = { current: 0, total: 0 };

  constructor(private gmp: GMPDocumentService) {}

  ngOnInit(): void {
    this.loadTemplates();
    this.checkOllamaStatus();
  }

  loadTemplates(): void {
    this.loading = true;
    this.gmp.getTemplates().subscribe({
      next: (res) => {
        this.templates = res.templates || [];
        this.loading = false;
      },
      error: (err) => {
        this.errorMessage = err.message;
        this.loading = false;
      },
    });
  }

  checkOllamaStatus(): void {
    this.gmp.getOllamaStatus().subscribe({
      next: (s) => (this.ollamaStatus = s),
      error: () => (this.ollamaStatus = { success: false, available: false, model: '', models: [] }),
    });
  }

  selectTemplate(id: string): void {
    this.selectedTemplateId = id;
    this.loading = true;
    this.gmp.getTemplateSchema(id).subscribe({
      next: (res) => {
        this.templateSchema = res.template;
        this.sectionData = {};
        for (const s of this.templateSchema.sections) {
          if (s.default_data) {
            this.sectionData[s.id] = { ...s.default_data };
          }
        }
        this.loading = false;
      },
      error: (err) => {
        this.errorMessage = err.message;
        this.loading = false;
      },
    });
  }

  canProceedFromStep(step: number): boolean {
    if (step === 1) return !!this.templateSchema;
    if (step === 2) return !!this.docTitle && !!this.productName && !!this.processType;
    return true;
  }

  nextStep(): void {
    if (this.currentStep < this.totalSteps && this.canProceedFromStep(this.currentStep)) {
      this.currentStep++;
    }
  }

  prevStep(): void {
    if (this.currentStep > 1) {
      this.currentStep--;
    }
  }

  goToStep(n: number): void {
    if (n < this.currentStep || (n === this.currentStep + 1 && this.canProceedFromStep(this.currentStep))) {
      this.currentStep = n;
    }
  }

  toggleSection(id: string): void {
    this.expandedSections[id] = !this.expandedSections[id];
  }

  fillSectionWithAI(section: GMPSectionSchema): void {
    this.sectionGenerating[section.id] = true;
    this.gmp.previewSection({
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
        this.successMessage = `${section.title} filled with AI`;
        setTimeout(() => (this.successMessage = ''), 3000);
      },
      error: (err) => {
        this.sectionGenerating[section.id] = false;
        this.errorMessage = `Failed to generate ${section.title}: ${err.message}`;
        setTimeout(() => (this.errorMessage = ''), 5000);
      },
    });
  }

  fillAllSectionsWithAI(): void {
    if (!this.templateSchema) return;
    const sectionsToFill = this.templateSchema.sections.filter(
      s => s.llm_prompt && !this.sectionHasContent(s.id)
    );
    if (sectionsToFill.length === 0) {
      this.successMessage = 'All sections already have content';
      setTimeout(() => (this.successMessage = ''), 3000);
      return;
    }

    this.fillAllInProgress = true;
    this.fillAllProgress = { current: 0, total: sectionsToFill.length };
    let completed = 0;

    // Run all section fills in parallel
    sectionsToFill.forEach((section) => {
      this.sectionGenerating[section.id] = true;
      this.gmp.previewSection({
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
          completed++;
          this.fillAllProgress.current = completed;
          if (completed === sectionsToFill.length) {
            this.fillAllInProgress = false;
            this.successMessage = `${sectionsToFill.length} sections filled with AI`;
            setTimeout(() => (this.successMessage = ''), 4000);
          }
        },
        error: (err) => {
          this.sectionGenerating[section.id] = false;
          completed++;
          this.fillAllProgress.current = completed;
          if (completed === sectionsToFill.length) {
            this.fillAllInProgress = false;
          }
          this.errorMessage = `Failed on ${section.title}: ${err.message}`;
          setTimeout(() => (this.errorMessage = ''), 5000);
        },
      });
    });
  }

  generateDocument(): void {
    this.generating = true;
    this.errorMessage = '';
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

    this.gmp.generateDocument(request).subscribe({
      next: (res) => {
        this.generating = false;
        if (res.success) {
          this.generatedDocUrl = this.gmp.getDownloadUrl(res.filename!);
          this.generatedFilename = res.filename!;
          this.generatedPreview = res.preview_sections || [];
          this.successMessage = 'Document generated successfully';
        }
      },
      error: (err) => {
        this.generating = false;
        this.errorMessage = err.message;
      },
    });
  }

  downloadDocument(): void {
    if (this.generatedDocUrl) {
      window.open(this.generatedDocUrl, '_blank');
    }
  }

  resetBuilder(): void {
    this.currentStep = 1;
    this.selectedTemplateId = '';
    this.templateSchema = null;
    this.docTitle = '';
    this.productName = '';
    this.processType = '';
    this.description = '';
    this.docNumber = '';
    this.revision = '01';
    this.sectionData = {};
    this.expandedSections = {};
    this.generatedDocUrl = '';
    this.generatedFilename = '';
    this.generatedPreview = [];
    this.loadTemplates();
  }

  getSectionIcon(type: string): string {
    const icons: Record<string, string> = {
      approval_block: '✓',
      references: '📖',
      attachments: '📎',
      general_instructions: 'ℹ',
      step_procedure: '≡',
      equipment_list: '⚙',
      materials_list: '◉',
      flowchart: '◈',
      checklist: '☑',
      comments: '💬',
      review: '★',
      label_accountability: '▣',
      free_text: '¶',
    };
    return icons[type] || '●';
  }

  sectionHasContent(id: string): boolean {
    const data = this.sectionData[id];
    if (!data) return false;
    return Object.keys(data).length > 0;
  }

  formatSectionType(type: string): string {
    return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  get filledSectionsCount(): number {
    if (!this.templateSchema) return 0;
    return this.templateSchema.sections.filter(s => this.sectionHasContent(s.id)).length;
  }
}
