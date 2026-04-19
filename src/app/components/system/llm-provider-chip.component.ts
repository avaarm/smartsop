import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

interface SystemStatus {
  success: boolean;
  ollama: { reachable: boolean; base_url: string; model: string };
  fallback: {
    name: string;
    model: string;
    healthy: boolean;
    has_api_key: boolean;
  } | null;
  active_provider: 'ollama' | 'openai' | 'anthropic' | 'none';
  config: {
    provider: '' | 'ollama' | 'openai' | 'anthropic';
    has_openai_key: boolean;
    openai_model: string;
    has_anthropic_key: boolean;
    anthropic_model: string;
    config_path: string;
  };
}

interface SaveConfigResponse {
  success: boolean;
  config: {
    provider: string;
    has_openai_key: boolean;
    openai_model: string;
    has_anthropic_key: boolean;
    anthropic_model: string;
  };
}

/**
 * Sidebar-footer chip showing which LLM provider is active, with a
 * click-to-configure modal. Also auto-opens the modal once on first
 * run when no provider is available — that's the Ollama onboarding
 * entry point.
 */
@Component({
  selector: 'app-llm-provider-chip',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <button class="chip" [class.chip-good]="active === 'ollama'"
            [class.chip-warn]="active === 'openai' || active === 'anthropic'"
            [class.chip-err]="active === 'none'"
            (click)="openModal()"
            [title]="chipTooltip()">
      <span class="dot"></span>
      <span class="chip-label">{{ chipLabel() }}</span>
    </button>

    <div *ngIf="showModal" class="backdrop" (click)="closeModal()"></div>
    <div *ngIf="showModal" class="modal" role="dialog" aria-modal="true">
      <header class="modal-header">
        <h3>AI provider</h3>
        <button class="icon-btn" (click)="closeModal()" aria-label="Close">×</button>
      </header>

      <p class="lead">
        SmartSOP uses a local-first AI to keep your documents private.
        Ollama is the default; pick a cloud provider if you can't run
        Ollama on this machine.
      </p>

      <div class="tabs">
        <button [class.active]="selectedProvider === 'ollama'"
                (click)="selectedProvider = 'ollama'">Ollama (local)</button>
        <button [class.active]="selectedProvider === 'anthropic'"
                (click)="selectedProvider = 'anthropic'">Anthropic</button>
        <button [class.active]="selectedProvider === 'openai'"
                (click)="selectedProvider = 'openai'">OpenAI</button>
      </div>

      <!-- Ollama panel -->
      <div *ngIf="selectedProvider === 'ollama'" class="panel">
        <div class="status-row">
          <span class="status-dot" [class.ok]="status?.ollama?.reachable"></span>
          <span *ngIf="status?.ollama?.reachable">
            Ollama is running at {{ status?.ollama?.base_url }}
          </span>
          <span *ngIf="!status?.ollama?.reachable">
            Ollama is not reachable at {{ status?.ollama?.base_url || 'localhost:11434' }}
          </span>
        </div>
        <ol *ngIf="!status?.ollama?.reachable" class="steps">
          <li>
            Download Ollama from
            <a href="https://ollama.com" target="_blank" rel="noopener">ollama.com</a>
            and install it.
          </li>
          <li>Open Ollama and pull the default model: <code>ollama pull llama3</code></li>
          <li>Come back here and click Retry.</li>
        </ol>
        <button class="btn primary" (click)="refresh()">Retry connection</button>
      </div>

      <!-- Anthropic panel -->
      <div *ngIf="selectedProvider === 'anthropic'" class="panel">
        <p class="panel-note">
          Uses Claude via Anthropic's API. Your prompts leave this machine.
        </p>
        <label>API key</label>
        <input type="password" [(ngModel)]="anthropicKey"
               [placeholder]="status?.config?.has_anthropic_key ? '•••• saved ••••' : 'sk-ant-…'" />
        <label>Model <span class="hint">(optional)</span></label>
        <input type="text" [(ngModel)]="anthropicModel"
               [placeholder]="status?.config?.anthropic_model || 'claude-3-5-haiku-20241022'" />
        <button class="btn primary"
                (click)="save('anthropic')"
                [disabled]="saving">
          {{ saving ? 'Saving…' : 'Use Anthropic' }}
        </button>
      </div>

      <!-- OpenAI panel -->
      <div *ngIf="selectedProvider === 'openai'" class="panel">
        <p class="panel-note">
          Uses GPT-4o-mini by default. Your prompts leave this machine.
        </p>
        <label>API key</label>
        <input type="password" [(ngModel)]="openaiKey"
               [placeholder]="status?.config?.has_openai_key ? '•••• saved ••••' : 'sk-…'" />
        <label>Model <span class="hint">(optional)</span></label>
        <input type="text" [(ngModel)]="openaiModel"
               [placeholder]="status?.config?.openai_model || 'gpt-4o-mini'" />
        <button class="btn primary"
                (click)="save('openai')"
                [disabled]="saving">
          {{ saving ? 'Saving…' : 'Use OpenAI' }}
        </button>
      </div>

      <footer class="modal-footer">
        <span class="config-path">Config: {{ status?.config?.config_path }}</span>
      </footer>
    </div>
  `,
  styles: [`
    .chip {
      display: flex; align-items: center; gap: 6px;
      padding: 4px 10px; border-radius: 100px;
      background: hsl(0 0% 11%); border: 1px solid hsl(0 0% 18%);
      color: hsl(0 0% 85%); font-size: 11px; font-weight: 500;
      font-family: inherit; cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
    }
    .chip:hover { background: hsl(0 0% 14%); border-color: hsl(0 0% 22%); }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: hsl(0 0% 40%); }
    .chip-good .dot { background: hsl(143 70% 50%); box-shadow: 0 0 0 3px hsl(143 70% 50% / 0.15); }
    .chip-warn .dot { background: hsl(221 83% 58%); }
    .chip-err .dot { background: hsl(0 70% 55%); animation: pulse 1.8s infinite; }
    @keyframes pulse { 50% { box-shadow: 0 0 0 6px hsl(0 70% 55% / 0); } }
    .chip-label { white-space: nowrap; }

    .backdrop {
      position: fixed; inset: 0;
      background: hsl(0 0% 0% / 0.45);
      z-index: 100;
    }
    .modal {
      position: fixed; top: 10vh; left: 50%;
      transform: translateX(-50%);
      width: min(480px, 92vw);
      max-height: 80vh; overflow-y: auto;
      background: hsl(0 0% 100%); color: hsl(240 5.9% 10%);
      border-radius: 12px; box-shadow: 0 20px 40px -10px hsl(0 0% 0% / 0.3);
      z-index: 101; padding: 20px 24px;
      font-family: inherit;
    }
    .modal-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 6px;
    }
    .modal-header h3 { margin: 0; font-size: 16px; font-weight: 600; }
    .icon-btn {
      background: none; border: none; font-size: 22px; color: hsl(240 3.8% 46.1%);
      cursor: pointer; padding: 0 4px; line-height: 1;
    }
    .icon-btn:hover { color: hsl(240 5.9% 10%); }
    .lead { font-size: 12px; color: hsl(240 3.8% 46.1%); margin: 0 0 16px; line-height: 1.55; }

    .tabs {
      display: flex; gap: 2px; margin-bottom: 16px;
      border-bottom: 1px solid hsl(240 5.9% 90%);
    }
    .tabs button {
      padding: 8px 14px; background: none; border: none; font-family: inherit;
      font-size: 12px; font-weight: 500; color: hsl(240 3.8% 46.1%);
      border-bottom: 2px solid transparent; cursor: pointer;
    }
    .tabs button.active {
      color: hsl(240 5.9% 10%); border-bottom-color: hsl(240 5.9% 10%);
    }

    .panel { display: flex; flex-direction: column; gap: 10px; }
    .panel label {
      font-size: 11px; font-weight: 600; color: hsl(240 5.9% 10%); margin-top: 6px;
    }
    .panel .hint { color: hsl(240 3.8% 46.1%); font-weight: 400; }
    .panel input {
      padding: 8px 10px; border: 1px solid hsl(240 5.9% 90%); border-radius: 6px;
      font-family: inherit; font-size: 12px;
    }
    .panel input:focus {
      outline: none; border-color: hsl(240 5.9% 30%);
      box-shadow: 0 0 0 3px hsl(240 5.9% 90% / 0.6);
    }
    .panel-note {
      font-size: 11px; color: hsl(240 3.8% 46.1%); margin: 0 0 4px; line-height: 1.5;
    }

    .status-row {
      display: flex; align-items: center; gap: 8px;
      padding: 10px 12px; background: hsl(240 4.8% 95.9%); border-radius: 6px;
      font-size: 12px;
    }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: hsl(0 70% 55%); flex-shrink: 0; }
    .status-dot.ok { background: hsl(143 70% 45%); }

    .steps { padding-left: 20px; margin: 10px 0; font-size: 12px; line-height: 1.6; }
    .steps code {
      font-family: 'SF Mono', Menlo, monospace;
      font-size: 11px; padding: 1px 5px;
      background: hsl(240 4.8% 94%); border-radius: 3px;
    }
    .steps a { color: hsl(221 83% 45%); text-decoration: none; }
    .steps a:hover { text-decoration: underline; }

    .btn {
      padding: 8px 14px; border-radius: 6px; font-family: inherit;
      font-size: 12px; font-weight: 500; cursor: pointer;
      border: 1px solid transparent; align-self: flex-start;
    }
    .btn.primary { background: hsl(240 5.9% 10%); color: white; }
    .btn.primary:hover:not(:disabled) { opacity: 0.9; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }

    .modal-footer {
      margin-top: 16px; padding-top: 12px;
      border-top: 1px solid hsl(240 5.9% 90%);
    }
    .config-path {
      font-size: 10px; color: hsl(240 3.8% 46.1%);
      font-family: 'SF Mono', Menlo, monospace;
    }
  `],
})
export class LlmProviderChipComponent implements OnInit {
  status: SystemStatus | null = null;
  showModal = false;
  saving = false;

  selectedProvider: 'ollama' | 'openai' | 'anthropic' = 'ollama';

  openaiKey = '';
  openaiModel = '';
  anthropicKey = '';
  anthropicModel = '';

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.refresh().then(() => {
      // Auto-open on first run if no provider is available AND the user
      // hasn't explicitly dismissed the onboarding before.
      const dismissed = localStorage.getItem('llm_onboarding_dismissed') === '1';
      if (!dismissed && this.active === 'none') {
        this.openModal();
      }
    });
  }

  get active(): string {
    return this.status?.active_provider ?? 'none';
  }

  chipLabel(): string {
    if (!this.status) return 'Checking AI…';
    switch (this.active) {
      case 'ollama': return `Ollama · ${this.status.ollama.model || 'llama3'}`;
      case 'openai': return `OpenAI · ${this.status.fallback?.model || 'gpt'}`;
      case 'anthropic': return `Anthropic · ${this.status.fallback?.model || 'claude'}`;
      default: return 'No AI configured';
    }
  }

  chipTooltip(): string {
    return this.active === 'none'
      ? 'Click to set up an AI provider (Ollama, OpenAI, or Anthropic)'
      : 'Click to change AI provider';
  }

  openModal(): void {
    this.showModal = true;
    this.selectedProvider =
      this.active === 'none' ? 'ollama' : (this.active as any);
    // Reset input state from current config
    this.openaiModel = this.status?.config?.openai_model ?? '';
    this.anthropicModel = this.status?.config?.anthropic_model ?? '';
  }

  closeModal(): void {
    this.showModal = false;
    localStorage.setItem('llm_onboarding_dismissed', '1');
  }

  async refresh(): Promise<void> {
    try {
      this.status = await this.http
        .get<SystemStatus>('/api/system/status')
        .toPromise() as SystemStatus;
    } catch {
      this.status = null;
    }
  }

  async save(provider: 'openai' | 'anthropic'): Promise<void> {
    const body: any = { provider };
    if (provider === 'openai') {
      if (this.openaiKey) body.openai_api_key = this.openaiKey;
      if (this.openaiModel) body.openai_model = this.openaiModel;
    } else {
      if (this.anthropicKey) body.anthropic_api_key = this.anthropicKey;
      if (this.anthropicModel) body.anthropic_model = this.anthropicModel;
    }
    this.saving = true;
    try {
      await this.http
        .post<SaveConfigResponse>('/api/system/llm-config', body)
        .toPromise();
      // Clear in-memory key (already on disk)
      this.openaiKey = '';
      this.anthropicKey = '';
      await this.refresh();
      this.closeModal();
    } finally {
      this.saving = false;
    }
  }
}
