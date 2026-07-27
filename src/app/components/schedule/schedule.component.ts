import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { AssignmentService, Assignment, Recurrence } from '../../services/assignment.service';
import { ProtocolService, Protocol } from '../../services/protocol.service';
import { AccountService, Account } from '../../services/account.service';

@Component({
  selector: 'app-schedule',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './schedule.component.html',
  styleUrl: './schedule.component.scss',
})
export class ScheduleComponent implements OnInit {
  account: Account | null = null;
  assignments: Assignment[] = [];
  protocols: Protocol[] = [];
  loading = false;
  errorMessage = '';

  showForm = false;
  form: { protocol_id: number | null; assigned_to: string; due_date: string; recurrence: Recurrence; notes: string } =
    { protocol_id: null, assigned_to: '', due_date: '', recurrence: 'none', notes: '' };
  saving = false;

  readonly recurrences: Recurrence[] = ['none', 'daily', 'weekly', 'monthly'];

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private assignmentService: AssignmentService,
    private protocolService: ProtocolService,
    private accountService: AccountService,
    private router: Router,
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
    this.assignmentService.list(this.account.id).subscribe({
      next: (res) => { this.assignments = res.assignments; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  private loadProtocols(): void {
    if (!this.account) return;
    this.protocolService.listProtocols(this.account.id)
      .subscribe({ next: (res) => (this.protocols = res.protocols), error: () => {} });
  }

  // ── Grouping for the board ──

  get overdue(): Assignment[] {
    return this.assignments.filter(a => a.status === 'pending' && a.is_overdue);
  }
  get upcoming(): Assignment[] {
    return this.assignments.filter(a => a.status === 'pending' && !a.is_overdue);
  }
  get done(): Assignment[] {
    return this.assignments.filter(a => a.status === 'completed');
  }

  // ── Create ──

  openForm(): void {
    this.showForm = true;
    this.form = { protocol_id: null, assigned_to: '', due_date: '', recurrence: 'none', notes: '' };
  }

  save(): void {
    if (!this.account || !this.form.protocol_id) return;
    this.saving = true;
    this.assignmentService.create(this.account.id, {
      protocol_id: this.form.protocol_id,
      assigned_to: this.form.assigned_to,
      due_date: this.form.due_date,
      recurrence: this.form.recurrence,
      notes: this.form.notes,
    }).subscribe({
      next: () => { this.saving = false; this.showForm = false; this.load(); },
      error: (err) => { this.saving = false; this.errorMessage = err.message; },
    });
  }

  // ── Row actions ──

  start(a: Assignment): void {
    if (!this.account) return;
    this.assignmentService.start(this.account.id, a.id).subscribe({
      next: (res) => this.router.navigate(['/protocols', a.protocol_id, 'run'],
                                          { queryParams: { run: res.run.id } }),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  complete(a: Assignment): void {
    if (!this.account) return;
    this.assignmentService.update(this.account.id, a.id, { status: 'completed' }).subscribe({
      next: () => this.load(),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  remove(a: Assignment): void {
    if (!this.account || !this.isBrowser) return;
    if (!confirm(`Remove the assignment for "${a.protocol_title}"?`)) return;
    this.assignmentService.remove(this.account.id, a.id).subscribe({
      next: () => this.load(),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  formatDue(iso: string): string {
    if (!iso) return 'No due date';
    return new Date(iso + 'T00:00:00').toLocaleDateString('en-US',
      { month: 'short', day: 'numeric', year: 'numeric' });
  }
}
