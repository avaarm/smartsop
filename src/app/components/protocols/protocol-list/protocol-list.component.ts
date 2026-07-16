import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ProtocolService, Protocol } from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';

@Component({
  selector: 'app-protocol-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './protocol-list.component.html',
  styleUrl: './protocol-list.component.scss',
})
export class ProtocolListComponent implements OnInit {
  activeAccount: Account | null = null;
  protocols: Protocol[] = [];
  loading = false;
  creating = false;
  errorMessage = '';

  showNewForm = false;
  newTitle = '';
  newDescription = '';

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private protocolService: ProtocolService,
    private accountService: AccountService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.accountService.activeAccount$.subscribe(a => {
      this.activeAccount = a;
      if (a && this.isBrowser) this.loadProtocols();
    });
    if (this.isBrowser) this.accountService.loadSavedAccount();
  }

  loadProtocols(): void {
    if (!this.activeAccount) return;
    this.loading = true;
    this.protocolService.listProtocols(this.activeAccount.id).subscribe({
      next: (res) => { this.protocols = res.protocols; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  createProtocol(): void {
    if (!this.activeAccount || !this.newTitle.trim()) return;
    this.creating = true;
    this.protocolService.createProtocol(this.activeAccount.id, {
      title: this.newTitle.trim(),
      description: this.newDescription.trim(),
    }).subscribe({
      next: (res) => {
        this.creating = false;
        this.router.navigate(['/protocols', res.protocol.id]);
      },
      error: (err) => { this.errorMessage = err.message; this.creating = false; },
    });
  }

  open(p: Protocol): void {
    this.router.navigate(['/protocols', p.id]);
  }

  formatDate(iso: string | null | undefined): string {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
}
