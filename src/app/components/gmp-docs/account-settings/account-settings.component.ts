import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  AccountService,
  Account,
  DocumentRecord,
  TrainingExample,
  TrainingStats,
} from '../../../services/account.service';

@Component({
  selector: 'app-account-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './account-settings.component.html',
  styleUrl: './account-settings.component.scss',
})
export class AccountSettingsComponent implements OnInit {
  // Tabs
  activeTab: 'account' | 'training' | 'export' | 'history' = 'account';

  // Accounts
  accounts: Account[] = [];
  activeAccount: Account | null = null;
  loading = false;
  saving = false;
  successMessage = '';
  errorMessage = '';

  // Account form
  accountForm = {
    name: '',
    facility_name: '',
    department: '',
    default_product: '',
    default_process: '',
    style_notes: '',
    terminologyText: '',  // newline-separated "KEY: VALUE" pairs
    referenceSopsText: '', // newline-separated SOP list
  };

  // Training data
  trainingExamples: TrainingExample[] = [];
  trainingStats: TrainingStats | null = null;
  trainingPage = 1;
  trainingPages = 1;
  trainingTotal = 0;
  trainingSourceFilter = '';
  trainingLoading = false;

  // Manual training entry
  manualPrompt = '';
  manualCompletion = '';
  manualSectionType = 'step_procedure';

  // Document history
  documents: DocumentRecord[] = [];
  documentsLoading = false;

  // Export
  exportLoading = false;
  modelfileResult: { model_name: string; instructions: string } | null = null;

  constructor(private accountService: AccountService) {}

  ngOnInit(): void {
    this.loadAccounts();
    this.accountService.activeAccount$.subscribe(a => {
      this.activeAccount = a;
      if (a) this.populateForm(a);
    });
  }

  loadAccounts(): void {
    this.loading = true;
    this.accountService.listAccounts().subscribe({
      next: (res) => {
        this.accounts = res.accounts;
        this.loading = false;
        // Auto-select if there's a saved active account
        this.accountService.loadSavedAccount();
      },
      error: (err) => {
        this.errorMessage = err.message;
        this.loading = false;
      },
    });
  }

  selectAccount(account: Account): void {
    this.accountService.setActiveAccount(account);
    this.loadTrainingStats();
    this.loadTrainingExamples();
    this.loadDocuments();
  }

  createAccount(): void {
    if (!this.accountForm.name.trim()) return;
    this.saving = true;
    this.accountService.createAccount({
      name: this.accountForm.name,
      facility_name: this.accountForm.facility_name,
      department: this.accountForm.department,
      default_product: this.accountForm.default_product,
      default_process: this.accountForm.default_process,
      style_notes: this.accountForm.style_notes,
      terminology: this.parseTerminology(),
      reference_sops: this.parseReferenceSops(),
    }).subscribe({
      next: (res) => {
        this.accounts.push(res.account);
        this.selectAccount(res.account);
        this.saving = false;
        this.successMessage = 'Account created';
        setTimeout(() => this.successMessage = '', 3000);
      },
      error: (err) => {
        this.saving = false;
        this.errorMessage = err.message;
        setTimeout(() => this.errorMessage = '', 5000);
      },
    });
  }

  saveAccount(): void {
    if (!this.activeAccount) return;
    this.saving = true;
    this.accountService.updateAccount(this.activeAccount.id, {
      name: this.accountForm.name,
      facility_name: this.accountForm.facility_name,
      department: this.accountForm.department,
      default_product: this.accountForm.default_product,
      default_process: this.accountForm.default_process,
      style_notes: this.accountForm.style_notes,
      terminology: this.parseTerminology(),
      reference_sops: this.parseReferenceSops(),
    }).subscribe({
      next: (res) => {
        this.activeAccount = res.account;
        this.accountService.setActiveAccount(res.account);
        const idx = this.accounts.findIndex(a => a.id === res.account.id);
        if (idx >= 0) this.accounts[idx] = res.account;
        this.saving = false;
        this.successMessage = 'Settings saved';
        setTimeout(() => this.successMessage = '', 3000);
      },
      error: (err) => {
        this.saving = false;
        this.errorMessage = err.message;
        setTimeout(() => this.errorMessage = '', 5000);
      },
    });
  }

