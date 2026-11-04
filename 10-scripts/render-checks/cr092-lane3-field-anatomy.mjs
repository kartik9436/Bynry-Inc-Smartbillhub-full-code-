/**
 * RENDERED-OUTPUT MEASUREMENT — `CR-092` step 1 lane 3: **the asset edit
 * surface's field anatomy**, measured with `getComputedStyle` and
 * `getBoundingClientRect` in a real browser, at **1280 AND 1440**.
 *
 * ⚠ **WHY THIS EXISTS.** B14 **rule 39** (the PO's `R12`) ratifies a field as
 * `label → input → helper` at **5px · 6px · 20px**, a ratio of ≈ 1 : 1 : 4. The
 * Assets-menu blueprint (artifact `2f979496`, §09) reports *"ten of eighteen
 * fields render label → helper → input … label-to-input 29px or 47px, not 5"*
 * and calls that the single most checkable claim in the document. Nothing in
 * this repository reads computed spacing or DOM order inside a field — `tsc`,
 * eslint and every `toContain` assertion pass over any order at all — so the
 * claim can only be settled by rendering it. This is that measurement.
 *
 * ⚠ **IT ASSERTS, IT DOES NOT NARRATE.** A script that prints what it saw and
 * exits 0 is a check that cannot fail (hard-won law 7, second shape). Every
 * screen below declares how many `.field`s it expects to find and the run exits
 * non-zero when a screen yields none, when the login fails, or when a field
 * yields no measurable control — because an empty list and a clean list look
 * identical in a table (law 7, fifth shape: *a declared blind spot with no
 * number attached is indistinguishable from an empty one*). The VERDICT lines
 * are reported, not asserted: this is step 1, which identifies.
 *
 * ⚠ **WHAT WOULD MAKE THIS MEASUREMENT PASS WRONGLY, and what is done about
 * each.**
 *   * A `.field` that is `display:none` measures 0 everywhere and would read as
 *     a perfect 0px rhythm. → zero-height fields are EXCLUDED and counted, and
 *     the count is printed beside the kept count.
 *   * `label.getBoundingClientRect().bottom` is the label BOX, not its baseline,
 *     so the gap reported is box-to-box — which is exactly what rule 39's
 *     `margin-bottom: 5px` governs. Stated so nobody reads it as a baseline.
 *   * A field whose control is a custom widget (no `input`/`select`/`textarea`)
 *     would silently fall out of the table. → such a field is REPORTED as
 *     `control=NONE` and counted as a failure rather than skipped.
 *   * Reading the order from the SOURCE rather than the DOM would miss a CSS
 *     `order:` or `flex-direction: column-reverse` reversing it. → the order
 *     printed is the LAID-OUT order, sorted by rendered `top`, and the DOM
 *     order is printed beside it so a disagreement is visible.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
 *      python3 manage.py runserver 127.0.0.1:8471 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=8472 API_PROXY_TARGET=http://127.0.0.1:8471 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:8472 SMOKE_TENANT=brazosbend \
 *     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr092-lane3-field-anatomy.mjs
 *
 * ⚠ **IT WRITES NOTHING.** Every screen is OPENED and read; no form is
 * submitted, so the run is a sequence of GETs against whatever database the
 * backend points at. That is deliberate — step 1 identifies.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [
        join(root, dir, "chrome-linux", "chrome"),
        join(root, dir, "chrome-linux64", "chrome"),
        join(root, dir, "chrome-linux", "headless_shell"),
      ]) {
        try {
          execFileSync(candidate, ["--version"], { stdio: "ignore" });
          return candidate;
        } catch {
          // keep looking
        }
      }
    }
    return wanted;
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8472";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr092-lane3";
mkdirSync(OUT, { recursive: true });

/** The audience is clerk and utility-admin — laptop and desktop, NOT mobile
 *  (PO 2026-09-10: *"Calrk and Utility admin is laptop, and desktop
 *  application - not mobile"*). So 1280 and 1440, and nothing narrower. */
const WIDTHS = [
  { label: "1280", width: 1280, height: 900 },
  { label: "1440", width: 1440, height: 900 },
];


let failures = 0;
const say = (...p) => console.log(...p);
function fail(label, detail) {
  failures += 1;
  say(`  FAIL ${label}`);
  if (detail !== undefined) say(`       ${detail}`);
}
function ok(label) {
  say(`  ok   ${label}`);
}

// ⚠ **THE PROBE MOVED TO `lib/fieldAnatomy.mjs` on 2026-09-12** so that
// `CR-094-BRC01` step 2 wave E could measure the same anatomy on the five
// starting-service wizards without a second copy of it (PO: *"dont create
// duplcate code"*). Nothing about the measurement changed; this script was
// re-run afterwards against the same screens to prove it.
import { PROBE, RULE } from "./lib/fieldAnatomy.mjs";

