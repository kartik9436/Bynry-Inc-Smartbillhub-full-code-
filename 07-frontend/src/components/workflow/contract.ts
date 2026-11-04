// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the ETL workflow kit's PROP CONTRACT (design B15 §12)
// Rules:    BR-MET-088 (the transform stage offers the REAL target columns) ·
//           BR-MET-090 (a rule is a declared row: severity and action are two
//           columns, and a run stores the rules AS THEY WERE) ·
//           BR-MET-091 (a rule the product cannot evaluate is DECLARED and
//           marked unavailable, never omitted)
// Impacts:  components/workflow/** only.
// ───────────────────────────────────────────────────────
//
// THE SHAPES THIS KIT DRAWS, TYPED AGAINST THE ENDPOINT CONTRACT AND NOT
// AGAINST A FETCH.
//
// ⚠ THIS FILE CALLS NOTHING. It declares the payload shapes of design B15 §12
// so the components can be written, tested and reviewed while a sibling lane
// builds stages 1–3 of the server. `api/endpoints.ts` is deliberately NOT
// touched: adding a wrapper for a route nobody serves would put a typed
// promise in the shared file that the next lane has to reconcile, and the shape
// is what this kit needs, not the transport.
//
// Field names are SNAKE_CASE because that is what the API sends (`endpoints.ts`
// keeps the server's own casing at every one of its response types). A camelCase
// mirror here would be a second vocabulary for the same payload — the exact
// thing this kit exists to stop.
//
// WHERE EACH SHAPE COMES FROM (B15 §12, "the stage endpoints are named for what
// they DO, and only one of them writes"):
//
//   1  POST /imports                  → ReceivedFile        (rows, bytes, SHA-256)
//   2  GET  /imports/{id}/columns     → TargetColumn[]      (BR-MET-088)
//   3  POST /imports/{id}/transform   → ReconcileFigure[]   (in / dropped / forward)
//   4  POST /imports/{id}/validate    → RuleResult[] + RejectedRow[] + figures
//   5  POST /imports/{id}/dry-run     → DryRun              (writes NOTHING)
//   6  POST /imports/{id}/load        → the ONLY writer
//   7  GET  /imports/{id}             → Receipt
//   9  POST /imports/{id}/rollback    → reversed + skipped, and WHY skipped

/* ── Stage 1 · EXTRACT ────────────────────────────────────────────────────── */

/**
 * What `POST /imports` says it received.
 *
 * ⚠ `sha256` IS THE SERVER'S OWN DIGEST (design B15 §16 TC-2: *"a file's SHA-256
 * is computed server-side and matches the receipt — a client-supplied hash
 * proves nothing"*). This kit only ever DISPLAYS it.
 */
export interface ReceivedFile {
  name: string;
  rows: number;
  /** Already formatted by the server — "96 KB". The UI never divides bytes. */
  size_label: string;
  sha256: string;
}

/** One card on the Extract stage. */
export type SourceChoice =
  | {
      id: string;
      /** Catalogue key — "Upload a file". */
      title_key: string;
      /** Catalogue key — "CSV, fixed-width, BAI2, XLSX". */
      sub_key: string;
      available: true;
    }
  | {
      id: string;
      title_key: string;
      sub_key: string;
      available: false;
      /**
       * PLAIN ENGLISH, and never an id (CR-016 / G28): a utility clerk reads
       * this sentence. The provenance goes in the code comment beside the
       * catalogue value, where support can still reach it.
       */
      unavailable_reason_key: string;
    };

/* ── Stage 2 · TRANSFORM ──────────────────────────────────────────────────── */

/**
 * One entry in the `MAPS TO` picker — BR-MET-088, verbatim: *"The `MAPS TO`
 * picker on every row of stage 2 is populated from the columns the target table
 * actually has, so a column that exists can always be mapped and a column that
 * does not can never be offered."*
 *
 * ⚠ SO IT IS A PROP, NOT A CONSTANT IN THIS FILE. The list arrives from
 * `GET /imports/{id}/columns` for the run's own target, including the tenant's
 * own custom fields. A hand-written label list is the failure BR-MET-088 names.
 */
