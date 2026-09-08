import { Component, OnInit, OnDestroy, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import {
  ProtocolService, ProtocolRun, ProtocolRunStep, RunStepStatus, BranchOption, componentMeta,
  Deviation, DeviationSeverity,
} from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';

@Component({
  selector: 'app-protocol-run',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './protocol-run.component.html',
  styleUrl: './protocol-run.component.scss',
})
export class ProtocolRunComponent implements OnInit, OnDestroy {
  account: Account | null = null;
  run: ProtocolRun | null = null;
  steps: ProtocolRunStep[] = [];
  protocolId!: number;

  loading = false;
  errorMessage = '';

  /** Per-run-step countdown state: remaining seconds, keyed by run step id. */
  remaining: Record<number, number> = {};
  private ticker: any = null;

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private protocolService: ProtocolService,
    private accountService: AccountService,
    private route: ActivatedRoute,
    public router: Router,
  ) {}

  ngOnInit(): void {
    this.protocolId = Number(this.route.snapshot.paramMap.get('id'));
    this.accountService.activeAccount$.subscribe(a => {
      this.account = a;
      if (a && this.isBrowser && !this.run) this.startOrResume();
    });
    if (this.isBrowser) {
      this.accountService.loadSavedAccount();
      this.ticker = setInterval(() => this.tick(), 1000);
    }
  }

  ngOnDestroy(): void {
    if (this.ticker) clearInterval(this.ticker);
  }

  /** Resume the newest in-progress run for this protocol, else start a new one. */
  private startOrResume(): void {
    if (!this.account) return;
    this.loading = true;
    const runId = Number(this.route.snapshot.queryParamMap.get('run')) || null;
    if (runId) {
      this.protocolService.getRun(this.account.id, runId).subscribe({
        next: (res) => this.applyRun(res.run),
        error: (err) => { this.errorMessage = err.message; this.loading = false; },
      });
      return;
    }
    this.protocolService.startRun(this.account.id, this.protocolId).subscribe({
      next: (res) => {
        this.applyRun(res.run);
        this.router.navigate([], {
          relativeTo: this.route, queryParams: { run: res.run.id }, replaceUrl: true,
        });
      },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  private applyRun(run: ProtocolRun): void {
    this.run = run;
    this.steps = run.steps || [];
    this.loading = false;
    this.loadDeviations();
  }

  // ── Deviations / corrective actions ──
  deviations: Deviation[] = [];
  deviationStep: ProtocolRunStep | null = null;
  deviationForm: { title: string; description: string; severity: DeviationSeverity } =
    { title: '', description: '', severity: 'minor' };
  flagBusy = false;

  private loadDeviations(): void {
    if (!this.account || !this.run) return;
    this.protocolService.listDeviations(this.account.id, { run_id: this.run.id })
      .subscribe({ next: (res) => (this.deviations = res.deviations), error: () => {} });
  }

  deviationsForStep(step: ProtocolRunStep): Deviation[] {
    return this.deviations.filter(d => d.run_step_id === step.id);
  }

  /** Open the flag-deviation modal, defaulting the title to the step name. */
  openDeviation(step: ProtocolRunStep): void {
    this.deviationStep = step;
    this.deviationForm = { title: '', description: '', severity: 'minor' };
  }

  closeDeviation(): void {
    this.deviationStep = null;
  }

  submitDeviation(): void {
    if (!this.account || !this.run || !this.deviationStep) return;
    const title = this.deviationForm.title.trim();
    if (!title) return;
    this.flagBusy = true;
    this.protocolService.flagDeviation(this.account.id, {
      title,
      description: this.deviationForm.description,
      severity: this.deviationForm.severity,
      run_id: this.run.id,
      run_step_id: this.deviationStep.id,
    }).subscribe({
      next: (res) => {
        this.deviations = [res.deviation, ...this.deviations];
        this.flagBusy = false;
        this.deviationStep = null;
      },
      error: (err) => { this.flagBusy = false; this.errorMessage = err.message; },
    });
  }

  // ── Timers ──

  private tick(): void {
    for (const id of Object.keys(this.remaining)) {
      const key = Number(id);
      if (this.remaining[key] > 0) this.remaining[key]--;
    }
  }

  startTimer(step: ProtocolRunStep): void {
    if (step.duration_seconds != null) this.remaining[step.id] = step.duration_seconds;
  }

  resetTimer(step: ProtocolRunStep): void {
    if (step.duration_seconds != null) this.remaining[step.id] = step.duration_seconds;
  }

  timerRunning(step: ProtocolRunStep): boolean {
    return this.remaining[step.id] != null;
  }

  meta(type: string) { return componentMeta(type); }

  showMaterials = false;

  /** Aggregated reagents + typed components across the run's steps (deduped). */
  get materials(): { label: string; detail: string; icon: string }[] {
    const seen = new Map<string, { label: string; detail: string; icon: string }>();
    for (const step of this.steps) {
      for (const r of step.reagents || []) {
        if (!r.name?.trim()) continue;
        const key = 'r:' + r.name.toLowerCase();
        if (!seen.has(key)) seen.set(key, { label: r.name, detail: r.amount || '', icon: '🧪' });
      }
      for (const c of step.components || []) {
        const m = componentMeta(c.type);
        const val = c.value === true ? 'required' : String(c.value || '');
        const key = 'c:' + c.type + ':' + val.toLowerCase();
        if (!seen.has(key)) seen.set(key, { label: m.label, detail: val, icon: m.icon });
      }
    }
    return [...seen.values()];
  }

  // ── Branch decisions ──
  halted: { question: string; label: string } | null = null;
  highlightIndex: number | null = null;

  chooseBranch(step: ProtocolRunStep, option: BranchOption): void {
    const note = `Decision: ${step.branch?.question} → ${option.label}`;
    step.note = step.note ? `${step.note}\n${note}` : note;
    this.saveNote(step);

    if (option.action === 'halt') {
      this.halted = { question: step.branch?.question || '', label: option.label };
      if (this.isBrowser) window.scrollTo({ top: 0, behavior: 'smooth' });
    } else if (option.action === 'goto' && option.target) {
      this.scrollToStep(option.target - 1);
    }
  }

  private scrollToStep(index: number): void {
    if (!this.isBrowser || index < 0 || index >= this.steps.length) return;
    document.getElementById('run-step-' + index)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    this.highlightIndex = index;
    setTimeout(() => (this.highlightIndex = null), 2200);
  }

  formatClock(seconds: number | null | undefined): string {
    if (seconds == null) return '';
    const s = Math.max(0, seconds);
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${pad(h)}:${pad(m)}:${pad(sec)}`;
  }

  // ── Outcomes ──

  setStatus(step: ProtocolRunStep, status: RunStepStatus): void {
    if (!this.account || !this.run) return;
    const next = step.status === status ? 'pending' : status;
    this.protocolService.setRunStep(this.account.id, this.run.id, step.id, { status: next }).subscribe({
      next: (res) => {
        Object.assign(step, res.step);
        this.refreshProgress();
      },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  saveNote(step: ProtocolRunStep): void {
    if (!this.account || !this.run) return;
    this.protocolService.setRunStep(this.account.id, this.run.id, step.id, { note: step.note })
      .subscribe({ error: (err) => (this.errorMessage = err.message) });
  }

  saveExperimentId(): void {
    if (!this.account || !this.run) return;
    this.protocolService.updateRun(this.account.id, this.run.id, { experiment_id: this.run.experiment_id })
      .subscribe({ error: (err) => (this.errorMessage = err.message) });
  }

  private refreshProgress(): void {
    if (this.run) {
      this.run.completed_steps = this.steps.filter(s => s.status !== 'pending').length;
    }
  }

  finish(): void {
    if (!this.account || !this.run) return;
    this.protocolService.finishRun(this.account.id, this.run.id).subscribe({
      next: (res) => { this.run = { ...res.run, steps: this.steps }; },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  // ── View helpers ──

  get completedCount(): number {
    return this.steps.filter(s => s.status !== 'pending').length;
  }

  get progressPercent(): number {
    return this.steps.length ? (this.completedCount / this.steps.length) * 100 : 0;
  }

  /** Sum of remaining (not-yet-actioned) step durations — protocols.io's "Suggested Run Time". */
  get suggestedRunTime(): string {
    const secs = this.steps
      .filter(s => s.status === 'pending')
      .reduce((acc, s) => acc + (s.duration_seconds || 0), 0);
    if (!secs) return '—';
    const h = Math.floor(secs / 3600), m = Math.round((secs % 3600) / 60);
    return h ? `${h}h ${m}m` : `${m}m`;
  }

  formatStamp(iso: string | null): string {
    if (!iso) return '';
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });
  }
}
