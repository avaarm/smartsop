import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import {
  ProtocolService, Protocol, ProtocolStep, StepComponent, COMPONENT_LIBRARY, componentMeta,
  ProtocolVersion, VersionDiff, DocBlock,
} from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';
import { AuthService } from '../../../services/auth.service';
import { CommentService, Comment } from '../../../services/comment.service';

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
  body: DocBlock[] = [];
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
    private commentService: CommentService,
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

  /** A document-fidelity protocol: rendered as a real document (tables, headings,
      approval blocks), not a step list. */
  get isDocument(): boolean {
    return this.protocol?.doc_format === 'document';
  }

  ngOnInit(): void {
    // React to param changes too: navigating between versions (e.g. after a
    // restore or new-version) reuses this component instance, so a snapshot
    // read once would leave the page showing the old version.
    this.route.paramMap.subscribe(params => {
      const id = Number(params.get('id'));
      if (id && id !== this.protocolId) {
        this.protocolId = id;
        this.resetView();
        if (this.account && this.isBrowser) this.load();
      }
    });
    this.accountService.activeAccount$.subscribe(a => {
      this.account = a;
      if (a && this.isBrowser && !this.protocol) this.load();
    });
    if (this.isBrowser) this.accountService.loadSavedAccount();
  }

  /** Clear per-protocol view state when switching to a different version. */
  private resetView(): void {
    this.protocol = null;
    this.steps = [];
    this.body = [];
    this.docEditing = false;
    this.showVersions = false;
    this.diff = null;
    this.errorMessage = '';
  }

  private load(): void {
    if (!this.account) return;
    this.loading = true;
    this.protocolService.getProtocol(this.account.id, this.protocolId).subscribe({
      next: (res) => {
        this.protocol = res.protocol;
        this.steps = res.protocol.steps || [];
        this.body = res.protocol.body || [];
        this.loading = false;
        this.loadComments();
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

  copyProtocol(): void {
    if (!this.account) return;
    this.protocolService.copyProtocol(this.account.id, this.protocolId).subscribe({
      next: (res) => this.router.navigate(['/protocols', res.protocol.id]),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  // ── Save as reusable template ──

  showSaveTemplate = false;
  templateCategory = '';
  savingTemplate = false;
  readonly templateCategories = ['CMC', 'Batch Record', 'Validation Protocol', 'Stability Protocol',
                                 'Test Method', 'SOP', 'Cleaning Procedure', 'Deviation Report'];

  openSaveTemplate(): void {
    this.showSaveTemplate = true;
    this.templateCategory = this.protocol?.template_category || '';
  }

  confirmSaveTemplate(): void {
    if (!this.account || !this.templateCategory.trim()) return;
    this.savingTemplate = true;
    this.protocolService.saveAsTemplate(this.account.id, this.protocolId, this.templateCategory.trim())
      .subscribe({
        next: () => { this.savingTemplate = false; this.showSaveTemplate = false;
                      this.flash('Saved to your template library'); },
        error: (err) => { this.savingTemplate = false; this.errorMessage = err.message; },
      });
  }

  exportMenuOpen = false;

  exportProtocol(format: 'json' | 'pdf'): void {
    if (!this.account || !this.isBrowser) return;
    this.exportMenuOpen = false;
    this.protocolService.exportProtocol(this.account.id, this.protocolId, format).subscribe({
      next: (blob) => this.saveBlob(blob, `${this.slug()}-v${this.protocol?.version ?? 1}.${format}`),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  private slug(): string {
    return (this.protocol?.title || 'protocol')
      .replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'protocol';
  }

  private saveBlob(blob: Blob, filename: string): void {
    if (!this.isBrowser) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Document-fidelity view (tables, headings, approval blocks, fill-in) ──

  docEditing = false;

  toggleDocEdit(): void {
    if (this.docEditing) { this.saveBody(); return; }
    this.docEditing = true;
  }

  saveBody(): void {
    if (!this.account) return;
    this.protocolService.updateProtocol(this.account.id, this.protocolId, { body: this.body }).subscribe({
      next: () => { this.docEditing = false; this.flash('Document saved'); },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  downloadOriginal(): void {
    if (!this.account) return;
    this.exportMenuOpen = false;
    this.protocolService.downloadOriginal(this.account.id, this.protocolId).subscribe({
      next: (blob) => this.saveBlob(blob, this.protocol?.original_filename || `${this.slug()}.docx`),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  // Fill-in & export modal
  showFill = false;
  fillVars: string[] = [];
  fillValues: Record<string, string> = {};
  fillBusy = false;

  openFill(): void {
    if (!this.account) return;
    this.exportMenuOpen = false;
    this.showFill = true;
    this.fillVars = [];
    this.fillValues = {};
    this.protocolService.templateVariables(this.account.id, this.protocolId).subscribe({
      next: (res) => {
        this.fillVars = res.variables || [];
        for (const v of this.fillVars) this.fillValues[v] = '';
      },
      error: (err) => (this.errorMessage = err.message),
    });
  }

  exportFilled(): void {
    if (!this.account) return;
    this.fillBusy = true;
    this.protocolService.renderDocx(this.account.id, this.protocolId, this.fillValues).subscribe({
      next: (blob) => {
        this.saveBlob(blob, `${this.slug()}-filled.docx`);
        this.fillBusy = false;
        this.showFill = false;
        this.flash('Document exported');
      },
      error: (err) => { this.fillBusy = false; this.errorMessage = err.message; },
    });
  }

  // ── Version history / diff / rollback ──

  showVersions = false;
  versions: ProtocolVersion[] = [];
  diff: VersionDiff | null = null;
  diffFrom: ProtocolVersion | null = null;
  diffTo: ProtocolVersion | null = null;
  versionBusy = false;

  openVersions(): void {
    if (!this.account) return;
    this.showVersions = true;
    this.diff = null;
    this.protocolService.listVersions(this.account.id, this.protocolId).subscribe({
      next: (res) => (this.versions = res.versions),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  /** Compare a version against the one it supersedes (or explicit from/to). */
  showDiff(to: ProtocolVersion, from?: ProtocolVersion): void {
    if (!this.account) return;
    this.versionBusy = true;
    this.protocolService.diffVersions(this.account.id, this.protocolId, from?.id, to.id).subscribe({
      next: (res) => {
        this.diffFrom = res.from; this.diffTo = res.to; this.diff = res.diff;
        this.versionBusy = false;
      },
      error: (err) => { this.errorMessage = err.message; this.versionBusy = false; },
    });
  }

  hasPredecessor(v: ProtocolVersion): boolean {
    return this.versions.some(other => other.version === v.version - 1);
  }

  predecessor(v: ProtocolVersion): ProtocolVersion | undefined {
    return this.versions.find(other => other.version === v.version - 1);
  }

  restore(v: ProtocolVersion): void {
    if (!this.account) return;
    if (this.isBrowser &&
        !confirm(`Roll back to v${v.version}? This drafts a new version with v${v.version}'s content.`)) return;
    this.versionBusy = true;
    this.protocolService.restoreVersion(this.account.id, this.protocolId, v.id).subscribe({
      next: (res) => this.router.navigate(['/protocols', res.protocol.id]),
      error: (err) => { this.errorMessage = err.message; this.versionBusy = false; },
    });
  }

  changeClass(c: string): string { return 'chg-' + c; }

  // ── Comments & collaboration ──

  showComments = false;
  comments: Comment[] = [];
  commentFilter: 'all' | 'unresolved' | 'pinned' = 'all';
  newCommentTarget: number | 'protocol' = 'protocol';   // step id or 'protocol'
  newCommentBody = '';
  replyingTo: number | null = null;
  replyBody = '';
  commentBusy = false;

  get currentUserId(): number | null {
    return this.auth.currentUser$.value?.id ?? null;
  }

  loadComments(): void {
    if (!this.account) return;
    this.commentService.list(this.account.id, this.protocolId).subscribe({
      next: (res) => (this.comments = res.comments),
      error: () => {},
    });
  }

  openComments(): void {
    this.showComments = true;
    this.commentFilter = 'all';
    this.loadComments();
  }

  /** Top-level comments (not replies) that pass the active filter, pinned first. */
  get visibleThreads(): Comment[] {
    let list = this.comments.filter(c => c.parent_id === null);
    if (this.commentFilter === 'unresolved') list = list.filter(c => !c.resolved);
    if (this.commentFilter === 'pinned') list = list.filter(c => c.is_pinned);
    return [...list].sort((a, b) =>
      (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0) ||
      a.created_at.localeCompare(b.created_at));
  }

  repliesFor(id: number): Comment[] {
    return this.comments.filter(c => c.parent_id === id)
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
  }

  stepLabel(stepId: number | null): string {
    if (stepId === null) return 'General';
    const i = this.steps.findIndex(s => s.id === stepId);
    return i >= 0 ? `Step ${i + 1}` : 'Step';
  }

  stepCommentCount(stepId: number): number {
    return this.comments.filter(c => c.step_id === stepId).length;
  }

  get openCommentCount(): number {
    return this.comments.filter(c => !c.resolved).length;
  }

  addComment(): void {
    if (!this.account || !this.newCommentBody.trim()) return;
    this.commentBusy = true;
    const step_id = this.newCommentTarget === 'protocol' ? null : this.newCommentTarget;
    this.commentService.create(this.account.id, this.protocolId,
      { body: this.newCommentBody.trim(), step_id }).subscribe({
      next: () => { this.newCommentBody = ''; this.commentBusy = false; this.loadComments(); },
      error: (err) => { this.commentBusy = false; this.errorMessage = err.message; },
    });
  }

  startReply(c: Comment): void {
    this.replyingTo = c.id;
    this.replyBody = '';
  }

  sendReply(parent: Comment): void {
    if (!this.account || !this.replyBody.trim()) return;
    this.commentBusy = true;
    this.commentService.create(this.account.id, this.protocolId,
      { body: this.replyBody.trim(), parent_id: parent.id }).subscribe({
      next: () => { this.replyingTo = null; this.replyBody = ''; this.commentBusy = false; this.loadComments(); },
      error: (err) => { this.commentBusy = false; this.errorMessage = err.message; },
    });
  }

  togglePin(c: Comment): void {
    if (!this.account) return;
    this.commentService.update(this.account.id, this.protocolId, c.id, { is_pinned: !c.is_pinned })
      .subscribe({ next: (res) => Object.assign(c, res.comment), error: (err) => (this.errorMessage = err.message) });
  }

  toggleResolve(c: Comment): void {
    if (!this.account) return;
    this.commentService.update(this.account.id, this.protocolId, c.id, { resolved: !c.resolved })
      .subscribe({ next: (res) => Object.assign(c, res.comment), error: (err) => (this.errorMessage = err.message) });
  }

  deleteComment(c: Comment): void {
    if (!this.account) return;
    if (this.isBrowser && !confirm('Delete this comment' + (this.repliesFor(c.id).length ? ' and its replies?' : '?'))) return;
    this.commentService.remove(this.account.id, this.protocolId, c.id).subscribe({
      next: () => this.loadComments(),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  commentStamp(iso: string): string {
    return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
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
      section: step.section,
      title: step.title,
      description: step.description,
      warning: step.warning,
      duration_seconds: step.duration_seconds,
      reagents: step.reagents,
      components: step.components,
      branch: step.branch,
    }).subscribe({
      next: () => this.flash('Saved'),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  // ── Sections & materials (protocols.io-style structure) ──

  /** True when step i begins a new section (first step, or section changed). */
  isSectionStart(i: number): boolean {
    const s = (this.steps[i]?.section || '').trim();
    if (!s) return false;
    const prev = (this.steps[i - 1]?.section || '').trim();
    return i === 0 || s !== prev;
  }

  /** Ordered outline of named sections with their step count and rolled-up time. */
  get outline(): { name: string; index: number; steps: number; seconds: number }[] {
    const out: { name: string; index: number; steps: number; seconds: number }[] = [];
    this.steps.forEach((step, i) => {
      const name = (step.section || '').trim();
      if (!name) return;
      let entry = out.length && out[out.length - 1].name === name && this.contiguous(i, name)
        ? out[out.length - 1] : null;
      if (!entry) { entry = { name, index: i, steps: 0, seconds: 0 }; out.push(entry); }
      entry.steps++;
      entry.seconds += step.duration_seconds || 0;
    });
    return out;
  }

  private contiguous(i: number, name: string): boolean {
    return (this.steps[i - 1]?.section || '').trim() === name;
  }

  /** Aggregated reagents + typed components across every step (deduped). */
  get materials(): { label: string; detail: string; icon: string }[] {
    const seen = new Map<string, { label: string; detail: string; icon: string }>();
    for (const step of this.steps) {
      for (const r of step.reagents || []) {
        if (!r.name?.trim()) continue;
        const key = 'r:' + r.name.toLowerCase();
        if (!seen.has(key)) seen.set(key, { label: r.name, detail: r.amount || '', icon: '🧪' });
      }
      for (const c of step.components || []) {
        const m = this.meta(c.type);
        const val = c.value === true ? 'required' : String(c.value || '');
        const key = 'c:' + c.type + ':' + val.toLowerCase();
        if (!seen.has(key)) seen.set(key, { label: m.label, detail: val, icon: m.icon });
      }
    }
    return [...seen.values()];
  }

  showMaterials = false;

  fmtMins(seconds: number): string {
    if (!seconds) return '';
    const m = Math.round(seconds / 60);
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60), rem = m % 60;
    return rem ? `${h}h ${rem}m` : `${h}h`;
  }

  scrollToStep(i: number): void {
    if (!this.isBrowser) return;
    document.getElementById('step-' + i)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ── Decision / branch ──

  enableBranch(step: ProtocolStep): void {
    step.branch = { question: '', options: [{ label: 'Yes', action: 'continue', target: null }] };
  }

  disableBranch(step: ProtocolStep): void {
    step.branch = null;
    this.saveStep(step);
  }

  addBranchOption(step: ProtocolStep): void {
    step.branch?.options.push({ label: '', action: 'continue', target: null });
  }

  removeBranchOption(step: ProtocolStep, i: number): void {
    step.branch?.options.splice(i, 1);
    this.saveStep(step);
  }

  onBranchActionChange(step: ProtocolStep, opt: { action: string; target: number | null }): void {
    if (opt.action !== 'goto') opt.target = null;
    this.saveStep(step);
  }

  // ── Typed components ──
  readonly componentLibrary = COMPONENT_LIBRARY;
  addingComponentFor: number | null = null;   // step id whose picker is open

  meta(type: string) { return componentMeta(type); }

  toggleComponentPicker(step: ProtocolStep): void {
    this.addingComponentFor = this.addingComponentFor === step.id ? null : step.id;
  }

  addComponent(step: ProtocolStep, type: string): void {
    const m = componentMeta(type);
    step.components = [...(step.components || []), { type, value: m.flag ? true : '' }];
    this.addingComponentFor = null;
    this.saveStep(step);
  }

  removeComponent(step: ProtocolStep, i: number): void {
    step.components.splice(i, 1);
    this.saveStep(step);
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
