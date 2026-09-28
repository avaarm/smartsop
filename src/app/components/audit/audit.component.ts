import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { AuditService, AuditEvent } from '../../services/audit.service';
import { AccountService, Account } from '../../services/account.service';

@Component({
  selector: 'app-audit',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './audit.component.html',
  styleUrl: './audit.component.scss',
})
export class AuditComponent implements OnInit {
  account: Account | null = null;
  events: AuditEvent[] = [];
  loading = false;
  errorMessage = '';
  actionFilter = '';

  readonly actions = [
    { value: '', label: 'All events' },
    { value: 'protocol.created', label: 'Protocol created' },
    { value: 'protocol.submitted', label: 'Submitted for review' },
    { value: 'protocol.signed', label: 'E-signature' },
    { value: 'protocol.made_effective', label: 'Made effective' },
    { value: 'protocol.retired', label: 'Retired' },
    { value: 'protocol.new_version', label: 'New version' },
    { value: 'run.finished', label: 'Run finished' },
    { value: 'deviation.created', label: 'Deviation flagged' },
    { value: 'deviation.resolved', label: 'Deviation resolved' },
    { value: 'competency.acknowledged', label: 'Training acknowledged' },
  ];

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(private auditService: AuditService, private accountService: AccountService) {}

  ngOnInit(): void {
    this.accountService.activeAccount$.subscribe(a => {
      this.account = a;
      if (a && this.isBrowser) this.load();
    });
    if (this.isBrowser) this.accountService.loadSavedAccount();
  }

  load(): void {
    if (!this.account) return;
    this.loading = true;
    this.auditService.list(this.account.id, this.actionFilter).subscribe({
      next: (res) => { this.events = res.events; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  exportCsv(): void {
    if (!this.account || !this.isBrowser) return;
    this.auditService.exportCsv(this.account.id).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'audit-trail.csv';
        a.click();
        URL.revokeObjectURL(url);
      },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  /** Category of an action, for the timeline dot color. */
  kind(action: string): string {
    if (action.startsWith('deviation')) return 'deviation';
    if (action === 'protocol.signed' || action === 'protocol.made_effective') return 'sign';
    if (action === 'competency.acknowledged') return 'training';
    if (action === 'run.finished') return 'run';
    return 'default';
  }

  label(action: string): string {
    return this.actions.find(a => a.value === action)?.label || action;
  }

  stamp(iso: string): string {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
    });
  }
}
