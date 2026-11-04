/**
 * The handset database: what tables exist, which group each belongs to, and
 * which are scoped to a technician. The DDL itself is in `migrations/` (applied
 * forward only); this file is the register that the tests hold the DDL to.
 *
 * Source: the design's *Mobile data* page §2 and §11, and the PO rulings of
 * 2026-10-21 recorded in the decision log (R130–R134).
 *
 * ⚠ TENANT: THE FILE, NEVER A COLUMN (R131, PO ruled 2026-10-21).
 * "On the handset the tenant is the database FILE, never a column.
 * field-<tenant>.sqlite, chosen at sign-in; a contractor working for two
 * utilities gets two files." So no table here carries `tenant_id`. The tenant
 * is checked instead when the file is opened — `database.ts` stamps the
 * tenant into `db_meta` on first open and refuses to open a file stamped for a
 * different one — which is the "check exists so that stays true rather than
 * being assumed" the Security page asks for. (The Security page's own sentence
 * "every table carries tenant_id" predates R131 and is superseded by it.)
 *
 * ⚠ TECHNICIAN: A REAL COLUMN, NOT NULL, ON TEN TABLES (R132), and every read
 * of a scoped table goes through `scoped.ts` (R133).
 *
 * ⚠ VALUES: money and meter figures are TEXT decimal strings, never REAL —
 * a reading of 48210.50 must come back as 48210.50 (CLAUDE.md hard rule 2 for
 * money; the same reasoning for a meter figure, which feeds a bill). The only
 * REAL columns are positions and distances; `schema.test.ts` holds that list.
 * A consumption figure never exists without its unit (hard rule 3): `unit` is
 * NOT NULL wherever a value is. Photographs are FILE PATHS, never BLOBs (R52).
 */

/** The ten tables that hold one technician's work (R132). */
export const TECHNICIAN_TABLES = [
  'work_order',
  'wo_item',
  'wo_reading',
  'route',
  'route_stop',
  'route_read',
  'outbox',
  'photo',
  'activity',
  'crew_time',
] as const;

/**
 * Every table whose rows belong to a technician and so may only be read through
 * `scoped.ts`: the ten above, plus `sync_state` (the technician is half its
 * key, R134) and `search_index` (built from scoped rows, carries the column).
 */
export const SCOPED_TABLES = [...TECHNICIAN_TABLES, 'sync_state', 'search_index'] as const;
export type ScopedTable = (typeof SCOPED_TABLES)[number];

export const TABLE_GROUPS = {
  /** A slice of the server, read-mostly. Server wins (R58). */
  mirror: ['work_order', 'wo_item', 'wo_reading', 'asset', 'premise', 'customer', 'document', 'technician'],
  /** Local-only, written by the technician. Handset wins; nothing unsent is ever deleted (R60). */
  capture: ['outbox', 'photo', 'activity', 'crew_time'],
  /** What joins the two. */
  bookkeeping: ['sync_state', 'search_index', 'settings'],
  /** Route reading (R73: one store, one outbox, one photo queue). */
  route: ['route', 'route_stop', 'route_read'],
  /** The downloaded template catalogue, shared by everyone on the handset. */
  catalogue: ['work_order_templates'],
  /** MQ-033 (`CR-192-BRC10`): a utility's read-format versions, kept by id.
   *  Not in the design's nineteen — the design predates read formats. */
  formats: ['read_format_version'],
  /** The store's own housekeeping — not in the design's nineteen. */
  store: ['schema_migrations', 'db_meta'],
} as const;

/** The design's nineteen, in its five groups. */
export const DESIGN_TABLES: readonly string[] = [
  ...TABLE_GROUPS.mirror,
  ...TABLE_GROUPS.capture,
  ...TABLE_GROUPS.bookkeeping,
  ...TABLE_GROUPS.route,
  ...TABLE_GROUPS.catalogue,
];

export const ALL_TABLES: readonly string[] = [...DESIGN_TABLES, ...TABLE_GROUPS.formats, ...TABLE_GROUPS.store];

/** Columns allowed to be REAL: positions, accuracies and distances. Nothing else. */
export const REAL_COLUMNS_ALLOWED = ['lat', 'lng', 'accuracy_m', 'metres_from_record'] as const;

/** Outbox and route-read states. `held_for_review` is the server's fourth answer
 *  (apps/work/sync.py RESULT_HELD): stored at the server, acknowledged. */
export const SEND_STATES = ['pending', 'sending', 'accepted', 'duplicate', 'refused', 'held_for_review'] as const;
export type SendState = (typeof SEND_STATES)[number];
/** Answered and acknowledged — the server has it; the row may age out. */
export const SETTLED_STATES: readonly SendState[] = ['accepted', 'duplicate', 'held_for_review'];
/** Not yet with the server. NEVER deleted, at any age (R60). `refused` is here
 *  too: the server did not keep it, so it waits for a person (Mobile data §10 rule 2). */
export const UNSENT_STATES: readonly SendState[] = ['pending', 'sending', 'refused'];

export const PHOTO_STATES = ['pending', 'uploading', 'uploaded', 'failed'] as const;
export type PhotoState = (typeof PHOTO_STATES)[number];
