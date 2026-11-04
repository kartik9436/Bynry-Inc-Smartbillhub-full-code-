// ── Trace ──────────────────────────────────────────────
// Change:   CR-016 (12-governance/11-change-requests.md) — "UI is very important,
//           we need to be sure all UI works correctly" / "How many styling, CSS
//           issues are there, can you compare it with r10" (PO, 2026-08-19)
// Defects:  DEF-302 (every dropdown rendered as an OS widget) and the register
//           rows this spec's own first run opened.
// Rules:    B14 rules 5, 8, 18, 20 (04-docs/02-decisions/14-ui-conventions.md) ·
//           05-prototype/r10-2026-08-16/styles.css (THE design system) ·
//           hard-won law 6 (diff the RUNNING app against 05-prototype) ·
//           hard-won law 7 (prove a new guard RED first)
// ───────────────────────────────────────────────────────
// THE GATE CLAUDE.md HARD-WON LAW 6 SAYS DOES NOT EXIST.
//
//     "Diff the running app against 05-prototype/. NO GATE LOOKS AT RENDERED
//      OUTPUT. Nine defects were found this way and by nothing else."
//
// And B14's own status table says the same thing about its twenty rules: most
// are "RATIFIED and UNENFORCED, because no gate in this repo reads rendered
// output." This is the gate that reads it.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY SOURCE-READING CHECKS CANNOT FIND THIS CLASS
// ══════════════════════════════════════════════════════════════════════════
// tsc, eslint and vitest all pass on a screen that renders as an operating
// system widget inside a designed page, because every one of them reads SOURCE
// and none of them reads PIXELS. Concretely, three shapes are invisible to all
// of them and visible to this spec:
//
//   1. A CLASS REFERENCED BY COMPONENTS AND DECLARED BY NO STYLESHEET —
//      DEF-244's shape, recorded as recurring SIX times in CLAUDE.md before
//      this spec was written. `className="kicker"` compiles, renders, and
//      styles NOTHING; it is byte-identical in the DOM to a class that works.
//   2. A CONTROL WITH NO CLASS AT ALL. `<select>` with no className is valid
//      TSX and a native OS dropdown on screen. `.input` never reaches it.
//   3. A `var(--token)` NOBODY DECLARED. With no fallback the whole
//      declaration is invalid at computed-value time and silently does
//      nothing; with a fallback it silently ships the fallback.
//
// ══════════════════════════════════════════════════════════════════════════
// HOW IT COMPARES — AGAINST THE APP'S OWN DESIGN SYSTEM, NOT A HARD-CODED HEX
// ══════════════════════════════════════════════════════════════════════════
// The reference for a form control is an ACTUAL `.input` element, injected into
// the live page and measured. So the gate cannot rot when a token is retuned:
// change `--color-surface` and both sides move together, and the gate keeps
// asking the only question that matters — does every control on this screen
// look like the design system's control?
//
// The values that are NOT derivable that way are quoted from r10 and carry the
// line they came from, because r10 is the authority (PO ruling 2026-08-16,
// "for this session we will be refering to r10 - as default").
//
// ══════════════════════════════════════════════════════════════════════════
// IT IS A RATCHET, NOT A PASS/FAIL — AND THAT IS DELIBERATE (the G23 pattern)
// ══════════════════════════════════════════════════════════════════════════
// The product FAILS all six rules today; that is the finding, not a reason to
// weaken the check. So the counts live in `ui-conformance-baseline.json` as
// EXACT numbers, exactly as `10-scripts/gates/surface_debt.txt` holds G23's:
//
//   * a count going UP  → a NEW violation shipped. RED.
//   * a count going DOWN → someone fixed something and did not lower the
//                          register. RED, because "a register that keeps
//                          claiming debt it has paid off is how a gate stops
//                          being a gate" (DEF-077, quoted in surface_debt.txt).
//
// A ceiling would be a number nobody ever has to look at again, and "nobody
// looked" is this whole change request.
//
// ══════════════════════════════════════════════════════════════════════════
// HOW TO RUN IT
// ══════════════════════════════════════════════════════════════════════════
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && E2E_BASE_URL=http://127.0.0.1:8080 \
//       E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//       npx playwright test e2e/CR-016-ui-conformance.spec.ts
//
// ⚠ REBUILD THE FRONTEND FIRST. `boot_stack.sh` serves `dist/`, so a stale
// bundle measures yesterday's CSS. The first attempt at this audit read a
// bundle without DEF-302's fix in it and would have reported a fixed defect as
// broken.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { SIDEBAR_DESTINATIONS } from "../src/routing/sidebarDestinations";

