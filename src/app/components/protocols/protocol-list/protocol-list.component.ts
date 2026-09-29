import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ProtocolService, Protocol, ProtocolTemplate, DocCategory, DocTemplate } from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';

@Component({
  selector: 'app-protocol-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './protocol-list.component.html',
  styleUrl: './protocol-list.component.scss',
})
export class ProtocolListComponent implements OnInit {
  activeAccount: Account | null = null;
  protocols: Protocol[] = [];
  loading = false;
  creating = false;
  errorMessage = '';

  showNewForm = false;
  newTitle = '';
  newDescription = '';

  // Regulatory template gallery
  templates: ProtocolTemplate[] = [];
  showTemplates = false;
  creatingFromTemplate = false;

  // Import modal
  showImport = false;
  importTab: 'paste' | 'file' = 'paste';
  importTitle = '';
  importText = '';
  importMode = 'document';
  importFile: File | null = null;
  importing = false;

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private protocolService: ProtocolService,
    private accountService: AccountService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.accountService.activeAccount$.subscribe(a => {
      this.activeAccount = a;
      if (a && this.isBrowser) { this.loadProtocols(); this.loadTemplates(); }
    });
    if (this.isBrowser) this.accountService.loadSavedAccount();
  }

  // ── Templates ──

  myTemplates: Protocol[] = [];

  private loadTemplates(): void {
    if (!this.activeAccount) return;
    this.protocolService.listTemplates(this.activeAccount.id)
      .subscribe({ next: (res) => (this.templates = res.templates), error: () => {} });
    this.loadMyTemplates();
  }

  private loadMyTemplates(): void {
    if (!this.activeAccount) return;
    this.protocolService.listTemplateLibrary(this.activeAccount.id)
      .subscribe({ next: (res) => (this.myTemplates = res.protocols), error: () => {} });
  }

  /** The org's own templates grouped by document type, for the gallery. */
  get myTemplateGroups(): { category: string; items: Protocol[] }[] {
    const groups = new Map<string, Protocol[]>();
    for (const t of this.myTemplates) {
      const cat = t.template_category || 'General';
      (groups.get(cat) || groups.set(cat, []).get(cat)!).push(t);
    }
    return [...groups.entries()].map(([category, items]) => ({ category, items }))
      .sort((a, b) => a.category.localeCompare(b.category));
  }

  openTemplates(): void {
    this.showTemplates = true;
    this.errorMessage = '';
    this.loadMyTemplates();
  }

  useTemplate(t: ProtocolTemplate): void {
    if (!this.activeAccount || this.creatingFromTemplate) return;
    this.creatingFromTemplate = true;
    this.protocolService.createFromTemplate(this.activeAccount.id, t.key).subscribe({
      next: (res) => {
        this.creatingFromTemplate = false;
        this.showTemplates = false;
        this.router.navigate(['/protocols', res.protocol.id]);
      },
      error: (err) => { this.errorMessage = err.message; this.creatingFromTemplate = false; },
    });
  }

  // Project setup (fill-in variables) when starting from a template.
  showVarSetup = false;
  varTemplate: Protocol | null = null;
  varList: string[] = [];
  varValues: Record<string, string> = {};
  varTitle = '';
  varBusy = false;

  /** Start a new working document from one of the org's own templates.
      If the template has {{placeholders}}, collect them first. */
  useMyTemplate(t: Protocol): void {
    if (!this.activeAccount || this.creatingFromTemplate) return;
    this.creatingFromTemplate = true;
    this.protocolService.templateVariables(this.activeAccount.id, t.id).subscribe({
      next: (res) => {
        this.creatingFromTemplate = false;
        if (res.variables.length) {
          this.varTemplate = t;
          this.varList = res.variables;
          this.varValues = {};
          res.variables.forEach(v => (this.varValues[v] = ''));
          this.varTitle = t.title;
          this.showTemplates = false;
          this.showVarSetup = true;
        } else {
          this.forkTemplate(t.id);
        }
      },
      error: (err) => { this.errorMessage = err.message; this.creatingFromTemplate = false; },
    });
  }

  private forkTemplate(id: number, opts?: { title?: string; variables?: Record<string, string> }): void {
    if (!this.activeAccount) return;
    this.creatingFromTemplate = true;
    this.protocolService.copyProtocol(this.activeAccount.id, id, opts).subscribe({
      next: (res) => {
        this.creatingFromTemplate = false;
        this.showTemplates = false;
        this.showVarSetup = false;
        this.router.navigate(['/protocols', res.protocol.id]);
      },
      error: (err) => { this.errorMessage = err.message; this.creatingFromTemplate = false; },
    });
  }

  confirmVarSetup(): void {
    if (!this.varTemplate) return;
    this.forkTemplate(this.varTemplate.id, { title: this.varTitle.trim() || undefined, variables: this.varValues });
  }

  /** A live preview of the project title with variables filled in. */
  get varTitlePreview(): string {
    return this.varTitle.replace(/\{\{\s*([\w .\-/#]+?)\s*\}\}/g,
      (m, k) => (this.varValues[String(k).trim()] || m));
  }

  // ── "What do you want to write?" — new-document picker ──
  showNewDoc = false;
  newDocStep: 'category' | 'template' = 'category';
  docCategories: DocCategory[] = [];
  builtinDocTemplates: DocTemplate[] = [];
  selectedCat: DocCategory | null = null;

  openNewDoc(): void {
    if (!this.activeAccount) return;
    this.showNewDoc = true;
    this.newDocStep = 'category';
    this.selectedCat = null;
    this.errorMessage = '';
    this.protocolService.docCategories(this.activeAccount.id)
      .subscribe({ next: (res) => (this.docCategories = res.categories), error: () => {} });
    this.protocolService.docTemplates(this.activeAccount.id)
      .subscribe({ next: (res) => (this.builtinDocTemplates = res.templates), error: () => {} });
    this.loadMyTemplates();
  }

  /** How many starting points a category offers (built-in + the org's own). */
  templateCountFor(cat: DocCategory): number {
    return this.builtinsForCat(cat).length + this.orgTemplatesForCat(cat).length;
  }

  pickCategory(cat: DocCategory): void {
    this.selectedCat = cat;
    this.newDocStep = 'template';
  }

  builtinsForCat(cat: DocCategory): DocTemplate[] {
    return this.builtinDocTemplates.filter(t => t.doc_category === cat.code);
  }

  orgTemplatesForCat(cat: DocCategory): Protocol[] {
    return this.myTemplates.filter(t =>
      t.doc_category === cat.code ||
      (!t.doc_category && (t.template_category || '').toLowerCase() === cat.name.toLowerCase()));
  }

  /** Start a new document from a built-in facility template. */
  useBuiltinDocTemplate(t: DocTemplate): void {
    if (!this.activeAccount || this.creatingFromTemplate) return;
    this.creatingFromTemplate = true;
    this.protocolService.createFromDocTemplate(this.activeAccount.id, t.key).subscribe({
      next: (res) => {
        this.creatingFromTemplate = false;
        this.showNewDoc = false;
        this.router.navigate(['/protocols', res.protocol.id]);
      },
      error: (err) => { this.errorMessage = err.message; this.creatingFromTemplate = false; },
    });
  }

  /** Start from one of the org's own templates (via the picker). */
  useOrgTemplateFromPicker(t: Protocol): void {
    this.showNewDoc = false;
    this.useMyTemplate(t);
  }

  /** Blank document in the chosen category. */
  startBlankInCategory(cat: DocCategory): void {
    if (!this.activeAccount || this.creating) return;
    this.creating = true;
    this.protocolService.createProtocol(this.activeAccount.id,
      { title: `New ${cat.name} document` }).subscribe({
      next: (res) => {
        this.creating = false;
        this.showNewDoc = false;
        // Tag it with the chosen category, then open it.
        this.protocolService.updateProtocol(this.activeAccount!.id, res.protocol.id,
          { doc_category: cat.code } as any).subscribe({ next: () => {}, error: () => {} });
        this.router.navigate(['/protocols', res.protocol.id]);
      },
      error: (err) => { this.errorMessage = err.message; this.creating = false; },
    });
  }

  search = '';

  loadProtocols(): void {
    if (!this.activeAccount) return;
    this.loading = true;
    this.protocolService.listProtocols(this.activeAccount.id, 1, this.search.trim()).subscribe({
      next: (res) => { this.protocols = res.protocols; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  clearSearch(): void {
    this.search = '';
    this.loadProtocols();
  }

  createProtocol(): void {
    if (!this.activeAccount || !this.newTitle.trim()) return;
    this.creating = true;
    this.protocolService.createProtocol(this.activeAccount.id, {
      title: this.newTitle.trim(),
      description: this.newDescription.trim(),
    }).subscribe({
      next: (res) => {
        this.creating = false;
        this.router.navigate(['/protocols', res.protocol.id]);
      },
      error: (err) => { this.errorMessage = err.message; this.creating = false; },
    });
  }

  open(p: Protocol): void {
    this.router.navigate(['/protocols', p.id]);
  }

  // ── Import ──

  importAsTemplate = false;
  importCategory = '';

  openImport(): void {
    this.showImport = true;
    this.importTab = 'paste';
    this.importTitle = '';
    this.importText = '';
    this.importMode = 'document';
    this.importFile = null;
    this.importAsTemplate = false;
    this.importCategory = '';
    this.errorMessage = '';
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.importFile = input.files && input.files.length ? input.files[0] : null;
    if (this.importFile && !this.importTitle.trim()) {
      this.importTitle = this.importFile.name.replace(/\.[^.]+$/, '').replace(/_/g, ' ');
    }
  }

  runImport(): void {
    if (!this.activeAccount) return;
    const acc = this.activeAccount.id;
    this.importing = true;
    this.errorMessage = '';

    const asTemplate = this.importAsTemplate;
    const done = (res: { protocol: Protocol }) => {
      this.importing = false;
      this.showImport = false;
      // A template lands in the library; go back to the list and open the gallery.
      if (asTemplate) { this.loadProtocols(); this.loadMyTemplates(); this.showTemplates = true; }
      else this.router.navigate(['/protocols', res.protocol.id]);
    };
    const fail = (err: Error) => { this.errorMessage = err.message; this.importing = false; };
    const category = this.importCategory.trim() || 'General';

    if (this.importTab === 'file') {
      if (!this.importFile) { this.importing = false; return; }
      const form = new FormData();
      form.append('file', this.importFile);
      form.append('mode', this.importMode);
      if (this.importTitle.trim()) form.append('title', this.importTitle.trim());
      if (asTemplate) { form.append('as_template', 'true'); form.append('category', category); }
      this.protocolService.importFromFile(acc, form).subscribe({ next: done, error: fail });
    } else {
      if (!this.importText.trim()) { this.importing = false; return; }
      this.protocolService.importFromText(acc, {
        title: this.importTitle.trim() || undefined, text: this.importText, mode: this.importMode,
        as_template: asTemplate || undefined, category: asTemplate ? category : undefined,
      }).subscribe({ next: done, error: fail });
    }
  }

  formatDate(iso: string | null | undefined): string {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
}
