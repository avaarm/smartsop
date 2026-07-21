import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { ProtocolService, Protocol, ProtocolStep } from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-protocol-detail',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './protocol-detail.component.html',
  styleUrl: './protocol-detail.component.scss',
})
export class ProtocolDetailComponent implements OnInit {
  account: Account | null = null;
  protocol: Protocol | null = null;
  steps: ProtocolStep[] = [];
  protocolId!: number;

  loading = false;
  errorMessage = '';
  successMessage = '';
  busy = false;

  // Sign modal
  showSign = false;
  signRole: 'reviewer' | 'approver' = 'reviewer';
  signDecision: 'approved' | 'rejected' = 'approved';
  signPassword = '';
  signMeaning = '';
  signComment = '';

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private protocolService: ProtocolService,
    private accountService: AccountService,
    private auth: AuthService,
    private route: ActivatedRoute,
    public router: Router,
  ) {}

  /** Owner/admin of the active account (or superadmin) — may approve/release. */
  get isManager(): boolean {
    const user = this.auth.currentUser$.value;
    if (!user || !this.account) return false;
    if (user.is_superadmin) return true;
    const m = user.memberships.find(x => x.account_id === this.account!.id);
    return !!m && (m.role === 'owner' || m.role === 'admin');
  }

  /** Content is only editable while the document is a draft (or was rejected). */
  get canEdit(): boolean {
    return !!this.protocol && (this.protocol.status === 'draft' || this.protocol.status === 'rejected');
  }

  get isSop(): boolean {
    return !!this.protocol && this.protocol.protocol_type !== 'protocol';
  }

  ngOnInit(): void {
    this.protocolId = Number(this.route.snapshot.paramMap.get('id'));
    this.accountService.activeAccount$.subscribe(a => {
      this.account = a;
      if (a && this.isBrowser && !this.protocol) this.load();
    });
    if (this.isBrowser) this.accountService.loadSavedAccount();
  }

  private load(): void {
    if (!this.account) return;
    this.loading = true;
    this.protocolService.getProtocol(this.account.id, this.protocolId).subscribe({
      next: (res) => {
        this.protocol = res.protocol;
        this.steps = res.protocol.steps || [];
        this.loading = false;
      },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  private flash(msg: string): void {
    this.successMessage = msg;
    setTimeout(() => (this.successMessage = ''), 2000);
  }

  // ── Protocol meta ──

  saveMeta(): void {
    if (!this.account || !this.protocol || !this.protocol.title.trim()) return;
    const p = this.protocol;
    this.protocolService.updateProtocol(this.account.id, this.protocolId, {
      title: p.title, description: p.description, protocol_type: p.protocol_type,
      sop_number: p.sop_number, department: p.department, review_date: p.review_date,
    }).subscribe({
      next: (res) => { this.applyProtocol(res.protocol); this.flash('Saved'); },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  private applyProtocol(p: Protocol): void {
    // Preserve loaded steps (lifecycle responses may not re-send them in order).
    this.protocol = { ...p, steps: this.steps };
  }

  // ── Controlled-document lifecycle ──

  submit(): void {
    if (!this.account) return;
    this.busy = true;
    this.protocolService.submitProtocol(this.account.id, this.protocolId).subscribe({
      next: (res) => { this.applyProtocol(res.protocol); this.busy = false; this.flash('Submitted for review'); },
      error: (err) => { this.errorMessage = err.message; this.busy = false; },
    });
  }

  openSign(role: 'reviewer' | 'approver', decision: 'approved' | 'rejected' = 'approved'): void {
    this.signRole = role;
    this.signDecision = decision;
    this.signPassword = '';
    this.signMeaning = '';
    this.signComment = '';
    this.errorMessage = '';
    this.showSign = true;
  }

  submitSign(): void {
    if (!this.account || !this.signPassword) return;
    this.busy = true;
    this.protocolService.signProtocol(this.account.id, this.protocolId, {
      role: this.signRole, decision: this.signDecision, password: this.signPassword,
      meaning: this.signMeaning || undefined, comment: this.signComment || undefined,
    }).subscribe({
      next: (res) => {
        this.applyProtocol(res.protocol);
        this.showSign = false; this.busy = false;
        this.flash(this.signDecision === 'approved' ? 'Signature applied' : 'Marked rejected');
      },
      error: (err) => { this.errorMessage = err.message; this.busy = false; },
    });
  }

  makeEffective(): void {
    if (!this.account) return;
    this.busy = true;
    this.protocolService.makeEffective(this.account.id, this.protocolId,
      { review_date: this.protocol?.review_date || undefined }).subscribe({
      next: (res) => { this.applyProtocol(res.protocol); this.busy = false; this.flash('Released — now effective'); },
      error: (err) => { this.errorMessage = err.message; this.busy = false; },
    });
  }

  retire(): void {
    if (!this.account) return;
    if (this.isBrowser && !confirm('Retire this SOP? It will no longer be the effective version.')) return;
    this.protocolService.retireProtocol(this.account.id, this.protocolId).subscribe({
      next: (res) => { this.applyProtocol(res.protocol); this.flash('Retired'); },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  createNewVersion(): void {
    if (!this.account) return;
    this.protocolService.newVersion(this.account.id, this.protocolId).subscribe({
      next: (res) => this.router.navigate(['/protocols', res.protocol.id]),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  statusLabel(s: string): string {
    return ({ draft: 'Draft', in_review: 'In review', approved: 'Approved',
              effective: 'Effective', retired: 'Retired', rejected: 'Rejected' } as any)[s] || s;
  }

  typeLabel(t: string): string {
    return ({ protocol: 'Protocol', sop: 'SOP', gmp_sop: 'GMP SOP' } as any)[t] || t;
  }

  formatDate(iso: string | null | undefined): string {
    if (!iso) return '';
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
    });
  }

  deleteProtocol(): void {
    if (!this.account || !this.protocol) return;
    if (this.isBrowser && !confirm('Delete this protocol? This cannot be undone.')) return;
    this.protocolService.deleteProtocol(this.account.id, this.protocolId).subscribe({
      next: () => this.router.navigate(['/protocols']),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  runProtocol(): void {
    this.router.navigate(['/protocols', this.protocolId, 'run']);
  }

  // ── Steps ──

  addStep(): void {
    if (!this.account) return;
    this.protocolService.addStep(this.account.id, this.protocolId, { title: '', description: '' }).subscribe({
      next: (res) => { this.steps = [...this.steps, res.step]; },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  saveStep(step: ProtocolStep): void {
    if (!this.account) return;
    this.protocolService.updateStep(this.account.id, this.protocolId, step.id, {
      title: step.title,
      description: step.description,
      warning: step.warning,
      duration_seconds: step.duration_seconds,
      reagents: step.reagents,
    }).subscribe({
      next: () => this.flash('Saved'),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  deleteStep(step: ProtocolStep): void {
    if (!this.account) return;
    this.protocolService.deleteStep(this.account.id, this.protocolId, step.id).subscribe({
      next: () => { this.steps = this.steps.filter(s => s.id !== step.id); },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  moveStep(index: number, dir: -1 | 1): void {
    const target = index + dir;
    if (!this.account || target < 0 || target >= this.steps.length) return;
    const reordered = [...this.steps];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    this.steps = reordered;
    this.protocolService.reorderSteps(this.account.id, this.protocolId, reordered.map(s => s.id)).subscribe({
      error: (err) => { this.errorMessage = err.message; this.load(); },
    });
  }

  // Duration helpers (UI works in minutes)
  durationMinutes(step: ProtocolStep): number | null {
    return step.duration_seconds != null ? Math.round(step.duration_seconds / 60) : null;
  }

  setDurationMinutes(step: ProtocolStep, value: any): void {
    const mins = value === '' || value == null ? null : Number(value);
    step.duration_seconds = mins == null || isNaN(mins) ? null : Math.max(0, Math.round(mins * 60));
    this.saveStep(step);
  }

  addReagent(step: ProtocolStep): void {
    step.reagents = [...(step.reagents || []), { name: '', amount: '' }];
  }

  removeReagent(step: ProtocolStep, i: number): void {
    step.reagents.splice(i, 1);
    this.saveStep(step);
  }
}