  populateForm(account: Account): void {
    this.accountForm.name = account.name;
    this.accountForm.facility_name = account.facility_name;
    this.accountForm.department = account.department;
    this.accountForm.default_product = account.default_product;
    this.accountForm.default_process = account.default_process;
    this.accountForm.style_notes = account.style_notes;
    try {
      const terms = JSON.parse(account.terminology || '{}');
      this.accountForm.terminologyText = Object.entries(terms)
        .map(([k, v]) => `${k}: ${v}`).join('\n');
    } catch { this.accountForm.terminologyText = ''; }
    try {
      const sops = JSON.parse(account.reference_sops || '[]');
      this.accountForm.referenceSopsText = (sops as string[]).join('\n');
    } catch { this.accountForm.referenceSopsText = ''; }
  }

  parseTerminology(): Record<string, string> {
    const result: Record<string, string> = {};
    for (const line of this.accountForm.terminologyText.split('\n')) {
      const idx = line.indexOf(':');
      if (idx > 0) {
        result[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
      }
    }
    return result;
  }

  parseReferenceSops(): string[] {
    return this.accountForm.referenceSopsText
      .split('\n').map(s => s.trim()).filter(Boolean);
  }

  // ── Training Data ──

  loadTrainingStats(): void {
    if (!this.activeAccount) return;
    this.accountService.getTrainingStats(this.activeAccount.id).subscribe({
      next: (res) => this.trainingStats = res,
    });
  }

  loadTrainingExamples(): void {
    if (!this.activeAccount) return;
    this.trainingLoading = true;
    this.accountService.listTrainingExamples(
      this.activeAccount.id, this.trainingPage, this.trainingSourceFilter || undefined
    ).subscribe({
      next: (res) => {
        this.trainingExamples = res.examples;
        this.trainingTotal = res.total;
        this.trainingPages = res.pages;
        this.trainingLoading = false;
      },
      error: () => this.trainingLoading = false,
    });
  }

  changeTrainingPage(delta: number): void {
    this.trainingPage = Math.max(1, Math.min(this.trainingPages, this.trainingPage + delta));
    this.loadTrainingExamples();
  }

  filterTrainingSource(source: string): void {
    this.trainingSourceFilter = source;
    this.trainingPage = 1;
    this.loadTrainingExamples();
  }

  rateExample(example: TrainingExample, rating: number): void {
    if (!this.activeAccount) return;
    this.accountService.rateExample(this.activeAccount.id, example.id, rating).subscribe({
      next: () => {
        example.quality_rating = rating;
        this.loadTrainingStats();
      },
    });
  }

  addManualExample(): void {
    if (!this.activeAccount || !this.manualPrompt.trim() || !this.manualCompletion.trim()) return;
    this.accountService.addTrainingExample(this.activeAccount.id, {
      prompt: this.manualPrompt,
      completion: this.manualCompletion,
      section_type: this.manualSectionType,
    }).subscribe({
      next: () => {
        this.manualPrompt = '';
        this.manualCompletion = '';
        this.loadTrainingExamples();
        this.loadTrainingStats();
        this.successMessage = 'Training example added';
        setTimeout(() => this.successMessage = '', 3000);
      },
      error: (err) => {
        this.errorMessage = err.message;
        setTimeout(() => this.errorMessage = '', 5000);
      },
    });
  }

  // ── Documents ──

  loadDocuments(): void {
    if (!this.activeAccount) return;
    this.documentsLoading = true;
    this.accountService.listDocuments(this.activeAccount.id).subscribe({
      next: (res) => {
        this.documents = res.documents;
        this.documentsLoading = false;
      },
      error: () => this.documentsLoading = false,
    });
  }

  // ── Export ──

  exportJsonl(): void {
    if (!this.activeAccount) return;
    window.open(this.accountService.getExportJsonlUrl(this.activeAccount.id), '_blank');
  }

  exportJsonlEdited(): void {
    if (!this.activeAccount) return;
    window.open(this.accountService.getExportJsonlUrl(this.activeAccount.id, undefined, 'user_edited'), '_blank');
  }

  exportFull(): void {
    if (!this.activeAccount) return;
    window.open(this.accountService.getExportFullUrl(this.activeAccount.id), '_blank');
  }

  generateModelfile(): void {
    if (!this.activeAccount) return;
    this.exportLoading = true;
    this.accountService.generateModelfile(this.activeAccount.id).subscribe({
      next: (res) => {
        this.modelfileResult = res;
        this.exportLoading = false;
      },
      error: (err) => {
        this.exportLoading = false;
        this.errorMessage = err.message;
        setTimeout(() => this.errorMessage = '', 5000);
      },
    });
  }

  formatDate(iso: string): string {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  }
}
