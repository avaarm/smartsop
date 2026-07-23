import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';

import {
  ProtocolService, Deviation, DeviationSeverity, DeviationStatus,
} from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';

@Component({
  selector: 'app-deviations',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './deviations.component.html',
  styleUrl: './deviations.component.scss',
})
export class DeviationsComponent implements OnInit {
  account: Account | null = null;
  deviations: Deviation[] = [];
  loading = false;
  errorMessage = '';

  statusFilter = 'open';
  severityFilter = '';

  /** The deviation open in the triage drawer. */
  selected: Deviation | null = null;
  saving = false;

  readonly severities: DeviationSeverity[] = ['minor', 'major', 'critical'];
  readonly statuses: DeviationStatus[] = ['open', 'investigating', 'resolved', 'closed'];

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(private protocolService: ProtocolService, private accountService: AccountService) {}

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
    this.protocolService.listDeviations(this.account.id, {
      status: this.statusFilter || undefined,
      severity: this.severityFilter || undefined,
    }).subscribe({
      next: (res) => { this.deviations = res.deviations; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  select(d: Deviation): void {
    // Edit a copy so cancelling the drawer doesn't mutate the row.
    this.selected = { ...d };
  }

  close(): void {
    this.selected = null;
  }

  save(): void {
    if (!this.account || !this.selected) return;
    const d = this.selected;
    this.saving = true;
    this.protocolService.updateDeviation(this.account.id, d.id, {
      status: d.status,
      severity: d.severity,
      corrective_action: d.corrective_action,
      assigned_to: d.assigned_to,
    }).subscribe({
      next: () => { this.saving = false; this.selected = null; this.load(); },
      error: (err) => { this.saving = false; this.errorMessage = err.message; },
    });
  }

  get openCount(): number {
    return this.deviations.filter(d => d.status === 'open' || d.status === 'investigating').length;
  }

  get criticalCount(): number {
    return this.deviations.filter(d => d.severity === 'critical').length;
  }

  formatStamp(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });
  }
}
