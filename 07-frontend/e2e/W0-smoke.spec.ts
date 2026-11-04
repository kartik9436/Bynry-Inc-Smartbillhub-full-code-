// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-001 (EP-SHL-01 §Stories — shell chrome)  Screens: shell-chrome
// Rules:    BR-SHL-001 (sidebar, canonical module order) · BR-SHL-030 (data-driven language catalogs) · B12 r3 §5 (FI-06 harness)
// ───────────────────────────────────────────────────────
// FI-06 W0 smoke — NOT a journey (no J-ID: journeys activate per the wiring
// index; see e2e/README.md). This spec proves the HARNESS end-to-end:
//   1. boot the real app and see the shell (browser half — skips honestly
//      when no app server answers, so CI stays green before the stack exists);
//   2. flip the language through the i18n handle (src/i18n/index.ts) until the
//      real switcher UI lands with the S48 packet;
//   3. read the expectation CSV (server-free half — ALWAYS runs, so a broken
//      loader is red even with no app anywhere).
import { expect, test } from "@playwright/test";

import { bootApp, skipUnlessAppServer } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";
import { loadMoneyTriples, moneyTriple } from "./support/expected";

// BR-SHL-001: the 11 modules in canonical order (en catalog labels).
//
// CORRECTED 2026-08-11, and how it was wrong matters more than what it said.
// This array carried Settings SECOND — the order BR-SHL-001 held when this file
// was written on 2026-08-09. **The PO amended the rule on 2026-08-10** ("Setting
// should be at last on nav bar"), the shell moved Settings to LAST that day, and
// this expectation stayed stale for a day and a half **because it had never once
// executed**: `skipUnlessAppServer` skipped it on every run, since nothing in
// this repo started an app server. The first run against a live stack failed it
// immediately, quoting both orders. That is DEF-057 in one test — a check whose
// only outcomes were "skipped" and "skipped" is not a check — and it is why the
// census in `support/census.ts` now fails a run that executed no browser
// assertion. Logged as DEF-059.
const SIDEBAR_MODULES_EN = [
  "Dashboard",
  "Plans & Rates",
  "Assets",
  "Premises",
  "Accounts",
  "Reads",
  "Billing",
  "Payments",
  "Finance",
  "Reports",
  "Settings",
];

// The same eleven from the es catalog — the assertion that the language switch
// re-renders the WHOLE list rather than one label. Same correction as above:
// this file used to assert `last() === "Informes"`, which was Reports sitting
// last under the pre-amendment order.
const SIDEBAR_MODULES_ES = [
  "Panel",
  "Planes y tarifas",
  "Activos",
  "Inmuebles",
  "Cuentas",
  "Lecturas",
  "Facturación",
  "Pagos",
  "Finanzas",
  "Informes",
  "Configuración",
];

// Tagged @app-server (DEF-057, 2026-08-11) so `support/census.ts` counts these
// assertions SEPARATELY from the server-free half below. Without the split, the
// CSV loader's always-green count masks a browser half that executed nothing —
// which is the exact shape of the defect the census exists to stop.
test.describe("W0 smoke — the app shell boots in the harness", { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);

  test("sidebar renders the 11 modules in BR-SHL-001 canonical order", async ({ page }) => {
    await bootApp(page);
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    const labels = nav.locator(".side-item .side-label");
    await expect(labels).toHaveCount(11);
    await expect(labels).toHaveText(SIDEBAR_MODULES_EN);
  });

  test("language switch re-renders the shell from another catalog (BR-SHL-030)", async ({
    page,
  }) => {
    await bootApp(page);
    // No switcher UI exists yet (FI-03 switcher / S48 packet) — drive the
    // i18n singleton through its window handle; react-i18next re-renders.
    await page.evaluate(() => {
      const handle = (
        window as Window & {
          __SMARTBILLHUB_I18N__?: { changeLanguage: (lng: string) => Promise<unknown> };
        }
      ).__SMARTBILLHUB_I18N__;
      if (handle === undefined) {
        throw new Error("i18n window handle missing — see src/i18n/index.ts");
      }
      return handle.changeLanguage("es");
    });
    // The es catalog takes over: nav label AND every module label re-render.
    const nav = page.getByRole("navigation", { name: "Navegación principal" });
    await expect(nav.locator(".side-item .side-label")).toHaveText(SIDEBAR_MODULES_ES);
  });
});

test.describe("W0 smoke — expectation-CSV loader (the money-assertion source)", () => {
  // Server-free: these never skip — they ARE the CI signal that the harness
  // is wired even where no app or browser can run.

  test("loads all 245 machine-computed money triples", () => {
    expect(loadMoneyTriples()).toHaveLength(245);
  });

  test("money figures arrive as exact decimal strings — rule 2, never floats", () => {
    const triple = moneyTriple("flat", "cycle", "full");
    // Frozen figures straight from the dataset — never hand math (B12 §6b).
    expect(triple.total).toBe("97.41");
    expect(triple.paid).toBe("97.41");
    expect(triple.outstanding).toBe("0.00");
    expect(triple.next_late_fee).toBe("0.00");
  });

  test("quoted notes fields (embedded commas) parse per RFC-4180", () => {
    const backbill = moneyTriple("flat", "backbill", "full");
    expect(backbill.notes).toBe("3 months, period-labeled groups, per-version pricing (BR-BIL-018)");
    expect(backbill.total).toBe("292.23");
  });

  test("an expectation the dataset does not carry throws loudly", () => {
    expect(() => moneyTriple("flat", "cycle", "no-such-outcome")).toThrow(
      /no money-triples.csv row/,
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-001@b16a4de (harness proof rides the shell story snapshot)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ playwright 4 pass · 2 skip (no app server; browser binaries un-downloadable in the authoring sandbox — CDN policy-denied) · [E2E bring-up lane 2026-08-11] the browser half EXECUTED for the first time against a live stack and FAILED (DEF-059 — stale sidebar order); corrected and re-run 10 passed · 22 app-server assertions · 8 server-free
// exceptions: none · [E2E bring-up lane 2026-08-11] the header's line 8 claim — *"skips honestly when no app server answers, so CI stays green before the stack exists"* — is NO LONGER the posture. It skips honestly, and the RUN now fails, because a suite that executed zero browser assertions proved nothing (DEF-057). The describe carries @app-server so support/census.ts can tell the two halves apart.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
