// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-4283 — nine screens outside the shell still read the
//          admin-only `GET /settings/regional`, so the `DEF-SHL-4272` Billing
//          Clerk lockout survived in a narrower form.
//          Parent: DEF-SHL-4272 (a clerk could not use the product AT ALL,
//          2026-08-21 → 2026-09-06, sixteen days).
// Rules:   BR-SHL-252 as amended 2026-09-06 (the values a screen needs to DRAW
//          ITSELF are served to any signed-in member of the tenant) · A4
//          `settings_lookups` (a Billing Clerk has NO cell — unchanged) ·
//          DEF-196 (the gate this must never widen) · hard-won law 2's mirror
//          (a hold with no expiry test is a promise nobody is keeping) ·
//          hard-won law 7 (a check that cannot cover its whole subject must
//          print what it SKIPPED beside what it checked)
// ───────────────────────────────────────────────────────
//
// WHICH COMPONENTS READ AN ADMIN-ONLY ENDPOINT — ENUMERATED FROM THE SOURCE
// TREE, NEVER FROM A LIST TYPED BY HAND.
//
// ⚠ **THIS FILE EXISTS BECAUSE THE SAME DEFECT ESCAPED TWICE, THE SECOND TIME
// FROM ITS OWN FIX.** `DEF-SHL-4272` moved the app shell's two boot reads to
// `GET /shell/display`, which every signed-in tenant role may make. It moved
// nothing else. `GET /settings/regional` is `SettingsReadAnyWriteSystemAdmin` —
// `{system_admin, executive}` — so every OTHER component still calling it went
// on answering a Billing Clerk `403 AUTH-002`:
//
//   · `Reports → By premises` (A4 `reports`, Clerk **Run**) gates its report on
//     `period !== null`, so for a clerk the report was never requested at all;
//     what they saw was *"Set the fiscal year start to see the current
//     period."* at a tenant whose fiscal year start IS set.
//   · `Payments → Refunds` (A4 `payments_record`, Clerk **Full**, and the
//     screen a clerk RAISES refunds on) drew the same sentence in its header,
//     through `useFinancePeriod`, which SEVEN screens share.
//
// **Nothing looked for them.** No gate asks which component reads an admin-only
// endpoint, and every other frontend suite passes formatting as a prop or seeds
// the query cache, so a 403 from this endpoint is invisible exactly as it was
// for the shell. The lane that fixed the shell named FOUR of these in its
// report; a count at the tip found different files again. **A report is not the
// repo.** This is.
//
// ── WHAT WOULD MAKE THIS CHECK PASS WRONGLY (law 7, habit 2) ───────────────
// A glob that matches nothing, or a regex that finds nothing, would compare an
// EMPTY set against the allow-list and — if the allow-list were also read from
// the same empty scan — tick. Three controls below stop that, and each is
// asserted BEFORE the real question is asked:
//   (1) the glob must match a four-figure number of files;
//   (2) the scan must find the two Settings screens, which are known callers
//       and are never going to move;
//   (3) the allow-list is a literal written here, so an empty scan fails it.
// And the count of files the scan CANNOT see is printed beside the count it
// read, because a declared blind spot with no number attached is
// indistinguishable from an empty one.
import { describe, expect, it } from "vitest";

/** Every `.ts` and `.tsx` under `src/`, source text, comments included. */
function sources(): Record<string, string> {
  // `import.meta.glob`, NOT `node:fs`: the front end's tsconfig carries no node
  // types, so a `readFileSync` draft runs green under vitest and fails
  // `tsc --noEmit` (four other suites in this repo say the same in their own
  // comments). The pattern must be a static literal, hence two calls.
  const tsx = import.meta.glob("../**/*.tsx", {
    query: "?raw",
    import: "default",
    eager: true,
  }) as Record<string, string>;
  const ts = import.meta.glob("../**/*.ts", {
    query: "?raw",
    import: "default",
    eager: true,
  }) as Record<string, string>;
  return { ...tsx, ...ts };
}

