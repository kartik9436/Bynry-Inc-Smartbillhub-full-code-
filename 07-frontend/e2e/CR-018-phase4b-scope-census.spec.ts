// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 4b — the layout containers (PO, "start 4b")
// Rules:    CR-018 §6 "Every screen renders identically to its pre-migration
//           self" · hard-won law 6 (diff the running app; no gate reads output)
// Impacts:  nothing in src/ — an instrument, not a screen.
// ───────────────────────────────────────────────────────
//
// WHAT THIS MEASURES AND WHY IT IS THE WHOLE OF PHASE 4b's FIRST STEP
//
// `.met-panel` is the biggest remaining shared class (46 components) and Phase
// 4a reported it as the hard one because `components/FormModal.css` styles
// `input`, `select`, `textarea`, `label:has(> …)` and `input[type=date]` AS ITS
// DESCENDANTS — eight rules a parent selector can express and Route B cannot.
//
// ⚠ THAT REPORT WAS WRONG, AND READING THE RULE IS WHAT MADE IT WRONG. Those
// selectors name THREE scopes, not one:
//
//     .view input:not(…), .view select, .view textarea,
//     .fin-page input:not(…), .fin-page select, .fin-page textarea,
//     .met-panel input:not(…), .met-panel select, .met-panel textarea { … }
//
// and the rule's own comment says what they are for: `<main className="view">`
// *"wraps every screen inside the shell"* and is *"the scope this always
// wanted"*; `.fin-page`/`.met-panel` were *"kept as well for anything rendered
// outside the shell"*. They are a BELT-AND-BRACES fallback, not `.met-panel`'s
// styling. If every `.met-panel` and every `.fin-page` in the product sits
// inside `.view`, those six selector lines style nothing that `.view` does not
// already style, and `.met-panel` is a plain four-declaration leaf class that
// migrates like any other.
//
// Statically that looks certain: all 46 `.met-panel` users and all 14
// `.fin-page` users are routed feature screens under the shell's `<Outlet/>`,
// and the repo contains no `createPortal`. **But "I read the CSS and it looked
// complete" is the exact sentence this rule's own comment records as the reason
// its first fix missed every screen the PO photographed.** So it is measured.
//
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && npm run build && \
//       E2E_BASE_URL=http://127.0.0.1:8123 CR018_OUT=/tmp/p4b/before \
//       npx playwright test e2e/CR-018-phase4b-scope-census.spec.ts
//
// ⚠ REBUILD FIRST, and write BEFORE and AFTER to DIFFERENT directories — a
// second run into the same one overwrites the baseline and the diff then passes
// vacuously.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { baseUrl, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const OUT = process.env.CR018_OUT ?? "/tmp/p4b/census";

/** Screens chosen for FORM-CONTROL density inside `.met-panel` / `.fin-page`,
 *  because controls are the only thing the eight rules touch. */
const SCREENS = [
  { name: "reads", path: "/reads" },
  { name: "payments", path: "/payments" },
  { name: "payments-outstandings", path: "/payments/outstandings" },
  { name: "payments-deposits", path: "/payments/deposits" },
  { name: "payments-collections", path: "/payments/collections" },
  { name: "finance-gl", path: "/finance/gl?view=chart" },
  { name: "finance-close", path: "/finance/close" },
  { name: "finance-revenue", path: "/finance/revenue" },
  { name: "reports-account-ledger", path: "/reports/account-ledger" },
  { name: "reports-library", path: "/reports" },
  { name: "dashboard", path: "/dashboard" },
  { name: "accounts", path: "/accounts" },
  { name: "bills", path: "/billing/bills" },
  { name: "premises-detail", path: "/premises" },
  { name: "audit-retention", path: "/settings/audit-log" },
  // ⚠ ADDED FOR PHASE 4b-3, AND THE REASON IS THE POINT. The first run of the
  // kicker/note migration reported "0 differences" over FIVE kickers and FOUR
  // notes — for 153 migrated sites. Those two live on the settings screens, and
  // the walk did not go there. A clean diff over 9 of 153 elements is not a
  // proof, it is the same vacuous-walk shape this file already carries a
  // warning about, one migration later.
  { name: "settings-company", path: "/settings/company" },
  { name: "settings-users2", path: "/settings/users" },
  { name: "settings-services2", path: "/settings/services" },
  { name: "settings-routes2", path: "/settings/routes-cycles" },
  { name: "settings-accounting2", path: "/settings/accounting" },
  { name: "settings-reference2", path: "/settings/reference-data" },
  { name: "settings-templates2", path: "/settings/reference-data/templates" },
  { name: "settings-numbering", path: "/settings/numbering" },
  { name: "settings-notifications", path: "/settings/notifications" },
  { name: "checklist", path: "/checklist" },
] as const;

