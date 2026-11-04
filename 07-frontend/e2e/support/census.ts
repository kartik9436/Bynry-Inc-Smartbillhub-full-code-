// ── Trace ──────────────────────────────────────────────
// Component: FI-06 E2E assertion census — the reporter that makes a SKIPPED
//            browser suite report itself instead of passing silently.
// Defect:   DEF-057 (2026-08-11) — *"a job whose only possible outcomes are
//           'passed' and 'passed' is not a check"*. PO ruling the same day:
//           **"we ahve to prove against human clicking"**.
// Rules:    CLAUDE.md hard-won law 3 (defaults fail closed — the unsafe option
//           must be the one you TYPE) · law 7 (a guard is trusted only after it
//           is seen RED)
// Tests:    PROVED RED twice before being trusted green, both quoted in the
//           lane report. (1) `--grep "expectation-CSV"` selects only
//           server-free tests: `4 passed` → **exit 1**, "no test carries the
//           @app-server tag in this selection". (2) The exact DEF-057 scenario,
//           E2E_BASE_URL pointing at a dead port: `6 skipped, 4 passed` →
//           **exit 1**, "6 @app-server test(s) were selected and 6 skipped".
//           The same run with `E2E_ALLOW_NO_APP_SERVER=1` exits 0 with a
//           WARNING banner, so the escape hatch was verified too.
// Impacts:  07-frontend/playwright.config.ts (registers it) ·
//           .github/workflows/qa.yml (reads its exit code)
// ───────────────────────────────────────────────────────
//
// WHAT THIS COUNTS AND WHY IT IS COUNTED THIS WAY
//
// Playwright emits one `expect` STEP per `expect()` that actually executes, so
// the count below is the runner's own arithmetic and not a tally this file
// keeps. A test that skips executes none; a test that dies in `beforeEach`
// executes none; a spec file nobody selected executes none. That is exactly the
// number DEF-057 says nobody was printing.
//
// THE CENSUS IS SPLIT IN TWO, and the split is the whole point.
// `07-frontend/e2e` holds two kinds of test:
//
//   · SERVER-FREE — the expectation-CSV and B5 loaders. They always run, so
//     their count is never zero, so a total-only census would report a healthy
//     number while every browser assertion silently skipped. That is the
//     DEF-057 trap wearing a different hat.
//   · APP-SERVER — anything that drives a browser against a running product.
//     Tagged `@app-server` (the tag is STATIC, so the census knows how many
//     exist even when all of them skip) and counted separately.
//
// A run that executed ZERO app-server assertions FAILS. Not warns — fails,
// because that is the state this whole lane exists to stop reading as success.
// The escape hatch is named and must be typed:
//
//     E2E_ALLOW_NO_APP_SERVER=1 npx playwright test
//
// which downgrades it to a loud warning, for a developer with no stack up.
// Nothing in `.github/workflows/qa.yml` sets it, deliberately.

