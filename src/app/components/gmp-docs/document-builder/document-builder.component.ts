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
  Paper,
} from '../../../services/gmp-document.service';
import { AccountService, Account } from '../../../services/account.service';

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

  // Paper scraping state
  paperSearchQuery = '';
  paperSearchResults: Paper[] = [];
  paperSearchLoading = false;
  paperAutofillLoading: Record<string, boolean> = {};
  importedPapers: Paper[] = [];

  activeAccount: Account | null = null;

  constructor(private gmp: GMPDocumentService, private accountService: AccountService) {}

  ngOnInit(): void {
    this.loadTemplates();
    this.checkOllamaStatus();
    this.accountService.activeAccount$.subscribe(a => this.activeAccount = a);
    this.accountService.loadSavedAccount();
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

  // Group templates into the record categories the user wants:
  // Records (batch records, reports, forms, validations, qualifications) and
  // Procedures (SOPs + deviation/change forms). The card UI renders one
  // group per category heading.
  private readonly categoryOrder: { key: string; label: string; description: string }[] = [
    { key: 'batch_record',  label: 'Batch Records',   description: 'Executed GMP manufacturing records' },
    { key: 'validation',    label: 'Validations',     description: 'IQ / OQ / PQ protocols and reports' },
    { key: 'qualification', label: 'Qualifications',  description: 'Equipment and facility qualification' },
    { key: 'form',          label: 'Forms',           description: 'Deviation, change control, and quality forms' },
    { key: 'report',        label: 'Reports',         description: 'Investigations, annual reviews, and summaries' },
    { key: 'sop',           label: 'Procedures (SOP)', description: 'Standard operating procedures' },
  ];

  get templateCategories(): { key: string; label: string; description: string; templates: GMPTemplate[] }[] {
    return this.categoryOrder
      .map(cat => ({
        ...cat,
        templates: this.templates.filter(t => t.doc_type === cat.key),
      }))
      .filter(cat => cat.templates.length > 0);
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
    const ctx: Record<string, any> = {
      product_name: this.productName,
      process_type: this.processType,
      description: this.description,
    };
    if (this.activeAccount) ctx['account_id'] = this.activeAccount.id;
    this.gmp.previewSection({
      doc_type: this.selectedTemplateId,
      section_id: section.id,
      context: ctx,
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
      const ctx: Record<string, any> = {
        product_name: this.productName,
        process_type: this.processType,
        description: this.description,
      };
      if (this.activeAccount) ctx['account_id'] = this.activeAccount.id;
      this.gmp.previewSection({
        doc_type: this.selectedTemplateId,
        section_id: section.id,
        context: ctx,
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
      account_id: this.activeAccount?.id,
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

  // ── Paper Scraping ──

  searchPapers(): void {
    const query = this.paperSearchQuery.trim();
    if (!query) return;
    this.paperSearchLoading = true;
    this.paperSearchResults = [];
    this.gmp.searchPapers(query, 10).subscribe({
      next: (res) => {
        this.paperSearchResults = res.papers || [];
        this.paperSearchLoading = false;
        if (this.paperSearchResults.length === 0) {
          this.errorMessage = 'No open-access papers found for that query';
          setTimeout(() => (this.errorMessage = ''), 5000);
        }
      },
      error: (err) => {
        this.paperSearchLoading = false;
        this.errorMessage = err.message;
      },
    });
  }

  suggestPaperQuery(): void {
    // Pre-fill search with relevant terms from basic info
    const parts = [this.productName, this.processType].filter(Boolean);
    this.paperSearchQuery = parts.join(' ');
    if (this.paperSearchQuery) {
      this.searchPapers();
    }
  }

  importFromPaper(paper: Paper): void {
    this.paperAutofillLoading[paper.pmcid] = true;
    this.gmp.autofillFromPaper(paper.pmcid, {
      product_name: this.productName,
      process_type: this.processType,
    }).subscribe({
      next: (res) => {
        this.paperAutofillLoading[paper.pmcid] = false;
        if (res.section_data) {
          // Merge into existing section data
          for (const [sectionId, data] of Object.entries(res.section_data)) {
            this.sectionData[sectionId] = data;
          }
        }
        if (!this.importedPapers.find(p => p.pmcid === paper.pmcid)) {
          this.importedPapers.push(paper);
        }
        const imported = Object.keys(res.section_data || {}).length;
        this.successMessage = `Imported ${imported} sections from "${paper.title.slice(0, 60)}…"`;
        setTimeout(() => (this.successMessage = ''), 5000);
      },
      error: (err) => {
        this.paperAutofillLoading[paper.pmcid] = false;
        this.errorMessage = `Failed to import from paper: ${err.message}`;
        setTimeout(() => (this.errorMessage = ''), 6000);
      },
    });
  }

  formatAuthors(authors: string[]): string {
    if (!authors || authors.length === 0) return '';
    if (authors.length === 1) return authors[0];
    if (authors.length <= 3) return authors.join(', ');
    return `${authors[0]}, ${authors[1]}, et al.`;
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
    this.paperSearchQuery = '';
    this.paperSearchResults = [];
    this.importedPapers = [];
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
