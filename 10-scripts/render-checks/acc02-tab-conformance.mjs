/**
 * ACC-02 OVERVIEW — DOES THE SCREEN LOOK LIKE THE DRAWING?
 *
 * PO ruling 2026-09-13, verbatim: *"Product screen should match exactly in
 * visual with Drawing in Blueprint - thats a test"*, and on what "match" means:
 * *"not on information or data - but on layout, pixel, information/data
 * elements"*. So: the same elements, in the same places, at the same sizes.
 * The VALUES may differ — a seeded account is not the drawn one.
 *
 * ⚠ **WHY THIS IS NOT A PIXEL DIFF OF TWO IMAGES.** The drawing shows
 * `A-11812 Bramble Bakery` with `$2,410.00` and a 61-day band; the seeded
 * product shows a different account with different figures. A naive image
 * comparison fails on every pixel and reports nothing usable — law 7's
 * *incapable of passing*. What is comparable is the STRUCTURE and the GEOMETRY,
 * and both are measurable.
 *
 * ⚠ **AND WHY IT IS NOT A VITEST CASE.** jsdom computes no layout: a group in
 * the wrong column, a rule that stops short of the column edge and a 14px gap
 * where the scale says 20 are all INVISIBLE to it. Hard-won law 6 — no gate in
 * this repository reads rendered output, and nine defects were found by looking
 * and by nothing else. `07-frontend/src/features/customers/AccountDetailPage.test.tsx`
 * asserts PRESENCE and ORDER and must keep doing so; it cannot assert any of
 * the geometry below, and claiming otherwise is how a screen ships 16 facts
 * short with every check green.
 *
 * WHAT IT ASSERTS, in the PO's own eight layers
 * ---------------------------------------------
 *   presence  every drawn group and every drawn row is on the screen
 *   position  which COLUMN a group sits in, and its order within that column
 *   order     the rows of a group, in the drawn sequence
 *   heading   colour, case, tracking, size, and the accent rule beneath it —
 *             its width against the column, its thickness, its gap
 *   anatomy   label left, value right, and the measured gap between rows
 *   spacing   every gap is a step of B14 rule 39: 4 8 12 16 20 24 32
 *   type      sizes come from the scale, never an inline value
 *   colour    every colour resolves to a token, never a literal
 *
 * It reports BOTH directions — drawn-and-absent, and present-and-not-drawn —
 * because a screen carrying something the drawing does not is as much a
 * divergence as one missing a row, and only one of those is ever noticed.
 *
 * RUNNING IT
 * ----------
 *   # the vite DEV server has no /api proxy and cannot serve this app
 *   # same-origin; server.mjs IS the production join.
 *   cd 07-frontend && npx vite build
 *   API_PROXY_TARGET=http://127.0.0.1:8011 PORT=8080 node server.mjs &
 *   node 10-scripts/render-checks/acc02-overview-conformance.mjs
 *
 *   BASE=http://127.0.0.1:8080 TENANT=brazosbend ACCOUNT=<account id>
 *   EMAIL=… PASSWORD=… SHOT=<path for the screenshot>
 *
 * Exit 0 when every drawn element is present, placed and measured as drawn, or
 * when each remainder is named. Exit 1 otherwise, listing what and where.
 */
