import { Component, OnInit, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  AccountService,
  Account,
  ProtocolUpload,
  ProtocolKnowledge,
} from '../../../services/account.service';
import {
  TEMPLATES_BY_CATEGORY,
  templateName,
} from './document-templates';

interface QueuedUpload {
  file: File;
  progress: 'queued' | 'uploading' | 'done' | 'error';
  error?: string;
}

@Component({
  selector: 'app-protocols',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './protocols.component.html',
  styleUrl: './protocols.component.scss',
})
export class ProtocolsComponent implements OnInit {
  // Accounts
  accounts: Account[] = [];
  activeAccount: Account | null = null;
  accountsLoading = false;

  // Inline create-account form (shown when no accounts exist)
  showCreateForm = false;
  creating = false;
  newAccountName = '';
  newFacilityName = '';

  // Uploads
  protocolUploads: ProtocolUpload[] = [];
  protocolsLoading = false;
  isDragging = false;
  uploadQueue: QueuedUpload[] = [];

  // Per-item state
  analyzingProtocol: Record<number, boolean> = {};
  expandedKnowledge: Record<number, boolean> = {};
  expandedUpload: Record<number, boolean> = {};

  // Toasts
  successMessage = '';
  errorMessage = '';

  // Document-type picker data (grouped for <optgroup>)
  readonly templateGroups = TEMPLATES_BY_CATEGORY;
  readonly templateName = templateName;

  // Upload id → persistence state for the doc-type dropdown
  savingDocType: Record<number, boolean> = {};

  constructor(private accountService: AccountService) {}

  ngOnInit(): void {
    this.loadAccounts();
    this.accountService.activeAccount$.subscribe((a) => {
      if (a?.id !== this.activeAccount?.id) {
        this.activeAccount = a;
        if (a) this.loadProtocols();
      }
    });
  }

  // ── Accounts ──

  loadAccounts(): void {
    this.accountsLoading = true;
    this.accountService.listAccounts().subscribe({
      next: (res) => {
        this.accounts = res.accounts;
        this.accountsLoading = false;
        if (this.accounts.length === 0) {
          this.showCreateForm = true;
        } else {
          this.accountService.loadSavedAccount();
        }
      },
      error: (err) => {
        this.accountsLoading = false;
        this.errorMessage = err.message;
      },
    });
  }

  selectAccount(account: Account | null): void {
    if (!account) return;
    this.accountService.setActiveAccount(account);
    this.activeAccount = account;
    this.loadProtocols();
  }

  createAccount(): void {
    if (!this.newAccountName.trim()) return;
    this.creating = true;
    this.accountService
      .createAccount({
        name: this.newAccountName.trim(),
        facility_name: this.newFacilityName.trim(),
      })
      .subscribe({
        next: (res) => {
          this.accounts.push(res.account);
          this.selectAccount(res.account);
          this.creating = false;
          this.showCreateForm = false;
          this.newAccountName = '';
          this.newFacilityName = '';
          this.toast('Workspace created — now upload your documents', 'success');
        },
        error: (err) => {
          this.creating = false;
          this.toast(err.message, 'error');
        },
      });
  }

  // ── Protocol upload ──

