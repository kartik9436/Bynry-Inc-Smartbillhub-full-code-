/**
 * @jest-environment node
 *
 * T-09 — the schema applies from zero, and its shape obeys the rules it
 * claims: the design's nineteen tables plus two of the store's own; tenant is
 * the FILE, never a column (R131); technician_id NOT NULL on the ten (R132);
 * no BLOB anywhere (photographs are paths, R52); REAL only for positions;
 * every figure with its unit (hard rule 3).
 */
import { rawRunner } from '../../src/db/database';
import {
  ALL_TABLES,
  DESIGN_TABLES,
  REAL_COLUMNS_ALLOWED,
  TECHNICIAN_TABLES,
} from '../../src/db/schema';
import { openStore } from './support/fixtures';

type Col = { name: string; type: string; notnull: number; pk: number };

function tablesOf(db: ReturnType<typeof openStore>): string[] {
  return rawRunner(db)
    .all<{ name: string }>(
      `SELECT name FROM sqlite_master WHERE type = 'table'
         AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'search_index_%' ORDER BY name`,
    )
    .map((r) => r.name);
}

function columnsOf(db: ReturnType<typeof openStore>, table: string): Col[] {
  return rawRunner(db).all<Col>(`SELECT name, type, "notnull", pk FROM pragma_table_info('${table}')`);
}

describe('the handset schema', () => {
  const db = openStore();
  afterAll(() => db.close());

  test('applies from zero and creates exactly the registered tables', () => {
    expect(tablesOf(db)).toEqual([...ALL_TABLES].sort());
    expect(DESIGN_TABLES).toHaveLength(19);
  });

  test('search_index is an FTS5 virtual table', () => {
    const row = rawRunner(db).get<{ sql: string }>(`SELECT sql FROM sqlite_master WHERE name = 'search_index'`);
    expect(row?.sql).toMatch(/USING fts5/i);
  });

  test('no table carries a tenant column — the tenant is the file (R131)', () => {
    for (const t of ALL_TABLES) {
      expect(columnsOf(db, t).map((c) => c.name)).not.toContain('tenant_id');
    }
  });

  test.each(TECHNICIAN_TABLES)('%s carries technician_id NOT NULL (R132)', (table) => {
    const col = columnsOf(db, table).find((c) => c.name === 'technician_id');
    expect(col).toBeDefined();
    expect(col!.notnull === 1 || col!.pk > 0).toBe(true);
  });

  test('sync_state is keyed by the pair (R134)', () => {
    const pk = columnsOf(db, 'sync_state')
      .filter((c) => c.pk > 0)
      .sort((a, b) => a.pk - b.pk)
      .map((c) => c.name);
    expect(pk).toEqual(['technician_id', 'table_name']);
  });

  test('no BLOB column anywhere — a photograph is a path (R52)', () => {
    for (const t of ALL_TABLES) {
      for (const c of columnsOf(db, t)) expect(c.type.toUpperCase()).not.toBe('BLOB');
    }
    expect(columnsOf(db, 'photo').find((c) => c.name === 'local_path')?.type).toBe('TEXT');
  });

  test('REAL only for positions and distances — never money, never a meter figure', () => {
    const offenders: string[] = [];
    for (const t of ALL_TABLES) {
      for (const c of columnsOf(db, t)) {
        const affinity = c.type.toUpperCase();
        if (/REAL|FLOA|DOUB|NUMERIC|DECIMAL/.test(affinity) && !(REAL_COLUMNS_ALLOWED as readonly string[]).includes(c.name)) {
          offenders.push(`${t}.${c.name} ${c.type}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  test('a reading is never stored without its unit (hard rule 3)', () => {
    for (const t of ['wo_reading', 'route_read']) {
      expect(columnsOf(db, t).find((c) => c.name === 'unit')?.notnull).toBe(1);
      expect(columnsOf(db, t).find((c) => c.name === 'value')?.type).toBe('TEXT');
    }
  });

  test('the outbox and photo indexes the design names exist', () => {
    const names = rawRunner(db)
      .all<{ name: string }>(`SELECT name FROM sqlite_master WHERE type = 'index'`)
      .map((r) => r.name);
    for (const ix of ['ix_outbox_send', 'ix_outbox_purge', 'ix_photo_send', 'ix_read_send', 'ix_read_stop', 'ix_asset_serial', 'ix_asset_badge', 'ix_asset_device', 'ix_wo_day']) {
      expect(names).toContain(ix);
    }
  });

  test('a state outside the vocabulary is refused by the database itself', () => {
    expect(() =>
      rawRunner(db).run(
        `INSERT INTO outbox (id, technician_id, kind, channel, payload, seq, captured_by, captured_at, state)
         VALUES ('x', 'dana', 'reading', 'job', '{}', 1, 'dana', '2026-10-21', 'lost')`,
      ),
    ).toThrow(/CHECK constraint/);
  });
});
