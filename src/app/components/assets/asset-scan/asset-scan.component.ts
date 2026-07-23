import { Component, OnInit, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { AssetService, Asset } from '../../../services/asset.service';

/**
 * Landing page for a scanned QR tag (/scan/:slug).
 *
 * This is the field workflow the QR feature exists for: point a phone at the
 * tag on a machine and land on that machine's hazards and its SOPs, ready to
 * run — not on a generic document.
 */
@Component({
  selector: 'app-asset-scan',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './asset-scan.component.html',
  styleUrl: './asset-scan.component.scss',
})
export class AssetScanComponent implements OnInit {
  asset: Asset | null = null;
  loading = true;
  errorMessage = '';

  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  constructor(private assetService: AssetService, private route: ActivatedRoute) {}

  ngOnInit(): void {
    if (!this.isBrowser) return;
    const slug = this.route.snapshot.paramMap.get('slug') || '';
    this.assetService.scan(slug).subscribe({
      next: (res) => { this.asset = res.asset; this.loading = false; },
      error: (err) => { this.errorMessage = err.message; this.loading = false; },
    });
  }
}
