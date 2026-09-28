import { Component, OnInit, OnDestroy, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import {
  ProtocolService, ProtocolRun, ProtocolRunStep, RunStepStatus, BranchOption, componentMeta,
  Deviation, DeviationSeverity,
} from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';
import { OfflineService } from '../../../services/offline.service';

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

  // Offline state (surfaced in the run banner).
  online = true;
  pendingSync = 0;
  justSynced = 0;

  /** Per-run-step countdown state: remaining seconds, keyed by run step id. */
  remaining: Record<number, number> = {};
  private ticker: any = null;

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private protocolService: ProtocolService,
    private accountService: AccountService,
    private offline: OfflineService,
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

      this.offline.pending$.subscribe(n => (this.pendingSync = n));
      this.offline.online$.subscribe(isOnline => {
        const cameBack = isOnline && !this.online;
        this.online = isOnline;
        if (cameBack) this.syncNow();
      });
      this.offline.synced$.subscribe(n => {
        if (n > 0) {
          this.justSynced = n;
          setTimeout(() => (this.justSynced = 0), 4000);
        }
      });
    }
  }

  /** Flush the offline queue, then reconcile the run against the server. */
  private syncNow(): void {
    this.offline.flush().then(() => {
      if (this.account && this.run) {
        this.protocolService.getRun(this.account.id, this.run.id).subscribe({
          next: (res) => { this.applyRun(res.run); this.offline.cacheRun(res.run); },
          error: () => {},
        });
      }
    });
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
      // Offline: serve the cached copy so the run stays usable with no network.
      if (!this.offline.isOnline) {
        const cached = this.offline.getCachedRun(runId);
        if (cached) { this.applyRun(cached); return; }
      }
      this.protocolService.getRun(this.account.id, runId).subscribe({
        next: (res) => { this.applyRun(res.run); this.offline.cacheRun(res.run); this.syncNow(); },
        error: (err) => {
          const cached = this.offline.getCachedRun(runId);
          if (cached) this.applyRun(cached);
          else { this.errorMessage = err.message; this.loading = false; }
        },
      });
      return;
    }
    this.protocolService.startRun(this.account.id, this.protocolId).subscribe({
      next: (res) => {
        this.applyRun(res.run);
        this.offline.cacheRun(res.run);
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

  /** Apply a step change locally + cache, so offline edits persist and render. */
  private applyLocalStep(step: ProtocolRunStep, patch: Partial<ProtocolRunStep>): void {
    Object.assign(step, patch);
    this.refreshProgress();
    if (this.run) this.offline.cacheRun({ ...this.run, steps: this.steps });
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

  // ── Completion gates (verification photo / second signature) ──

  gateStepId: number | null = null;
  gateForm: { verification: string; witness_email: string; witness_password: string } =
    { verification: '', witness_email: '', witness_password: '' };
  gateBusy = false;

  private hasFlag(step: ProtocolRunStep, type: string): boolean {
    return (step.components || []).some(c => c.type === type && c.value === true);
  }
  needsPhoto(step: ProtocolRunStep): boolean { return this.hasFlag(step, 'verification_photo'); }
  needsSignature(step: ProtocolRunStep): boolean { return this.hasFlag(step, 'second_signature'); }
  hasGate(step: ProtocolRunStep): boolean { return this.needsPhoto(step) || this.needsSignature(step); }

  /** True once every required gate on the step is satisfied. */
  gateSatisfied(step: ProtocolRunStep): boolean {
    if (this.needsPhoto(step) && !(step.verification || '').trim()) return false;
    if (this.needsSignature(step) && !step.witnessed_by) return false;
    return true;
  }

  openGate(step: ProtocolRunStep): void {
    this.gateStepId = step.id;
    this.gateForm = { verification: step.verification || '', witness_email: '', witness_password: '' };
    this.errorMessage = '';
  }
  closeGate(): void { this.gateStepId = null; }

  submitGate(step: ProtocolRunStep): void {
    if (!this.account || !this.run) return;
    this.gateBusy = true;
    this.protocolService.setRunStep(this.account.id, this.run.id, step.id, {
      status: 'done',
      verification: this.needsPhoto(step) ? this.gateForm.verification : undefined,
      witness_email: this.needsSignature(step) ? this.gateForm.witness_email : undefined,
      witness_password: this.needsSignature(step) ? this.gateForm.witness_password : undefined,
    }).subscribe({
      next: (res) => {
        Object.assign(step, res.step);
        this.refreshProgress();
        this.gateBusy = false;
        this.gateStepId = null;
      },
      error: (err) => { this.gateBusy = false; this.errorMessage = err.message; },
    });
  }

  // ── Outcomes ──

  setStatus(step: ProtocolRunStep, status: RunStepStatus): void {
    if (!this.account || !this.run) return;
    // Completing a gated step opens the gate form instead of marking Done directly.
    if (status === 'done' && step.status !== 'done' && this.hasGate(step) && !this.gateSatisfied(step)) {
      // Peer sign-off / verification needs the server; block it while offline.
      if (!this.online) {
        this.errorMessage = 'This step needs a connection to capture its verification / sign-off.';
        return;
      }
      this.openGate(step);
      return;
    }
    const next: RunStepStatus = step.status === status ? 'pending' : status;

    // Offline: apply locally and queue the change for replay on reconnect.
    if (!this.online) {
      const stamp = next === 'pending'
        ? { status: next, completed_by: '', completed_at: null }
        : { status: next, completed_by: 'you (offline)', completed_at: new Date().toISOString() };
      this.applyLocalStep(step, stamp as Partial<ProtocolRunStep>);
      this.offline.enqueue(this.account.id, this.run.id, step.id, { status: next });
      return;
    }

    this.protocolService.setRunStep(this.account.id, this.run.id, step.id, { status: next }).subscribe({
      next: (res) => { Object.assign(step, res.step); this.refreshProgress();
                       if (this.run) this.offline.cacheRun({ ...this.run, steps: this.steps }); },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  saveNote(step: ProtocolRunStep): void {
    if (!this.account || !this.run) return;
    if (!this.online) {
      this.applyLocalStep(step, {});
      this.offline.enqueue(this.account.id, this.run.id, step.id, { note: step.note });
      return;
    }
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
