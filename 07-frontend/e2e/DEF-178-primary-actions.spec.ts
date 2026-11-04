// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-001 (the button this was written for) · every wizard submit
//           Screens: all 23 sidebar destinations
// Rules:    BR-SHL-018/019 (wizard rail + the ONE commit) · US-SHL-009 (a form
//           states what it refused) · hard-won law 2 (built is not wired) ·
//           hard-won law 6 (diff the RUNNING app) · hard-won law 7 (prove a new
//           guard RED before trusting it green)
// Defect:   DEF-178 (2026-08-16, CRITICAL) — "THE 'START THIS RUN' BUTTON IS
//           WIRED TO NOTHING — a utility cannot bill anybody from the screen."
// ───────────────────────────────────────────────────────
// THE GUARD FOR A SILENT NO-OP, WHICH IS INVISIBLE TO EVERYTHING ELSE WE OWN.
//
// DEF-178 reached a running product past 27 of 27 gates, golden 33/33, 3,031
// backend and 1,250 frontend tests. Its own row says why none of them could
// see it: *"G13 catches an unwired PROP; nothing catches a button whose handler
// never calls its endpoint. The frontend tests assert the wizard RENDERS."*
//
// So this check does the one thing none of those do: it PRESSES the buttons, on
// a `load_sample_data` tenant, in a real browser, against the built bundle —
// and fails when a press changes nothing at all.
//
// WHAT COUNTS AS "NOTHING AT ALL", and the three-signal definition is the whole
// design. Plenty of correct primary actions issue no network request: Continue
// moves a wizard step, "+ New account" is a client-side route change, "Record
// payment" opens a dialog, an empty form's submit renders inline errors. A
// guard that demanded a request would fail on all four and be deleted inside a
// week — 10-scripts/03-golden-verify.py already names that outcome: *"the thing
// that actually happens to a permanently-red gate: someone deletes the check"*.
// A press is therefore SILENT only when ALL THREE are true afterwards:
//
//   · no network request was issued, AND
//   · the URL did not change, AND
//   · not one character of document text changed.
//
// Measured against the three real defects this was written from, that
// definition is exactly sharp enough:
//   /billing/run  "Start this run →"  DEF-178   0 reqs · same URL · same DOM
//   /accounts/new "Continue"          this lane 0 reqs · same URL · same DOM
//   /reads/upload "Continue"          this lane 0 reqs · same URL · same DOM
// and it clears every correct action on the other 20 destinations.
//
// PROVED RED BEFORE TRUSTED GREEN, AND THE FIRST RED PROOF FAILED THE GUARD
// RATHER THAN THE PRODUCT — which is the reason law 7 exists. Run against a
// bundle with the WizardFrame fix removed, version one of this file reported
// "13 pressed · 0 silent" and passed. It was sweeping only the 23 sidebar
// destinations, and two of the three real defects are on wizards the sidebar
// does not reach: `/accounts/new` and `/reads/upload` are opened BY a primary
// action, so the sweep pressed the door and never the thing behind it. Hence
// the second pass below. With it, the same broken bundle fails with:
//   SILENT NO-OP:
//   pressing "Continue" on /accounts/new issued no request, changed no URL and
//   changed no text on the page.
//   pressing "Continue" on /reads/upload issued no request, changed no URL and
//   changed no text on the page.
// Restoring the fix and rebuilding turns the same file green. Both runs are
// recorded in DEF-178's defect row.
// ⚠ **THIS CHECK WRITES, AND IT MUST ONLY EVER BE POINTED AT A DISPOSABLE
// TENANT.** Pressing every primary action means pressing the ones that commit:
// on the seeded tenant this run issues `PUT /settings/company`, `POST
// /settings/sample-data/seed` and `POST /deposit-batches/cut`. That is not a
// flaw to be designed out — a check that pressed only the safe buttons would
// have skipped `Start this run`, which is the button it exists for. It is a
// deployment constraint, stated here rather than discovered: run it against a
// `load_sample_data` tenant that can be dropped and reseeded, never against
// anything a customer can see.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

/** Every sidebar destination, including the tabbed children (SHELL_NAV). */
const DESTINATIONS = [
  "/dashboard",
  "/plans-rates",
  "/assets",
  "/premises",
  "/premises/units",
  "/accounts",
  "/reads",
  "/reads/routes",
  "/reads/cycles",
  "/billing",
  "/billing/run",
  "/billing/one-time",
  "/billing/budget",
  "/billing/fix",
  "/payments",
  "/payments/record",
  "/payments/outstandings",
  "/finance",
  "/finance/deposits",
  "/finance/taxes",
  "/finance/export",
  "/reports",
  "/settings",
] as const;

/**
 * ROUTES KNOWN TO CRASH, one line each, and the register can only SHRINK.
 *
 * Same discipline as `10-scripts/gates/i18n_known_gaps.txt`, for the same
 * reason and with the same three properties. NARROW: keyed on the exact route,
 * so the 2nd crashing route fails on the commit that creates it. LOUD: every
 * parked line is printed on every run. EXPIRING: a route listed here that no
 * longer crashes FAILS this spec until the line is deleted, so a dead licence
 * cannot sit waiting.
 *
 * This is a defect backlog, never an allowlist. Adding a line records that
 * shipped code is broken and needs a row in 12-governance/10-defect-log.csv.
 */
