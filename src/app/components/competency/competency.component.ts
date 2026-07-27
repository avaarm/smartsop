import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { CompetencyService, TrainingRecord } from '../../services/competency.service';
import { ProtocolService, Protocol } from '../../services/protocol.service';
import { AccountService, Account } from '../../services/account.service';

@Component({
  selector: 'app-competency',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './competency.component.html',
  styleUrl: './competency.component.scss',
})
export class CompetencyComponent implements OnInit {
  account: Account | null = null;
  records: TrainingRecord[] = [];
  protocols: Protocol[] = [];
  loading = false;
  errorMessage = '';

  showForm = false;
  form: { protocol_id: number | null; trainee: string; expires_at: string } =
    { protocol_id: null, trainee: '', expires_at: '' };
  saving = false;

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private competencyService: CompetencyService,
    private protocolService: ProtocolService,
    private accountService: AccountService,
  ) {}

  ngOnInit(): void {
    this.accountService.activeAccount$.subscribe(a => {
      this.account = a;
      if (a && this.isBrowser) { this.load(); this.loadProtocols(); }
    });
    if (this.isBrowser) this.accountService.loadSavedAccount();
  }

  load(): void {
    if (!this.account) return;
    this.loading = true;
    this.competencyService.list(this.account.id).subscribe({
      next: (res) => { this.records = res.training; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  private loadProtocols(): void {
    if (!this.account) return;
    this.protocolService.listProtocols(this.account.id)
      .subscribe({ next: (res) => (this.protocols = res.protocols), error: () => {} });
  }

  // ── Groups + KPI ──

  get assigned(): TrainingRecord[] { return this.records.filter(r => r.status === 'assigned'); }
  get current(): TrainingRecord[] { return this.records.filter(r => r.is_current); }
  get expired(): TrainingRecord[] { return this.records.filter(r => r.is_expired); }

  get compliancePercent(): number {
    const relevant = this.records.length;
    if (!relevant) return 100;
    return Math.round((this.current.length / relevant) * 100);
  }

  // ── Actions ──

  openForm(): void {
    this.showForm = true;
    this.form = { protocol_id: null, trainee: '', expires_at: '' };
  }

  save(): void {
    if (!this.account || !this.form.protocol_id || !this.form.trainee.trim()) return;
    this.saving = true;
    this.competencyService.assign(this.account.id, {
      protocol_id: this.form.protocol_id,
      trainee: this.form.trainee.trim(),
      expires_at: this.form.expires_at || undefined,
    }).subscribe({
      next: () => { this.saving = false; this.showForm = false; this.load(); },
      error: (err) => { this.saving = false; this.errorMessage = err.message; },
    });
  }

  acknowledge(r: TrainingRecord): void {
    if (!this.account) return;
    this.competencyService.acknowledge(this.account.id, r.id).subscribe({
      next: () => this.load(),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  remove(r: TrainingRecord): void {
    if (!this.account || !this.isBrowser) return;
    if (!confirm(`Remove the training record for ${r.trainee} on "${r.protocol_title}"?`)) return;
    this.competencyService.remove(this.account.id, r.id).subscribe({
      next: () => this.load(),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  formatDate(iso: string | null): string {
    if (!iso) return '—';
    const s = iso.length <= 10 ? iso + 'T00:00:00' : iso;
    return new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
}
