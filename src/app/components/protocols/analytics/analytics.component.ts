import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';

import { ProtocolService, Analytics } from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.scss',
})
export class AnalyticsComponent implements OnInit {
  account: Account | null = null;
  data: Analytics | null = null;
  loading = false;
  errorMessage = '';

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(private protocolService: ProtocolService, private accountService: AccountService) {}

  ngOnInit(): void {
    this.accountService.activeAccount$.subscribe(a => {
      this.account = a;
      if (a && this.isBrowser) this.load();
    });
    if (this.isBrowser) this.accountService.loadSavedAccount();
  }

  private load(): void {
    if (!this.account) return;
    this.loading = true;
    this.protocolService.getAnalytics(this.account.id).subscribe({
      next: (res) => { this.data = res; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  get completionRate(): number {
    if (!this.data || !this.data.totals.runs) return 0;
    return Math.round((this.data.totals.completed_runs / this.data.totals.runs) * 100);
  }

  get maxWeekRuns(): number {
    return Math.max(1, ...(this.data?.runs_by_week.map(w => w.runs) || [1]));
  }

  get outcomeTotal(): number {
    const o = this.data?.outcomes;
    return o ? o.done + o.failed + o.skipped + o.pending : 0;
  }

  outcomePercent(n: number): number {
    return this.outcomeTotal ? (n / this.outcomeTotal) * 100 : 0;
  }

  avgDuration(): string {
    const s = this.data?.avg_run_duration_seconds || 0;
    if (!s) return '—';
    const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
    return h ? `${h}h ${m}m` : `${m}m`;
  }

  shortDate(iso: string): string {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
}
