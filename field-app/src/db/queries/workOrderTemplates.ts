/**
 * `work_order_templates` — every published template, so FF-62 can raise an
 * order offline (R112: recently used first, search behind it). Not scoped:
 * the tenant's catalogue, identical for every technician on the handset.
 * Downloaded at sync from `GET work/mobile/templates` (`sync/extras.ts`).
 */
import type { TenantDb } from '../database';
import { toJson } from '../json';

/**
 * DEF-FLD-10613 (MQ-034): the catalogue sends `service` (and `job_type`) as an
 * object — `{id, code, name}` — and this table keeps a NAME in a TEXT column.
 * Stored as it came, Android's SQLite kept the object's `toString` and FF-62
 * printed `{id=01a07f62-…, code=water, name=Water}` on every card (B14 rule
 * 31: no database id on screen). The wire is normalised HERE, at the one
 * write, so no caller can put anything but a name or null in the column.
 */
export function nameOf(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') return plainName(value);
  if (typeof value === 'object' && !Array.isArray(value)) {
    const o = value as Record<string, unknown>;
    for (const k of ['name', 'code']) {
      const v = o[k];
      if (typeof v === 'string' && v.trim() !== '') return v.trim();
    }
  }
  return null;
}

/**
 * A stored value fit to show, or null. A row written before the fix can still
 * hold a serialised object — a template the catalogue no longer offers is never
 * re-downloaded — so reads and screens pass through this: plain text as it is;
 * a serialised map or JSON object reduced to its `name` (or `code`); anything
 * else, nothing.
 */
export function plainName(value: unknown): string | null {
  if (typeof value !== 'string') return value !== null && typeof value === 'object' ? nameOf(value) : null;
  const text = value.trim();
  if (text === '') return null;
  if (!(text.startsWith('{') || text.startsWith('['))) return text;
  try {
    return nameOf(JSON.parse(text) as unknown);
  } catch {
    // Android's `Map.toString()`: `{id=…, code=water, name=Water}`.
    const pick = (k: string) => new RegExp(`[{,\\s]${k}=([^,}]*)`).exec(text)?.[1]?.trim() || null;
    return pick('name') ?? pick('code');
  }
}

function clean<T extends TemplateRow | undefined>(row: T): T {
  return row ? ({ ...row, service: plainName(row.service) } as T) : row;
}

/** Every row read out of the table, its service made fit to show. */
export function cleanRows(rows: TemplateRow[]): TemplateRow[] {
  return rows.map((r) => clean(r));
}

export function cleanRow(row: TemplateRow | undefined): TemplateRow | undefined {
  return clean(row);
}

export interface TemplateRow {
  id: string;
  name: string;
  version: string;
  service: string | null;
  published: number;
  step_count: number;
  safety_count: number;
  reading_count: number;
  body: string | null;
  last_used_at: string | null;
  updated_at: string;
}

export function upsert(
  db: TenantDb,
  t: {
    id: string;
    name: string;
    version: string;
    /** A name, or the wire's `{id, code, name}` — stored as the name (DEF-FLD-10613). */
    service?: unknown;
    published?: boolean;
    stepCount?: number;
    safetyCount?: number;
    readingCount?: number;
    body?: unknown;
  },
  now: string,
): void {
  db.ref.run(
    `INSERT INTO work_order_templates (id, name, version, service, published, step_count, safety_count,
                                       reading_count, body, updated_at)
     VALUES (:id, :name, :version, :service, :published, :step_count, :safety_count, :reading_count, :body, :now)
     ON CONFLICT (id) DO UPDATE SET
       name = excluded.name, version = excluded.version, service = excluded.service,
       published = excluded.published, step_count = excluded.step_count, safety_count = excluded.safety_count,
       reading_count = excluded.reading_count, body = excluded.body, updated_at = excluded.updated_at`,
    {
      id: t.id,
      name: t.name,
      version: t.version,
      service: nameOf(t.service),
      published: t.published ?? true,
      step_count: t.stepCount ?? 0,
      safety_count: t.safetyCount ?? 0,
      reading_count: t.readingCount ?? 0,
      body: toJson(t.body),
      now,
    },
  );
}

/** FF-62: recently used first, then by name; paged. */
export function listPublished(db: TenantDb, opts: { limit: number; offset?: number }): TemplateRow[] {
  return cleanRows(
    db.ref.all<TemplateRow>(
      `SELECT * FROM work_order_templates WHERE published = 1
        ORDER BY last_used_at IS NULL, last_used_at DESC, name LIMIT :limit OFFSET :offset`,
      { limit: opts.limit, offset: opts.offset ?? 0 },
    ),
  );
}

/** The body the handset already holds for a template — a catalogue row carries none, so a refresh keeps it. */
export function bodyOf(db: TenantDb, id: string): unknown {
  const raw = db.ref.get<{ body: string | null }>('SELECT body FROM work_order_templates WHERE id = :id', { id })?.body;
  return raw ? (JSON.parse(raw) as unknown) : null;
}

export function markUsed(db: TenantDb, id: string, at: string): void {
  db.ref.run('UPDATE work_order_templates SET last_used_at = :at WHERE id = :id', { id, at });
}
