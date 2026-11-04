/**
 * The ONLY way to read or write a technician's table (R133, PO ruled
 * 2026-10-21): "Every read of a scoped table goes through one helper, and a
 * test fails any statement that bypasses it. Ten tables and one helper is
 * defensible; ten tables and two hundred queries each remembering the filter
 * is not."
 *
 * Two doors, and only two:
 *
 *  - `scoped(db, technicianId)` — what a screen sees. Every statement must name
 *    `:technician_id`, and the helper binds it, so the caller cannot pass the
 *    wrong one by accident and cannot forget it. Marco's screens are built on
 *    `scoped(db, 'marco')`; Dana's 62 unsent items are not in any answer.
 *
 *  - `deviceWide(db, reason)` — the few jobs that are about the HANDSET, not a
 *    person: sending every technician's unsent work under its own name
 *    (E2E-21: "signed in as nobody … all 93 items send"), applying the
 *    server's per-item answers, and the start-up purge. Each must state its
 *    reason, and `scoping.test.ts` holds the list of files allowed to.
 */
import type { SqlParams } from './driver';
import { rawRunner, ScopeViolationError, type QueryRunner, type TenantDb } from './database';

export type { QueryRunner } from './database';

export interface ScopedRunner extends QueryRunner {
  readonly technicianId: string;
}

function withTechnician(params: SqlParams | undefined, technicianId: string): SqlParams {
  if (Array.isArray(params)) {
    throw new ScopeViolationError('a scoped statement takes named parameters, so :technician_id can be bound');
  }
  return { ...((params as Record<string, unknown>) ?? {}), technician_id: technicianId } as SqlParams;
}

export function scoped(db: TenantDb, technicianId: string): ScopedRunner {
  if (!technicianId) throw new ScopeViolationError('no technician — a scoped read needs whose rows it is');
  const raw = rawRunner(db);
  const check = (sql: string): void => {
    if (!/:technician_id\b/.test(sql)) {
      throw new ScopeViolationError('a scoped statement must filter on :technician_id (R133)');
    }
  };
  return {
    technicianId,
    run: (sql, params) => (check(sql), raw.run(sql, withTechnician(params, technicianId))),
    get: (sql, params) => (check(sql), raw.get(sql, withTechnician(params, technicianId))),
    all: (sql, params) => (check(sql), raw.all(sql, withTechnician(params, technicianId))),
  };
}

/**
 * Why a statement may cross technicians. A closed list: adding one is a
 * decision, and `scoping.test.ts` names the files allowed to use each.
 */
export const DEVICE_WIDE_REASONS = {
  /** Sending every technician's unsent work under its own name (R64, BR-WRK-060). */
  send: 'send',
  /** Writing the server's per-item answer onto the row it answers, by its key. */
  receipt: 'receipt',
  /** The start-up purge (R60–R63). */
  purge: 'purge',
  /** Counting what is waiting, device-wide, for the sign-out warning (E2E-21). */
  count: 'count',
} as const;
export type DeviceWideReason = keyof typeof DEVICE_WIDE_REASONS;

export function deviceWide(db: TenantDb, reason: DeviceWideReason): QueryRunner {
  if (!(reason in DEVICE_WIDE_REASONS)) throw new ScopeViolationError(`not a device-wide reason: ${reason}`);
  return rawRunner(db);
}