export interface TargetColumn {
  /** The real column name — `address_line`, `inside_city_limits`. */
  id: string;
  /** What the operator reads — "Address line 1". */
  label: string;
  required: boolean;
  /**
   * The column's GROUP heading, already translated — plan U9 (PO 2026-09-30):
   * the asset sheets print their columns in six groups (Identity · Location ·
   * Service and billing · details · Dates · Purchase) and the picker shows the
   * same groups. Absent on every other target, which renders a flat list.
   */
  group?: string;
}

export type MappingStatus = "matched" | "ignored" | "unmapped";

export interface MappingRow {
  source_column: string;
  sample_value: string;
  /**
   * The chosen target column id, or `null` for `— ignore —`.
   *
   * ⚠ `null` AND "NOBODY MAPPED IT" ARE DIFFERENT ANSWERS and the type keeps
   * them apart through `status`: `ignored` is a decision the operator made and
   * `unmapped` is one nobody has made yet. Collapsing them is how a migration
   * silently drops the customer's own key (B15 §4.2A on `LEGACY_KEY`).
   */
  target_column: string | null;
  status: MappingStatus;
  /** Already-worded transform — "Trim whitespace". `null` when there is none. */
  transform_label: string | null;
}

/**
 * The three checkboxes of stage 2, **as the server names them** — and until
 * `DEF-522` that sentence was false. The middle option was declared here as
 * `keep_latest_on_duplicate_key` while `import_runs.ROW_HANDLING_KEYS` has
 * always called it `keep_latest_on_key`, and stage 2 read its options with a
 * dict comprehension over a fixed key tuple: an unknown name was not refused,
 * it was read as `false`. So an operator ticked *"keep the latest row when a
 * key appears twice"* and the server kept the FIRST row instead — no 400, no
 * log, and green tests on both sides because each side sent its own spelling.
 *
 * ⚠ **THE NAMES HERE ARE THE WIRE NAMES. Do not "tidy" one.** The server now
 * REFUSES an unrecognised row-handling key by name rather than coercing it to
 * `false`, so a rename on this side is a visible 400 rather than a silent
 * wrong answer — which is the point, but it is still a break.
 */
export interface RowHandling {
  drop_exact_duplicates: boolean;
  keep_latest_on_key: boolean;
  skip_rows_missing_required: boolean;
}

/* ── The figure strip · transform reconcile, validate KPI, result KPI ─────── */

export interface ReconcileFigure {
  id: string;
  label: string;
  /**
   * The count — or a pre-formatted stand-in while the stage that computes it is
   * still running.
   *
   * ⚠ **AN ABSENT COUNT IS NOT A ZERO, AND THAT IS `CR-036` AMENDMENT 1 (f).**
   * On a live deployment the stage-3 tiles read *"ROWS CHECKED 0 · PASSED CLEAN
   * 0 · ERRORS 0 · WARNINGS 0"* while the bar beside them read *"Validating…
   * 1,646 of 9,881 · 16% complete"* — two halves of one screen contradicting
   * each other, and the half the operator believes is the one with numbers on
   * it. The true statement was *not yet*; the screen said *none*. `DryRunFigure`
   * already carries this widening for the same reason; this is the same
   * argument on the tiles.
   */
  value: number | string;
  /** Errors and rejects render tinted — never as one number among five. */
  flagged: boolean;
}

/* ── Stage 3 · VALIDATE ───────────────────────────────────────────────────── */

/** BR-MET-090: severity and action are TWO columns, deliberately. */
export type RuleSeverity = "error" | "warning" | "pass" | "off";

/**
 * One row of `RULES THAT RAN`, stored by the run (BR-MET-090: *"a run's results
 * are STORED, never recomputed"*), so an old receipt keeps saying what actually
 * happened after a utility re-configures the rule.
 */
export interface RuleResult {
  /** Stable forever; referenced by run results and never reused. */
  code: string;
  /** Customer-facing English, no ids. */
  sentence: string;
  severity: RuleSeverity;
  /** Already worded — "Reject row", "Default to Residential". */
  action_label: string;
  hits: number;
  /**
   * BR-MET-091 — a rule the product cannot evaluate is DECLARED and marked
   * unavailable WITH ITS REASON, never omitted. A screen listing three rules
   * where four were expected tells the operator nothing.
   */
  available: boolean;
  /** Plain English, required whenever `available` is false. */
  unavailable_reason: string | null;
}