/**
 * Source with comments removed.
 *
 * ⚠ **THIS IS THE WHOLE DIFFERENCE BETWEEN NINE AND FOUR.** The register row
 * for this defect names nine files, counted by grepping the tip for
 * `/settings/regional`. Five of them — `meteringShared`, `financeShared`,
 * `JournalEntryModal`, `AccrualsPanel` and `portal/components/regional.tsx` —
 * name the endpoint in PROSE and make no such request: they take their values
 * from the shell's context or the portal's own payload. Counting a docstring as
 * a caller would send the next lane to "fix" five files that are already right,
 * and — worse — would push them to delete the explanations to make a check go
 * green.
 */
function code(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/**
 * `src/`-relative, so a failure message names the file a person would open.
 *
 * ⚠ `import.meta.glob` returns paths relative to THIS file, so a sibling in
 * `src/api/` comes back as `./endpoints.ts` and everything else as
 * `../features/…`. Stripping only `../` left `./endpoints.ts` in the offender
 * list, where it read as a real finding — the file that DEFINES the call being
 * reported as making it. Caught by running the check.
 */
function tidy(path: string): string {
  if (path.startsWith("./")) return `api/${path.slice(2)}`;
  return path.replace(/^\.\.\//, "");
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · WHO CALLS THE ADMIN-ONLY REGIONAL READ
// ══════════════════════════════════════════════════════════════════════════

/**
 * The files allowed to call `getRegionalSettings`, and WHY each one is.
 *
 * The first two are the Settings screens that EDIT these values: they need the
 * fields `/shell/display` deliberately drops and they are the admin surface by
 * definition. **`US-TEN-009 TC-5` still refuses a clerk at every settings view
 * and this file must never change that.**
 *
 * The last two are a STATED HOLD with its reason (hard-won law 2's mirror: a
 * hold with no expiry test is a promise nobody is keeping). Between them they
 * need `current_period.close_by` — the hand-off deadline, which is `close_day`
 * in another shape — and the raw `fy_start_month` / `fy_start_day`. Both are
 * gated on A4's `finance_reconcile_export` cell, `{System Admin, Executive}`,
 * which is exactly the pair `SettingsReadAnyWriteSystemAdmin` serves, so no
 * role that can open them is refused the read. Section 2 below is the test that
 * fires the day that stops being true.
 */
const REGIONAL_CALLERS_ALLOWED = [
  "features/tenancy/SettingsRegionalTab.tsx",
  "features/tenancy/SettingsRulePageView.tsx",
  "features/ledger/RevenueArPage.tsx",
  "features/payments/BadDebtPanel.tsx",
];

describe("DEF-SHL-4283 — who reads the admin-only GET /settings/regional", () => {
  it("scans the whole source tree and says what it could not see", () => {
    const all = sources();
    const scanned = Object.keys(all);
    // (1) The glob must have matched a real tree. An empty one makes every
    // assertion below vacuously true.
    // 853 files at the time of writing (2026-09-06). The floor is deliberately
    // well below that: this assertion is here to catch a glob that matched
    // NOTHING, not to police the tree's size, and a floor set at today's count
    // would go red on the first file anyone deletes.
    expect(scanned.length, "the glob matched no source files at all").toBeGreaterThan(400);
    // What this check CANNOT see, stated with a number rather than left to be
    // assumed (law 7's fifth shape). A request built from a variable, a path
    // assembled at runtime, or a call made from a `.js`/`.mjs` file outside
    // `src/` would not appear here.
    const blind = scanned.filter((p) => !/\.tsx?$/.test(p));
    // eslint-disable-next-line no-console
    console.log(
      `[DEF-SHL-4283] scanned ${scanned.length} files under src/ · ` +
        `outside this scan: ${blind.length} non-.ts/.tsx matches, plus every ` +
        `.mjs walkthrough in 10-scripts/ and any request whose path is built ` +
        `from a variable rather than written as a literal`,
    );
  });

  it("finds the two Settings screens — proof the scan can see a caller at all", () => {
    // (2) Without this, a regex that matched nothing would report "no offenders"
    // and tick. These two files are known callers and are not going to move:
    // they are the screens that EDIT the settings.
    const hits = Object.entries(sources())
      .filter(([path]) => !path.includes(".test."))
      .filter(([, text]) => /getRegionalSettings\s*\(/.test(code(text)))
      .map(([path]) => tidy(path));
    expect(hits).toContain("features/tenancy/SettingsRegionalTab.tsx");
    expect(hits).toContain("features/tenancy/SettingsRulePageView.tsx");
  });

  it("no component outside the allow-list calls getRegionalSettings", () => {
    const callers = Object.entries(sources())
      .filter(([path]) => !path.includes(".test."))
      // `endpoints.ts` DEFINES it; defining is not calling.
      .filter(([path]) => tidy(path) !== "api/endpoints.ts")
      .filter(([, text]) => /getRegionalSettings\s*\(/.test(code(text)))
      .map(([path]) => tidy(path))
      .sort();

    expect(
      callers,
      "a component reads the Admin/Executive GET /settings/regional. If a " +
        "Billing Clerk can reach this screen they get 403 AUTH-002 and the " +
        "screen breaks silently — that is DEF-SHL-4272 all over again. Draw " +
        "the period, the formats and the branding from GET /shell/display " +
        "instead; only add a file here with the reason it cannot.",
    ).toEqual([...REGIONAL_CALLERS_ALLOWED].sort());
  });

  it("no component builds the admin-only path by hand either", () => {
    // The allow-list above is by FUNCTION NAME, so a component calling
    // `client.get("/settings/regional")` directly would walk straight past it.
    const offenders = Object.entries(sources())
      .filter(([path]) => !path.includes(".test."))
      .filter(([path]) => tidy(path) !== "api/endpoints.ts")
      // ⚠ **A SCREEN ADDRESS IS NOT A READ (2026-10-02).** `d6a2ae5f8`
      // (DEF-SHL-5666, 2026-09-17) gave the shell's *time zone not set* warning
      // a LINK to the Settings → Regional screen —
      // `tenantPath("/settings/regional")` — and this case went red on it for
      // two weeks while no request was made at all. It was looking at the wrong
      // thing (law 7): the hazard is a GET, and a route the router resolves
      // client-side reaches no API. So an address built by `tenantPath(…)` is
      // removed before the search; every other literal still counts.
      .filter(([, text]) =>
        /["'`]\/settings\/regional["'`]/.test(
          code(text).replace(/tenantPath\(\s*["'`]\/settings\/regional["'`]\s*\)/g, ""),
        ),
      )
      .map(([path]) => tidy(path));
    expect(offenders, "a component requests /settings/regional as a literal path").toEqual([]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE HOLD'S EXPIRY TEST — hard-won law 2's mirror
// ══════════════════════════════════════════════════════════════════════════
//
// The two held files above are safe because of WHERE they are mounted, not
// because of what they read. `RevenueArPage` gates on A4's
// `finance_reconcile_export` cell and `BadDebtPanel` is mounted only inside it.
// **Both of those facts can change in a commit that touches neither file's
// read**, and then the hold is silently false — the shape `DEF-CWP-3925`
// records, where five portal cards went on refusing over screens that had
// landed days earlier.
//
// So the reasons are asserted, by name, here.

describe("DEF-SHL-4283 — the reason the two held files are safe is still true", () => {
  it("BadDebtPanel is mounted by RevenueArPage and by nothing else", () => {
    const mounts = Object.entries(sources())
      .filter(([path]) => !path.includes(".test."))
      .filter(([path]) => !tidy(path).startsWith("features/payments/BadDebtPanel"))
      .filter(([, text]) => /<BadDebtPanel[\s/>]/.test(code(text)))
      .map(([path]) => tidy(path));
    expect(
      mounts,
      "BadDebtPanel reads the Admin/Executive GET /settings/regional for the " +
        "raw fiscal-year anchor. That is only safe while its one mount point " +
        "is behind A4's finance_reconcile_export cell. Mounting it anywhere a " +
        "Billing Clerk can reach breaks it the way Reports → By premises broke.",
    ).toEqual(["features/ledger/RevenueArPage.tsx"]);
  });

  it("RevenueArPage still gates on the finance cell, which excludes the clerk", () => {
    const page = code(
      Object.entries(sources()).find(
        ([path]) => tidy(path) === "features/ledger/RevenueArPage.tsx",
      )?.[1] ?? "",
    );
    expect(page.length, "RevenueArPage.tsx was not found by the scan").toBeGreaterThan(0);
    expect(
      /useAccessCell\(\s*FINANCE_PERMISSION/.test(page),
      "RevenueArPage no longer gates on FINANCE_PERMISSION, so a Billing " +
        "Clerk may now reach it — and it reads the Admin/Executive settings " +
        "endpoint. Move it to GET /shell/display.",
    ).toBe(true);
    // And the cell itself is the finance one, not a widened alias.
    const shared = code(
      Object.entries(sources()).find(
        ([path]) => tidy(path) === "features/ledger/financeShared.tsx",
      )?.[1] ?? "",
    );
    expect(shared).toContain('FINANCE_PERMISSION = "finance_reconcile_export"');
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE MOVED SCREENS READ THE ROUTE EVERY ROLE MAY READ
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-SHL-4283 — the screens a clerk reaches read GET /shell/display", () => {
  it("useFinancePeriod — the hook seven Finance-frame screens share", () => {
    const chrome = code(
      Object.entries(sources()).find(
        ([path]) => tidy(path) === "features/ledger/financeChrome.tsx",
      )?.[1] ?? "",
    );
    expect(chrome.length, "financeChrome.tsx was not found by the scan").toBeGreaterThan(0);
    expect(chrome).toContain("queryKeys.shellDisplay");
    expect(chrome).toContain("getShellDisplay(client)");
    expect(chrome).not.toContain("getRegionalSettings");
  });

  it("the by-premises report — A4 gives a Billing Clerk Run on reports", () => {
    const report = code(
      Object.entries(sources()).find(
        ([path]) => tidy(path) === "features/reports/ByPremisesReportPage.tsx",
      )?.[1] ?? "",
    );
    expect(report.length, "ByPremisesReportPage.tsx was not found by the scan").toBeGreaterThan(0);
    expect(report).toContain("queryKeys.shellDisplay");
    expect(report).not.toContain("getRegionalSettings");
  });

  it("Payments → Refunds reads no period at all, and never the admin-only route", () => {
    // Named explicitly because this is the clerk's screen in the payments
    // module and the one the register row did not name.
    //
    // ⚠ **THIS CASE ASSERTED `useFinancePeriod` UNTIL 2026-10-02 AND WAS RED
    // FROM 2026-09-23.** `CR-138-BRC07` `P4.10` (`fb3526105`) moved Refunds out
    // of the Finance frame into payments, and the period left with the frame:
    // *"A refunds list is NOT period-scoped either way"* (the page's own note).
    // The hazard this case guards — a clerk's screen reading the Admin/Executive
    // `GET /settings/regional` — is now asserted directly instead of through
    // the hook that used to avoid it.
    const refunds = code(
      Object.entries(sources()).find(
        ([path]) => tidy(path) === "features/payments/RefundsPage.tsx",
      )?.[1] ?? "",
    );
    expect(refunds.length, "RefundsPage.tsx was not found by the scan").toBeGreaterThan(0);
    expect(refunds).not.toContain("getRegionalSettings");
    expect(refunds).not.toContain("queryKeys.regionalSettings");
    expect(refunds).toContain("useAccessCell(PAYMENTS_PERMISSION");
  });
});
