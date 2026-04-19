import {
  Component,
  ElementRef,
  Input,
  OnChanges,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';

/**
 * In-browser DOCX renderer. Fetches a .docx URL as a Blob and hands it
 * to ``docx-preview`` which renders close to Word fidelity — including
 * table borders, cell shading, column widths, fonts, and page setup.
 *
 * Used by the Document Builder's side-by-side compare to prove the
 * learned style actually shows up in the generated output.
 */
@Component({
  selector: 'app-docx-preview',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="preview-wrapper">
      <div *ngIf="loading" class="preview-loading">
        <div class="spinner"></div>
        <span>Rendering {{ label }}…</span>
      </div>
      <div *ngIf="error" class="preview-error">{{ error }}</div>
      <div #container class="preview-container"
           [class.has-content]="!loading && !error"></div>
    </div>
  `,
  styles: [`
    :host { display: block; }
    .preview-wrapper {
      position: relative;
      height: 100%;
      min-height: 400px;
      background: hsl(0 0% 97%);
      border-radius: 8px;
      overflow: auto;
    }
    .preview-loading {
      display: flex; align-items: center; justify-content: center;
      gap: 8px; padding: 60px 20px;
      font-size: 13px; color: hsl(240 3.8% 46.1%);
    }
    .preview-error {
      padding: 20px; font-size: 12px;
      color: hsl(0 70% 40%);
      background: hsl(0 70% 97%);
      border-radius: 8px;
      margin: 20px;
    }
    .spinner {
      width: 18px; height: 18px;
      border: 2px solid hsl(240 5.9% 90%);
      border-top-color: hsl(240 5.9% 30%);
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    .preview-container {
      padding: 12px;
      display: none;
    }
    .preview-container.has-content {
      display: block;
    }
    /* docx-preview renders <section.docx_wrapper> inside the container.
       Scale the rendered pages to fit our half-width panel. */
    ::ng-deep .preview-container .docx-wrapper {
      background: transparent !important;
      padding: 0 !important;
    }
    ::ng-deep .preview-container .docx-wrapper > section {
      background: white;
      box-shadow: 0 2px 8px hsl(0 0% 0% / 0.08);
      margin: 0 auto 12px !important;
      transform-origin: top center;
    }
  `],
})
export class DocxPreviewComponent implements OnChanges {
  /** URL to fetch the .docx file from (typically ``/api/download/...``). */
  @Input() url: string | null = null;
  /** Short label shown in the loading state (e.g. "learned style"). */
  @Input() label = 'document';
  /** Scale factor applied to rendered pages (1.0 = Word's natural size). */
  @Input() scale = 0.62;

  @ViewChild('container', { static: true }) container!: ElementRef<HTMLDivElement>;

  loading = false;
  error = '';

  async ngOnChanges(changes: SimpleChanges): Promise<void> {
    if (changes['url'] || changes['scale']) {
      await this.render();
    }
  }

  private async render(): Promise<void> {
    this.error = '';
    if (!this.url) {
      this.container.nativeElement.innerHTML = '';
      return;
    }

    this.loading = true;
    try {
      const resp = await fetch(this.url, { credentials: 'same-origin' });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status} loading ${this.url}`);
      }
      const blob = await resp.blob();

      // Clear previous render
      this.container.nativeElement.innerHTML = '';

      // docx-preview is large (~1.5MB) — lazy-load so it doesn't bloat
      // the initial bundle.
      const dp = await import('docx-preview');
      await dp.renderAsync(blob, this.container.nativeElement, undefined, {
        className: 'docx-wrapper',
        inWrapper: true,
        ignoreWidth: false,
        ignoreHeight: false,
        ignoreFonts: false,
        breakPages: true,
        useBase64URL: false,
        experimental: true,
        trimXmlDeclaration: true,
      });

      // Apply scale so full pages fit comfortably in half the window
      const wrapper = this.container.nativeElement.querySelector(
        '.docx-wrapper'
      ) as HTMLElement | null;
      if (wrapper) {
        wrapper.style.transform = `scale(${this.scale})`;
        wrapper.style.transformOrigin = 'top center';
        // docx-preview sets explicit widths — compensate so the scaled
        // element doesn't leave a huge right-side gap.
        wrapper.style.width = `${100 / this.scale}%`;
      }
    } catch (e) {
      this.error = (e as Error).message || 'Failed to render DOCX';
      // Swallow — preview is best-effort, not worth crashing the page
      console.error('[DocxPreview] render failed:', e);
    } finally {
      this.loading = false;
    }
  }
}