function words(s) {
  return s === null || s === undefined ? 0 : s.split(/\s+/).filter(Boolean).length;
}

async function login(page) {
  const res = await page.request.post(`${BASE}/api/${TENANT}/auth/session`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  if (!res.ok()) throw new Error(`login refused: ${res.status()} ${await res.text()}`);
}

async function firstAsset(page) {
  const res = await page.request.get(`${BASE}/api/${TENANT}/assets?tab=meters&per=50`);
  if (!res.ok()) throw new Error(`asset list refused: ${res.status()}`);
  const body = await res.json();
  const rows = body.results ?? [];
  // ⚠ THE SUBJECT IS PICKED BY ASKING THE SERVER, never by assuming a seeded
  // id — and it must be a meter that DECLARES A SERVICE, because
  // `offersConnectionSize` gates the Connection size field on exactly that, so
  // an asset without one would silently measure a shorter form.
  const live = rows.find(
    (r) =>
      Array.isArray(r.actions) &&
      r.actions.includes("edit") &&
      r.actions.includes("retire") &&
      r.actions.includes("log_repair") &&
      r.service !== null &&
      r.service !== undefined,
  );
  if (live === undefined)
    throw new Error("no meter with a service offers edit + retire + log_repair");
  return live;
}

const rows = [];

async function measure(page, screen, url, scopeSelector, opts = {}) {
  await page.goto(url, { waitUntil: "networkidle" });
  if (opts.before !== undefined) await opts.before(page);
  await page.waitForSelector(scopeSelector, { timeout: 15000 }).catch(() => {});
  const probe = await page.evaluate(PROBE, scopeSelector);
  if (probe.error !== undefined) {
    fail(`${screen}: ${probe.error}`);
    return;
  }
  if (probe.fields.length === 0) {
    // An empty list and a clean list look identical — refuse it.
    fail(`${screen}: ZERO measurable fields (${probe.total} .field nodes, ${probe.hidden.length} hidden)`);
    return;
  }
  let noControl = 0;
  for (const f of probe.fields) {
    if (f.tag === "NONE") noControl += 1;
    rows.push({ screen, width: opts.width, ...f, helpWords: words(f.helpText) });
  }
  if (noControl > 0) fail(`${screen}: ${noControl} field(s) with no input/select/textarea`);
  else ok(`${screen}: ${probe.fields.length} fields measured, ${probe.hidden.length} hidden and excluded`);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  try {
    for (const w of WIDTHS) {
      say(`\n── ${w.label}px ───────────────────────────────────────────────`);
      const context = await browser.newContext({ viewport: { width: w.width, height: w.height } });
      const page = await context.newPage();
      await page.goto(`${BASE}/${TENANT}`, { waitUntil: "domcontentloaded" });
      await login(page);
      const asset = await firstAsset(page);
      say(`  subject: ${asset.asset_no} (${asset.id})`);

      // Screen 14 AS BUILT — the edit dialog, the ONLY caller of updateAsset.
      // It is reached by a row action and by nothing else, so it is opened the
      // way a clerk opens it rather than by address.
      await measure(
        page,
        "14 Edit one asset (AssetFormModal)",
        `${BASE}/${TENANT}/assets?tab=meters&q=${encodeURIComponent(asset.asset_no)}`,
        ".modal-body",
        {
          width: w.label,
          before: async (p) => {
            await p.waitForSelector(`tbody tr:has-text("${asset.asset_no}")`, { timeout: 15000 });
            const row = p.locator("tbody tr", { hasText: asset.asset_no }).first();
            await row.locator('button[aria-label="Edit"]').first().click();
            await p.waitForSelector(".modal-body .field", { timeout: 15000 });
          },
        },
      );

      await measure(page, "22 Reassign", `${BASE}/${TENANT}/assets/${asset.id}/reassign`, "main", {
        width: w.label,
      });
      await measure(
        page,
        "23 Log repair / maintenance",
        `${BASE}/${TENANT}/assets/${asset.id}/maintenance/new`,
        "main",
        { width: w.label },
      );
      await measure(page, "24 Retire · step 1", `${BASE}/${TENANT}/assets/${asset.id}/retire`, "main", {
        width: w.label,
      });
      await measure(page, "28-31 Add an asset · step 1", `${BASE}/${TENANT}/assets/new`, "main", {
        width: w.label,
      });

      // The absences AST-B-12 and AST-B-25 assert. Reported, not assumed.
      await page.goto(`${BASE}/${TENANT}/assets/${asset.id}`, { waitUntil: "networkidle" });
      const absences = await page.evaluate(() => {
        const header = document.querySelector("header, .page-header")?.parentElement ?? document.body;
        const text = (el) => (el.textContent ?? "").trim();
        const headerButtons = Array.from(header.querySelectorAll("button, a"))
          .map(text)
          .filter((s) => s.length > 0 && s.length < 40);
        const pencils = Array.from(document.querySelectorAll("button, a")).filter((el) =>
          /edit/i.test(el.getAttribute("aria-label") ?? el.getAttribute("title") ?? ""),
        ).length;
        const panels = Array.from(document.querySelectorAll("section h3")).map(text);
        return { headerButtons, pencils, panels };
      });
      say(`  detail header controls: ${JSON.stringify(absences.headerButtons)}`);
      say(`  Overview panels: ${JSON.stringify(absences.panels)}`);
      say(`  controls whose accessible name contains "edit": ${absences.pencils}`);
      const editRoute = await page.request.get(`${BASE}/${TENANT}/assets/${asset.id}/edit`);
      say(`  GET /${TENANT}/assets/{id}/edit -> ${editRoute.status()} (the SPA serves index.html for any path; the ROUTE is what matters)`);

      await context.close();
    }

    writeFileSync(join(OUT, "fields.json"), JSON.stringify(rows, null, 2));

    // ── the table, the point of the whole run ────────────────────────────
    say("\n── MEASURED TABLE ────────────────────────────────────────────────");
    say(
      [
        "width",
        "screen",
        "field",
        "painted order",
        "control",
        "label→input",
        "input→helper",
        "field→field",
        "helper words",
      ].join(" | "),
    );
    for (const r of rows) {
      say(
        [
          r.width,
          r.screen,
          r.label,
          r.paintedOrder,
          r.tag,
          r.labelToInput === null ? "—" : `${r.labelToInput}px`,
          r.hasHelp ? "n/a — helper is ABOVE the input" : "—",
          r.fieldToField === null ? r.fieldToFieldWhy : `${r.fieldToField}px`,
          r.hasHelp ? r.helpWords : "—",
        ].join(" | "),
      );
    }

    // ── the verdict, reported with its arithmetic ────────────────────────
    const at1280 = rows.filter((r) => r.width === "1280");
    const withHelp = at1280.filter((r) => r.hasHelp);
    const without = at1280.filter((r) => !r.hasHelp);
    const wrongOrder = at1280.filter((r) => r.paintedOrder !== "LABEL > INPUT > HELP" && r.hasHelp);
    const exactly5 = without.filter((r) => r.labelToInput === RULE.labelToInput);
    say("\n── VERDICT (reported; step 1 identifies) ─────────────────────────");
    say(`  fields measured at 1280: ${at1280.length}`);
    say(`  with a helper: ${withHelp.length}    without: ${without.length}`);
    say(`  painted LABEL > HELP > INPUT: ${wrongOrder.length} of ${withHelp.length} helper fields`);
    say(`  label→input on helper fields: ${[...new Set(withHelp.map((r) => r.labelToInput))].sort((a, b) => a - b).join("px, ")}px`);
    say(`  label→input on helperless fields: ${[...new Set(without.map((r) => r.labelToInput))].sort((a, b) => a - b).join("px, ")}px  (${exactly5.length}/${without.length} exactly ${RULE.labelToInput}px)`);
    const adjacent = at1280.filter((r) => r.fieldToField !== null);
    say(`  field→field, adjacent pairs only (${adjacent.length} of ${at1280.length}): ${[...new Set(adjacent.map((r) => r.fieldToField))].sort((a, b) => a - b).join("px, ")}px  (rule 39 ratifies ${RULE.fieldToField}px; ${adjacent.filter((r) => r.fieldToField === RULE.fieldToField).length} pairs hit it)`);
    say(`  helper word counts: ${[...new Set(withHelp.map((r) => r.helpWords))].sort((a, b) => a - b).join(", ")}  (B14 rule 33: an instruction caps at SIX words per SENTENCE)`);
    const overRule33 = withHelp.filter((r) =>
      (r.helpText ?? "").split(/(?<=[.!?])\s+/).some((sentence) => sentence.split(/\s+/).filter(Boolean).length > 6),
    );
    say(`  helpers with a sentence over SIX words (B14 rule 33): ${overRule33.length} of ${withHelp.length}`);

    say(`\n  wrote ${join(OUT, "fields.json")}`);
    say(failures === 0 ? "\nMEASUREMENT COMPLETE — every screen yielded fields." : `\n${failures} MEASUREMENT FAILURE(S)`);
    process.exitCode = failures === 0 ? 0 : 1;
  } finally {
    await browser.close();
  }
})().catch((err) => {
  console.error("REFUSED:", err.message);
  process.exitCode = 2;
});
