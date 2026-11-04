/**
 * Opening the handset store for ONE tenant, and the transaction every capture
 * and every cascade runs inside.
 *
 * ⚠ THE TENANT IS THE FILE (R131, PO ruled 2026-10-21): `field-<tenant>.sqlite`,
 * chosen at sign-in. No table carries a tenant column and no query names one,
 * because a query on this handle CANNOT reach another tenant's rows — they are
 * in another file. What this module adds is the check that keeps that true
 * rather than assumed (Security §3): the first open stamps the tenant into
 * `db_meta`, and every later open refuses a file stamped for someone else — a
 * renamed or copied file, or a bug that passed the wrong name.
 *
 * ⚠ THE REFERENCE RUNNER REFUSES A SCOPED TABLE. `db.ref` is for the tables
 * nobody owns (premise, customer, asset, document, technician, settings, the
 * template catalogue). A statement on `db.ref` that names a technician's table
 * throws before it runs, so the only ways to reach one are `scoped()` — which
 * binds the technician — and `deviceWide()`, which must say why (`scoped.ts`).
 */
import { type DriverFactory, type RunResult, type SqlDriver, type SqlParams } from './driver';
import { MIGRATIONS, type Migration } from './migrations';
import * as dbMeta from './queries/dbMeta';
import * as ledger from './queries/schemaMigrations';
import { SCOPED_TABLES } from './schema';

export interface QueryRunner {
  run(sql: string, params?: SqlParams): RunResult;
  get<T = Record<string, unknown>>(sql: string, params?: SqlParams): T | undefined;
  all<T = Record<string, unknown>>(sql: string, params?: SqlParams): T[];
}

export class TenantMismatchError extends Error {
  constructor(readonly expected: string, readonly found: string) {
    super(`this store belongs to tenant "${found}", not "${expected}"`);
    this.name = 'TenantMismatchError';
  }
}

export class ScopeViolationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ScopeViolationError';
  }
}

export class MigrationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'MigrationError';
  }
}

const SCOPED_RE = new RegExp(`\\b(${SCOPED_TABLES.join('|')})\\b`, 'i');

/** SQL with its string literals and comments removed, so `kind = 'photo'` is
 *  not mistaken for the `photo` table. */
export function sqlWithoutLiterals(sql: string): string {
  return sql
    .replace(/--[^\n]*/g, ' ')
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/'(?:[^']|'')*'/g, "''");
}

/** The scoped tables a statement names, if any. */
export function scopedTablesIn(sql: string): string[] {
  const found = new Set<string>();
  const re = new RegExp(SCOPED_RE.source, 'gi');
  const text = sqlWithoutLiterals(sql);
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) found.add((m[1] ?? '').toLowerCase());
  return [...found];
}

const TENANT_RE = /^[a-z0-9][a-z0-9_-]{0,62}$/i;

export function tenantFileName(tenant: string): string {
  if (!TENANT_RE.test(tenant)) throw new Error(`not a tenant name: ${JSON.stringify(tenant)}`);
  return `field-${tenant.toLowerCase()}.sqlite`;
}

/** Raw access for `scoped.ts` and the migration runner only. `scoping.test.ts`
 *  fails any other file that calls it. */
export function rawRunner(db: TenantDb): QueryRunner {
  return db._raw;
}

export class TenantDb {
  /** @internal — through `rawRunner()` only. */
  readonly _raw: QueryRunner;
  readonly ref: QueryRunner;
  private depth = 0;
  private savepoint = 0;

  constructor(
    private readonly driver: SqlDriver,
    readonly tenant: string,
  ) {
    this._raw = {
      run: (sql, params) => driver.run(sql, params),
      get: (sql, params) => driver.get(sql, params),
      all: (sql, params) => driver.all(sql, params),
    };
    const guard = (sql: string): void => {
      const named = scopedTablesIn(sql);
      if (named.length > 0) {
        throw new ScopeViolationError(
          `"${named.join(', ')}" belongs to a technician — read it through scoped() (R133)`,
        );
      }
    };
    this.ref = {
      run: (sql, params) => (guard(sql), driver.run(sql, params)),
      get: (sql, params) => (guard(sql), driver.get(sql, params)),
      all: (sql, params) => (guard(sql), driver.all(sql, params)),
    };
  }

  /**
   * Everything inside `fn` lands together or not at all. Nested calls become
   * SAVEPOINTs, so a cascade called from inside a capture is still one act.
   * `fn` is synchronous on purpose — see `driver.ts`.
   */
  transaction<T>(fn: () => T): T {
    if (this.depth === 0) {
      this.driver.exec('BEGIN IMMEDIATE');
      this.depth = 1;
      try {
        const out = fn();
        this.driver.exec('COMMIT');
        return out;
      } catch (err) {
        this.driver.exec('ROLLBACK');
        throw err;
      } finally {
        this.depth = 0;
      }
    }
    const name = `sp_${++this.savepoint}`;
    this.driver.exec(`SAVEPOINT ${name}`);
    this.depth += 1;
    try {
      const out = fn();
      this.driver.exec(`RELEASE ${name}`);
      return out;
    } catch (err) {
      this.driver.exec(`ROLLBACK TO ${name}`);
      this.driver.exec(`RELEASE ${name}`);
      throw err;
    } finally {
      this.depth -= 1;
    }
  }

  /** @internal — DDL for the migration runner. */
  _exec(sql: string): void {
    this.driver.exec(sql);
  }

  close(): void {
    this.driver.close();
  }
}

/**
 * Apply every migration this build knows that the file has not had, each in
 * its own transaction. Refuses a file that has had a migration this build does
 * NOT know — a newer build wrote it — rather than running against a shape it
 * cannot read (Mobile data §9: "refuses a version it does not know and says so,
 * instead of silently storing nulls").
 */
export function migrate(db: TenantDb, now: () => string, migrations: readonly Migration[] = MIGRATIONS): number[] {
  migrations.forEach((m, i) => {
    if (m.id !== i + 1) throw new MigrationError(`migration ${m.name} is numbered ${m.id}, expected ${i + 1}`);
  });
  ledger.ensure(db);
  const applied = ledger.appliedIds(db);
  const known = new Set(migrations.map((m) => m.id));
  const unknown = applied.filter((id) => !known.has(id));
  if (unknown.length > 0) {
    throw new MigrationError(`this store was written by a newer build (migration ${unknown.join(', ')})`);
  }
  const done = new Set(applied);
  const ran: number[] = [];
  for (const m of migrations) {
    if (done.has(m.id)) continue;
    db.transaction(() => {
      for (const statement of m.statements) db._exec(statement);
      ledger.record(db, m.id, m.name, now());
    });
    ran.push(m.id);
  }
  return ran;
}

export interface OpenOptions {
  now?: () => string;
}

/** Open (and bring up to date) the store of one tenant. */
export function openTenantDb(factory: DriverFactory, tenant: string, options: OpenOptions = {}): TenantDb {
  const now = options.now ?? (() => new Date().toISOString());
  const driver = factory(tenantFileName(tenant));
  const db = new TenantDb(driver, tenant.toLowerCase());
  try {
    migrate(db, now);
    const stamped = dbMeta.get(db, 'tenant');
    if (stamped === undefined) dbMeta.set(db, 'tenant', db.tenant);
    else if (stamped !== db.tenant) throw new TenantMismatchError(db.tenant, stamped);
  } catch (err) {
    db.close();
    throw err;
  }
  return db;
}