//
// IT ALSO WRITES A RUN RECEIPT (added 2026-08-11, for gate G12). G12 is the
// wave-close journey gate; a gate that only reads the repo can see that a
// journey has a spec file, and cannot see whether that spec ever RAN or passed —
// which is the exact difference DEF-057 was about. So every run writes a receipt
// naming each journey id that executed, its status and its executed-assertion
// count, and `run_gates.py --wave-close` refuses to pass an activated journey it
// cannot find in a fresh record. The receipt is written on EVERY run, including
// a failing one, so a red journey is recorded as red rather than leaving the
// last green receipt in place.
//
// ── WHERE THE RECEIPT LIVES, AND WHY IT MOVED (DEF-113, 2026-08-15) ─────────
//
// It used to live at `07-frontend/test-results/journey-run.json` — INSIDE
// Playwright's `outputDir`, which Playwright **purges at the start of every
// run**. With five journey lanes in one working tree a genuine receipt vanished
// within 9 SECONDS of the run that produced it, twice, and two full wave-close
// runs reported "no run receipt" while a real one had existed minutes earlier.
// A wave-close claim read off that file — green OR red — was not evidence about
// this tree; it was evidence about whichever lane finished most recently.
//
// Two changes, and both are needed; either alone still loses evidence:
//
//   1. **DURABLE LOCATION.** `07-frontend/journey-evidence/` is NOT an output
//      directory, so no other run purges it. `test-results/journey-run.json` is
//      still written for backward compatibility (qa.yml and older docs name it),
//      but it is explicitly the COPY, never the record — see LEGACY_RECEIPT_PATH.
//   2. **MERGE, NEVER REPLACE.** A narrow run (`--grep J23`) knows about one
//      journey and must leave every other journey's record standing. So each run
//      writes its OWN shard — `journey-evidence/runs/<runId>.json`, a filename no
//      other run can pick — and the merged view is folded from the shards, newest
//      `recorded_at` per journey id winning. **No run ever read-modify-writes a
//      file another run may be writing**, which is what makes a concurrent run
//      safe rather than merely unlikely to collide. Every record carries its own
//      `recorded_at`, so G12 can age each journey separately: a J23 record from
//      four days ago is stale even when J24's is a minute old.
//
// Consequence worth stating plainly, because it is the point of the whole
// exercise: the merged file is DERIVED. If it is corrupt, missing or mid-write,
// G12 re-folds the shards itself and loses nothing. There is one source of
// truth (the shards) and a view over it (hard-won law 5).

import { mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { FullResult, Reporter, TestCase, TestResult, TestStep } from "@playwright/test/reporter";

export const APP_SERVER_TAG = "@app-server";

// e2e/support → 07-frontend.
const FRONTEND_ROOT = resolve(fileURLToPath(new URL(".", import.meta.url)), "../..");

/**
 * The durable evidence directory. NOT Playwright's outputDir — nothing purges it.
 *
 * `E2E_EVIDENCE_DIR` redirects it, and the one thing worth saying about that
 * override is what it CANNOT do: gate G12 reads a CONSTANT path, so pointing the
 * census somewhere else can only move evidence AWAY from where the wave close
 * looks — which reads as "not proven" and fails closed. There is no value of this
 * variable that manufactures evidence at the path the gate reads. It exists so
 * the guard's own red-proof (`g12_selftest.py`) can write throwaway receipts
 * without ever putting a fake journey record where a real wave close would
 * believe it.
 */
export const EVIDENCE_DIR = process.env.E2E_EVIDENCE_DIR
  ? resolve(process.env.E2E_EVIDENCE_DIR)
  : resolve(FRONTEND_ROOT, "journey-evidence");
/** One immutable shard per run. The source of truth; never read-modify-written. */
export const EVIDENCE_RUNS_DIR = resolve(EVIDENCE_DIR, "runs");
/** The merged view, folded from the shards. Derived — safe to delete, safe to re-fold. */
export const RUN_RECEIPT_PATH = resolve(EVIDENCE_DIR, "journey-run.json");
/**
 * The OLD path, kept as a copy for readers that still name it (qa.yml, e2e/README.md).
 * It lives inside Playwright's outputDir and so is destroyed by the next run of
 * anything — that is DEF-113 and is exactly why it is no longer the record.
 */
export const LEGACY_RECEIPT_PATH = process.env.E2E_EVIDENCE_DIR
  ? resolve(EVIDENCE_DIR, "legacy-journey-run.json")
  : resolve(FRONTEND_ROOT, "test-results/journey-run.json");

/**
 * Shards older than this are pruned after a successful merge. A wave close reads
 * the newest record per journey, so an ancient shard can only add noise — but it
 * is pruned rather than trusted-and-ignored so the directory cannot grow without
 * bound in a tree that runs the suite all day. 14 days is long enough that no
 * plausible wave close loses evidence to it and short enough to stay readable;
 * it is a housekeeping figure, not a freshness rule. FRESHNESS IS G12's, and it
 * is computed per record from `recorded_at` — never from how long a file has sat
 * on disk.
 */
const SHARD_RETENTION_MS = 14 * 24 * 60 * 60 * 1000;

/** `@J12` → `J12`; the census never invents an id, it reads the spec's own tag. */
function journeyIds(test: TestCase): string[] {
  return test.tags.filter((tag) => tag !== APP_SERVER_TAG).map((tag) => tag.replace(/^@/, ""));
}

const ALLOW_NO_APP_SERVER = process.env.E2E_ALLOW_NO_APP_SERVER === "1";

interface Bucket {
  assertions: number;
  ran: number;
  skipped: number;
  declared: number;
}

function emptyBucket(): Bucket {
  return { assertions: 0, ran: 0, skipped: 0, declared: 0 };
}

function isAppServer(test: TestCase): boolean {
  return test.tags.includes(APP_SERVER_TAG);
}

interface JourneyRecord {
  status: string;
  assertions: number;
  tests: number;
  specs: string[];
  /**
   * When THIS journey's record was written, ISO-8601. Per record, not per file:
   * a narrow run refreshes one journey and every other record keeps the moment
   * it was actually produced, so G12 can call one stale while another is fresh
   * (DEF-113). A record with no `recorded_at` is UNDATED and G12 refuses it —
   * an undatable claim of "it passed" is exactly what fails closed.
   */
  recorded_at?: string;
  /** The run that produced this record — traceable back to its own shard file. */
  run_id?: string;
}

// THE WORST STATUS WINS, and it has to be ranked rather than assigned in
// arrival order. Until 2026-08-15 this file kept "the last status that was not
// `passed`", which is not the same statement: a SERIAL journey that FAILS at
// step 3 skips every step below it, so the last non-passed status is `skipped`
// and the receipt recorded the money journey as **skipped when it had failed**.
// Both are red to gate G12 (it demands `passed`), so nothing was let through —
// but a receipt that says "skipped" where a step BROKE describes a journey
// nobody ran instead of a journey that hit a wall, and the receipt is the only
// artefact a wave close reads. Found on J2's first run (2026-08-15).
const STATUS_RANK: Record<string, number> = {
  passed: 0,
  skipped: 1,
  interrupted: 2,
  timedOut: 3,
  failed: 4,
};

export function worseStatus(current: string, incoming: string): string {
  // An unknown status outranks every known one: a status this file cannot
  // grade must never be quietly treated as the mildest.
  const rank = (status: string): number => STATUS_RANK[status] ?? 99;
  return rank(incoming) > rank(current) ? incoming : current;
}

/**
 * Write JSON so no reader can ever see a half-written file: a temp name in the
 * same directory, then a rename, which POSIX makes atomic. A journey batch and a
 * wave-close gate run at the same time in this tree; without this, the gate's
 * read of a file mid-write is a JSON parse error that reads as "no evidence".
 */
function writeAtomically(path: string, payload: unknown): void {
  const temp = `${path}.${process.pid}.${Math.random().toString(36).slice(2, 8)}.tmp`;
  writeFileSync(temp, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
  renameSync(temp, path);
}

/**
 * Fold every run shard into one journey map, NEWEST `recorded_at` per id winning.
 *
 * The merge rule is deliberately "newest wins" and not "worst wins": a journey
 * that failed at 10:00 and passes at 10:30 has passed, and a wave close asks
 * what the product does NOW. Staleness is then G12's question, per record, and
 * it has the timestamp it needs to ask it. An undated record loses to any dated
 * one and is kept only when nothing dated exists, so it stays visible to the
 * gate that must refuse it rather than being silently dropped here.
 */
export function foldShards(runsDir: string): Record<string, JourneyRecord> {
  const merged: Record<string, JourneyRecord> = {};
  let names: string[] = [];
  try {
    names = readdirSync(runsDir).filter((n) => n.endsWith(".json"));
  } catch {
    return merged;
  }
  for (const name of names.sort()) {
    let shard: { journeys?: Record<string, JourneyRecord> };
    try {
      shard = JSON.parse(readFileSync(join(runsDir, name), "utf-8"));
    } catch {
      // A shard that will not parse is skipped, never fatal: one corrupt file
      // must not take the other lanes' evidence down with it.
      continue;
    }
    for (const [id, record] of Object.entries(shard.journeys ?? {})) {
      const held = merged[id];
      if (held === undefined || (record.recorded_at ?? "") > (held.recorded_at ?? "")) {
        merged[id] = record;
      }
    }
  }
  return Object.fromEntries(Object.entries(merged).sort(([a], [b]) => a.localeCompare(b)));
}

/** Housekeeping only — see SHARD_RETENTION_MS. Never a freshness decision. */
function pruneOldShards(runsDir: string, retentionMs: number): void {
  const cutoff = Date.now() - retentionMs;
  for (const name of readdirSync(runsDir)) {
    const path = join(runsDir, name);
    try {
      if (statSync(path).mtimeMs < cutoff) {
        rmSync(path, { force: true });
      }
    } catch {
      /* another run may have pruned it first; that is fine. */
    }
  }
}

export default class AssertionCensus implements Reporter {
  private readonly browser = emptyBucket();
  private readonly serverFree = emptyBucket();
  private readonly journeys = new Map<string, JourneyRecord>();
  private readonly assertionsByTest = new Map<string, number>();

  private bucket(test: TestCase): Bucket {
    return isAppServer(test) ? this.browser : this.serverFree;
  }

  onTestBegin(test: TestCase): void {
    this.bucket(test).declared += 1;
  }

  onStepEnd(test: TestCase, _result: TestResult, step: TestStep): void {
    // "expect" is Playwright's own category for an executed expect() call.
    if (step.category === "expect") {
      this.bucket(test).assertions += 1;
      this.assertionsByTest.set(test.id, (this.assertionsByTest.get(test.id) ?? 0) + 1);
    }
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const bucket = this.bucket(test);
    if (result.status === "skipped") {
      bucket.skipped += 1;
    } else {
      bucket.ran += 1;
    }
    // The receipt half. A journey's status is the WORST of its tests: one
    // skipped or failed step of a journey means the journey did not run, and a
    // receipt that averaged it away would be the same false comfort in a file.
    for (const id of journeyIds(test)) {
      const record = this.journeys.get(id) ?? { status: "passed", assertions: 0, tests: 0, specs: [] };
      record.assertions += this.assertionsByTest.get(test.id) ?? 0;
      record.tests += 1;
      const spec = test.location.file.split("/").slice(-1)[0];
      if (!record.specs.includes(spec)) {
        record.specs.push(spec);
      }
      record.status = worseStatus(record.status, result.status);
      this.journeys.set(id, record);
    }
  }

  private writeReceipt(result: FullResult): void {
    const now = new Date().toISOString();
    // A run id no concurrent run can pick: the clock alone collides (two lanes
    // starting in the same millisecond is not hypothetical when a script fans
    // out), so the pid and a random suffix are part of it.
    const runId = `${now.replace(/[:.]/g, "-")}-${process.pid}-${Math.random().toString(36).slice(2, 8)}`;
    for (const record of this.journeys.values()) {
      record.recorded_at = now;
      record.run_id = runId;
    }
    const receipt = {
      generated_at: now,
      run_id: runId,
      base_url: process.env.E2E_BASE_URL ?? null,
      tenant: process.env.E2E_TENANT ?? null,
      run_status: result.status,
      app_server_assertions: this.browser.assertions,
      server_free_assertions: this.serverFree.assertions,
      journeys: Object.fromEntries([...this.journeys].sort(([a], [b]) => a.localeCompare(b))),
    };

    // (1) THE SHARD — this run's own immutable evidence, under a name no other
    // run can choose. Written first, and written even when the merge below
    // fails, because the shard is the record and the merge is only a view.
    let shardWritten = false;
    try {
      mkdirSync(EVIDENCE_RUNS_DIR, { recursive: true });
      writeAtomically(join(EVIDENCE_RUNS_DIR, `${runId}.json`), receipt);
      shardWritten = true;
    } catch (error) {
      // A receipt that cannot be written must SAY so — G12 will then fail for
      // want of it, which is the correct outcome, but a silent write failure
      // would leave a stale receipt looking current.
      process.stdout.write(`\n⚠  could not write the journey run receipt shard: ${String(error)}\n`);
    }

    // (2) THE MERGED VIEW — every shard folded together, newest record per
    // journey winning, written atomically so a reader never sees half a file.
    // A narrow run therefore refreshes ITS journeys and leaves the rest standing;
    // that is DEF-113's "merge rather than replace", and it is done by folding
    // immutable files rather than by editing a shared one, so two runs merging
    // at the same instant cannot lose a record: each fold sees the other's shard
    // or does not, and the next fold sees both.
    let merged = receipt.journeys as Record<string, JourneyRecord>;
    if (shardWritten) {
      try {
        merged = foldShards(EVIDENCE_RUNS_DIR);
        writeAtomically(RUN_RECEIPT_PATH, { ...receipt, merged_from_shards: true, journeys: merged });
        pruneOldShards(EVIDENCE_RUNS_DIR, SHARD_RETENTION_MS);
      } catch (error) {
        process.stdout.write(`\n⚠  could not merge the journey run receipts: ${String(error)}\n`);
      }
    }

    // (3) THE LEGACY COPY, for readers that still name the old path. It sits in
    // Playwright's outputDir and the next run of anything deletes it — which is
    // why it is written LAST and claimed as nothing. Its failure is not reported
    // as an evidence failure, because it is not evidence.
    try {
      mkdirSync(dirname(LEGACY_RECEIPT_PATH), { recursive: true });
      writeFileSync(
        LEGACY_RECEIPT_PATH,
        `${JSON.stringify({ ...receipt, journeys: merged, durable_copy_at: RUN_RECEIPT_PATH }, null, 2)}\n`,
        "utf-8",
      );
    } catch {
      /* the durable copy above is the record; this one is a convenience. */
    }
  }

  // `async` is not decoration: Reporter.onEnd is declared as returning a
  // Promise of the override object, and TypeScript refuses the synchronous
  // form — which is precisely the kind of error that lived undetected in this
  // directory until `tsconfig.e2e.json` first pointed a typecheck at it.
  async onEnd(result: FullResult): Promise<{ status?: FullResult["status"] } | void> {
    this.writeReceipt(result);
    const total = this.browser.assertions + this.serverFree.assertions;
    const line = (label: string, b: Bucket): string =>
      `  ${label.padEnd(12)} ${String(b.assertions).padStart(5)} assertions · ` +
      `${b.ran} ran · ${b.skipped} skipped (of ${b.declared} selected)`;

    process.stdout.write("\n── E2E ASSERTION CENSUS ──────────────────────────────────\n");
    process.stdout.write(line("app-server", this.browser) + "\n");
    process.stdout.write(line("server-free", this.serverFree) + "\n");
    process.stdout.write(`  ${"TOTAL".padEnd(12)} ${String(total).padStart(5)} assertions executed\n`);
    const journeyLine =
      this.journeys.size === 0
        ? "  journeys      none — no spec claimed a catalog journey id"
        : `  journeys      ${[...this.journeys]
            .map(([id, r]) => `${id}:${r.status}(${r.assertions})`)
            .sort()
            .join(" · ")}`;
    process.stdout.write(`${journeyLine}\n`);

    if (this.browser.assertions > 0) {
      process.stdout.write("──────────────────────────────────────────────────────────\n\n");
      return;
    }

    const why =
      this.browser.declared === 0
        ? `no test carries the ${APP_SERVER_TAG} tag in this selection`
        : `${this.browser.declared} ${APP_SERVER_TAG} test(s) were selected and ${this.browser.skipped} skipped`;
    const diagnosis =
      `\n  ZERO browser assertions executed — ${why}.\n` +
      "  Nothing here proved that the running product renders anything.\n" +
      "  Start the stack (08-qa/01-e2e/stack/boot_stack.sh) and point\n" +
      "  E2E_BASE_URL at it, or type E2E_ALLOW_NO_APP_SERVER=1 to accept it.\n";

    if (ALLOW_NO_APP_SERVER) {
      process.stdout.write(`\n⚠  WARNING (E2E_ALLOW_NO_APP_SERVER=1 was typed)${diagnosis}`);
      process.stdout.write("──────────────────────────────────────────────────────────\n\n");
      return;
    }
    process.stdout.write(`\n✗  FAILED${diagnosis}`);
    process.stdout.write("──────────────────────────────────────────────────────────\n\n");
    // Overrides a green run. `result.status` is read so a genuinely failed run
    // is not re-labelled as merely censused.
    return { status: result.status === "passed" ? "failed" : result.status };
  }
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-057 / PO ruling 2026-08-11 ("we ahve to prove against human clicking")
// generated: 2026-08-11 by the E2E bring-up lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e`✔ · run_gates 18 PASS · 0 FAIL · 1 SKIP✔ · proved RED before trusted green (both cases in the Tests line above)
// [J2 journey lane 2026-08-15] AMENDED — `worseStatus` replaces the arrival-order
//   status merge. Found by running J2 (the money journey) for the first time: it
//   is SERIAL, it FAILED at step 3, steps 4–11 then skipped, and the receipt
//   recorded `J2: skipped` for a journey that had broken. Ranked now, worst wins.
//   Proved RED before trusted green (law 7): the same run's receipt read
//   `"status": "skipped"` before the change and `"status": "failed"` after, with
//   nothing else in the run altered. G12 rejected both (it demands `passed`), so
//   this corrects what the receipt SAYS, not what the gate does.
//   `npm run typecheck:e2e`✔
// [evidence-integrity lane 2026-08-15] DEF-113 — the receipt left Playwright's
//   purged `outputDir` for `07-frontend/journey-evidence/`, and it MERGES instead
//   of replacing: one immutable shard per run, folded newest-record-per-journey,
//   never a read-modify-write, so a narrow run refreshes its own journeys and two
//   concurrent runs cannot delete each other's evidence. Every record carries its
//   own `recorded_at` so G12 can age each journey separately.
//   PROVED RED before trusted green (law 7), with the PRE-FIX reporter restored
//   from git for the red half and both halves run against real Playwright:
//     · narrow run — before: the receipt read `journeys: ['ZZPROOF-B']`, journey
//       A's record destroyed by a run that never mentioned it; after: both stand.
//     · six CONCURRENT runs — before: `['ZZPROOF-B']`; after: both, 6 shards.
//     · outputDir purge — a receipt placed in the output directory, then one
//       unrelated run: BEFORE `journey-run.json`, AFTER the directory is empty.
//   `10-scripts/gates/g12_selftest.py` keeps the gate half red-provable forever
//   (17 cases, run in .github/workflows/gates.yml). `npm run typecheck:e2e`✔
// exceptions: `eslint` does NOT cover this file — `npm run lint` lints `src` only, so no lint result is claimed here. Reported rather than fixed: widening the lint scope is a 07-frontend-wide change with its own review, and this lane's fix for the same class was the typecheck (tsconfig.e2e.json), which nothing had either
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