const KNOWN_CRASHES: Record<string, string> = {};

interface Press {
  dest: string;
  label: string;
  verdict: string;
}

test("every primary action on every sidebar destination does something", async ({ page }) => {
  test.setTimeout(30 * 60_000);

  let requests: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/")) requests.push(`${r.method()} ${r.url().replace(/.*\/api/, "/api")}`);
  });

  await signIn(page);

  const presses: Press[] = [];
  const silent: string[] = [];
  const crashed: string[] = [];
  const staleLicences: string[] = [];
  const discovered = new Set<string>();

  async function pressEveryPrimaryOn(dest: string): Promise<void> {
    const url = `/${tenant()}${dest}`;
    await page.goto(url);
    await page.waitForLoadState("networkidle").catch(() => undefined);
    await page.waitForTimeout(1200);

    const boundary = (await page.getByText(/Unexpected Application Error/i).count()) > 0;
    const licence = KNOWN_CRASHES[dest];
    if (boundary) {
      if (licence === undefined) crashed.push(`${dest} rendered a React error boundary`);
      else console.log(`PARKED CRASH  ${dest} — ${licence}`);
      return;
    }
    if (licence !== undefined) {
      staleLicences.push(
        `${dest} is listed in KNOWN_CRASHES but no longer crashes — delete that line (it is fixed).`,
      );
    }

    const labels: string[] = await page.locator("main .btn-primary").evaluateAll((els) =>
      els
        .filter(
          (e) =>
            !(e as HTMLButtonElement).disabled && (e as HTMLElement).offsetParent !== null,
        )
        .map((e) => (e.textContent ?? "").trim())
        .filter((s) => s.length > 0),
    );

    for (const label of [...new Set(labels)]) {
      // Land on a clean copy of the screen for every button: one press must not
      // be judged against the state the previous press left behind.
      await page.goto(url);
      await page.waitForLoadState("networkidle").catch(() => undefined);
      await page.waitForTimeout(1000);

      const button = page.locator("main .btn-primary", { hasText: label }).first();
      if ((await button.count()) === 0) continue;
      if (!(await button.isEnabled().catch(() => false))) continue;

      const urlBefore = page.url();
      const textBefore = await page.locator("body").innerText();
      requests = [];
      await button.click({ timeout: 10_000 }).catch(() => undefined);
      await page.waitForTimeout(2200);

      const textAfter = await page.locator("body").innerText();
      const navigated = page.url() !== urlBefore;
      const changed = textAfter !== textBefore;
      const requested = requests.length > 0;

      let verdict: string;
      if (/Unexpected Application Error/i.test(textAfter)) {
        verdict = "CRASHED";
        crashed.push(`pressing "${label}" on ${dest} rendered a React error boundary`);
      } else if (requested) {
        verdict = `request (${requests[0]})`;
      } else if (navigated) {
        verdict = "navigated";
      } else if (changed) {
        verdict = "answered on screen";
      } else {
        verdict = "SILENT NO-OP";
        silent.push(
          `pressing "${label}" on ${dest} issued no request, changed no URL and changed no text on the page.`,
        );
      }
      presses.push({ dest, label, verdict });

      // ⚠ ONE LEVEL DEEPER, AND IT IS NOT OPTIONAL — IT IS WHERE TWO OF THE
      // THREE REAL DEFECTS LIVED. The sidebar reaches list screens; their
      // primary action is "+ New account" / "↑ Upload reads", and the DEAD
      // button is the Continue on the wizard those OPEN. A sweep that stops at
      // the sidebar presses the door and never the thing behind it. The first
      // version of this file did exactly that and reported "0 silent" against a
      // build with two silent buttons in it.
      if (navigated) {
        const landed = page.url().split(`/${tenant()}`)[1]?.split("?")[0] ?? "";
        if (landed !== "" && !DESTINATIONS.includes(landed as (typeof DESTINATIONS)[number])) {
          discovered.add(landed);
        }
      }
    }
  }

  for (const dest of DESTINATIONS) {
    await pressEveryPrimaryOn(dest);
  }
  // The screens the sidebar's own buttons opened — the wizards.
  const secondPass = [...discovered];
  console.log("\nreached by a primary action, sweeping those too:", JSON.stringify(secondPass));
  for (const dest of secondPass) {
    await pressEveryPrimaryOn(dest);
  }

  console.log("\n──────── primary actions pressed ────────");
  for (const p of presses) console.log(`${p.verdict.padEnd(34)} ${p.dest}  "${p.label}"`);
  console.log(`──────── ${presses.length} pressed · ${silent.length} silent · ${crashed.length} crashed ────────`);

  // A press that MUST exist: if the billing wizard ever stops offering its
  // start control, this spec would otherwise pass by pressing nothing — the
  // "job whose only outcomes are passed and passed" this suite has met before.
  expect(
    presses.some((p) => p.dest === "/billing/run" && /start this run/i.test(p.label)),
    "the bill run wizard must still offer 'Start this run' — DEF-178's own button",
  ).toBe(true);
  expect(presses.length, "no primary action was pressed at all").toBeGreaterThan(10);

  expect(staleLicences, staleLicences.join("\n")).toHaveLength(0);
  expect(crashed, crashed.join("\n")).toHaveLength(0);
  expect(silent, `SILENT NO-OP:\n${silent.join("\n")}`).toHaveLength(0);
});
