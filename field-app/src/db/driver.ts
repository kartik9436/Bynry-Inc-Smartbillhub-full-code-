/**
 * The one interface every SQL statement on the handset goes through.
 *
 * Two implementations exist and they must stay interchangeable:
 *   - `drivers/expoSqlite.ts` — expo-sqlite, inside the app on the handset;
 *   - `tests/db/support/nodeDriver.ts` — better-sqlite3, under Jest in Node.
 * Both are SYNCHRONOUS. That is deliberate: a capture is a handful of inserts
 * that must land together or not at all (Mobile data §1 — "a reading, its photo
 * row and its idempotency key must land together"), and a synchronous
 * BEGIN … COMMIT cannot be interleaved with another write by an `await`.
 * The network is asynchronous; the database is not.
 *
 * Parameters are NAMED (`:technician_id`) with keys written WITHOUT the colon,
 * or positional (`?`) as an array. Each driver adapts that to its library.
 * `undefined` binds as NULL and a boolean as 1/0, in both drivers, so a query
 * never behaves differently on the handset from how it behaved in a test.
 */
export type SqlValue = string | number | null | Uint8Array;
export type SqlInput = SqlValue | boolean | undefined;
export type SqlParams = Readonly<Record<string, SqlInput>> | readonly SqlInput[];

export interface RunResult {
  changes: number;
}

export interface SqlDriver {
  /** Several statements, no parameters, no result (DDL, PRAGMA, BEGIN). */
  exec(sql: string): void;
  run(sql: string, params?: SqlParams): RunResult;
  get<T = Record<string, unknown>>(sql: string, params?: SqlParams): T | undefined;
  all<T = Record<string, unknown>>(sql: string, params?: SqlParams): T[];
  close(): void;
}

/** Opens (creating if absent) the database file of that name. */
export type DriverFactory = (fileName: string) => SqlDriver;

/** `undefined` → NULL, boolean → 1/0; everything else unchanged. */
export function normaliseValue(value: SqlInput): SqlValue {
  if (value === undefined) return null;
  if (typeof value === 'boolean') return value ? 1 : 0;
  return value;
}