export interface RejectedRow {
  row_number: number;
  /** The row's key as the file gave it — "P-11902". */
  key: string;
  /** What is wrong, in plain English. */
  problem: string;
  /** What to do about it — "Load the premise first". */
  suggested_fix: string;
  /** CR-028 debt sweep D8: the row's SOURCE cells as staged — the inline
   *  "fix here" editor's inputs, labelled by the operator's own file headers.
   *  Absent (older server / other callers) hides the editor. */
  raw?: Record<string, string | null>;
  /** `BR-MET-1032`: the cells among them showing `••••6789` because the server
   *  holds that identifier encrypted. The editor opens those EMPTY, against the
   *  mask as a placeholder — see `RejectList`. Absent names none. */
  masked?: readonly string[];
}

/* ── Stage 4 · LOAD ───────────────────────────────────────────────────────── */

export interface DryRunFigure {
  id: string;
  label: string;
  /** Pre-formatted: a count, or "426 addresses", or the target's name. */
  value: string;
  numeric: boolean;
}

/* ⛔ **`WriteMode` LIVED HERE AND IS GONE — CR-042.**
 *
 * It carried a `caution` field, and the comment above it explained that the
 * caution existed for `Replace the batch`, whose behaviour on rows in the
 * database and not in the file was unruled (B15 §8 Q6 / OQ-326). The PO ruled
 * on 2026-08-21 (BR-MET-099) and then withdrew the mode entirely on 2026-08-27
 * (*"replace option is not required"*), so there is no destructive mode left to
 * caution about and no second shape of write-mode option to describe.
 *
 * The two remaining options are `WriteModeOption` in `./WriteModeChoice`, which
 * is where the ONE shared control lives. A type that describes a control is
 * best kept beside the control; keeping it here is how this kit ended up with
 * two write-mode vocabularies in the first place. */

/**
 * The approval sentence, with ITS OWN NUMBERS.
 *
 * ⚠ THE THRESHOLD IS DATA, NOT A SCREEN CONSTANT. B15 §4.4 records the 5% as
 * *"r10 copy, not a signed rule"*, and DEF-435 is what a screen constant no
 * server enforces costs (BR-RAT-091 clause 2). So the percentage, the count and
 * the batch size all arrive from the server and this kit prints what it is
 * given.
 */
export interface ApprovalNote {
  threshold_pct: number;
  rejected: number;
  of_rows: number;
  /** Additional server-worded sentence, or `null`. */
  always_requires: string | null;
}

export interface LoadOptions {
  create_rollback_point: boolean;
  notify_on_finish: boolean;
}

/* ── Stage 5 · RESULT ─────────────────────────────────────────────────────── */

/**
 * The six-field receipt of B15 §4.5.
 *
 * ⚠ EVERY FIELD IS NULLABLE AND THE UI PRINTS "not recorded" RATHER THAN A
 * BLANK. A receipt with a silently empty session line reads as a receipt with
 * nothing to hide; the stated-absence discipline says the opposite.
 */
export interface Receipt {
  run_id: string;
  /** Already formatted by the server, in the tenant's own zone. */
  finished_label: string;
  duration_label: string;
  source_label: string | null;
  file_sha256: string | null;
  file_hash_verified: boolean;
  run_by: string | null;
  session_and_ip: string | null;
  mapping_used: string | null;
  rollback_point: RollbackPoint | null;
}

/**
 * ⚠ THE EXPIRY IS A SERVER SENTENCE, NOT "30 DAYS" TYPED INTO A SCREEN.
 * B15 §8 Q7 asks whether the rollback window is 30 days at all, and it is
 * unruled. r10 prints the promise; if the UI held the number, the screen would
 * be making it.
 */
export interface RollbackPoint {
  id: string;
  /** "available for 30 days", worded and dated by the server. */
  expiry_label: string;
}
