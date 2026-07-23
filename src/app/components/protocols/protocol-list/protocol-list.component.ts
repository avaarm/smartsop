import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ProtocolService, Protocol, ProtocolTemplate } from '../../../services/protocol.service';
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
  importMode = 'numbered';
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

  // ── Regulatory templates ──

  private loadTemplates(): void {
    if (!this.activeAccount) return;
    this.protocolService.listTemplates(this.activeAccount.id)
      .subscribe({ next: (res) => (this.templates = res.templates), error: () => {} });
  }

  openTemplates(): void {
    this.showTemplates = true;
    this.errorMessage = '';
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

  loadProtocols(): void {
    if (!this.activeAccount) return;
    this.loading = true;
    this.protocolService.listProtocols(this.activeAccount.id).subscribe({
      next: (res) => { this.protocols = res.protocols; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
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

  openImport(): void {
    this.showImport = true;
    this.importTab = 'paste';
    this.importTitle = '';
    this.importText = '';
    this.importMode = 'numbered';
    this.importFile = null;
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

    const done = (res: { protocol: Protocol }) => {
      this.importing = false;
      this.showImport = false;
      this.router.navigate(['/protocols', res.protocol.id]);
    };
    const fail = (err: Error) => { this.errorMessage = err.message; this.importing = false; };

    if (this.importTab === 'file') {
      if (!this.importFile) { this.importing = false; return; }
      const form = new FormData();
      form.append('file', this.importFile);
      form.append('mode', this.importMode);
      if (this.importTitle.trim()) form.append('title', this.importTitle.trim());
      this.protocolService.importFromFile(acc, form).subscribe({ next: done, error: fail });
    } else {
      if (!this.importText.trim()) { this.importing = false; return; }
      this.protocolService.importFromText(acc, {
        title: this.importTitle.trim() || undefined, text: this.importText, mode: this.importMode,
      }).subscribe({ next: done, error: fail });
    }
  }

  formatDate(iso: string | null | undefined): string {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
}
