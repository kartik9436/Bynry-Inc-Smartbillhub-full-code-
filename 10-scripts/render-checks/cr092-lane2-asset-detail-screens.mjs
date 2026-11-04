/**
 * SCREENS 08 · 09 · 11 · 12 · 13 — DOES ONE ASSET'S DETAIL MATCH ITS DRAWING?
 * ══════════════════════════════════════════════════════════════════════════
 *
 * The `01 Assets Menu Blueprint.pdf` section 03 walk, run against the product
 * rather than read off the source. It exists because **no gate in this
 * repository reads rendered output** (hard-won law 6), and because the
 * assertions it makes are the ones a green vitest suite cannot make: the asset
 * number is printed ONCE, the place line LEADS with the address, and the
 * `Work & maintenance` tab lands on `Open work` and links to either half.
 *
 * RUN IT (the production join — vite's dev server has NO /api proxy):
 *   cd 07-frontend && npx vite build
 *   node 10-scripts/render-checks/cr092-lane2-asset-detail-screens.mjs
 *
 * Exit 0 = every check held at both widths · 1 = a finding · 2 = nothing walked.
 */
import { existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
/** The staff app's two required widths (PO 2026-09-10). `WIDTHS=1440` runs one
 *  of them, for re-proving a single width after a fix. */
const WIDTHS = (process.env.WIDTHS ?? "1280,1440").split(",").map((n) => Number(n.trim()));
const HEIGHT = 900;

const findings = [];
const held = [];
const say = (...a) => console.log(...a);
function check(ok, label, detail = "") {
  (ok ? held : findings).push(`${label}${detail ? " — " + detail : ""}`);
  say(`${ok ? "  ok  " : "  ✗   "} ${label}${detail ? " — " + detail : ""}`);
}

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#signin-email", { timeout: 20000 });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

/** Every asset the registry's Meters tab lists, newest page first. */
async function assetHrefs(page) {
  await page.goto(`${BASE}/${TENANT}/assets?tab=meters`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('a[href*="/assets/"]', { timeout: 20000 });
  return page.$$eval('a[href*="/assets/"]', (as) =>
    [...new Set(as.map((a) => a.getAttribute("href")))].filter(
      (h) => h && /\/assets\/[0-9a-f-]{20,}$/.test(h),
    ),
  );
}

/** ⚠ **`networkidle` NEVER SETTLES ON THIS SPA AND EVERY `goto` PAID A 30s
 *  TIMEOUT** — the first run of this file spent four minutes producing one line
 *  of output. Wait for the thing being measured instead: the page head. A wait
 *  that times out THROWS and is reported, which is the difference between "not
 *  drawn" and "not looked at". */
async function settled(page) {
  await page.waitForSelector(".page-header", { timeout: 45000 });
  await page.waitForTimeout(350);
}

const run = async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  try {
    for (const width of WIDTHS) {
      say(`\n══ ${width}×${HEIGHT} ═══════════════════════════════════════════`);
      const context = await browser.newContext({ viewport: { width, height: HEIGHT } });
      const page = await context.newPage();
      await signIn(page);
      const hrefs = await assetHrefs(page);
      if (hrefs.length === 0) {
        say("NOTHING WALKED: the Meters tab listed no asset");
        process.exitCode = 2;
        return;
      }
      /* ⚠ **PICK AN ASSET THAT CAN MAKE THESE CHECKS FAIL.** The first draft
         took `hrefs[0]` and landed on a meter in INVENTORY: no account, no
         reads, no assignment rows, no maintenance. Six of its checks were then
         true of an empty screen and could not have gone red — hard-won law 7's
         own shape, and it hid a real defect in the place line that the vitest
         fixture caught instead. So the walk now scores every asset on the page
         and takes the richest, and it PRINTS what it found. */
      let href = hrefs[0];
      let best = -1;
      /* `ASSET=<uuid>` pins the walk to one asset, so a re-run after a fix does
         not pay for the scoring loop again. The scoring loop below is what
         FOUND that asset; the override is a shortcut, never the default. */
      if (process.env.ASSET) {
        href = `/${TENANT}/assets/${process.env.ASSET}`;
      }
      if (!process.env.ASSET)
      for (const candidate of hrefs.slice(0, 6)) {
        await page.goto(`${BASE}${candidate}`, { waitUntil: "domcontentloaded" });
      await settled(page);
        const score = await page.evaluate(() => {
          const text = document.body.textContent ?? "";
          const facts = [...document.querySelectorAll("[data-asset-facts] dd")];
          const dashes = facts.filter((d) => (d.textContent ?? "").trim() === "—").length;
          return (
            (text.includes("In inventory") ? 0 : 4) +
            (document.querySelector('[data-asset-facts] a[href*="/accounts/"]') ? 4 : 0) +
            Math.max(0, facts.length - dashes)
          );
        });
        if (score > best) {
          best = score;
          href = candidate;
        }
      }
      say(`walking ${href} (richest of ${Math.min(hrefs.length, 6)} candidates, score ${best})`);

      /* ⚠ **THE HISTORY HALF CANNOT BE MEASURED ON AN ASSET WITH NO HISTORY**,
         and this tenant seeds none — the blueprint itself records `0 rows in
         asset_maintenance` on the walked tenant. So the walk APPENDS one entry
         through the product's own append-only door before it looks. It is a
         POST the screen itself makes (`BR-AST-018`: corrections are new rows,
         there is no delete), issued from inside the page so it carries the
         session the browser already has. `SEED=0` skips it. */
      if (process.env.SEED !== "0" && width === WIDTHS[0]) {
        const assetId = href.split("/").pop();
        await page.goto(`${BASE}${href}?tab=work&section=history`, { waitUntil: "domcontentloaded" });
        await settled(page);
        const already = await page.evaluate(
          () => document.querySelectorAll("section table tbody tr").length,
        );
        const seeded = already > 0 ? `skipped, ${already} row(s) already` : await page.evaluate(
          async ([tenant, id]) => {
            const reply = await fetch(`/api/${tenant}/assets/${id}/maintenance`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                kind: "repair",
                detail: "Replaced the register and resealed",
                cost: "84.0000",
              }),
            });
            return `${reply.status}`;
          },
          [TENANT, assetId],
        );
        say(`seeded one maintenance entry → HTTP ${seeded}`);
      }

      // ── Screen 08 · Overview ──────────────────────────────────────────
      await page.goto(`${BASE}${href}`, { waitUntil: "domcontentloaded" });
      await settled(page);
      const head = await page.evaluate(() => ({
        kicker: document.querySelector("[data-kicker]")?.textContent?.trim() ?? "",
        title: document.querySelector(".page-header h1")?.textContent?.trim() ?? "",
        rollup: document.querySelector(".page-header-rollup")?.textContent?.trim() ?? "",
        actions: [...document.querySelectorAll(".page-header-actions button, .page-header-actions a")]
          .map((b) => (b.getAttribute("aria-label") || b.textContent || "").trim())
          .filter(Boolean),
        more: document.querySelectorAll(".page-header-actions [data-row-more]").length,
        menu: [...document.querySelectorAll(".page-header-actions [data-row-more] button")]
          .map((b) => b.textContent.trim()),
        facts: [...document.querySelectorAll("[data-asset-facts] dt")].map((d) => d.textContent.trim()),
        sideways: document.documentElement.scrollWidth > window.innerWidth,
      }));
      say(`\nSCREEN 08 · ${head.title}`);
      say(`   kicker : ${head.kicker}`);
      say(`   place  : ${head.rollup}`);
      say(`   actions: ${head.actions.join(" | ")}`);
      say(`   menu   : ${head.menu.join(" | ")}`);
      check(!head.kicker.includes(head.title), "08-1 the asset number is NOT in the kicker", head.kicker);
      check(head.title.length > 0, "08-1 the number is in the title", head.title);
      check(!/^\s*×/.test(head.rollup) && !head.rollup.includes("×"), "08-2 no multiplier in the place line", head.rollup);
      check(!head.rollup.includes("assigned to"), "08-2 the words 'assigned to' are gone");
      check(head.more === 1, "08-3 the header carries ONE `…` overflow", `found ${head.more}`);
      /* ⚠ **THE RULE IS NOT "BOTH VERBS ARE THERE" — `BR-AST-006` SAYS THE
         SERVER'S ACTION SET DECIDES**, and an in-service meter is offered no
         `delete` at all. The first draft asserted both and went red on a
         perfectly correct header. What page 41 actually requires is that
         whichever of the two the state offers is in the MENU and is not also a
         visible button. */
      const menuVerbs = ["Edit", "Delete"].filter((verb) => head.menu.includes(verb));
      check(menuVerbs.length > 0, "08-3 the menu holds at least one of Edit / Delete", head.menu.join(","));
      for (const verb of ["Edit", "Delete"]) {
        if (head.actions.includes(verb) && !head.menu.includes(verb)) {
          check(false, `08-3 ${verb} is a visible button, not under the overflow`);
        }
      }
      check(
        !["Edit", "Delete"].some((verb) => head.actions.includes(verb) && !head.menu.includes(verb)),
        "08-3 neither verb is a visible button",
        head.actions.join(" | "),
      );
      check(head.facts.includes("Premises"), "08-4 the Assignment label reads `Premises`");
      check(head.facts.includes("Sub-meters on it"), "08-5 `Sub-meters on it` is drawn");
      check(head.facts.includes("Last test"), "08-7 `Last test`");
      check(head.facts.includes("Warranty ends"), "08-8 `Warranty ends`");
      check(head.facts.includes("Book value"), "08-9 `Book value` is drawn");
      check(head.facts.includes("Treatment"), "08-9 `Treatment` is drawn");
      check(!head.sideways, "the page body does not scroll sideways");

      // ── Screen 09 · Reads ─────────────────────────────────────────────
      await page.goto(`${BASE}${href}?tab=reads`, { waitUntil: "domcontentloaded" });
      await settled(page);
      const reads = await page.evaluate(() => ({
        arrived: document.querySelector("[data-asset-reads]") !== null,
        rows: document.querySelectorAll("[data-asset-reads] tbody tr").length,
        // `StatusPill` renders `.pill`; the two guesses in the first draft
        // (`.status-pill`, `[data-tone]`) match nothing, so this counted zero
        // of everything and could not have failed.
        pills: document.querySelectorAll("[data-asset-reads] tbody .pill").length,
        firstStatus:
          document.querySelector("[data-asset-reads] tbody tr td:last-child")?.textContent?.trim() ?? "(no rows)",
        sideways: document.documentElement.scrollWidth > window.innerWidth,
      }));
      say(`\nSCREEN 09 · reads arrived=${reads.arrived} rows=${reads.rows} lastCell="${reads.firstStatus}"`);
      check(reads.arrived, "09 the read log is on screen");
      check(!reads.sideways, "09 no sideways scroll");
      /* ⚠ **THE PILL CANNOT BE MEASURED ON A METER WITH NO READS**, and most of
         this tenant's meters have none. The skip is PRINTED rather than counted
         as a pass — hard-won law 7's *reporting zero over a scope it silently
         excludes*. `ASSET=01a09bc5-aeb6-7ce7-8774-b92edbb4985f` is one that has
         two. */
      if (reads.rows === 0) {
        say("  skip  09-3 — this meter has no reads, so no status cell was drawn");
      } else {
        check(reads.pills > 0, "09-3 the status renders as a PILL", `${reads.pills} pill(s)`);
        check(
          !/^[a-z_]+$/.test(reads.firstStatus),
          "09-3 the status is a WORD, not the served code",
          reads.firstStatus,
        );
      }

      // ── Screen 11 · Assignment history ────────────────────────────────
      await page.goto(`${BASE}${href}?tab=assignments`, { waitUntil: "domcontentloaded" });
      await settled(page);
      const assign = await page.evaluate(() => {
        const rows = [...document.querySelectorAll("table tbody tr")];
        return {
          rows: rows.length,
          unitLinks: document.querySelectorAll('table tbody a[href*="/units/"]').length,
          currentPills: [...document.querySelectorAll("table tbody span")].filter((s) =>
            s.textContent.trim() === "Current",
          ).length,
          bold: document.querySelectorAll("table tbody strong").length,
          sideways: document.documentElement.scrollWidth > window.innerWidth,
        };
      });
      say(`\nSCREEN 11 · rows=${assign.rows} unitLinks=${assign.unitLinks} currentPills=${assign.currentPills}`);
      check(assign.bold === 0, "11-5 no bold `Current` left", `${assign.bold} <strong>`);
      check(!assign.sideways, "11 no sideways scroll");

      // ── Screen 12 · Work & maintenance ────────────────────────────────
      await page.goto(`${BASE}${href}?tab=work`, { waitUntil: "domcontentloaded" });
      await settled(page);
      const work = await page.evaluate(() => ({
        tabLabels: [...document.querySelectorAll("[data-page-header-tabs] [data-tab]")].map((b) =>
          b.textContent.trim(),
        ),
        sections: [...document.querySelectorAll('[role="tab"][data-section]')].map((b) => ({
          id: b.getAttribute("data-section"),
          label: b.textContent.trim(),
          on: b.getAttribute("aria-selected") === "true",
        })),
        openPanel: document.body.textContent.includes("Open work"),
        sideways: document.documentElement.scrollWidth > window.innerWidth,
      }));
      say(`\nSCREEN 12 · tabs: ${work.tabLabels.join(" | ")}`);
      say(`   sub-tabs: ${work.sections.map((s) => `${s.label}${s.on ? "*" : ""}`).join(" | ")}`);
      check(work.tabLabels.includes("Work & maintenance"), "12-2 the tab reads `Work & maintenance`");
      check(work.sections.length === 2, "12-3 two sub-tabs", `${work.sections.length}`);
      check(work.sections[0]?.on === true, "12-3 `Open work` is the default sub-tab");
      check(!work.sideways, "12 no sideways scroll");

      // the legacy address still opens the merged tab
      await page.goto(`${BASE}${href}?tab=maintenance`, { waitUntil: "domcontentloaded" });
      await settled(page);
      const legacy = await page.evaluate(() =>
        document.querySelectorAll('[role="tab"][data-section]').length,
      );
      check(legacy === 2, "12-1 `?tab=maintenance` still opens the merged tab");

      // the History half, by address
      await page.goto(`${BASE}${href}?tab=work&section=history`, { waitUntil: "domcontentloaded" });
      await settled(page);
      const history = await page.evaluate(() => {
        const on = [...document.querySelectorAll('[role="tab"][data-section]')].find(
          (b) => b.getAttribute("aria-selected") === "true",
        );
        const heads = [...document.querySelectorAll("table thead th")].map((h) => h.textContent.trim());
        return {
          section: on?.getAttribute("data-section") ?? "(none)",
          heads,
          foot: document.querySelector("[data-work-cost-foot]")?.textContent?.trim() ?? "(none)",
          logBelow:
            (() => {
              /* ⚠ **SCOPED TO THE PANEL, BECAUSE THE PAGE HEAD CARRIES A
                 `Log repair` TOO.** A document-wide `querySelectorAll("button")`
                 finds the HEADER's control first, which sits above every table
                 on every screen — so the first draft of this check reported
                 "above" over a panel whose own button was correctly below. */
              const panel = [...document.querySelectorAll("section")].find((el) =>
                el.querySelector("table"),
              );
              if (!panel) return "(no table)";
              const table = panel.querySelector("table");
              const log = [...panel.querySelectorAll("button")].find((b) =>
                /Log (repair|test)/.test(b.textContent),
              );
              if (!log) return "(no log button in the panel)";
              return table.compareDocumentPosition(log) & Node.DOCUMENT_POSITION_FOLLOWING
                ? "below"
                : "above";
            })(),
        };
      });
      say(`\nSCREEN 12 · History section=${history.section}`);
      say(`   columns : ${history.heads.join(" | ")}`);
      say(`   foot    : ${history.foot}`);
      say(`   log btn : ${history.logBelow}`);
      check(history.section === "history", "12-3 `?section=history` lands on History");
      /* ⚠ **A LIST WITH NO ROWS DRAWS NO TABLE, SO THESE TWO WOULD PASS OVER
         NOTHING.** Hard-won law 7: a check that reports zero over a scope it
         silently excludes is indistinguishable from an empty one, so the skip
         is PRINTED beside what was checked rather than counted as a pass. */
      if (history.heads.length === 0) {
        say("  skip  12-6 / 12-7 / 12-9 — this asset has no maintenance entries, so no table was drawn");
      } else {
        check(history.heads.includes("Record"), "12-6 the `Record` column", history.heads.join(","));
        check(!history.heads.includes("Type"), "12-6 the old `Type` column is gone");
        check(history.logBelow === "below", "12-9 the log control sits BELOW the table", history.logBelow);
        check(history.foot !== "(none)", "12-7 the three-figure cost foot", history.foot);
      }

      // ── Screen 13 · Audit ─────────────────────────────────────────────
      await page.goto(`${BASE}${href}?tab=audit`, { waitUntil: "domcontentloaded" });
      await settled(page);
      const audit = await page.evaluate(() => ({
        kicker: document.querySelector("[data-kicker]")?.textContent?.trim() ?? "",
        title: document.querySelector(".page-header h1")?.textContent?.trim() ?? "",
        permanent: /permanent record/i.test(document.body.textContent),
        sideways: document.documentElement.scrollWidth > window.innerWidth,
      }));
      say(`\nSCREEN 13 · kicker="${audit.kicker}"`);
      check(!audit.kicker.includes(audit.title), "13-3 the kicker carries no asset number");
      check(!audit.permanent, "13-4 no `permanent record` sentence (OQ-1340 is OPEN)");
      check(!audit.sideways, "13 no sideways scroll");

      await context.close();
    }
  } finally {
    await browser.close();
  }
  say(`\n════ ${held.length} held · ${findings.length} finding(s)`);
  for (const f of findings) say(`   ✗ ${f}`);
  process.exitCode = findings.length === 0 ? 0 : 1;
};

run().catch((error) => {
  console.error(error);
  process.exitCode = 2;
});
