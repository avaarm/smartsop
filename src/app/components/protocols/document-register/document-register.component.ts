import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ProtocolService, RegisterGroup, RegisterItem } from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';

@Component({
  selector: 'app-document-register',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './document-register.component.html',
  styleUrl: './document-register.component.scss',
})
export class DocumentRegisterComponent implements OnInit {
  account: Account | null = null;
  batchRecords: RegisterGroup[] = [];
  procedures: RegisterGroup[] = [];
  status: 'effective' | 'approved' | 'all' = 'effective';
  loading = false;
  errorMessage = '';
  collapsed: Record<string, boolean> = {};

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private protocolService: ProtocolService,
    private accountService: AccountService,
    public router: Router,
  ) {}

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
    this.protocolService.documentRegister(this.account.id, this.status).subscribe({
      next: (res) => {
        this.batchRecords = res.batch_records;
        this.procedures = res.procedures;
        this.loading = false;
      },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  setStatus(s: 'effective' | 'approved' | 'all'): void {
    this.status = s;
    this.load();
  }

  get brCount(): number { return this.batchRecords.reduce((n, g) => n + g.items.length, 0); }
  get procCount(): number { return this.procedures.reduce((n, g) => n + g.items.length, 0); }
  get isEmpty(): boolean { return !this.loading && this.brCount === 0 && this.procCount === 0; }

  toggle(key: string): void { this.collapsed[key] = !this.collapsed[key]; }

  /** GMP revision convention: v1 = Rev 00, v2 = Rev 01 … (zero-padded 2 digits). */
  revision(item: RegisterItem): string {
    return String(Math.max(0, item.version - 1)).padStart(2, '0');
  }

  open(item: RegisterItem): void {
    this.router.navigate(['/protocols', item.id]);
  }
}