  loadProtocols(): void {
    if (!this.activeAccount) return;
    this.protocolsLoading = true;
    this.accountService.listProtocols(this.activeAccount.id).subscribe({
      next: (res) => {
        this.protocolUploads = res.uploads;
        this.protocolsLoading = false;
      },
      error: () => (this.protocolsLoading = false),
    });
  }

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files?.length) return;
    this.enqueueFiles(Array.from(input.files));
    input.value = '';
  }

  @HostListener('dragover', ['$event'])
  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = true;
  }

  @HostListener('dragleave', ['$event'])
  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    // Only un-highlight if we're leaving the document, not entering a child
    if ((event.relatedTarget as Node | null) === null) {
      this.isDragging = false;
    }
  }

  @HostListener('drop', ['$event'])
  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
    if (!event.dataTransfer?.files?.length) return;
    this.enqueueFiles(Array.from(event.dataTransfer.files));
  }

  private enqueueFiles(files: File[]): void {
    if (!this.activeAccount) {
      this.toast('Select or create a workspace first', 'error');
      return;
    }
    const accepted = files.filter((f) => {
      const ext = f.name.split('.').pop()?.toLowerCase();
      return ext === 'docx' || ext === 'pdf';
    });
    const rejected = files.length - accepted.length;
    if (rejected > 0) {
      this.toast(
        `${rejected} file(s) skipped — only .docx and .pdf are supported`,
        'error'
      );
    }
    for (const file of accepted) {
      const q: QueuedUpload = { file, progress: 'queued' };
      this.uploadQueue.push(q);
      this.uploadOne(q);
    }
  }

  private uploadOne(q: QueuedUpload): void {
    if (!this.activeAccount) return;
    q.progress = 'uploading';
    this.accountService
      .uploadProtocol(this.activeAccount.id, q.file)
      .subscribe({
        next: (res) => {
          q.progress = 'done';
          this.protocolUploads.unshift(res.upload);
          setTimeout(() => {
            this.uploadQueue = this.uploadQueue.filter((x) => x !== q);
          }, 1500);
        },
        error: (err) => {
          q.progress = 'error';
          q.error = err.message;
        },
      });
  }

  dismissQueued(q: QueuedUpload): void {
    this.uploadQueue = this.uploadQueue.filter((x) => x !== q);
  }

  analyzeAll(): void {
    const pending = this.protocolUploads.filter(
      (u) => u.status === 'parsed' || (u.status === 'error' && !u.knowledge?.length)
    );
    for (const u of pending) this.analyzeUpload(u);
  }

  analyzeUpload(upload: ProtocolUpload): void {
    if (!this.activeAccount) return;
    this.analyzingProtocol[upload.id] = true;
    this.accountService
      .analyzeProtocol(this.activeAccount.id, upload.id)
      .subscribe({
        next: (res) => {
          this.analyzingProtocol[upload.id] = false;
          const idx = this.protocolUploads.findIndex((u) => u.id === upload.id);
          if (idx >= 0) this.protocolUploads[idx] = res.upload;
          this.expandedUpload[upload.id] = true;
          this.toast(`Extracted knowledge from ${upload.filename}`, 'success');
        },
        error: (err) => {
          this.analyzingProtocol[upload.id] = false;
          this.toast(err.message, 'error');
        },
      });
  }

  toggleKnowledgeActive(k: ProtocolKnowledge): void {
    if (!this.activeAccount) return;
    this.accountService
      .updateKnowledge(this.activeAccount.id, k.id, { is_active: !k.is_active })
      .subscribe({
        next: (res) => (k.is_active = res.knowledge.is_active),
      });
  }

  deleteUpload(upload: ProtocolUpload): void {
    if (!this.activeAccount) return;
    if (!confirm(`Remove "${upload.filename}" and its extracted knowledge?`)) return;
    this.accountService
      .deleteProtocol(this.activeAccount.id, upload.id)
      .subscribe({
        next: () => {
          this.protocolUploads = this.protocolUploads.filter((u) => u.id !== upload.id);
          this.toast('Protocol removed', 'success');
        },
      });
  }

  toggleUploadExpand(id: number): void {
    this.expandedUpload[id] = !this.expandedUpload[id];
  }

  toggleKnowledgeExpand(id: number): void {
    this.expandedKnowledge[id] = !this.expandedKnowledge[id];
  }

  // ── Derived stats ──

  get totalKnowledgeItems(): number {
    return this.protocolUploads.reduce(
      (n, u) => n + (u.knowledge?.length ?? 0),
      0
    );
  }

  get activeKnowledgeItems(): number {
    return this.protocolUploads.reduce(
      (n, u) => n + (u.knowledge?.filter((k) => k.is_active).length ?? 0),
      0
    );
  }

  get analyzedCount(): number {
    return this.protocolUploads.filter((u) => u.status === 'complete').length;
  }

  get needsAnalysisCount(): number {
    return this.protocolUploads.filter(
      (u) => u.status === 'parsed' && (u.knowledge?.length ?? 0) === 0
    ).length;
  }

  // ── Labels ──

  getCategoryLabel(category: string): string {
    return {
      terminology: 'Terminology & Phrases',
      procedural_rules: 'Procedural Rules',
      writing_style: 'Writing Style',
      section_structure: 'Section Structure',
      formatting: 'Formatting Patterns',
    }[category] ?? category;
  }

  getCategoryIcon(category: string): string {
    return {
      terminology: 'Aa',
      procedural_rules: '!!',
      writing_style: '~~',
      section_structure: '#',
      formatting: '{}',
    }[category] ?? '?';
  }

  getStatusLabel(status: string): string {
    return {
      uploaded: 'Uploaded',
      parsed: 'Parsed',
      analyzing: 'Analyzing…',
      complete: 'Knowledge extracted',
      error: 'Error',
    }[status] ?? status;
  }

  formatDate(iso: string): string {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  /** Persist a doc-type change (via <select> onChange). */
  onDocTypeChange(upload: ProtocolUpload, newType: string): void {
    if (!this.activeAccount) return;
    const previous = upload.doc_type;
    // Optimistic UI update
    upload.doc_type = newType;
    upload.doc_type_source = 'user';
    this.savingDocType[upload.id] = true;

    this.accountService
      .updateProtocol(this.activeAccount.id, upload.id, { doc_type: newType })
      .subscribe({
        next: (res) => {
          const idx = this.protocolUploads.findIndex((u) => u.id === upload.id);
          if (idx >= 0) this.protocolUploads[idx] = res.upload;
          this.savingDocType[upload.id] = false;
        },
        error: (err) => {
          // Roll back on failure
          upload.doc_type = previous;
          this.savingDocType[upload.id] = false;
          this.toast(err.message, 'error');
        },
      });
  }

  private toast(msg: string, kind: 'success' | 'error'): void {
    if (kind === 'success') {
      this.successMessage = msg;
      setTimeout(() => (this.successMessage = ''), 3500);
    } else {
      this.errorMessage = msg;
      setTimeout(() => (this.errorMessage = ''), 5000);
    }
  }
}
