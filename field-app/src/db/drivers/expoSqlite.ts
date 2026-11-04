/**
 * The handset's driver: expo-sqlite's synchronous API behind `SqlDriver`.
 *
 * FTS5 — expo-sqlite's config plugin compiles it in by default (`enableFTS`,
 * default true). SQLCipher (Security §2, "page-level AES, key in the platform
 * keystore") is that plugin's `useSQLCipher` option plus a `PRAGMA key` issued
 * right after open; it belongs to the security lane (T-12), which owns the key,
 * and is NOT switched on here. Until it is, the store is protected by the
 * platform sandbox only — said here so nobody reads this file as the guarantee.
 */
import { openDatabaseSync, type SQLiteBindParams, type SQLiteBindValue } from 'expo-sqlite';

import { normaliseValue, type DriverFactory, type SqlDriver, type SqlParams } from '../driver';

function bind(params?: SqlParams): SQLiteBindParams {
  if (params === undefined) return [];
  if (Array.isArray(params)) {
    return (params as readonly Parameters<typeof normaliseValue>[0][]).map(
      (v) => normaliseValue(v) as SQLiteBindValue,
    );
  }
  const out: Record<string, SQLiteBindValue> = {};
  for (const [key, value] of Object.entries(params)) {
    // expo-sqlite wants the prefix in the key; our queries write `:name`.
    out[`:${key}`] = normaliseValue(value) as SQLiteBindValue;
  }
  return out;
}

export const openExpoDriver: DriverFactory = (fileName: string): SqlDriver => {
  const db = openDatabaseSync(fileName);
  db.execSync('PRAGMA journal_mode = WAL;');
  return {
    exec: (sql) => db.execSync(sql),
    run: (sql, params) => ({ changes: db.runSync(sql, bind(params)).changes }),
    get: <T>(sql: string, params?: SqlParams) =>
      (db.getFirstSync<T>(sql, bind(params)) ?? undefined) as T | undefined,
    all: <T>(sql: string, params?: SqlParams) => db.getAllSync<T>(sql, bind(params)),
    close: () => db.closeSync(),
  };
};
