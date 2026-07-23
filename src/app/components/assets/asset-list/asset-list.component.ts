import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';

import { AssetService, Asset, AssetInput } from '../../../services/asset.service';
import { ProtocolService, Protocol } from '../../../services/protocol.service';
import { AccountService, Account } from '../../../services/account.service';

@Component({
  selector: 'app-asset-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './asset-list.component.html',
  styleUrl: './asset-list.component.scss',
})
export class AssetListComponent implements OnInit {
  account: Account | null = null;
  assets: Asset[] = [];
  protocols: Protocol[] = [];
  loading = false;
  errorMessage = '';
  search = '';

  /** The asset open in the editor drawer. `id === 0` means "new". */
  editing: (AssetInput & { id: number; qr_slug?: string }) | null = null;
  energyInput = '';
  saving = false;

  /** Inline QR SVG for the asset being previewed. */
  qrSvg: SafeHtml | null = null;
  qrAsset: Asset | null = null;

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(
    private assetService: AssetService,
    private protocolService: ProtocolService,
    private accountService: AccountService,
    private sanitizer: DomSanitizer,
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
    this.assetService.listAssets(this.account.id, this.search).subscribe({
      next: (res) => { this.assets = res.assets; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }

  private loadProtocols(): void {
    if (!this.account) return;
    this.protocolService.listProtocols(this.account.id)
      .subscribe({ next: (res) => (this.protocols = res.protocols), error: () => {} });
  }

  // ── Editor ──

  newAsset(): void {
    this.editing = { id: 0, name: '', asset_tag: '', location: '', manufacturer: '',
                     model: '', hazard_class: '', energy_sources: [], protocol_ids: [], notes: '' };
    this.energyInput = '';
  }

  edit(a: Asset): void {
    this.editing = {
      id: a.id, name: a.name, asset_tag: a.asset_tag, location: a.location,
      manufacturer: a.manufacturer, model: a.model, hazard_class: a.hazard_class,
      energy_sources: [...a.energy_sources], protocol_ids: [...a.protocol_ids],
      notes: a.notes, qr_slug: a.qr_slug,
    };
    this.energyInput = '';
  }

  closeEditor(): void {
    this.editing = null;
  }

  addEnergySource(): void {
    const v = this.energyInput.trim();
    if (!v || !this.editing) return;
    this.editing.energy_sources = [...(this.editing.energy_sources || []), v];
    this.energyInput = '';
  }

  removeEnergySource(i: number): void {
    if (!this.editing) return;
    this.editing.energy_sources = (this.editing.energy_sources || []).filter((_, idx) => idx !== i);
  }

  toggleProtocol(id: number): void {
    if (!this.editing) return;
    const ids = this.editing.protocol_ids || [];
    this.editing.protocol_ids = ids.includes(id) ? ids.filter(p => p !== id) : [...ids, id];
  }

  isLinked(id: number): boolean {
    return (this.editing?.protocol_ids || []).includes(id);
  }

  save(): void {
    if (!this.account || !this.editing) return;
    const { id, qr_slug, ...body } = this.editing;
    if (!body.name?.trim()) return;
    this.saving = true;
    const req = id
      ? this.assetService.updateAsset(this.account.id, id, body)
      : this.assetService.createAsset(this.account.id, body);
    req.subscribe({
      next: () => { this.saving = false; this.editing = null; this.load(); },
      error: (err) => { this.saving = false; this.errorMessage = err.message; },
    });
  }

  remove(a: Asset): void {
    if (!this.account || !this.isBrowser) return;
    if (!confirm(`Delete "${a.name}"? Its printed QR tags will stop resolving.`)) return;
    this.assetService.deleteAsset(this.account.id, a.id).subscribe({
      next: () => this.load(),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  // ── QR ──

  showQr(a: Asset): void {
    if (!this.account || !this.isBrowser) return;
    this.qrAsset = a;
    this.qrSvg = null;
    this.assetService.qrSvg(this.account.id, a.id, window.location.origin).subscribe({
      next: (svg) => (this.qrSvg = this.sanitizer.bypassSecurityTrustHtml(svg)),
      error: (err) => (this.errorMessage = err.message),
    });
  }

  closeQr(): void {
    this.qrAsset = null;
    this.qrSvg = null;
  }

  printQr(): void {
    if (this.isBrowser) window.print();
  }

  scanUrl(a: Asset): string {
    return this.isBrowser ? `${window.location.origin}/scan/${a.qr_slug}` : `/scan/${a.qr_slug}`;
  }
}
