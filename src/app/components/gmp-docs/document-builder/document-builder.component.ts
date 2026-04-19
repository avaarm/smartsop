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
  AppliedStyleSummary,
} from '../../../services/gmp-document.service';
import {
  AccountService,
  Account,
  EffectiveStyleSummary,
} from '../../../services/account.service';
import { DocxPreviewComponent } from '../docx-preview/docx-preview.component';

@Component({
  selector: 'app-document-builder',
  standalone: true,
  imports: [CommonModule, FormsModule, DocxPreviewComponent],
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
  generatedAppliedStyle: AppliedStyleSummary | null = null;
  errorMessage = '';
  successMessage = '';

  /** Whether to apply the learned style on the next generate. Flipped
   *  via the toggle on the generate step, and implicitly for the
   *  side-by-side "unstyled baseline" pass. */
  applyLearnedStyle = true;

  /** State for the side-by-side compare view. ``unstyledDocUrl`` is the
   *  freshly-generated baseline DOCX; present only while comparing. */
  compareOpen = false;
  unstyledDocUrl = '';
  unstyledGenerating = false;

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

  /** Summary of the consolidated style for the currently-selected doc_type —
   *  drives the "Using learned style from N docs" banner. */
  effectiveStyle: EffectiveStyleSummary | null = null;
  effectiveStyleLoading = false;

  constructor(private gmp: GMPDocumentService, private accountService: AccountService) {}

  ngOnInit(): void {
    this.loadTemplates();
    this.checkOllamaStatus();
    this.accountService.activeAccount$.subscribe(a => {
      this.activeAccount = a;
      this.refreshEffectiveStyle();
    });
    this.accountService.loadSavedAccount();
  }

  /** Refetch the effective style whenever the (account, doc_type) pair
   *  changes. Silent failures are fine — the banner just stays hidden. */
  private refreshEffectiveStyle(): void {
    this.effectiveStyle = null;
    if (!this.activeAccount) return;
    this.effectiveStyleLoading = true;
    this.accountService
      .getEffectiveStyle(this.activeAccount.id, this.selectedTemplateId || undefined)
      .subscribe({
        next: (res) => {
          this.effectiveStyle = res.summary;
          this.effectiveStyleLoading = false;
        },
        error: () => {
          this.effectiveStyle = null;
          this.effectiveStyleLoading = false;
        },
      });
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

  // Group templates into high-level categories that span the full lifecycle
  // of a cell therapy / biotech product: Manufacturing (GMP), Clinical,
  // Regulatory / IND, CMC, Quality, and Validation. Each top-level group
  // shows the user which doc_types roll up under it.
  private readonly groupOrder: { key: string; label: string; description: string; docTypes: string[] }[] = [
    {
      key: 'manufacturing',
      label: 'Manufacturing (GMP)',
      description: 'Batch records, SOPs, deviations, change control - the day-to-day production record',
      docTypes: ['batch_record', 'sop', 'form', 'report', 'qualification'],
    },
    {
      key: 'clinical',
      label: 'Clinical Trial',
      description: 'Protocols, brochures, consent, and CRFs for FDA-compliant clinical investigation',
      docTypes: ['clinical_protocol', 'investigator_brochure', 'informed_consent', 'crf'],
    },
    {
      key: 'regulatory',
      label: 'Regulatory / IND',
      description: 'IND application forms and regulatory correspondence per 21 CFR 312',
      docTypes: ['ind_form', 'ind_cover_letter'],
    },
    {
      key: 'cmc',
      label: 'CMC (Module 3)',
      description: 'Drug substance and drug product quality documentation per ICH CTD',
      docTypes: ['cmc_drug_substance', 'cmc_drug_product'],
    },
    {
      key: 'quality',
      label: 'Quality Systems',
      description: 'Risk assessments, quality agreements, and tech transfer per ICH Q9 / Q10',
      docTypes: ['risk_assessment', 'quality_agreement', 'tech_transfer'],
    },
    {
      key: 'validation',
      label: 'Validation',
      description: 'Process, cleaning, method, and stability validation protocols',
      docTypes: ['validation', 'process_validation', 'cleaning_validation', 'method_validation', 'stability_protocol'],
    },
  ];

  get templateCategories(): { key: string; label: string; description: string; templates: GMPTemplate[] }[] {
    return this.groupOrder
      .map(grp => ({
        key: grp.key,
        label: grp.label,
        description: grp.description,
        templates: this.templates.filter(t => grp.docTypes.includes(t.doc_type)),
      }))
      .filter(grp => grp.templates.length > 0);
  }

  checkOllamaStatus(): void {
    this.gmp.getOllamaStatus().subscribe({
      next: (s) => (this.ollamaStatus = s),
      error: () => (this.ollamaStatus = { success: false, available: false, model: '', models: [] }),
    });
  }

  selectTemplate(id: string): void {
    this.selectedTemplateId = id;
    this.refreshEffectiveStyle();
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
    // Close any active comparison — it's stale once we regenerate.
    this.compareOpen = false;
    this.unstyledDocUrl = '';
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
      apply_style: this.applyLearnedStyle,
    };

    this.gmp.generateDocument(request).subscribe({
      next: (res) => {
        this.generating = false;
        if (res.success) {
          this.generatedDocUrl = this.gmp.getDownloadUrl(res.filename!);
          this.generatedFilename = res.filename!;
          this.generatedPreview = res.preview_sections || [];
          this.generatedAppliedStyle = res.applied_style ?? null;
          this.successMessage = 'Document generated successfully';
        }
      },
      error: (err) => {
        this.generating = false;
        this.errorMessage = err.message;
      },
    });
  }

  /** Generate a parallel "no learned style" version of the current
   *  document and open the side-by-side compare view. Only makes sense
   *  when the primary doc was itself generated with a learned style. */
  openCompare(): void {
    if (!this.generatedFilename || !this.applyLearnedStyle) return;
    if (this.unstyledDocUrl) {
      // Already generated — just show it
      this.compareOpen = true;
      return;
    }
    this.unstyledGenerating = true;
    const request: GMPDocumentRequest = {
      doc_type: this.selectedTemplateId,
      title: this.docTitle + ' (baseline)',
      product_name: this.productName,
      process_type: this.processType,
      description: this.description,
      doc_number: this.docNumber ? this.docNumber + '-BASE' : undefined,
      revision: this.revision,
      sections: this.sectionData,
      // Intentionally NO account_id → the generator skips the style path
      // entirely. This gives us a clean template-default baseline.
      apply_style: false,
    };
    this.gmp.generateDocument(request).subscribe({
      next: (res) => {
        this.unstyledGenerating = false;
        if (res.success) {
          this.unstyledDocUrl = this.gmp.getDownloadUrl(res.filename!);
          this.compareOpen = true;
        }
      },
      error: (err) => {
        this.unstyledGenerating = false;
        this.errorMessage = err.message;
      },
    });
  }

  closeCompare(): void {
    this.compareOpen = false;
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
    this.generatedAppliedStyle = null;
    this.compareOpen = false;
    this.unstyledDocUrl = '';
    this.applyLearnedStyle = true;
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