/** Every property the eight rules can set, plus the ones a wrong scope moves. */
const PROPS = [
  "min-height", "height", "padding", "font-size", "font-family", "color",
  "caret-color", "background-color", "border-top-width", "border-top-style",
  "border-top-color", "border-radius", "appearance", "background-image",
  "display", "flex-direction", "gap",
  // Phase 4b-2 — the panel's own four declarations and the heading rule.
  "margin-top", "margin-right", "margin-bottom", "margin-left",
  "border-right-width", "border-bottom-width", "border-left-width",
  "font-weight", "line-height", "letter-spacing",
  // Phase 4b-3 — everything the two leaf text classes set.
  "text-transform", "text-decoration-line",
] as const;

test.describe("CR-018 Phase 4b — is `.met-panel` a styling scope or a leaf class?", () => {
  test("census every form control, and where it sits @app-server", async ({ page }) => {
    test.setTimeout(600_000);
    await signIn(page);
    mkdirSync(OUT, { recursive: true });

    const census: Record<string, unknown> = {};
    let controls = 0;
    let panels = 0;
    let leafTotal = 0;
    const outsideView: string[] = [];
    const perScreen: string[] = [];

    for (const screen of SCREENS) {
      await page.goto(`${baseUrl()}/${tenant()}${screen.path}`);
      await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => undefined);
      await page.waitForTimeout(1_500);

      const found = await page.evaluate((props) => {
        const rows: { key: string; style: string }[] = [];
        const scopes: string[] = [];

        // (1) Does every `.met-panel` / `.fin-page` sit inside `.view`? This is
        //     the question the deletion turns on.
        for (const cls of [".met-panel, [data-panel]", ".fin-page"]) {
          for (const el of Array.from(document.querySelectorAll(cls))) {
            if (el.closest("main.view") === null) {
              scopes.push(`${cls} outside .view: ${el.className}`);
            }
          }
        }

        // (2) Every control the eight rules can reach, PLUS the panels
        //     themselves and the headings and hints inside them — Phase 4b-2
        //     migrates `.met-panel` and `.met-panel h3` to utilities, and a
        //     census that watched only form controls would call that a no-op
        //     while every panel's border and padding moved.
        const nodes = Array.from(
          document.querySelectorAll<HTMLElement>(
            // ⚠ BOTH FORMS, deliberately. After the migration a panel is
            // `[data-panel]` and no longer carries `.met-panel`, so a selector
            // naming only the class would find NOTHING in the "after" run and
            // the diff would report a changed element set instead of comparing
            // anything. The union is what makes before and after line up.
            "input, select, textarea, label, .met-panel, [data-panel], " +
              ".met-panel h3, [data-panel] h3, .met-panel-hint, " +
              // Phase 4b-3 — the leaf text classes. Both forms again: after the
              // migration a kicker is `[data-kicker]` and carries no class.
              ".kicker, [data-kicker], .settings-note, [data-note], " +
              // Phase 4b-4 — all three of the remaining five, in ONE census.
              ".settings-refusal, [data-refusal], .met-table, [data-plaintable], " +
              ".met-table th, [data-plaintable] th, .met-table td, [data-plaintable] td, " +
              ".met-link, [data-inlinelink]",
          ),
        ).filter((el) => {
          const s = getComputedStyle(el);
          return s.display !== "none" && s.visibility !== "hidden";
        });
        nodes.forEach((el, i) => {
          const s = getComputedStyle(el);
          // A stable key: tag + ordinal + the scopes it is in, so the same
          // control is comparable across two runs of the app.
          const inMet = el.closest(".met-panel, [data-panel]") !== null;
          const inFin = el.closest(".fin-page") !== null;
          const inView = el.closest("main.view") !== null;
          const isPanel = el.classList.contains("met-panel") || el.dataset.panel === "";
          const leaf =
            el.classList.contains("kicker") || el.dataset.kicker === ""
              ? "|KICKER"
              : el.classList.contains("settings-note") || el.dataset.note === ""
                ? "|NOTE"
                : el.classList.contains("settings-refusal") || el.dataset.refusal === ""
                  ? "|REFUSAL"
                  : el.classList.contains("met-table") || el.dataset.plaintable === ""
                    ? "|TABLE"
                    : el.classList.contains("met-link") || el.dataset.inlinelink === ""
                      ? "|LINK"
                      : "";
          rows.push({
            key: `${el.tagName.toLowerCase()}#${i}${isPanel ? "|PANEL" : ""}${leaf}${inView ? "|view" : ""}${inMet ? "|met" : ""}${inFin ? "|fin" : ""}`,
            style: props.map((p) => `${p}:${s.getPropertyValue(p)}`).join(";"),
          });
        });
        const panelCount =
          document.querySelectorAll(".met-panel, [data-panel]").length +
          document.querySelectorAll(".fin-page").length;
        const leafCount = document.querySelectorAll(
          ".kicker, [data-kicker], .settings-note, [data-note], " +
            ".settings-refusal, [data-refusal], .met-table, [data-plaintable], " +
            ".met-link, [data-inlinelink]",
        ).length;
        return { rows, scopes, panelCount, leafCount };
      }, PROPS as unknown as string[]);

      census[screen.name] = found.rows;
      controls += found.rows.length;
      panels += found.panelCount;
      leafTotal += found.leafCount;
      perScreen.push(
        `${screen.name}: ${found.panelCount} panel(s), ${found.leafCount} leaf/leaves, ${found.rows.length} element(s)`,
      );
      outsideView.push(...found.scopes.map((s) => `${screen.name}: ${s}`));
    }

    writeFileSync(join(OUT, "census.json"), JSON.stringify(census, null, 2));
    writeFileSync(join(OUT, "outside-view.json"), JSON.stringify(outsideView, null, 2));

    // ⚠ NOT AN EMPTY LOOP, AND THE FIRST DRAFT WAS ONE FOR THE QUESTION IT ASKS.
    // It counted CONTROLS and asserted no panel sits outside `.view` — but a
    // screen that renders NO PANEL satisfies that trivially, and nothing said
    // how many panels the walk had actually seen. The first run reported a
    // clean result over 8 screens holding just 6 controls inside a
    // `.met-panel`. The panel count is the denominator of this proof, so it is
    // counted and asserted.
    expect(controls, "no form controls were found at all — the walk did not reach the screens")
      .toBeGreaterThan(30);
    // The leaf classes get the same treatment as the panels: a migration is not
    // proved by a walk that never met the thing it migrated.
    //
    // ⚠ THE FLOOR IS 20 AND THE MIGRATION WAS 153 SITES — THE GAP IS REAL AND
    // WORTH STATING RATHER THAN HIDING. A source SITE is not a rendered
    // ELEMENT: most kickers and notes live inside wizard steps, modals and
    // unopened tabs, so a walk of 25 top-level screens meets **26** of them, and
    // that is the ceiling of what any browser census here can see. The first
    // draft of this assertion demanded 40 and failed on a healthy tree — a
    // threshold picked from the source count rather than measured.
    //
    // So this floor does the job it can do: it catches a walk that has gone
    // BLIND (a route renamed, a sign-in that silently failed, a selector that
    // stopped matching), which is the failure that makes every other assertion
    // here vacuous. The other 127 sites are covered by `tsc` and by the fact
    // that one codemod wrote all of them the same way — which is weaker, and is
    // said out loud instead of being implied by a green tick.
    const leaves = leafTotal;
    expect(
      leaves,
      `the walk saw ${leaves} kicker/note element(s) — it has gone blind, ` +
        `because 25 screens render about 26:\n  ${perScreen.join("\n  ")}`,
    ).toBeGreaterThan(20);

    expect(
      panels,
      `the walk saw no .met-panel / .fin-page at all, so "none sits outside .view" ` +
        `is vacuous:\n  ${perScreen.join("\n  ")}`,
    ).toBeGreaterThan(20);

    // THE FINDING, asserted rather than assumed: if this is empty, `.met-panel`
    // and `.fin-page` add nothing to those selectors that `.view` does not
    // already give, and the six lines can go.
    expect(
      outsideView,
      "a `.met-panel` or `.fin-page` renders OUTSIDE `main.view`, so its scope " +
        "in FormModal.css is load-bearing after all and must NOT be deleted",
    ).toEqual([]);

    // eslint-disable-next-line no-console
    console.log(
      `phase4b · ${panels} panel(s) and ${controls} control(s) across ${SCREENS.length} screens -> ${OUT}\n  ` +
        perScreen.join("\n  "),
    );
  });
});
