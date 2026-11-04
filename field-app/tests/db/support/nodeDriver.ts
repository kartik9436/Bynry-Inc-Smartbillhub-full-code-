/**
 * The Node driver: better-sqlite3 behind the same `SqlDriver` the handset uses,
 * so every query is tested as the SQL it is, not as a mock of it.
 * better-sqlite3 ships with FTS5, which is what lets the search index be tested.
 */
import Database from 'better-sqlite3';

import { normaliseValue, type DriverFactory, type SqlDriver, type SqlParams } from '../../../src/db/driver';

type Bound = unknown[] | Record<string, unknown>;

function bind(params?: SqlParams): Bound {
  if (params === undefined) return [];
  if (Array.isArray(params)) return (params as Parameters<typeof normaliseValue>[0][]).map(normaliseValue);
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(params)) out[key] = normaliseValue(value);
  return out;
}

function call<R>(stmt: Database.Statement, method: 'run' | 'get' | 'all', params: Bound): R {
  // better-sqlite3 takes an array as spread positionals and an object as named.
  return (Array.isArray(params) ? stmt[method](...params) : stmt[method](params)) as R;
}

export function nodeDriver(file = ':memory:'): SqlDriver {
  const db = new Database(file);
  db.pragma('journal_mode = WAL');
  return {
    exec: (sql) => {
      db.exec(sql);
    },
    run: (sql, params) => ({ changes: call<Database.RunResult>(db.prepare(sql), 'run', bind(params)).changes }),
    get: <T>(sql: string, params?: SqlParams) => call<T | undefined>(db.prepare(sql), 'get', bind(params)),
    all: <T>(sql: string, params?: SqlParams) => call<T[]>(db.prepare(sql), 'all', bind(params)),
    close: () => db.close(),
  };
}

/**
 * A factory that keeps one in-memory database per FILE NAME, so a test can open
 * `field-north.sqlite` and `field-south.sqlite` and get two separate stores —
 * the handset's tenant boundary (R131) — without touching the disk.
 */
export function memoryFactory(): DriverFactory & { files: Map<string, SqlDriver> } {
  const files = new Map<string, SqlDriver>();
  const factory = ((fileName: string) => {
    let d = files.get(fileName);
    if (!d) {
      d = nodeDriver(':memory:');
      files.set(fileName, d);
    }
    // A re-open returns the same connection with a no-op close, so "close and
    // reopen" in a test keeps the data, as a file on disk would.
    const held = d;
    return { ...held, close: () => undefined };
  }) as DriverFactory & { files: Map<string, SqlDriver> };
  factory.files = files;
  return factory;
}
