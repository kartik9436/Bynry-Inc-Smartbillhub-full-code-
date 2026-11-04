// ── Trace ──────────────────────────────────────────────
// Change:  CR-039 wave A task 2 — *"offer all ten services at signup"*.
//          CR-063 (2026-09-02) — Fire is the ELEVENTH, and the catalogue is no
//          longer one migration, so this file reads the whole directory.
// Rules:   BR-RAT-024 (the platform sells ELEVEN services, in the seed order —
//          amended 2026-09-02, `fire` APPENDED at 11) ·
//          PO 2026-08-17 (CR-010 B-9 + mandate 4, *"we will provdie full list
//          for all services - they can always select what they want out of it;
//          more is better ; less is contraint"*), re-confirmed 2026-08-27
//          (*"yes I already confirmed it"*).
// ───────────────────────────────────────────────────────
// ⚠ **WHY THIS FILE READS A DJANGO MIGRATION FROM A VITEST SUITE.**
//
// A2 was RULED on 2026-08-17 and the backend was rewritten to match on
// 2026-08-18 — `_validate_signup` checks each posted code against the live
// `Service` catalogue, and `_enable_signup_services` gives all ten a
// `tenant_services` row. **`SIGNUP_SERVICES` stayed at six for ten more days**,
// so a storm-water, solar, thermal or battery utility signed up successfully
// and got every service it sells `enabled=False`, silently, because the chip
// was never on the page.
//
// **Nothing in this repo could see that.** G13 catches an unwired prop, G40 an
// unrendered component, G15 catalogue parity, G18 a dead key — every one of
// them compares a frontend artefact to another frontend artefact. The failure
// was a frontend CONSTANT disagreeing with a DATABASE SEED, and no check in
// thirty-odd gates crosses that boundary. So this one does: it parses the
// service seed out of `tenancy/migrations/` and asserts the chip list IS that
// list, in that order.
//
// A derived list would only ever agree with itself, which is exactly how the
// six survived. **The migrations are the authority; this file is the
// comparison.**
//
// ⚠ **IT READ ONE FILE UNTIL 2026-09-02 AND THE CATALOGUE OUTGREW IT THE DAY
// AN ELEVENTH SERVICE ARRIVED.** `CR-063` appends `fire` in
// `0033_cr063_fire_service.py`, because `0001_initial.py` has run on every
// existing database and cannot gain a row — so a reader pointed at `0001` alone
// would have called a correct chip list wrong, and a lane would have "fixed" it
// by deleting the fire row from the screen. **It now scans the whole migrations
// directory** for either seed shape, in migration-number order, so a TWELFTH
// service appended in `0034` is picked up with no edit here at all. That is the
// same lesson as `DEF-524` — a check whose hardcoded path outlives what it
// names reports PASS through real defects — read forwards for once.
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";
import { SIGNUP_SERVICES } from "./SignupWizard";

// ⚠ A BARE `import … from "node:fs"` PASSES VITEST AND FAILS `tsc` (no
// @types/node in the app tsconfig). Reached the way `serviceNamespace.test.ts`
// and `styles/routeBUtilities.test.ts` already do.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  // CR-063 — the catalogue is more than one migration now, so the directory is
  // scanned rather than one filename read. Typed by hand for the same reason
  // `readFileSync` is: there is no @types/node in the app tsconfig.
  readdirSync(p: string): string[];
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

/** The repo root, from this file's own location — `07-frontend/src/features/tenancy`. */
const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const REPO = nodePath.join(HERE, "..", "..", "..", "..");
const MIGRATIONS_DIR = nodePath.join(REPO, "06-backend", "apps", "tenancy", "migrations");

/**
 * The platform catalogue in seed order, assembled from EVERY migration that
 * declares services.
 *
 * `0001_initial.py` holds `SERVICE_SEED` (the first ten) and
 * `0033_cr063_fire_service.py` holds `FIRE_SEED` (the eleventh); a twelfth
 * would hold its own. Files are read in migration-number order, which is the
 * order the database applies them, so the list this returns is the order a
 * clerk sees. Nothing here is hardcoded to a filename.
 */
function seededServiceCodes(): string[] {
  const files = nodeFs
    .readdirSync(MIGRATIONS_DIR)
    .filter((name) => /^\d{4}_.*\.py$/.test(name))
    .sort();
  // A directory with no migrations at all is a FAILURE, never a skip: a test
  // that quietly passes when it cannot find its authority is the shape of
  // DEF-524 (a gate whose hardcoded path outlived the file it named and
  // reported PASS through six defects).
  expect(files.length, `no migrations found in ${MIGRATIONS_DIR}`).toBeGreaterThan(0);

  const codes: string[] = [];
  for (const name of files) {
    const source = nodeFs.readFileSync(nodePath.join(MIGRATIONS_DIR, name), "utf8");
    const block = /(?:SERVICE_SEED|FIRE_SEED)\s*=\s*\[([\s\S]*?)\]/.exec(source);
    if (!block) continue;
    for (const m of block[1].matchAll(/\(\s*"([a-z_]+)"\s*,/g)) codes.push(m[1]);
  }
  expect(codes.length, `no service seed found under ${MIGRATIONS_DIR}`).toBeGreaterThan(0);
  return codes;
}

describe("CR-039 A2 — signup offers every service the platform sells", () => {
  it("the chip list IS the platform seed, in the seed order", () => {
    const seeded = seededServiceCodes();
    expect(seeded).toHaveLength(11); // BR-RAT-024, amended 2026-09-02 (CR-063)
    expect(SIGNUP_SERVICES.map((s) => s.code)).toEqual(seeded);
  });

  it("fire is APPENDED at position 11 and nothing above it moved", () => {
    // CR-063. The ORDER is the assertion and not only the membership: the seed
    // order IS the ruling (BR-RAT-024), and a fire row INSERTED higher up would
    // renumber ten services on a live customer's database — the one thing
    // CR-063 refuses to do.
    const seeded = seededServiceCodes();
    expect(seeded[10]).toBe("fire");
    expect(seeded.slice(0, 10)).toEqual([
      "electric",
      "water",
      "gas",
      "sewer",
      "trash",
      "storm_water",
      "solar",
      "broadband",
      "thermal_heat",
      "battery",
    ]);
  });

  it("the five that were missing are the five that were missing", () => {
    // Named rather than counted, so a future edit that drops one and adds
    // another cannot keep this green on the arithmetic. `fire` joins the four
    // for exactly the reason the other four are here: it was absent from this
    // screen while the backend served it, which is the silent shape.
    const codes = SIGNUP_SERVICES.map((s) => s.code);
    for (const code of ["storm_water", "solar", "thermal_heat", "battery", "fire"]) {
      expect(codes).toContain(code);
    }
  });

  it("every chip has a label key, and the key resolves to a NAME not a code", () => {
    const catalog = en as Record<string, string>;
    for (const service of SIGNUP_SERVICES) {
      expect(service.labelKey).toBe(`tenancy.signup.service.${service.code}`);
      expect(catalog[service.labelKey]).toBeTruthy();
      expect(catalog[service.labelKey]).not.toBe(service.code);
    }
  });
});