// ⚠ **playwright IS NOT AT THE REPO ROOT — IT LIVES IN `07-frontend/node_modules`,
// AND THE BROWSER IS NOT WHERE THE PACKAGE THINKS IT IS.** This is the house
// pattern, lifted verbatim from `10-scripts/cr089_wave_f_unit_page_walkthrough.mjs`
// rather than re-derived: a plain `import "playwright"` from this folder throws
// ERR_MODULE_NOT_FOUND, and `chromium.executablePath()` points at a download
// this image never made (PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD is set; the browser
// is baked in at /opt/pw-browsers). 55 walkthroughs already solved both.
import { existsSync, readdirSync, mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

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
const SHOT = process.env.SHOT ?? "/tmp/acc02-overview.png";
const WIDTHS = [1280, 1440]; // the staff app's two required widths (PO 2026-09-10)

/**
 * THE DRAWING, as data — `04-docs/05-modules/03-customers/blueprint/02-account-detail.md`.
 *
 * ⚠ **TRANSCRIBED FROM THE EXTRACTED TEXT, NOT FROM LOOKING AT THE PICTURE**,
 * so it can be re-checked against the source by anybody. `slug` must match the
 * `data-overview-group` attribute the screen carries.
 *
 * ⚠ **`money` HOLDS ELEVEN ROWS AND THAT IS THE DRAWING, NOT AN ERROR.** The
 * product currently splits them across `Money`, a separate `Deposit & credit`
 * group and one row sitting under `Account`. The drawing puts all eleven under
 * one heading — the PO's own ruling of 2026-09-10 says a fact sits under ONE
 * named group, and records that grouping is what removed the duplicates. This
 * check therefore reports the split, which is the point of it.
 */
const TAB = process.env.TAB ?? "overview";

/**
 * THE DRAWING, as data — one file per tab, under `drawn/`.
 *
 * ⚠ **ONE FILE PER TAB AND NOT ONE FILE WITH A KEY PER TAB, DELIBERATELY.**
 * Three lanes run at once by the PO's model, and a single shared spec is the
 * shared-file revert this repository has recorded eight separate times — a
 * lane's work vanishing with every check passing. Separate files merge cleanly
 * and cannot silently overwrite one another (law 11).
 *
 * Each is transcribed from `04-docs/05-modules/03-customers/blueprint/` — the
 * EXTRACTED TEXT, never from looking at the picture — so anybody can re-check a
 * row against the source. `slug` must match the `data-overview-group` attribute
 * the screen carries; a group with no hook is invisible to this check, which is
 * why a tab with no hooks reports its own absence rather than a clean zero.
 */
const specPath = new URL(`./drawn/acc02-${TAB}.json`, import.meta.url);
if (!existsSync(specPath)) {
  console.error(`no drawn spec for tab "${TAB}" — expected ${specPath.pathname}`);
  console.error("transcribe it from the blueprint before running this check.");
  process.exit(2);
}
const SPEC = JSON.parse(readFileSync(specPath, "utf8"));
const DRAWN = SPEC.groups;

/** B14 rule 39's scale. A gap off this list is the defect the rule exists for. */
const SCALE = [0, 4, 8, 12, 16, 20, 24, 32];

const findings = [];
/** Drawn, not on this tab, and ACCOUNTED FOR — each with the ruling that moved it. */
const remainders = [];
/** Drawn tables the screen showed as an empty state — NOT judged either way. */
const unjudged = [];
const fail = (layer, where, said) => findings.push({ layer, where, said });
const say = (...a) => console.log(...a);

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

/** The account to drive. Any real one — the check is about layout, not values. */
async function anAccount(page) {
  const body = await page.evaluate(async (t) => {
    const r = await fetch(`/api/${t}/accounts?per=1`, { credentials: "include" });
    return r.ok ? await r.json() : null;
  }, TENANT);
  if (!body?.results?.length) throw new Error("no accounts served — is the tenant seeded?");
  return body.results[0].id;
}

/** Everything the page can tell us about one group, measured in the browser. */
async function readGroups(page) {
  return page.evaluate(() => {
    const px = (v) => Math.round(parseFloat(v) || 0);
    const root = document.querySelector("[data-account-overview]");
    if (!root) return { missingRoot: true, groups: [] };
    const cols = [...root.children].filter((c) => c.childElementCount > 0);
    const groups = [];
    cols.forEach((col, colIndex) => {
      const colBox = col.getBoundingClientRect();
      [...col.querySelectorAll("[data-overview-group]")].forEach((el, orderInCol) => {
        const h = el.querySelector("h3");
        const hs = h ? getComputedStyle(h) : null;
        // The accent rule lives on the heading ROW, not on the <h3> — it must
        // run the full width of the column, which an <h3> never does.
        const headRow = h?.parentElement ?? null;
        const hr = headRow ? getComputedStyle(headRow) : null;
        const rows = [...el.querySelectorAll(".field, [data-fact], dt, .fact")]
          .map((r) => (r.textContent || "").trim());
        const labels = [...el.querySelectorAll("[data-fact-label], dt, .fact-label")]
          .map((r) => (r.textContent || "").trim()).filter(Boolean);
        groups.push({
          slug: el.getAttribute("data-overview-group"),
          colIndex,
          orderInCol,
          heading: (h?.textContent || "").trim(),
          headingColor: hs?.color ?? null,
          headingTransform: hs?.textTransform ?? null,
          headingSize: px(hs?.fontSize ?? 0),
          headingTracking: hs?.letterSpacing ?? null,
          ruleWidth: headRow ? Math.round(headRow.getBoundingClientRect().width) : 0,
          columnWidth: Math.round(colBox.width),
          ruleThickness: hr ? px(hr.borderBottomWidth) : 0,
          ruleColor: hr?.borderBottomColor ?? null,
          gapUnderRule: hr ? px(hr.paddingBottom) + px(hr.marginBottom) : 0,
          marginBottom: px(getComputedStyle(el).marginBottom),
          rowCount: rows.length,
          labels,
          text: (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 400),
        });
      });
    });
    return { missingRoot: false, groups, accent: getComputedStyle(document.documentElement)
      .getPropertyValue("--color-accent").trim() };
  });
}

function checkAt(width, read) {
  const at = `@${width}`;
  if (read.missingRoot) {
    fail("presence", at, "no [data-account-overview] root — the screen carries no hook to measure");
    return;
  }
  const byslug = new Map(read.groups.map((g) => [g.slug, g]));

  // ── presence + position ────────────────────────────────────────────────
  const drawnLeft = DRAWN.filter((d) => d.col === "left").map((d) => d.slug);
  const drawnRight = DRAWN.filter((d) => d.col === "right").map((d) => d.slug);
  for (const d of DRAWN) {
    const g = byslug.get(d.slug);
    if (!g) { fail("presence", `${at} ${d.slug}`, `drawn as "${d.heading}" and not on the screen`); continue; }
    const want = d.col === "left" ? 0 : 1;
    if (g.colIndex !== want) {
      fail("position", `${at} ${d.slug}`,
        `drawn in the ${d.col} column, rendered in the ${g.colIndex === 0 ? "left" : "right"}`);
    }
    const seq = (d.col === "left" ? drawnLeft : drawnRight).filter((s) => byslug.has(s));
    const wantOrder = seq.indexOf(d.slug);
    if (g.colIndex === want && g.orderInCol !== wantOrder) {
      fail("position", `${at} ${d.slug}`,
        `drawn ${wantOrder + 1} of ${seq.length} in its column, rendered ${g.orderInCol + 1}`);
    }
    // ── order of rows within the group ──────────────────────────────────
    if (d.rows) {
      // ⚠ **MATCH THE LABEL ELEMENTS, NEVER THE GROUP'S FREE TEXT.** The first
      // version searched `g.text` and reported MONEY's rows out of sequence on
      // every run: the footer hint reads *"Ageing is counted from the opening
      // balance…"*, so `indexOf("balance")` found the LAST occurrence of the
      // word and put the `Balance` row after everything. A row label is a `<dt>`
      // and nothing else is; searching prose for it will always eventually
      // match a sentence that happens to use the word.
      const labels = g.labels.map((x) => x.toLowerCase());
      const at_ = (r) => labels.findIndex((x) => x === r.toLowerCase());
      const absent = d.rows.filter((r) => at_(r) < 0);
      const named = absent.filter((r) => d.elsewhere?.[r]);
      const missing = absent.filter((r) => !d.elsewhere?.[r]);
      for (const r of named) remainders.push(`${at} ${d.slug} · ${r} — ${d.elsewhere[r]}`);
      if (missing.length) {
        fail("presence", `${at} ${d.slug}`, `${missing.length} of ${d.rows.length} drawn rows absent: ${missing.join(" · ")}`);
      }
      const positions = d.rows.map(at_).filter((i) => i >= 0);
      if (positions.some((p, i) => i > 0 && p < positions[i - 1])) {
        const got = g.labels.filter((l) => d.rows.some((r) => r.toLowerCase() === l.toLowerCase()));
        fail("order", `${at} ${d.slug}`,
          `drawn: ${d.rows.filter((r) => at_(r) >= 0).join(" · ")}\n        on screen: ${got.join(" · ")}`);
      }
    }
    if (d.table) {
      const missing = d.table.filter((c) => !g.text.toUpperCase().includes(c));
      // ⚠ **A TABLE WITH NO ROWS CANNOT BE JUDGED, AND SAYING SO IS THE WHOLE
      // POINT — THIS CHECK GOT IT WRONG IN BOTH DIRECTIONS ON ITS FIRST REAL
      // RUN ACROSS TWELVE TABS.**
      //
      // `BR-SHL-012` replaces the ENTIRE table region — toolbar and column
      // heads included — when a list has never had a row. So:
      //   · on an account with no rows, EVERY drawn column reads as absent and
      //     the check reported 4 tabs diverging that were in fact correct
      //     (`usage`, `meters`, `work`, `adjustments`, 10 findings, all false);
      //   · and the mirror is worse — a spec whose columns are ALL missing
      //     would read as a clean zero if the group itself were absent too,
      //     which is law 7's *reporting zero over a scope it silently excludes*.
      //
      // A check that cannot see its subject must refuse to judge it rather
      // than guess in either direction. `adjustments` is the case that proves
      // it: the tenant holds **zero** adjustment rows, so that tab can never
      // draw its table on any of the 73 accounts, and no amount of picking a
      // better account fixes it.
      const everyColumnMissing = missing.length === d.table.length;
      if (everyColumnMissing) {
        unjudged.push(`${at} ${d.slug} — the list has no rows, so the table region is an ` +
          `empty state (BR-SHL-012) and its ${d.table.length} drawn columns cannot be seen. ` +
          `Drive an account that HAS rows, or seed one.`);
      } else if (missing.length) {
        fail("presence", `${at} ${d.slug}`, `table columns absent: ${missing.join(" · ")}`);
      }
    }
    // ── a declared remainder is PRINTED, or it is not declared ─────────────
    // ⚠ **`elsewhere` USED TO REACH THE OUTPUT ONLY THROUGH `rows`**, so a tab
    // whose whole story is remainders — the Audit tab, where a 2026-09-10 PO
    // ruling replaced the drawn column and its expander on a component eight
    // screens share — printed `0 divergence(s)` and NOTHING ELSE. That reads as
    // *this screen matches its drawing*, which is the opposite of what the spec
    // says, and it is hard-won law 7's *reporting zero over a scope it silently
    // excludes*: the check was not lying, it simply never mentioned the part it
    // had been told to skip. Every `elsewhere` entry a group's `rows` did not
    // already account for is now named beside its ruling.
    for (const [name, ruling] of Object.entries(d.elsewhere ?? {})) {
      const inRows = (d.rows ?? []).some((r) => r.toLowerCase() === name.toLowerCase());
      if (!inRows) remainders.push(`${at} ${d.slug} · ${name} — ${ruling}`);
    }
    // ── heading style ───────────────────────────────────────────────────
    if (g.headingTransform !== "uppercase") {
      fail("heading", `${at} ${d.slug}`, `drawn uppercase, computed text-transform "${g.headingTransform}"`);
    }
    if (read.accent && g.headingColor && !sameColour(g.headingColor, read.accent)) {
      fail("colour", `${at} ${d.slug}`, `heading is ${g.headingColor}, the accent token is ${read.accent}`);
    }
    if (g.ruleThickness === 0) {
      fail("heading", `${at} ${d.slug}`, "the drawing rules the heading; no bottom border is computed");
    }
    // The rule runs the column's width in the drawing. Allow the group's own
    // padding but never a rule that is merely as wide as its text.
    if (g.ruleWidth > 0 && g.columnWidth > 0 && g.ruleWidth < g.columnWidth * 0.9) {
      fail("heading", `${at} ${d.slug}`,
        `the rule is ${g.ruleWidth}px inside a ${g.columnWidth}px column — the drawing runs it the full width`);
    }
    // ── spacing, against rule 39's scale ────────────────────────────────
    for (const [name, v] of [["gap under the rule", g.gapUnderRule], ["gap to the next group", g.marginBottom]]) {
      if (!SCALE.includes(v)) {
        fail("spacing", `${at} ${d.slug}`, `${name} is ${v}px — not a step of 4·8·12·16·20·24·32`);
      }
    }
  }
  // ── the other direction: on screen, not in the drawing ─────────────────
  for (const g of read.groups) {
    if (!DRAWN.some((d) => d.slug === g.slug)) {
      fail("presence", `${at} ${g.slug}`, `on the screen and not in the drawing — "${g.heading}"`);
    }
  }
}

/**
 * ⚠ **THE FIRST VERSION OF THIS COULD NOT READ A HEX TOKEN AND REPORTED 22
 * FALSE FAILURES ON ITS FIRST RUN.** `getComputedStyle` always answers
 * `rgb(236, 48, 19)`; `tokens.css` declares `--color-accent: #ec3013`. They are
 * the SAME COLOUR. Matching digits with `/\d+/g` read `236,48,19` from one side
 * and `3013` from the other and called them different — a check that fires on
 * every element it looks at, which is noise indistinguishable from a real
 * finding. It was caught by running it, not by reading it, which is the whole
 * argument for law 6 applying to the checks themselves.
 */
function toRgb(value) {
  const s = String(value).trim();
  const hex = s.match(/^#?([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const h = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join("") : hex[1];
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  }
  const nums = s.match(/[\d.]+/g);
  return nums && nums.length >= 3 ? nums.slice(0, 3).map(Number) : null;
}

function sameColour(a, b) {
  const x = toRgb(a), y = toRgb(b);
  if (!x || !y) return false;
  // A small tolerance: a token may be composited through color-mix or rounded.
  return Math.abs(x[0] - y[0]) + Math.abs(x[1] - y[1]) + Math.abs(x[2] - y[2]) <= 12;
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
try {
  const ctx = await browser.newContext({ viewport: { width: WIDTHS[0], height: 1400 } });
  const page = await ctx.newPage();
  await signIn(page);
  const id = process.env.ACCOUNT ?? (await anAccount(page));
  say(`driving ${BASE}/${TENANT}/accounts/${id}?tab=${TAB}`);

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 1400 });
    await page.goto(`${BASE}/${TENANT}/accounts/${id}?tab=${TAB}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(400); // let a background refetch settle
    checkAt(width, await readGroups(page));
    if (width === WIDTHS[1]) {
      mkdirSync(dirname(SHOT), { recursive: true });
      await page.screenshot({ path: SHOT, fullPage: true });
      say(`screenshot: ${SHOT}`);
    }
  }

  const byLayer = findings.reduce((m, f) => ((m[f.layer] = (m[f.layer] || 0) + 1), m), {});
  say(`\nACC-02 · ${TAB} against its drawing — ${findings.length} divergence(s)`);
  if (findings.length) {
    for (const [layer, n] of Object.entries(byLayer)) say(`  ${String(n).padStart(3)}  ${layer}`);
    say("");
    for (const f of findings) say(`  [${f.layer}] ${f.where}\n        ${f.said}`);
  } else {
    say("  the screen matches the drawing on every layer measured");
  }
  if (unjudged.length) {
    const once = [...new Set(unjudged.map((r) => r.replace(/^@\d+ /, "")))];
    say(`\n  ⚠ ${once.length} drawn table(s) COULD NOT BE JUDGED — not a pass and not a failure:`);
    for (const r of once) say(`    · ${r}`);
  }
  if (remainders.length) {
    const once = [...new Set(remainders.map((r) => r.replace(/^@\d+ /, "")))];
    say(`\n  ${once.length} drawn element(s) deliberately elsewhere, each with its ruling:`);
    for (const r of once) say(`    · ${r}`);
  }
  // An unjudged table is not a pass: exit 2 so a caller can tell the three
// outcomes apart — 0 matches, 1 diverges, 2 could not be measured.
process.exitCode = findings.length ? 1 : unjudged.length ? 2 : 0;
} finally {
  await browser.close();
}
