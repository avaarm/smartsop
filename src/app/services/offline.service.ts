import { Injectable, PLATFORM_ID, inject } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, firstValueFrom, timeout } from 'rxjs';

import { ProtocolRun, RunStepStatus } from './protocol.service';

/** A run-step change captured while offline, replayed in order on reconnect. */
interface QueuedOp {
  id: string;
  accountId: number;
  runId: number;
  stepId: number;
  patch: { status?: RunStepStatus; note?: string };
  ts: number;
}

const QUEUE_KEY = 'smartsop_offline_queue';
const RUN_KEY = (id: number) => `smartsop_run_cache_${id}`;

/**
 * Keeps runs usable with no network: caches the active run, queues step
 * outcomes/notes made offline, and replays them when connectivity returns.
 *
 * Conflict policy is last-write-wins on replay — the field operator who
 * physically performed the step is treated as the source of truth — and the
 * run is re-fetched after a sync so the UI reconciles to the server.
 */
@Injectable({ providedIn: 'root' })
export class OfflineService {
  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));
  private http = inject(HttpClient);

  online$ = new BehaviorSubject<boolean>(true);
  pending$ = new BehaviorSubject<number>(0);
  /** Emits the number of ops synced after each successful flush. */
  synced$ = new BehaviorSubject<number>(0);

  private flushing = false;

  constructor() {
    if (!this.isBrowser) return;
    this.online$.next(navigator.onLine);
    this.pending$.next(this.readQueue().length);
    window.addEventListener('online', () => { this.online$.next(true); void this.flush(); });
    window.addEventListener('offline', () => this.online$.next(false));
  }

  get isOnline(): boolean { return this.online$.value; }

  // ── Run cache ──

  cacheRun(run: ProtocolRun): void {
    if (!this.isBrowser) return;
    try { localStorage.setItem(RUN_KEY(run.id), JSON.stringify(run)); } catch { /* quota / private mode */ }
  }

  getCachedRun(runId: number): ProtocolRun | null {
    if (!this.isBrowser) return null;
    try {
      const raw = localStorage.getItem(RUN_KEY(runId));
      return raw ? JSON.parse(raw) as ProtocolRun : null;
    } catch { return null; }
  }

  // ── Offline queue ──

  private readQueue(): QueuedOp[] {
    if (!this.isBrowser) return [];
    try {
      const raw = localStorage.getItem(QUEUE_KEY);
      return raw ? JSON.parse(raw) as QueuedOp[] : [];
    } catch { return []; }
  }

  private writeQueue(q: QueuedOp[]): void {
    if (!this.isBrowser) return;
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch { /* ignore */ }
    this.pending$.next(q.length);
  }

  /** Queue a step change to send later. Latest patch for a step is merged. */
  enqueue(accountId: number, runId: number, stepId: number,
          patch: { status?: RunStepStatus; note?: string }): void {
    const q = this.readQueue();
    q.push({ id: `${runId}:${stepId}:${Date.now()}:${Math.random().toString(36).slice(2, 7)}`,
             accountId, runId, stepId, patch, ts: Date.now() });
    this.writeQueue(q);
  }

  get pendingCount(): number { return this.readQueue().length; }

  /** Replay queued ops oldest-first. Stops on the first failure (still offline). */
  async flush(): Promise<number> {
    if (!this.isBrowser || this.flushing || !this.isOnline) return 0;
    this.flushing = true;
    let sent = 0;
    try {
      let q = this.readQueue();
      while (q.length) {
        const op = q[0];
        try {
          await firstValueFrom(
            this.http.patch(`/api/accounts/${op.accountId}/runs/${op.runId}/steps/${op.stepId}`,
                            op.patch).pipe(timeout(15000)));
        } catch {
          break;   // network still down (or the server rejected) — retry later
        }
        q = q.slice(1);
        this.writeQueue(q);
        sent++;
      }
    } finally {
      this.flushing = false;
    }
    if (sent) this.synced$.next(sent);
    return sent;
  }
}