import { baseUrl, signIn, skipUnlessAppServer, tenant } from "./support/app";

/** The register, read as a FILE rather than imported. A JSON import needs an
 *  import attribute under Playwright's ESM loader and a matching tsc flag; a
 *  read is the same fact with no build-configuration surface, and it is the
 *  idiom `support/census.ts` and `J24.spec.ts` already use here. */
const BASELINE_FILE = fileURLToPath(new URL("./ui-conformance-baseline.json", import.meta.url));
const BASELINE = JSON.parse(readFileSync(BASELINE_FILE, "utf-8")) as {
  totals: Record<string, unknown>;
  perScreen: Record<string, Record<string, number>>;
};

skipUnlessAppServer(test);

/** Destinations the sidebar does NOT offer but a person reaches by clicking a
 *  tab. The template catalogue is here because it is the screen in the PO's
 *  second screenshot, and because it is the one screen measured so far that
 *  renders TWO table font sizes at once (B14 rule 20 broken inside one page). */
const EXTRA_DESTINATIONS = [
  "/settings/reference-data/templates",
  "/settings/reference-data/routes-cycles",
] as const;

const DESTINATIONS = [...SIDEBAR_DESTINATIONS, ...EXTRA_DESTINATIONS];

/* r10's kicker, quoted from `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`:
 *
 *    .kicker{font-size:11px;letter-spacing:0.1em;text-transform:uppercase;
 *            color:var(--color-accent);font-family:var(--font-heading);
 *            font-weight:800}
 *
 * It is the one r10 class the app's markup asks for BY NAME — 26 files, the
 * shared `PageHeader` among them — and no app stylesheet declares it, so its
 * three load-bearing values are quoted rather than derived from a live element
 * the way controls are. They are written INLINE in the `page.evaluate` below
 * and not as a module constant: that callback is serialised and run in the
 * browser, so it cannot close over anything in this file. A constant here would
 * be a second copy that nothing keeps in step with the one that runs.
 */

type ScreenFindings = {
  path: string;
  nativeSelects: number;
  foreignControls: number;
  inlineWrappingLabels: number;
  tableBodyFontSizes: string[];
  tableHeaderFontSizes: string[];
  buttonFontSizes: string[];
  controlHeights: number[];
  nonConformingKickers: number;
  samples: string[];
};

