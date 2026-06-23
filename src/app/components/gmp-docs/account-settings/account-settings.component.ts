import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  AccountService,
  Account,
  DocumentRecord,
  TrainingExample,
  TrainingStats,
  Member,
  MemberRole,
} from '../../../services/account.service';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-account-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './account-settings.component.html',
  styleUrl: './account-settings.component.scss',
})
export class AccountSettingsComponent implements OnInit {
  // Tabs
  activeTab: 'account' | 'team' | 'training' | 'export' | 'history' = 'account';

  // Team members
  members: Member[] = [];
  membersLoading = false;
  newMemberEmail = '';
  newMemberRole: MemberRole = 'member';
  addingMember = false;
  readonly roles: MemberRole[] = ['member', 'admin', 'owner'];

  // Accounts
  accounts: Account[] = [];
  activeAccount: Account | null = null;
  loading = false;
  saving = false;
  successMessage = '';
  errorMessage = '';
  showCreateForm = false;

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
  documentsPage = 1;
  documentsPages = 1;
  documentsTotal = 0;

  // Export
  exportLoading = false;
  modelfileResult: { model_name: string; instructions: string } | null = null;

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(private accountService: AccountService, private auth: AuthService) {}

  /** True if the signed-in user can manage the team for the active account. */
  get canManageTeam(): boolean {
    const user = this.auth.currentUser$.value;
    if (!user || !this.activeAccount) return false;
    if (user.is_superadmin) return true;
    const membership = user.memberships.find(m => m.account_id === this.activeAccount!.id);
    return !!membership && (membership.role === 'owner' || membership.role === 'admin');
  }

  ngOnInit(): void {
    this.accountService.activeAccount$.subscribe(a => {
      this.activeAccount = a;
      if (a) this.populateForm(a);
    });
    // Account data comes from the backend over a relative URL that can't be
    // resolved during server-side rendering, so defer the fetch to the browser.
    if (!this.isBrowser) return;
    this.loadAccounts();
  }

  loadAccounts(): void {
    this.loading = true;
    this.accountService.listAccounts().subscribe({
      next: (res) => {
        this.accounts = res.accounts;
        this.loading = false;
        if (this.accounts.length === 0) {
          this.showCreateForm = true;
        }
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
    this.trainingPage = 1;
    this.documentsPage = 1;
    this.loadTrainingStats();
    this.loadTrainingExamples();
    this.loadDocuments();
    this.loadMembers();
  }

  // ── Team management ──

  loadMembers(): void {
    if (!this.activeAccount) return;
    this.membersLoading = true;
    this.accountService.listMembers(this.activeAccount.id).subscribe({
      next: (res) => { this.members = res.members; this.membersLoading = false; },
      error: (err) => { this.errorMessage = err.message; this.membersLoading = false; },
    });
  }

  addMember(): void {
    if (!this.activeAccount || !this.newMemberEmail.trim()) return;
    this.addingMember = true;
    this.errorMessage = '';
    this.accountService.addMember(this.activeAccount.id, this.newMemberEmail.trim(), this.newMemberRole).subscribe({
      next: (res) => {
        this.members = [...this.members, res.member];
        this.newMemberEmail = '';
        this.newMemberRole = 'member';
        this.addingMember = false;
        this.successMessage = `${res.member.email} added to the team`;
      },
      error: (err) => { this.errorMessage = err.message; this.addingMember = false; },
    });
  }

  changeMemberRole(member: Member, role: MemberRole): void {
    if (!this.activeAccount || member.role === role) return;
    this.accountService.updateMemberRole(this.activeAccount.id, member.user_id, role).subscribe({
      next: (res) => { member.role = res.member.role; },
      error: (err) => { this.errorMessage = err.message; this.loadMembers(); },
    });
  }

  removeMember(member: Member): void {
    if (!this.activeAccount) return;
    this.accountService.removeMember(this.activeAccount.id, member.user_id).subscribe({
      next: () => { this.members = this.members.filter(m => m.user_id !== member.user_id); },
      error: (err) => { this.errorMessage = err.message; },
    });
  }

  isSelf(member: Member): boolean {
    return this.auth.currentUser$.value?.id === member.user_id;
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
        this.showCreateForm = false;
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
    this.accountService.listDocuments(this.activeAccount.id, this.documentsPage).subscribe({
      next: (res) => {
        this.documents = res.documents;
        this.documentsTotal = res.total;
        this.documentsPages = res.pages;
        this.documentsLoading = false;
      },
      error: () => this.documentsLoading = false,
    });
  }

  changeDocumentsPage(delta: number): void {
    this.documentsPage = Math.max(1, Math.min(this.documentsPages, this.documentsPage + delta));
    this.loadDocuments();
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
