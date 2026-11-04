/**
 * @jest-environment node
 *
 * T-09 — migrations are numbered, forward-only, and refuse what they cannot read.
 */
import { createHash } from 'crypto';
import { readdirSync } from 'fs';
import { join } from 'path';

import { migrate, MigrationError, openTenantDb, rawRunner, TenantDb } from '../../src/db/database';
import { MIGRATIONS, type Migration } from '../../src/db/migrations';
import { m0001 } from '../../src/db/migrations/0001_initial';
import { m0003 } from '../../src/db/migrations/0003_reading_kind_text';
import { m0004 } from '../../src/db/migrations/0004_read_formats';
import { m0005 } from '../../src/db/migrations/0005_outbox_work_order_number';
import { memoryFactory, nodeDriver } from './support/nodeDriver';

const NOW = () => '2026-10-21T08:00:00.000Z';

/**
 * 0001 has shipped the moment this lane merges. Its text is pinned so an edit
 * goes RED and the change is made as 0002 instead — a handset carrying the old
 * build can only move forward. If this fails because you meant to change the
 * schema: revert 0001 and add 0002.
 */
const M0001_SHA256 = '6ba76e705a6c40e2d7556f9440102f0e67764b2bf89a9484a564024c06302e3d';

describe('migrations', () => {
  test('are numbered 1, 2, 3 … with no gaps, each file matching its number', () => {
    MIGRATIONS.forEach((m, i) => expect(m.id).toBe(i + 1));
    const files = readdirSync(join(__dirname, '../../src/db/migrations')).filter((f) => /^\d{4}_.*\.ts$/.test(f));
    expect(files.map((f) => Number(f.slice(0, 4)))).toEqual(MIGRATIONS.map((m) => m.id));
  });

  test('are forward only — no migration carries a down', () => {
    for (const m of MIGRATIONS) expect(Object.keys(m).sort()).toEqual(['id', 'name', 'statements']);
  });

  test('0001 has not been edited since it was written', () => {
    const digest = createHash('sha256').update(m0001.statements.join('\n;\n')).digest('hex');
    expect(digest).toBe(M0001_SHA256);
  });

  test('applies from zero, records itself, and a second open applies nothing', () => {
    const factory = memoryFactory();
    const db = openTenantDb(factory, 'north', { now: NOW });
    expect(rawRunner(db).all('SELECT id, name FROM schema_migrations ORDER BY id')).toEqual([
      { id: 1, name: 'initial' },
      { id: 2, name: 'document_help' },
      { id: 3, name: 'reading_kind_text' },
      { id: 4, name: 'read_formats' },
      { id: 5, name: 'outbox_work_order_number' },
      { id: 6, name: 'photo_route_read' },
      { id: 7, name: 'route_read_lower_than_last' },
    ]);
    const again = new TenantDb(factory('field-north.sqlite'), 'north');
    expect(migrate(again, NOW)).toEqual([]);
  });

  test('refuses a store written by a newer build rather than misread it', () => {
    const factory = memoryFactory();
    const db = openTenantDb(factory, 'north', { now: NOW });
    rawRunner(db).run(`INSERT INTO schema_migrations (id, name, applied_at) VALUES (${MIGRATIONS.length + 1}, 'from_the_future', 'x')`);
    expect(() => openTenantDb(factory, 'north', { now: NOW })).toThrow(MigrationError);
  });

  test('a migration that fails half way leaves nothing of itself behind', () => {
    const db = new TenantDb(nodeDriver(), 'north');
    const broken: Migration[] = [
      m0001,
      { id: 2, name: 'broken', statements: ['CREATE TABLE half_done (id TEXT)', 'THIS IS NOT SQL'] },
    ];
    expect(() => migrate(db, NOW, broken)).toThrow();
    const tables = rawRunner(db)
      .all<{ name: string }>(`SELECT name FROM sqlite_master WHERE name = 'half_done'`)
      .map((r) => r.name);
    expect(tables).toEqual([]);
    expect(rawRunner(db).all('SELECT id FROM schema_migrations')).toEqual([{ id: 1 }]);
  });

  test('0002 moves a store that has only 0001 forward, keeping its documents (DEF-FLD-10581)', () => {
    const db = new TenantDb(nodeDriver(), 'north');
    expect(migrate(db, NOW, [m0001])).toEqual([1]);
    rawRunner(db).run(
      `INSERT INTO document (id, owner_kind, owner_id, title, kind, source, updated_at)
       VALUES ('d1', 'tenant', NULL, 'Lone worker policy', 'pdf', 'server', 'x')`,
    );
    // exactly 0002, not "every migration after 0001": 0003 (DEF-FLD-10585) follows it
    expect(migrate(db, NOW, MIGRATIONS.slice(0, 2))).toEqual([2]);
    expect(rawRunner(db).get('SELECT title, ref, url FROM document WHERE id = :id', { id: 'd1' })).toEqual({
      title: 'Lone worker policy',
      ref: null,
      url: null,
    });
  });

  test('0003 (DEF-FLD-10585) upgrades an older store: its readings become number readings, no words', () => {
    const db = new TenantDb(nodeDriver(), 'north');
    const before = MIGRATIONS.filter((m) => m.id < m0003.id);
    expect(migrate(db, NOW, before)).toEqual(before.map((m) => m.id));
    rawRunner(db).run(
      `INSERT INTO wo_reading (technician_id, id, work_order_id, position, prompt, unit, value, updated_at)
       VALUES ('dana', 'r1', 'wo1', 1, 'Final read', 'kWh', '48100', 'x')`,
    );
    expect(migrate(db, NOW, [...before, m0003])).toEqual([3]);
    expect(rawRunner(db).all('SELECT kind, value, value_text, unit FROM wo_reading')).toEqual([
      { kind: 'number', value: '48100', value_text: null, unit: 'kWh' },
    ]);
    // a kind the server does not have is refused by the column itself
    expect(() =>
      rawRunner(db).run(
        `INSERT INTO wo_reading (technician_id, id, work_order_id, position, prompt, unit, kind, updated_at)
         VALUES ('dana', 'r2', 'wo1', 2, 'x', '', 'photo', 'x')`,
      ),
    ).toThrow();
  });

  test('0004 (MQ-033) upgrades an older store: its routes and readings keep everything and carry no format', () => {
    const db = new TenantDb(nodeDriver(), 'north');
    const before = MIGRATIONS.filter((m) => m.id < m0004.id);
    expect(migrate(db, NOW, before)).toEqual(before.map((m) => m.id));
    rawRunner(db).run(
      `INSERT INTO route_read (technician_id, id, route_id, stop_id, asset_id, unit, value, updated_at)
       VALUES ('ray', 'r1', 'wlk-07', 's1', 'a1', 'gal', '52410', 'x')`,
    );
    expect(migrate(db, NOW, [...before, m0004])).toEqual([4]);
    expect(rawRunner(db).all('SELECT value, unit, read_format_version_id, answers FROM route_read')).toEqual([
      { value: '52410', unit: 'gal', read_format_version_id: null, answers: null },
    ]);
    expect(rawRunner(db).all('SELECT COUNT(*) AS n FROM read_format_version')).toEqual([{ n: 0 }]);
  });

  test('0005 (DEF-FLD-10623) fills an older outbox row with its job number where the job is still on the phone', () => {
    const db = new TenantDb(nodeDriver(), 'north');
    const before = MIGRATIONS.filter((m) => m.id < m0005.id);
    expect(migrate(db, NOW, before)).toEqual(before.map((m) => m.id));
    rawRunner(db).run(
      `INSERT INTO work_order (technician_id, id, number, server_updated_at, updated_at) VALUES ('dana', 'wo1', 'WO-0155', 'x', 'x')`,
    );
    for (const [id, wo] of [
      ['o1', 'wo1'],
      ['o2', 'wo-gone'],
      ['o3', null],
    ] as const) {
      rawRunner(db).run(
        `INSERT INTO outbox (id, technician_id, work_order_id, route_id, kind, channel, payload, seq, captured_by, captured_at)
         VALUES (:id, 'dana', :wo, NULL, 'reading', 'job', '{}', 1, 'dana', 'x')`,
        { id, wo },
      );
    }
    expect(migrate(db, NOW, [...before, m0005])).toEqual([5]);
    expect(rawRunner(db).all('SELECT id, work_order_number FROM outbox ORDER BY id')).toEqual([
      { id: 'o1', work_order_number: 'WO-0155' },
      { id: 'o2', work_order_number: null },
      { id: 'o3', work_order_number: null },
    ]);
  });

  test('0006 (DEF-FLD-10631, FB-003) names each older photo\'s reading — by the capture key, or by its declaration', () => {
    const db = new TenantDb(nodeDriver(), 'north');
    const before = MIGRATIONS.filter((m) => m.id < 6);
    const m0006 = MIGRATIONS.find((m) => m.id === 6)!;
    expect(m0006).toBeDefined();
    expect(migrate(db, NOW, before)).toEqual(before.map((m) => m.id));
    const raw = rawRunner(db);
    raw.run(
      `INSERT INTO route_read (technician_id, id, route_id, stop_id, asset_id, unit, capture_key, state, updated_at)
       VALUES ('ray', 'r1', 'wlk', 's1', 'a1', 'gal', 'k-read', 'pending', 'x')`,
    );
    const outbox = (id: string, kind: string, payload: string) =>
      raw.run(
        `INSERT INTO outbox (id, technician_id, work_order_id, route_id, kind, channel, payload, seq, captured_by, captured_at)
         VALUES (:id, 'ray', NULL, 'wlk', :kind, 'route', :payload, 1, 'ray', 'x')`,
        { id, kind, payload },
      );
    outbox('k-read', 'route_read', '{"route_read_id":"r1"}');
    outbox('d1', 'photo', '{"photo_id":"p1","route_read_id":"r1"}');
    outbox('k-later', 'photo', '{"route_read_id":"r1"}');
    outbox('d2', 'photo', '{"photo_id":"p2","route_read_id":"r1"}');
    outbox('d3', 'photo', '{"photo_id":"p3","task_id":"t1"}');
    const photo = (id: string, outboxId: string, declareId: string) =>
      raw.run(
        `INSERT INTO photo (id, technician_id, outbox_id, declare_id, route_id, local_path, sha256, bytes, captured_by, captured_at)
         VALUES (:id, 'ray', :o, :d, 'wlk', 'file:///x', 'h', 1, 'ray', 'x')`,
        { id, o: outboxId, d: declareId },
      );
    photo('p1', 'k-read', 'd1'); // saved WITH the reading
    photo('p2', 'k-later', 'd2'); // added AFTER saving: its own act
    photo('p3', 'k-job', 'd3'); // a job photo: no reading
    expect(migrate(db, NOW, [...before, m0006])).toEqual([6]);
    expect(raw.all('SELECT id, route_read_id FROM photo ORDER BY id')).toEqual([
      { id: 'p1', route_read_id: 'r1' },
      { id: 'p2', route_read_id: 'r1' },
      { id: 'p3', route_read_id: null },
    ]);
  });

  test('refuses a list with a gap', () => {
    const db = new TenantDb(nodeDriver(), 'north');
    expect(() => migrate(db, NOW, [{ ...m0001, id: 2 }])).toThrow(MigrationError);
  });
});