test.describe("CR-016 — the running app against r10, measured in computed style", () => {
  test("the walk covers the real product and is not an empty loop", () => {
    // Without this, a broken import or an emptied list turns every assertion
    // below into a loop over nothing that reports itself as a pass — DEF-057's
    // shape, and the reason DEF-176's spec carries the same guard.
    expect(DESTINATIONS.length).toBeGreaterThanOrEqual(20);
    expect(DESTINATIONS).toContain("/settings/reference-data/templates");
  });

  test("every screen conforms to the design system @app-server", async ({ page }) => {
    test.setTimeout(900_000);
    await signIn(page);

    const findings: ScreenFindings[] = [];

    for (const path of DESTINATIONS) {
      // Client-side navigation, the way a person clicking the sidebar moves —
      // and the only affordable way to walk 24 screens through ONE 6.4 MB
      // chunk. A settings SUB-tab needs a real load to mount, so those go
      // through `goto`.
      if (path.startsWith("/settings/")) {
        await page.goto(`${baseUrl()}/${tenant()}${path}`);
      } else {
        await page.evaluate((to) => {
          window.history.pushState({}, "", to);
          window.dispatchEvent(new PopStateEvent("popstate"));
        }, `/${tenant()}${path}`);
      }
      await page.waitForURL((url) => url.pathname === `/${tenant()}${path}`, { timeout: 30_000 });
      // Wait for the DATA, not the paint (DEF-176's lesson): a list's filter
      // selects do not exist until its options have arrived, so a check that
      // ran on first paint would count zero controls and pass.
      await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => undefined);
      await page.waitForTimeout(1_800);

      const screen = await page.evaluate(() => {
        const cs = (el: Element) => getComputedStyle(el);
        const visible = (el: Element) => {
          const s = cs(el);
          return s.display !== "none" && s.visibility !== "hidden";
        };
        const main = document.querySelector("main.view") ?? document.body;

        // ── THE REFERENCE. An actual `.input`, styled by the app's own
        // stylesheet, measured live. Nothing below compares against a literal.
        const probe = document.createElement("input");
        probe.type = "text";
        probe.className = "input";
        probe.style.position = "absolute";
        probe.style.left = "-9999px";
        main.appendChild(probe);
        const ref = cs(probe);
        const reference = {
          border: `${ref.borderTopWidth} ${ref.borderTopStyle} ${ref.borderTopColor}`,
          background: ref.backgroundColor,
          minHeight: ref.minHeight,
        };
        probe.remove();

        const samples: string[] = [];
        const controls = Array.from(
          main.querySelectorAll<HTMLElement>("input, select, textarea"),
        ).filter(
          (el) =>
            visible(el) &&
            !["hidden", "checkbox", "radio", "file", "range"].includes(
              (el as HTMLInputElement).type,
            ),
        );

        // RULE A (B14 rule 8, "Dropdowns share ONE chevron style") — a select
        // whose computed `appearance` is not `none` is the browser drawing its
        // own control on top of ours. DEF-302 exactly.
        const nativeSelects = controls.filter(
          (el) => el.tagName === "SELECT" && cs(el).appearance !== "none",
        );

        // RULE B — a control whose border or background is not the design
        // system's is FOREIGN. `2px inset rgb(118,118,118)` on white is the
        // platform's own control and is what an unclassed `<input>` computes to.
        const foreign = controls.filter((el) => {
          const s = cs(el);
          return (
            `${s.borderTopWidth} ${s.borderTopStyle} ${s.borderTopColor}` !== reference.border ||
            s.backgroundColor !== reference.background
          );
        });
        for (const el of foreign.slice(0, 3)) {
          const s = cs(el);
          samples.push(
            `foreign control <${el.tagName.toLowerCase()} class="${el.className}"> ` +
              `border=${s.borderTopWidth} ${s.borderTopStyle} ${s.borderTopColor} ` +
              `bg=${s.backgroundColor} (design system: border=${reference.border} bg=${reference.background})`,
          );
        }

        // RULE C — a <label> is display:inline by default, so one that WRAPS
        // its control puts its text on the control's LAST baseline. On a
        // 12-row textarea that drops the word "Body" to the bottom-left
        // corner, which is what the PO photographed.
        const inlineWrapping = Array.from(main.querySelectorAll<HTMLElement>("label")).filter(
          (l) => visible(l) && l.querySelector("input, select, textarea") && cs(l).display === "inline",
        );
        for (const l of inlineWrapping.slice(0, 2)) {
          samples.push(`inline label wrapping a control: ${l.outerHTML.slice(0, 120)}`);
        }

        // RULE D (B14 rule 20) — "Table type is ONE size (13.5px) everywhere;
        // no inline overrides."
        //
        // ⚠ MEASURED PER ROLE, td AND th SEPARATELY, AND THAT IS A CORRECTION
        // (CR-016 design-system slice, 2026-08-19). The first version of this
        // rule pooled `table td, table th` into ONE set and called anything
        // above one entry a violation. That target is unreachable — by r10
        // ITSELF, which gives the two roles two sizes in the same block:
        //
        //     .table    { font-size: 13.5px; }
        //     .table th { font-size: 11px; letter-spacing: 0.08em; ... }
        //     — 05-prototype/r10-2026-08-16/styles.css, "— tables —"
        //
        // So the pooled count could only be driven to 1 by deleting the header
        // tier the design system requires, and `screensWithMoreThanOneTableSize`
        // was even worse: it counted a screen as broken for having a header at
        // all, and would have gone UP as the product was FIXED. A register that
        // rewards a regression is not a register.
        //
        // Split, each half asks the question rule 20 actually asks: is the body
        // type one size product-wide, and is the header tier one size product-
        // wide? DEF-310's stated closure — "the set becomes ['13.5px']" — is
        // now literally the body half's target.
        // THE HEADER TIER IS `thead`, AND NOTHING ELSE. A `<th>` anywhere else
        // is a cell in a body row — a row header ("0–30 days") beside the
        // figures it labels, or a `<tfoot>` total — and it has to match the
        // `<td>`s on its own line, not the column labels three rows up.
        // Splitting on the ELEMENT put the ageing table's band labels in the
        // header set; splitting on "not inside tbody" then put its `<tfoot>`
        // total there instead. `thead` is the only boundary that means what
        // this rule means.
        const inHead = (c: Element) => c.closest("thead") !== null;
        const tableBodyFontSizes = Array.from(
          new Set(
            Array.from(main.querySelectorAll("table td, table th"))
              .filter((c) => !inHead(c))
              .filter(visible)
              .map((c) => cs(c).fontSize),
          ),
        ).sort();
        const tableHeaderFontSizes = Array.from(
          new Set(
            Array.from(main.querySelectorAll("table thead th"))
              .filter(visible)
              .map((c) => cs(c).fontSize),
          ),
        ).sort();

        // RULE E (B14 rule 5) — "Two button sizes only — default and small
        // (12px). No inline font sizes."
        const buttonFontSizes = Array.from(
          new Set(
            Array.from(main.querySelectorAll("button"))
              .filter(visible)
              .map((b) => cs(b).fontSize),
          ),
        ).sort();

        // RULE F — control HEIGHT. r10 gives `.input` one height (min-height
        // 36px) and the pager select one small tier. More than two rendered
        // heights on a screen means controls drawn by three different rules.
        const controlHeights = Array.from(
          new Set(controls.map((el) => Math.round(el.getBoundingClientRect().height))),
        ).sort((a, b) => a - b);

        // RULE G — the `.kicker`. Measured document-wide, not pane-wide,
        // because it is the shared PageHeader's own element.
        const kickers = Array.from(document.querySelectorAll<HTMLElement>(".kicker")).filter(
          visible,
        );
        const badKickers = kickers.filter((k) => {
          const s = cs(k);
          return s.fontSize !== "11px" || s.textTransform !== "uppercase" || s.fontWeight !== "800";
        });
        for (const k of badKickers.slice(0, 1)) {
          const s = cs(k);
          samples.push(
            `.kicker renders ${s.fontSize}/${s.textTransform}/${s.fontWeight}/${s.color} — ` +
              `r10 draws 11px/uppercase/800/accent. NO app stylesheet declares .kicker.`,
          );
        }

        return {
          nativeSelects: nativeSelects.length,
          foreignControls: foreign.length,
          inlineWrappingLabels: inlineWrapping.length,
          tableBodyFontSizes,
          tableHeaderFontSizes,
          buttonFontSizes,
          controlHeights,
          nonConformingKickers: badKickers.length,
          samples,
        };
      });

      findings.push({ path, ...screen });
    }

    // ── The product-wide totals, which is what the register records ────────
    const totals = {
      nativeSelects: findings.reduce((n, f) => n + f.nativeSelects, 0),
      foreignControls: findings.reduce((n, f) => n + f.foreignControls, 0),
      inlineWrappingLabels: findings.reduce((n, f) => n + f.inlineWrappingLabels, 0),
      nonConformingKickers: findings.reduce((n, f) => n + f.nonConformingKickers, 0),
      distinctTableBodyFontSizes: Array.from(
        new Set(findings.flatMap((f) => f.tableBodyFontSizes)),
      ).sort(),
      distinctTableHeaderFontSizes: Array.from(
        new Set(findings.flatMap((f) => f.tableHeaderFontSizes)),
      ).sort(),
      distinctButtonFontSizes: Array.from(
        new Set(findings.flatMap((f) => f.buttonFontSizes)),
      ).sort(),
      distinctControlHeights: Array.from(
        new Set(findings.flatMap((f) => f.controlHeights)),
      ).sort((a, b) => a - b),
      // Rule 20 broken WITHIN one page — now within one ROLE on one page, so a
      // header tier is not counted as a second body size.
      screensWithMoreThanOneTableSize: findings.filter(
        (f) => f.tableBodyFontSizes.length > 1 || f.tableHeaderFontSizes.length > 1,
      ).length,
    };

    const perScreen = Object.fromEntries(
      findings
        .filter(
          (f) =>
            f.nativeSelects + f.foreignControls + f.inlineWrappingLabels + f.nonConformingKickers >
            0,
        )
        .map((f) => [
          f.path,
          {
            nativeSelects: f.nativeSelects,
            foreignControls: f.foreignControls,
            inlineWrappingLabels: f.inlineWrappingLabels,
            nonConformingKickers: f.nonConformingKickers,
          },
        ]),
    );

    const evidence =
      `\n\nMEASURED (computed style, ${DESTINATIONS.length} screens):\n` +
      JSON.stringify({ totals, perScreen }, null, 2) +
      `\n\nSAMPLES:\n` +
      findings
        .flatMap((f) => f.samples.map((s) => `  ${f.path} — ${s}`))
        .slice(0, 12)
        .join("\n") +
      `\n\nIf a number went DOWN, something was FIXED — lower it in ` +
      `07-frontend/e2e/ui-conformance-baseline.json in the same commit. ` +
      `If it went UP, a new violation shipped.\n`;

    expect(
      {
        nativeSelects: totals.nativeSelects,
        foreignControls: totals.foreignControls,
        inlineWrappingLabels: totals.inlineWrappingLabels,
        nonConformingKickers: totals.nonConformingKickers,
        distinctTableBodyFontSizes: totals.distinctTableBodyFontSizes,
        distinctTableHeaderFontSizes: totals.distinctTableHeaderFontSizes,
        distinctButtonFontSizes: totals.distinctButtonFontSizes,
        distinctControlHeights: totals.distinctControlHeights,
        screensWithMoreThanOneTableSize: totals.screensWithMoreThanOneTableSize,
      },
      `UI conformance drifted from the recorded register.${evidence}`,
    ).toEqual(BASELINE.totals);

    expect(perScreen, `Per-screen conformance drifted from the register.${evidence}`).toEqual(
      BASELINE.perScreen,
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 12-governance/11-change-requests.md → CR-016 PART C item 1 (quoted in full at the head of this file) + 04-docs/02-decisions/14-ui-conventions.md B14 rules 2/5/8/20 + 05-prototype/r10-2026-08-16/styles.css and SMARTBillHub.dc.html <style> (THE design system) + 12-governance/10-defect-log.csv DEF-302/DEF-308..DEF-313
// generated: 2026-08-19 by the CR-016 r10 conformance lane
// checklist: A✔ B✔ C=deferred(no backend half — this gate reads a browser, not an API) D=deferred(no API call) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST, TWICE (hard-won law 7). (1) Against a register asserting full conformance it FAILED and printed the whole measurement: 26 native selects on 10 screens, 6 table font sizes, 5 button font sizes, 10 non-conforming .kickers, 4 control heights, 10 screens with more than one table size. (2) Against a build with `appearance: none` DELETED from `select.input` — DEF-302's own fix — it FAILED naming the exact regression, `- "nativeSelects": 26 / + "nativeSelects": 28`, which is the two `.input` selects that fix had corrected. The file was restored from a byte snapshot and verified with `sha256sum -c` (OK) before the tree was left. Against the restored build: 2 passed, 1.5 min. tsc -p tsconfig.e2e.json --noEmit✔
// exceptions: (1) it is a RATCHET against an exact register, not a pass/fail — the product fails all six rules today and a check that could not land until they were fixed is a check that never lands. The register cannot drift in EITHER direction, which is the G23/surface_debt.txt discipline · (2) it walks screens reachable by NAVIGATION and opens no modal, wizard or panel, so `inlineWrappingLabels: 0` is a floor and not a clean bill — the label in the PO's second screenshot lives in a create panel this walk never opens, and the baseline's own README says so · (3) it compares controls against an `.input` injected into the live page rather than against literal values, so it cannot rot when a token is retuned — the trade is that a wrong `.input` would make everything agree with a wrong reference, which is why `.kicker` and rules 5/20 are quoted from r10 instead · (4) it asserts nothing about colour beyond border and background, and nothing about spacing, icons or copy — B14 rules 1, 3, 4, 6, 7, 9–17 and 19 stay RATIFIED and UNENFORCED and B14's amended §"What is actually enforced today" says which
// status: VERIFIED-UNRATIFIED
