/**
 * THE handset store the app has open, and nothing else: one tenant's file
 * (`field-<tenant>.sqlite`, R131), opened when a technician signs in and closed
 * when the handset is signed out. Every screen wave reads through the root data
 * provider (`session/FieldRuntime.tsx`), which reads this.
 *
 *   - Signing in to the SAME tenant again (a switch of technician, an unlock)
 *     keeps the file open — the tenant is the file, the technician is a scope.
 *   - Signing in to ANOTHER tenant closes the first file before opening the
 *     second, so two tenants are never open at once.
 *   - Closing deletes nothing. A file is a file: the outbox, the photographs'
 *     rows and every captured value are on disk when it is closed and are
 *     there when it is opened again (R60, R64 — *"A sign-out deletes nothing"*).
 *
 * `storeOutboxPort` is the session's view of the open store (`session/
 * outboxPort.ts`): how much is waiting, per technician, and the remote
 * sign-out's mirror drop. With no store open it REFUSES rather than answering
 * zero — *nothing waiting* on a handset holding a day of work is the one wrong
 * answer that port must never give.
 */
import type { UnsentCount, OutboxPort } from '../session/outboxPort';
import { removeJobMirror } from '../sync/delta';
import { openTenantDb, type OpenOptions, type TenantDb } from './database';
import type { DriverFactory } from './driver';
import * as outboxQ from './queries/outbox';
import * as photoQ from './queries/photo';
import * as workOrderQ from './queries/workOrder';
import { deviceWide, scoped } from './scoped';

type Listener = (db: TenantDb | null) => void;

export class StoreHolder {
  private db: TenantDb | null = null;
  private readonly listeners = new Set<Listener>();

  constructor(
    private readonly factory: DriverFactory,
    private readonly options: OpenOptions = {},
  ) {}

  /** The open store, or null when nobody is signed in. */
  get current(): TenantDb | null {
    return this.db;
  }

  /** Open this tenant's file (or keep it open). Throws when the file is someone else's. */
  open(tenant: string): TenantDb {
    const wanted = tenant.toLowerCase();
    if (this.db && this.db.tenant === wanted) return this.db;
    this.close();
    this.db = openTenantDb(this.factory, wanted, this.options);
    this.emit();
    return this.db;
  }

  /** Close the file. Deletes nothing. */
  close(): void {
    if (!this.db) return;
    const db = this.db;
    this.db = null;
    db.close();
    this.emit();
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(): void {
    for (const l of this.listeners) l(this.db);
  }
}

class NoStoreOpenError extends Error {
  constructor() {
    super('no handset store is open — nobody is signed in');
    this.name = 'NoStoreOpenError';
  }
}

/** The session's door into the open store: counts, and the mirror drop. No delete of captured work. */
export function storeOutboxPort(holder: StoreHolder): OutboxPort {
  return {
    async unsentCounts(): Promise<UnsentCount[]> {
      const db = holder.current;
      if (!db) throw new NoStoreOpenError();
      const count = deviceWide(db, 'count');
      const byTech = new Map<string, UnsentCount>();
      const row = (id: string) => {
        let r = byTech.get(id);
        if (!r) {
          r = { technicianId: id, items: 0, photos: 0 };
          byTech.set(id, r);
        }
        return r;
      };
      for (const r of outboxQ.countUnsentByTechnician(count)) row(r.technician_id).items += r.n;
      for (const r of photoQ.countWaitingByTechnician(count)) row(r.technician_id).photos += r.n;
      return [...byTech.values()];
    },
    async dropMirror(technicianId: string): Promise<void> {
      const db = holder.current;
      if (!db) throw new NoStoreOpenError();
      // The MIRROR only: the technician's downloaded jobs, the same removal a
      // tombstone makes (R57). The outbox, photos, activity and crew time —
      // what they CAPTURED — are not touched (Security §4, R115).
      const s = scoped(db, technicianId);
      db.transaction(() => {
        for (;;) {
          const page = workOrderQ.listDay(s, { before: '9999-12-31T23:59:59.999Z', limit: 200 });
          if (page.length === 0) break;
          for (const order of page) removeJobMirror(s, order.id);
          if (page.length < 200) break;
        }
      });
    },
  };
}
