#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-048 · the Templates & Notifications teardown (v1, 29 Aug 2026)
//           · wave H, the screen-repair lane (30 Aug 2026)
// Screens:  SET-09 (templates list + one template open) · SET-12 / SET-12D
//           · SET-08 (Numbering), which the same PO report covers
// Rules:    B14 rule 16 (a pagination footer on every list table) · B14 rule 21
//           (per-file Tailwind migration) · BR-SHL-025 (a refusal carries its
//           reason) · OQ-274 (desktop-first, ruled breakpoints only)
// Why:      hard-won law 6 — NO GATE LOOKS AT RENDERED OUTPUT, and three weeks
//           of fixes to these screens did not converge because every check we
//           have reads SOURCE. jsdom performs no layout, so a column collapsed
//           to 108px passes every existing test.
// ───────────────────────────────────────────────────────
/**
 * Measure the teardown screens in a REAL browser, print the geometry, and FAIL
 * when a number leaves the range the repair landed it in.
 *
 * ⚠ **THIS ASSERTED NOTHING UNTIL 2026-08-30, AND THAT WAS THE WHOLE PROBLEM.**
 * The first version's job was to produce numbers a person could put beside the
 * teardown's drawings, and it did: the template designer's frame was 448px
 * inside a 1424px page, the notifications list was ten sections all 330px with
 * a widest-to-narrowest ratio of exactly 1.00, and five tables were between
 * 14px and 692px wider than the cards holding them. Every one of those numbers
 * was invisible to `tsc`, to eslint, to G31 and to 220 passing DOM cases,
 * because **no check in this repo renders anything**.
 *
 * So it exits non-zero now. A printer tells you what happened after somebody
 * looks; a gate tells the lane that broke it, at the moment it breaks it —
 * which is the only version of this that stops the PO being the check.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8000 --noreload &
 *   (cd 07-frontend && npx vite build && API_PROXY_TARGET=http://127.0.0.1:8000 node server.mjs &)
 *   node 10-scripts/render-checks/cr048-notifications-geometry.mjs
 *
 * Use other ports if those are taken — `SMOKE_BASE` is the frontend's origin.
 * Env: SMOKE_BASE, SMOKE_TENANT, SMOKE_EMAIL, SMOKE_PASSWORD, SMOKE_OUT — the
 * same names `12-smoke-walkthrough.mjs` uses, so one stack serves both.
 *
 * ── WHAT IT ASSERTS, AND WHY EACH ONE EARNED ITS PLACE ───────────────────
 * Every threshold below is a MEASURED number with slack, never a round one
 * somebody liked. The measured value is quoted beside each check so the next
 * lane can tell a regression from a redesign.
 *
 *   1. NO `.settings-grid` ON THE THREE SCREENS. That container is
 *      `repeat(auto-fit, minmax(320px, 1fr))` — the right shape for a tab that
 *      IS a row of equal cards, and the cause of every geometry defect in this
 *      CR for a screen that has a layout of its own. This is the root-cause
 *      check and it is the cheapest one here.
 *   2. THE DESIGNER GETS THE PAGE. Frame ≥ 1200px (measured 1392, was 448),
 *      rail ≥ 300px (measured 344, was 108 — one word per line), output ≥ 900px
 *      (measured 1032, was 324).
 *   3. THE NOTIFICATIONS LIST IS CARDS AND A RAIL. Two tracks, the body at
 *      least three times the rail (measured 1056 : 320). A ratio near 1.00 is
 *      the arithmetic signature of the defect the PO photographed.
 *   4. NO TABLE ESCAPES ITS SECTION, and no page scrolls sideways. A table
 *      inside its own `overflow-x` box is fine — that is the box being
 *      measured, not the table.
 *   5. EVERY LIST TABLE HAS A PAGINATION FOOTER (B14 rule 16). Two had none.
 *      ⚠ This does NOT check the page SIZE: 50/100/200/500/1000 default 50 is
 *      the PO's own ratified ladder (2026-08-09) and is not this lane's to
 *      move — see the CR row.
 *   6. NO REFUSAL SETS THE HEIGHT OF ITS CARD. A danger-tier box taller than
 *      170px is the shape that made a 330px card 318px of red.
 *   7. THE NUMBERING HEADER IS ONE LINE (it was two, because "Next Counter"
 *      needed 146px in a 130px column), and the sticky rail is fully reachable
 *      at 1280×720, where 89px of its foot used to be below the window.
 *   8. AND THE TABS THAT ARE GENUINELY A CARD GRID ARE UNCHANGED — Company,
 *      Security and Regional still resolve to three equal tracks. Fixing
 *      Notifications by widening the shared grid would have been a worse day
 *      than the one being fixed, and this is what says so.
 *
 *   ── CR-048 wave J, 30 Aug 2026 ─────────────────────────────────────────
 *   9. THE SUB-STRIP CARRIES FOUR TABS, and the rights wording and the email
 *      sender are on their own and NOT on the settings tab. PO, walking the
 *      deployed v2.86.0: *"Create a seperate tab for this - under notification
 *      only"* and *"Email sender (SMTP) - create seperate tab under
 *      notification"*.
 *  10. ⚠ **THE BR-NOT-015 WARNING TRAVELLED WITH THE RIGHTS CLAUSES**, in full
 *      and still capped. This is the assertion with a legal consequence: the
 *      five clauses are NOT ours to invent — disconnection rules differ by
 *      state and by utility — and the red notice saying so is a deliberate
 *      refusal to imply otherwise. A card that renders without it LOOKS
 *      FINISHED, which is why it is asserted by name in a browser.
 *  11. THE SETTINGS TAB IS SHORTER, and this is the number the whole wave is
 *      for: **4367px before, 2584px after** at 1728×1080 — 1783px and 41% —
 *      because two whole sections became two pages. Threshold 3400px.
 *  12. THE SENDER'S TWO LOAD-BEARING FACTS SURVIVED AS MARKS, not paragraphs:
 *      that configuring it sends nothing, and that the secret field holds a
 *      NAME rather than a password. Each is under 30 characters on the page
 *      with the server's whole 100+ character sentence on `title` — wave I's
 *      discipline, applied to a form instead of a table cell.
 *  13. DEF-2472 — the route sentence carries no internal id and no instruction
 *      naming the page the reader is standing on, and the provenance is on
 *      `data-route-br-ref` where support reads it (DEF-335's own remedy).
 */
// Borrows `playwright-core` from 07-frontend/node_modules and finds a chromium
// under PLAYWRIGHT_BROWSERS_PATH even when the pinned revision is absent — the
// same two tricks `12-smoke-walkthrough.mjs` uses, for the same reason: this
// script must have no dependencies of its own.
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

//: The repository root, derived from THIS FILE rather than from the caller's
//: working directory — the preflight reads `07-frontend/package.json` and
//: walks `06-backend/apps`, and this script gets run from the repo root and
//: from `07-frontend` alike.
const ROOT = fileURLToPath(new URL("../..", import.meta.url));

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr048-geometry";

//: The PO's own browser was ~1600px of content beside the sidebar. Anything
//: narrower would stack the layout LEGITIMATELY and prove nothing.
const VIEWPORT = { width: 1728, height: 1080 };
//: The second size is a plain laptop, and it is where the numbering rail's
//: foot fell off the bottom of the window. A rail that only works on a large
//: monitor is a rail that does not work.
const LAPTOP = { width: 1280, height: 720 };

mkdirSync(OUT, { recursive: true });

// ── The ledger of failures. Nothing throws mid-run: a lane fixing one of these
// ── wants ALL the numbers, not the first one that tripped.
const failures = [];
function check(ok, message) {
  if (ok) {
    console.log(`   ✓ ${message}`);
  } else {
    console.log(`   ⛔ ${message}`);
    failures.push(message);
  }
}

/** Every direct child of `selector`, with its width and its text density. */
const GEOMETRY = (selector) => `(() => {
  const el = document.querySelector(${JSON.stringify(selector)});
  if (!el) return { missing: true };
  const kids = [...el.children].map((c) => {
    const r = c.getBoundingClientRect();
    const text = (c.innerText || "").trim();
    const lines = text ? text.split("\\n").filter(Boolean) : [];
    const longest = lines.reduce((m, l) => Math.max(m, l.length), 0);
    return {
      tag: c.tagName.toLowerCase(),
      testid: c.getAttribute("data-testid"),
      width: Math.round(r.width),
      height: Math.round(r.height),
      lines: lines.length,
      longestLine: longest,
      firstLine: lines[0] ? lines[0].slice(0, 46) : "",
    };
  });
  const r = el.getBoundingClientRect();
  return {
    width: Math.round(r.width),
    display: getComputedStyle(el).display,
    columns: getComputedStyle(el).gridTemplateColumns,
    kids,
  };
})()`;

/**
 * Every table on the page: how far it runs past the box that is supposed to
 * contain it, and whether it carries a footer.
 *
 * ⚠ THE BOX, NOT THE TABLE. A table inside its own `overflow-x: auto` wrapper
 * is CLIPPED, and `getBoundingClientRect` reports its full unclipped width —
 * so measuring the table would report a 470px table in a 312px scroller as a
 * 142px escape when nothing escapes at all. The scroller is what the reader
 * sees, so the scroller is what is measured. This distinction cost this lane a
 * false alarm before it was written down.
 */
const TABLES = `(() => {
  return [...document.querySelectorAll("table")].map((tb) => {
    const box = tb.parentElement;
    const bcs = getComputedStyle(box);
    const scrolls = bcs.overflowX === "auto" || bcs.overflowX === "scroll";
    const outer = scrolls ? box : tb;
    const sec = tb.closest("section,aside") || box;
    const cap = sec.querySelector("h3");
    return {
      name: cap ? cap.innerText.trim().split("\\n")[0].slice(0, 34) : "(unnamed)",
      width: Math.round(outer.getBoundingClientRect().width),
      section: Math.round(sec.getBoundingClientRect().width),
      escape: Math.round(
        outer.getBoundingClientRect().right - sec.getBoundingClientRect().right,
      ),
      scrolls,
      rows: tb.querySelectorAll("tbody tr").length,
      pager: sec.querySelector(".table-pager") !== null,
      // ⚠ A TABLE WHOSE ROWS HOLD TYPED FIELDS IS A FORM, NOT A LIST, and
      // B14 rule 16 is a rule about lists. The numbering screen is the case
      // that says why: 34 rows of number series, every row an editable format
      // and counter, and ONE Save that commits the whole table in a single
      // transaction (BR-TEN-024). Paging that would hide half the edits from
      // the button that saves them — a worse defect than the missing footer.
      // A checkbox does not count: the rules matrix toggles rows on and off
      // and is still a list of thirty events, and it carries a footer.
      isForm:
        tb.querySelectorAll(
          "tbody input:not([type=checkbox]):not([type=radio]), tbody select, tbody textarea",
        ).length > 0,
    };
  });
})()`;

/** Every danger-tier box, with the height it is taking from its card. */
const REFUSALS = `(() => {
  return [...document.querySelectorAll("[data-refusal]")]
    .map((el) => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return {
        testid: el.getAttribute("data-testid"),
        width: Math.round(r.width),
        height: Math.round(r.height),
        chars: (el.innerText || "").trim().length,
        maxHeight: cs.maxHeight,
      };
    })
    .filter((n) => n.height > 0);
})()`;

/**
 * CR-048 wave I — ONE COLUMN OF A LIST, MEASURED.
 *
 * Finds the column by its HEADER TEXT rather than by index, because a column
 * chooser can reorder them and an index would then silently measure a
 * different column and pass.
 *
 * `range.getClientRects()` is the only honest way to count LINE BOXES: a cell
 * is 34px tall whether that is one line with padding or two lines in a shorter
 * row, and `height / lineHeight` guesses. One rect per line box is what the
 * browser actually laid out.
 */
const COLUMN = (label) => `(() => {
  const th = [...document.querySelectorAll("thead th")]
    .find((h) => (h.innerText || "").trim().split("\\n")[0].trim().toLowerCase()
                 === ${JSON.stringify(label)}.toLowerCase());
  if (!th) return { missing: true };
  const index = th.cellIndex;
  const cells = [...document.querySelectorAll("tbody tr")]
    .map((tr) => tr.children[index])
    .filter(Boolean)
    .map((td) => {
      const text = (td.innerText || "").trim();
      let lineBoxes = 0;
      for (const node of td.querySelectorAll("*")) {
        for (const child of node.childNodes) {
          if (child.nodeType === 3 && child.nodeValue.trim() !== "") {
            const r = document.createRange();
            r.selectNodeContents(child);
            lineBoxes += r.getClientRects().length;
          }
        }
      }
      for (const child of td.childNodes) {
        if (child.nodeType === 3 && child.nodeValue.trim() !== "") {
          const r = document.createRange();
          r.selectNodeContents(child);
          lineBoxes += r.getClientRects().length;
        }
      }
      const box = td.getBoundingClientRect();
      return {
        text: text.slice(0, 60),
        chars: text.length,
        lines: text ? text.split("\\n").filter(Boolean).length : 0,
        lineBoxes,
        height: Math.round(box.height),
        icons: td.querySelectorAll("svg").length,
      };
    });
  return {
    label: (th.innerText || "").trim().split("\\n")[0].trim(),
    width: Math.round(th.getBoundingClientRect().width),
    rows: cells.length,
    cells,
  };
})()`;

/** Every heading on the page, so "this section is gone" is a fact and not a
 *  guess about which element held it. */
const HEADINGS = `[...document.querySelectorAll("h1,h2,h3,h4")].map((h) => h.innerText.trim())`;

const SIDEWAYS = `document.documentElement.scrollWidth - document.documentElement.clientWidth`;

/** SET-09's route, and the two templates the PO photographed on 2026-08-30. */
const TEMPLATES_PATH = "/settings/reference-data/templates";
const PO_TEMPLATES = ["email_corrected_bill", "sms_bill_ready"];

/**
 * CR-048 wave I — every place this screen renders PROSE where a value or a
 * short label belongs, measured in characters AND pixels.
 *
 * ⚠ **THE CHARACTER COUNT IS NOT DECORATION.** At the 1728px viewport this
 * script runs, both disabled-control paragraphs fitted on one 18px line, so a
 * pixel-only check reports a healthy screen over 112 characters of explanation
 * sitting under a button — and the same block is three lines deep in the 344px
 * rail and on any smaller window. Measuring only what this viewport happens to
 * show is how these screens passed every check for three weeks.
 *
 * `titleChars` is the other half and it is what makes this safe to enforce: the
 * fix is to MOVE the sentence to the control's tooltip, never to delete it, so
 * a marker whose title is empty is a control that refuses without saying why
 * (BR-SHL-025) and must fail just as loudly as the paragraph did.
 */
const WAVE_I = `(() => {
  const root = document.querySelector("[data-testid='template-detail-page']");
  if (!root) return { missing: true };
  const box = (el) => el.getBoundingClientRect();
  const text = (el) => (el.innerText || "").trim();

  const notes = [...document.querySelectorAll("[data-control-note]")].map((el) => ({
    testid: el.getAttribute("data-testid"),
    chars: text(el).length,
    height: Math.round(box(el).height),
    titleChars: (el.getAttribute("title") || "").length,
  }));

  const notice = document.querySelector("[data-testid='preview-notice']");
  const previewNotice = notice
    ? {
        chars: text(notice).length,
        height: Math.round(box(notice).height),
        text: text(notice).slice(0, 60),
      }
    : null;

  // How many SEPARATE blocks in the rendered-document column make the
  // "nothing is sent" claim. It was the panel hint plus the notice, with the
  // test-send note saying it a third time in the rail alongside.
  const output = document.querySelector("[data-testid='designer-output']");
  const previewSaysSentOnce = output
    ? [...output.querySelectorAll("p, .panel-hint")].filter((el) =>
        /nothing (is |here is )?sent|not sent|nothing leaves/i.test(text(el)),
      ).length
    : 0;

  const rows = [...document.querySelectorAll("[data-testid^='merge-field-']")];
  return {
    notes,
    previewNotice,
    previewSaysSentOnce,
    mergeRows: rows.length,
    mergeRowMax: rows.reduce((m, r) => Math.max(m, Math.round(box(r).height)), 0),
    mergeBadges: document.querySelectorAll("[data-testid^='merge-field-'] [data-badge]").length,
    historyOnEditTab: document.querySelector("[data-testid='version-history']") !== null,
    historyLink: (() => {
      const el = document.querySelector("[data-testid='history-link']");
      return el ? text(el) : null;
    })(),
  };
})()`;

/** The version history on its own page: does it fit, and is the trail cell a
 *  VALUE rather than a rendered code comment? */
const HISTORY_PAGE = `(() => {
  const page = document.querySelector("[data-testid='version-history-page']");
  const table = document.querySelector("[data-testid='version-history']");
  if (!page || !table) {
    return { page: page !== null, back: false, table: null, trail: [],
             overflow: 0, sideways: ${SIDEWAYS} };
  }
  const scroller = table.parentElement;
  const card = table.closest("section");
  const r = (el) => el.getBoundingClientRect();
  return {
    page: true,
    back: document.querySelector("[data-testid='history-back']") !== null,
    table: { width: Math.round(r(scroller).width) },
    // ⚠ THE SCROLLER, NOT THE TABLE — a table inside its own overflow-x box is
    // CLIPPED, and getBoundingClientRect reports its full unclipped width. The
    // scroller is what the reader sees. (The same distinction the TABLES probe
    // above records costing this lane a false alarm.)
    overflow: Math.round(r(scroller).right - r(card).right),
    trail: [...document.querySelectorAll("[data-testid^='version-trail-']")].map((el) => ({
      height: Math.round(r(el).height),
      chars: (el.innerText || "").trim().length,
      text: (el.innerText || "").trim(),
    })),
    sideways: ${SIDEWAYS},
  };
})()`;

async function report(page, label, selector) {
  const g = await page.evaluate(GEOMETRY(selector));
  console.log(`\n── ${label}  (${selector})`);
  if (g.missing) {
    console.log("   (not on the page)");
    return null;
  }
  console.log(`   container ${g.width}px · display:${g.display} · columns:${g.columns}`);
  for (const k of g.kids) {
    const id = k.testid ? `[${k.testid}]` : `<${k.tag}>`;
    // The longest line is the tell: a column wide enough to read holds 40+
    // characters; one holding fewer than 20 is wrapping mid-phrase.
    const flag = k.longestLine > 0 && k.longestLine < 20 ? "  ⚠ WRAPS MID-PHRASE" : "";
    console.log(
      `     ${id.padEnd(26)} ${String(k.width).padStart(5)}px  ` +
        `${String(k.lines).padStart(3)} lines  longest ${String(k.longestLine).padStart(3)} chars` +
        `  "${k.firstLine}"${flag}`,
    );
  }
  return g;
}

/** Assertions 4, 5 and 6, which are the same three questions on every screen. */
async function checkTablesAndRefusals(page, screen) {
  const tables = await page.evaluate(TABLES);
  for (const t of tables) {
    console.log(
      `     table «${t.name}» ${t.width}px in a ${t.section}px section` +
        `${t.scrolls ? " (scrolls inside its own box)" : ""} · ${t.rows} rows · ` +
        `footer ${t.pager ? "yes" : "NO"}`,
    );
  }
  for (const t of tables) {
    check(
      t.escape <= 1,
      `${screen}: «${t.name}» stays inside its card` +
        (t.escape > 1 ? ` — it runs ${t.escape}px past it, over whatever is beside it` : ""),
    );
    // B14 rule 16 exempts a summary table about one thing; a list of more than
    // ten rows is not that, and 10 is the smallest list anyone would page.
    if (t.rows > 10 && !t.isForm) {
      check(t.pager, `${screen}: «${t.name}» (${t.rows} rows) has a pagination footer`);
    } else if (t.rows > 10) {
      console.log(
        `     («${t.name}» is a form with one Save, not a list — B14 rule 16 does not page it)`,
      );
    }
  }

  const refusals = await page.evaluate(REFUSALS);
  for (const n of refusals) {
    if (n.height > 60) {
      console.log(
        `     refusal [${n.testid}] ${n.width}×${n.height}px · ${n.chars} chars · max-height ${n.maxHeight}`,
      );
    }
  }
  for (const n of refusals) {
    // 170px is a paragraph; past it the box is deciding how tall the card is.
    // Measured worst case before the repair: 318px in a 330px card.
    check(
      n.height <= 170,
      `${screen}: the refusal [${n.testid}] takes ${n.height}px of its card` +
        (n.height > 170 ? " — past 170px it is the thing deciding how tall the card is" : ""),
    );
  }

  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `${screen}: the page does not scroll sideways (${sideways}px)`);
}

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

async function shoot(page, name) {
  const path = join(OUT, `${name}.png`);
  await page.screenshot({ path, fullPage: true });
  console.log(`   screenshot → ${path}`);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 140)}`);
  });

  console.log(`geometry: ${BASE} tenant=${TENANT} viewport=${VIEWPORT.width}x${VIEWPORT.height}`);

  await signIn(page);

  // ── PREFLIGHT · IS THE STACK THIS IS POINTED AT ACTUALLY CURRENT? ─────────
  //
  // ⚠ **`DEF-2471` — THIS COST TWO FULL INVESTIGATIONS IN ONE HOUR, AND THE
  // SECOND HAPPENED AFTER THE FIRST WAS UNDERSTOOD.** This harness measures a
  // LIVE STACK: a `vite build` served by `07-frontend/server.mjs`, proxying to
  // a Django `runserver`. Neither rebuilds itself, and the backend runs
  // `--noreload`, so it can NEVER pick up a source change. Point this at a
  // stale stack and it reports FAILURE, in detail, with total confidence, over
  // screens that are correct — and every number it prints is true of an app
  // nobody is running any more.
  //
  // First time: `dist/` was 2.5 hours old and **17 assertions failed**, every
  // one of them a fix that WAS in the source. Second time: the frontend was
  // fresh and the BACKEND had been up five hours, so **6 assertions failed on
  // strings the backend source no longer contains**.
  //
  // **A check whose output cannot distinguish "the screen is broken" from "you
  // are looking at yesterday's screen" is worse than no check, because it is
  // trusted** — CLAUDE.md law 11's own words about `--stat`. So this REFUSES
  // rather than measuring, with exit code 2 so a caller can tell a stale stack
  // from a real geometry failure.
  //
  // ⚠ **AND WHERE IT CANNOT KNOW, IT SAYS SO** rather than passing. A probe
  // that silently no-ops is the thing law 1 is about: this repo has shipped a
  // guard whose docstring claimed a guarantee it never checked.
  async function preflight(page, browser) {
    const repoVersion = JSON.parse(
      readFileSync(join(ROOT, "07-frontend", "package.json"), "utf8"),
    ).version;
    // ⚠ AFTER SIGN-IN, NOT BEFORE. The version chip lives in the app shell and
    // the shell is not drawn on the sign-in page — the first draft of this
    // probe ran there, found nothing, and reported "not checked" on every run.
    const served = await page.evaluate(
      `(() => {
         const el = document.querySelector("[data-testid='app-version']");
         return el ? (el.innerText || "").trim().replace(/^v/, "") : null;
       })()`,
    );
    if (served === null) {
      console.log(
        "   preflight: no [data-testid='app-version'] on the page —" +
          " FRONTEND STALENESS IS NOT BEING CHECKED on this run",
      );
    } else if (served !== repoVersion) {
      console.error(
        `\nSTALE FRONTEND — refusing to measure.\n` +
          `  the repo says   ${repoVersion}  (07-frontend/package.json)\n` +
          `  the server says ${served}  (${BASE})\n\n` +
          `  Rebuild first:  (cd 07-frontend && npx vite build)\n` +
          `  Every geometry number below this line would describe an app that is\n` +
          `  no longer what the source says. That is not a screen defect.\n`,
      );
      await browser.close();
      process.exit(2);
    } else {
      console.log(`   preflight: frontend build is current (${served})`);
    }

    // The backend has no version endpoint (`CR-004 §7` records that as owed),
    // so it is checked by AGE — and the hard part is finding the RIGHT server.
    // Six `runserver` processes are usually up, one per lane, and the first
    // draft of this probe picked whichever `ps` listed first and refused on a
    // server this harness does not talk to.
    //
    // So it is resolved rather than guessed: BASE's port → the `server.mjs`
    // process serving it → that process's own `API_PROXY_TARGET` (out of
    // `/proc/<pid>/environ`, which is the only place it exists) → the
    // `runserver` on that port.
    const wantPort = new URL(BASE).port || "80";
    let target = null;
    let backendPid = null;
    let started = null;
    try {
      const rows = execSync("ps -eo pid,lstart,cmd", { encoding: "utf8" }).split("\n");
      for (const row of rows) {
        // ⚠ `/node server\.mjs/` alone ALSO matches the `/bin/bash -c … nohup
        // node server.mjs …` wrapper that started it, whose own environment
        // carries neither variable. The first draft matched a wrapper, took its
        // empty target, and reported "could not resolve" on every run — the
        // silent no-op this probe exists to avoid. So the row must be the
        // server ITSELF, and a candidate that yields no target is skipped
        // rather than ending the search.
        if (!/(^|\s)node server\.mjs\s*$/.test(row) || /grep/.test(row)) continue;
        const pid = row.trim().split(/\s+/)[0];
        let env;
        try {
          // Per row, not per loop: one unreadable /proc must not abort the scan.
          env = readFileSync(`/proc/${pid}/environ`, "utf8").split("\0");
        } catch {
          continue;
        }
        const port = (env.find((e) => e.startsWith("PORT=")) ?? "PORT=8080").slice(5);
        if (port !== wantPort) continue;
        const found = (env.find((e) => e.startsWith("API_PROXY_TARGET=")) ?? "").slice(17);
        if (!found) continue;
        target = found;
        break;
      }
      if (target) {
        const backendPort = new URL(target).port || "80";
        for (const row of rows) {
          if (!/manage\.py runserver/.test(row) || /grep/.test(row)) continue;
          if (!row.includes(`:${backendPort}`)) continue;
          const m = row.match(/^\s*(\d+)\s+(.{24})\s/);
          if (m) {
            backendPid = m[1];
            started = new Date(m[2]).getTime();
          }
          break;
        }
      }
    } catch {
      /* best-effort: /proc and ps are not guaranteed on every runner */
    }
    if (started === null) {
      console.log(
        `   preflight: could not resolve the backend behind ${BASE}` +
          `${target ? ` (proxy target ${target})` : ""} —` +
          " BACKEND STALENESS IS NOT BEING CHECKED on this run",
      );
      return;
    }
    const changed = execSync(
      `find ${join(ROOT, "06-backend", "apps")} -name '*.py' -newermt @${Math.floor(
        started / 1000,
      )} -print -quit`,
      { encoding: "utf8" },
    ).trim();
    if (changed) {
      console.error(
        `\nSTALE BACKEND — refusing to measure.\n` +
          `  ${BASE} proxies to ${target}, served by pid ${backendPid},\n` +
          `  started ${new Date(started).toISOString()} with --noreload.\n` +
          `  ${changed} has changed since, and --noreload means that server will\n` +
          `  NEVER pick it up.\n\n` +
          `  Restart it, then re-run. Six assertions failed exactly this way on\n` +
          `  2026-08-30, on strings the backend source no longer contained.\n`,
      );
      await browser.close();
      process.exit(2);
    }
    console.log(
      `   preflight: backend (pid ${backendPid} on ${target}) is newer than every backend source file`,
    );
  }
  await preflight(page, browser);

  // ── SET-12 · the notifications list ──────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/settings/notifications`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1400);
  console.log("\n═══ SET-12 · Settings → Notifications ═══");
  await shoot(page, "set12-notifications");
  const grid12 = await page.evaluate(GEOMETRY(".settings-grid"));
  check(
    grid12.missing === true,
    "SET-12 renders no `.settings-grid` — a screen with a layout is not a row of equal cards",
  );
  await report(page, "the page", "[data-testid='notifications-layout']");
  const body = await report(page, "cards and a rail", "[data-testid='notifications-main']");
  const railBox = await page.evaluate(
    `(() => { const r = document.querySelector("[data-testid='notifications-rail']");
      return r ? Math.round(r.getBoundingClientRect().width) : 0; })()`,
  );
  if (body !== null) {
    console.log(`   body ${body.width}px : rail ${railBox}px`);
    // Measured after the repair: 1056 : 320 = 3.30. Before it, ten sections at
    // 330px each — 1.00, which is what "there is no rail" looks like as a
    // number. 2.0 is the loosest reading that is still unambiguously a rail.
    const ratio = body.width / Math.max(railBox, 1);
    check(
      railBox > 0 && ratio >= 2,
      railBox > 0 && ratio >= 2
        ? `SET-12 is cards and a rail (body:rail = ${ratio.toFixed(2)}:1, was 1.00:1)`
        : `SET-12's body and rail are ${ratio.toFixed(2)}:1 — at anything near 1:1 there is no rail, only equal columns`,
    );
  }
  await checkTablesAndRefusals(page, "SET-12");

  // ── a RAW TRANSLATION KEY anywhere on the page ───────────────────────────
  const rawKeys = await page.evaluate(`(() => {
    const hits = [];
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walk.nextNode())) {
      const t = n.nodeValue.trim();
      // A rendered key looks like a dotted path and nothing else.
      if (/^[a-z][a-zA-Z0-9]*(\\.[a-zA-Z0-9_]+){2,}$/.test(t)) hits.push(t);
    }
    return [...new Set(hits)];
  })()`);
  check(rawKeys.length === 0, `SET-12 shows no raw translation key (${rawKeys.join(", ") || "none"})`);


  // ── CR-048 wave I · SET-12 · THREE SECTIONS GONE, ONE PARAGRAPH SHORTENED ─
  //
  // The PO walked the deployed screen and said *"i agree - please remove"* of
  // three whole sections, and of the red note on every unfireable event row:
  // *"keep the fact, kill the paragraph"*. Both halves are measured here,
  // because both are invisible to every other check in this repo: a deleted
  // section still compiles, and a three-line note in a table cell passes `tsc`,
  // eslint and every `toContain` assertion in the suite.
  console.log("\n── CR-048 wave I · what the Notifications tab still holds");
  const headings12 = await page.evaluate(HEADINGS);
  console.log(`     headings: ${headings12.join(" · ")}`);
  for (const gone of [
    "Send-time elections",
    "Which letter each tone sends",
    "Letters this utility can produce",
  ]) {
    check(
      !headings12.some((h) => h.startsWith(gone)),
      !headings12.some((h) => h.startsWith(gone))
        ? `SET-12 no longer draws «${gone}»`
        : `SET-12 still draws «${gone}» — the PO asked for it to be removed`,
    );
  }
  // *"'Messages needing attention' gets its own tab under Notifications."* The
  // settings half must not hold it, and the tab strip must be able to reach it.
  const worklistOnSettings = headings12.some((h) => h.startsWith("Messages needing attention"));
  check(
    !worklistOnSettings,
    worklistOnSettings
      ? "SET-12's settings half still holds the worklist — it was given its own tab so it would stop sharing a page with six cards of configuration"
      : "SET-12's settings half no longer holds the worklist — it has its own tab",
  );
  const subtabs = await page.evaluate(
    `(() => { const s = document.querySelector("[data-testid='notifications-subtabs']");
      return s ? [...s.querySelectorAll("button")].map((b) => b.innerText.trim()) : null; })()`,
  );
  console.log(`     sub-tabs: ${subtabs === null ? "(none)" : subtabs.join(" | ")}`);
  // ⚠ FOUR SINCE CR-048 WAVE J, not two. The PO gave two more rulings on the
  // same strip on 2026-08-30 — *"Create a seperate tab for this - under
  // notification only"* (the rights wording) and *"Email sender (SMTP) -
  // create seperate tab under notification"*. This is the count, not a
  // minimum: a strip that quietly grew a fifth tab is a change nobody ruled.
  check(
    subtabs !== null && subtabs.length === 4,
    subtabs !== null && subtabs.length === 4
      ? `SET-12 has a second level of FOUR (${subtabs.join(" | ")})`
      : `SET-12's sub-tab strip has ${subtabs === null ? "no" : subtabs.length} tab(s), not the four the PO ruled`,
  );

  // ══ CR-048 wave J · TWO SECTIONS LEFT THIS TAB, AND THE PAGE IS SHORTER ══
  //
  // Both blocks are that same fault at SECTION scale: prose and a form stacked
  // under six cards of ordinary configuration on a screen a clerk opens to
  // change a sender address. Neither is too long for a page — each IS a
  // different page.
  for (const gone of ["Email sender", "Customer rights wording"]) {
    const still = headings12.some((h) => h.startsWith(gone));
    check(
      !still,
      still
        ? `SET-12's settings half still draws «${gone}» — it was given its own tab so it would stop sharing a page with six cards of configuration`
        : `SET-12's settings half no longer draws «${gone}» — it has its own tab`,
    );
  }
  // ⚠ **THE HEIGHT IS THE WHOLE POINT AND IT IS THE ONLY THING NO OTHER CHECK
  // IN THIS REPO CAN SEE.** Measured on the running app at 1728×1080, same
  // viewport both times: the settings tab was **4367px** before wave J and is
  // **2584px** after — 1783px shorter, a 41% drop, because two whole sections
  // moved to tabs of their own. 3400 is the loosest threshold that still
  // separates the two unambiguously; it is a measured midpoint with slack, not
  // a round number somebody liked.
  const stackHeight = await page.evaluate(
    `(() => { const el = document.querySelector("[data-testid='notifications-layout']");
      return el ? Math.round(el.getBoundingClientRect().height) : -1; })()`,
  );
  console.log(`     settings-tab content height: ${stackHeight}px (was 4367, now ~2584)`);
  check(
    stackHeight > 0 && stackHeight < 3400,
    stackHeight > 0 && stackHeight < 3400
      ? `SET-12's settings half is ${stackHeight}px — down from 4367px before the two tabs`
      : `SET-12's settings half is ${stackHeight}px, at or above the 4367px it was before wave J — a section came back`,
  );

  // ⚠ THE MARKER, AND ITS HEIGHT IS THE WHOLE POINT. Before wave I this was a
  // `RefusalStrip` carrying a 95-character sentence inside a table cell: it wrapped
  // to three lines and set the height of every row it appeared on. One line box is
  // the assertion, not "shorter than before" — a marker that can wrap is a
  // paragraph again the first time the column narrows.
  const markers = await page.evaluate(`(() => {
    return [...document.querySelectorAll("[data-testid^='rule-noTrigger-']")].map((el) => {
      const r = document.createRange();
      r.selectNodeContents(el);
      const box = el.getBoundingClientRect();
      return {
        testid: el.getAttribute("data-testid"),
        text: (el.innerText || "").trim(),
        lineBoxes: r.getClientRects().length,
        height: Math.round(box.height),
        title: (el.getAttribute("title") || "").length,
        danger: el.hasAttribute("data-refusal"),
      };
    });
  })()`);
  if (markers.length === 0) {
    console.log("     (no unfireable event on this page — nothing to measure)");
  }
  for (const m of markers.slice(0, 3)) {
    console.log(
      `     marker [${m.testid}] "${m.text}" · ${m.lineBoxes} line box(es) · ${m.height}px · ` +
        `title ${m.title} chars · danger tier ${m.danger ? "YES" : "no"}`,
    );
  }
  const worstMarker = markers.reduce((w, m) => (m.lineBoxes > w ? m.lineBoxes : w), 0);
  const tallestMarker = markers.reduce((w, m) => (m.height > w ? m.height : w), 0);
  check(
    markers.length > 0 && worstMarker === 1,
    markers.length > 0 && worstMarker === 1
      ? `every unfireable-event marker is ONE line (${markers.length} of them, tallest ${tallestMarker}px, was 3 lines / 60px+)`
      : `an unfireable-event marker wraps to ${worstMarker} lines — that is the paragraph the PO asked to be killed`,
  );
  check(
    markers.every((m) => m.title > 40),
    markers.every((m) => m.title > 40)
      ? "…and every one of them still carries the WHOLE sentence on hover (BR-NOT-018 keeps its fact)"
      : "a marker lost the full sentence — BR-NOT-018 needs the event NAMED and REFUSED, not merely flagged",
  );
  check(
    markers.every((m) => !m.danger),
    markers.every((m) => !m.danger)
      ? "…and none of them is the danger tier, which B14 rule 6 keeps for a destructive commit"
      : "an unfireable-event marker is still painted as a refusal — twelve red boxes down one column is what taught the reader to stop reading them",
  );

  // ── the Messages tab, where the worklist went ────────────────────────────
  await page.goto(`${BASE}/${TENANT}/settings/notifications/messages`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1400);
  console.log("\n═══ SET-12 · the Messages tab ═══");
  await shoot(page, "set12-messages");
  const headingsMsg = await page.evaluate(HEADINGS);
  console.log(`     headings: ${headingsMsg.join(" · ")}`);
  check(
    headingsMsg.some((h) => h.startsWith("Messages needing attention")),
    headingsMsg.some((h) => h.startsWith("Messages needing attention"))
      ? "the worklist has its own tab and the worklist is on it"
      : "the Messages tab does not draw the worklist — the block was removed rather than moved",
  );
  const settingsFollowed = headingsMsg.some((h) => h.startsWith("Email sender"));
  check(
    !settingsFollowed,
    settingsFollowed
      ? "…but the settings cards followed it onto the Messages tab, which is the same mixing one tab further along"
      : "…and the settings cards did not follow it there",
  );
  await checkTablesAndRefusals(page, "SET-12 messages");

  // ── CR-048 wave J · the rights tab, where the rights wording went ────────
  //
  // ⚠ **THE ASSERTION THIS SECTION EXISTS FOR IS THE SECOND ONE, AND IT IS A
  // LEGAL ONE.** `BR-NOT-015` says the five clauses are NOT ours to invent:
  // disconnection rules differ by state and by utility, and the platform ships
  // a starting point rather than a regulator's words. The red notice saying so
  // is a deliberate refusal to imply otherwise, and it must arrive on the tab
  // the clauses arrived on. A card rendering without its warning LOOKS
  // FINISHED — which is exactly why this is measured in a browser and asserted
  // by name rather than left to a reader to notice.
  await page.goto(`${BASE}/${TENANT}/settings/notifications/rights`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1400);
  console.log("\n═══ SET-12 · the Customer rights wording tab ═══");
  await shoot(page, "set12-rights");
  const headingsRights = await page.evaluate(HEADINGS);
  console.log(`     headings: ${headingsRights.join(" · ")}`);
  check(
    headingsRights.some((h) => h.startsWith("Customer rights wording")),
    headingsRights.some((h) => h.startsWith("Customer rights wording"))
      ? "the rights wording has its own tab and the wording is on it"
      : "the rights tab does not draw the wording — the block was removed rather than moved",
  );
  const rightsNotice = await page.evaluate(`(() => {
    const el = document.querySelector("[data-testid='rights-platform-notice']");
    if (!el) return null;
    const box = el.getBoundingClientRect();
    return {
      chars: (el.innerText || "").trim().length,
      text: (el.innerText || "").trim().slice(0, 60),
      height: Math.round(box.height),
      danger: el.hasAttribute("data-refusal"),
    };
  })()`);
  check(
    rightsNotice !== null,
    rightsNotice !== null
      ? `⚠ the BR-NOT-015 warning TRAVELLED WITH THE CLAUSES (${rightsNotice.chars} chars, ${rightsNotice.height}px, danger tier ${rightsNotice.danger ? "YES" : "no"})`
      : "⚠ THE BR-NOT-015 WARNING IS NOT ON THE RIGHTS TAB — platform-supplied placeholder wording is now presented as if it were the utility's own regulator's words, on the most consequential document this product produces",
  );
  if (rightsNotice !== null) {
    // Not softened, either. The two halves CR-007 said may never be dropped.
    check(
      rightsNotice.text.length > 0 && rightsNotice.chars > 300,
      rightsNotice.chars > 300
        ? `…and it was not softened in the move (${rightsNotice.chars} chars, the server's sentence in full)`
        : `…but it has been shortened to ${rightsNotice.chars} chars — CR-007 forbade softening it`,
    );
    // Wave H's cap still holds on its new tab: a refusal may not set the height
    // of its card. It was 238 × 318px on the old tab before that fix.
    check(
      rightsNotice.height <= 170,
      rightsNotice.height <= 170
        ? `…and it is still capped at ${rightsNotice.height}px, so it does not set the height of its card`
        : `…but it is ${rightsNotice.height}px, above wave H's 170px cap — the tallest refusal in the product is back`,
    );
  }
  const rightsClauses = await page.evaluate(
    `document.querySelectorAll("[data-testid^='rights-clause-']").length`,
  );
  console.log(`     rights clauses drawn: ${rightsClauses}`);
  check(
    rightsClauses > 0,
    rightsClauses > 0
      ? `the clauses the warning warns about are on the same tab as the warning (${rightsClauses})`
      : "the rights tab draws a warning and no clauses — a warning that outlived what it warns about",
  );
  const senderFollowedRights = headingsRights.some((h) => h.startsWith("Email sender"));
  check(
    !senderFollowedRights,
    senderFollowedRights
      ? "…but the sender card followed it onto the rights tab, which is the same mixing one tab along"
      : "…and nothing else followed it there",
  );
  await checkTablesAndRefusals(page, "SET-12 rights");

  // ── CR-048 wave J · the sender tab, where the SMTP card went ─────────────
  await page.goto(`${BASE}/${TENANT}/settings/notifications/sender`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1400);
  console.log("\n═══ SET-12 · the Email sender (SMTP) tab ═══");
  await shoot(page, "set12-sender");
  const headingsSender = await page.evaluate(HEADINGS);
  console.log(`     headings: ${headingsSender.join(" · ")}`);
  check(
    headingsSender.some((h) => h.startsWith("Email sender")),
    headingsSender.some((h) => h.startsWith("Email sender"))
      ? "the email sender has its own tab and the card is on it"
      : "the sender tab does not draw the card — the block was removed rather than moved",
  );
  const senderFields = await page.evaluate(
    `["smtp_host","smtp_port","smtp_username","smtp_secret_ref","sender_from_address"]
       .filter((n) => document.querySelector("[data-testid='sender-" + n + "']") !== null)`,
  );
  check(
    senderFields.length === 5,
    senderFields.length === 5
      ? "…with all five inputs (a moved form that lost a field is a moved card that lost its warning)"
      : `…but only ${senderFields.length} of its five inputs came with it: ${senderFields.join(", ")}`,
  );
  // ⚠ **THE TWO LOAD-BEARING FACTS, AS MARKS RATHER THAN PARAGRAPHS.** The PO
  // ruled both must survive the move: that configuring this SENDS NOTHING, and
  // that the secret field holds the NAME of a secret rather than a password.
  // Wave I's own discipline applies — the fact stays, the paragraph goes, and
  // the whole sentence is one hover away. Three stacked paragraphs above the
  // first input were 100+ characters each; a mark is three or four words.
  const senderMarks = await page.evaluate(`(() => {
    return [...document.querySelectorAll(
      "[data-testid='sender-no-send'],[data-testid='sender-route']," +
      "[data-testid^='sender-note-']")].map((el) => {
      const r = document.createRange();
      r.selectNodeContents(el);
      return {
        testid: el.getAttribute("data-testid"),
        text: (el.innerText || "").trim(),
        chars: (el.innerText || "").trim().length,
        lineBoxes: r.getClientRects().length,
        title: (el.getAttribute("title") || "").length,
      };
    });
  })()`);
  for (const m of senderMarks) {
    console.log(
      `     mark [${m.testid}] "${m.text}" · ${m.chars} chars · ${m.lineBoxes} line box(es) · ` +
        `title ${m.title} chars`,
    );
  }
  const noSend = senderMarks.find((m) => m.testid === "sender-no-send");
  const secret = senderMarks.find((m) => m.testid === "sender-note-smtp_secret_ref");
  check(
    noSend !== undefined && noSend.chars < 30 && noSend.title > 100,
    noSend === undefined
      ? "FACT 1 is gone: nothing on this card says configuring it sends nothing"
      : noSend.chars < 30 && noSend.title > 100
        ? `FACT 1 survives as a mark: "${noSend.text}" (${noSend.chars} chars) with the whole ${noSend.title}-char sentence on hover`
        : `FACT 1 is ${noSend.chars} chars inline with a ${noSend.title}-char title — either it is a paragraph again or the sentence was dropped`,
  );
  check(
    secret !== undefined && secret.chars < 30 && secret.title > 100,
    secret === undefined
      ? "FACT 2 is gone: nothing says the secret field holds a NAME rather than a password"
      : secret.chars < 30 && secret.title > 100
        ? `FACT 2 survives as a mark: "${secret.text}" (${secret.chars} chars) with the whole ${secret.title}-char sentence on hover`
        : `FACT 2 is ${secret.chars} chars inline with a ${secret.title}-char title`,
  );
  const worstSenderMark = senderMarks.reduce((w, m) => (m.lineBoxes > w ? m.lineBoxes : w), 0);
  check(
    senderMarks.length > 0 && worstSenderMark === 1,
    senderMarks.length > 0 && worstSenderMark === 1
      ? `every sender mark is ONE line (${senderMarks.length} of them) — the three stacked paragraphs above the first input are gone`
      : `a sender mark wraps to ${worstSenderMark} lines, which is a paragraph again`,
  );
  // ── DEF-2472 · the sentence a water clerk reads carries no internal id and
  //    no instruction pointing at the page they are standing on. Read off the
  //    RENDERED page, because that is where the PO read it.
  const routeText = await page.evaluate(
    `(() => { const el = document.querySelector("[data-testid='sender-route']");
      return el ? (el.getAttribute("title") || "") : null; })()`,
  );
  const routeRef = await page.evaluate(
    `(() => { const el = document.querySelector("[data-testid='sender-route']");
      return el ? el.getAttribute("data-route-br-ref") : null; })()`,
  );
  if (routeText === null) {
    check(false, "DEF-2472: the sender route fact is not on the page at all");
  } else {
    const leaks = ["C-12", "BR-NOT", "OQ-", "ESP", "Settings →", "email_dispatch_active"].filter(
      (t) => routeText.includes(t),
    );
    check(
      leaks.length === 0,
      leaks.length === 0
        ? "DEF-2472: the route sentence names no internal id and no page the reader is already on"
        : `DEF-2472: the route sentence still carries ${leaks.join(", ")} — "${routeText.slice(0, 90)}"`,
    );
    check(
      routeRef !== null && routeRef.length > 0,
      routeRef
        ? `…and the provenance is on the machine field where support reads it (${routeRef})`
        : "…but the provenance went nowhere — DEF-335's remedy is to MOVE it to a machine field, not to delete it",
    );
  }
  await checkTablesAndRefusals(page, "SET-12 sender");

  await page.goto(`${BASE}/${TENANT}/settings/notifications`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);

  // ── SET-12D · one rule open ──────────────────────────────────────────────
  const opened = await page.evaluate(`(() => {
    const b = [...document.querySelectorAll("tbody button")]
      .find((x) => (x.getAttribute("aria-label") || x.getAttribute("title") || "").length > 0 &&
                   /edit/i.test(x.getAttribute("aria-label") || x.getAttribute("title") || ""));
    if (!b) return false;
    b.click();
    return true;
  })()`);
  if (opened) {
    await page.waitForTimeout(1600);
    console.log("\n═══ SET-12D · one notification rule open ═══");
    await shoot(page, "set12d-rule");
    const grid12d = await page.evaluate(GEOMETRY(".settings-grid"));
    check(
      grid12d.missing === true,
      "SET-12D renders no `.settings-grid` — its body column was three 336px tracks, so a 660px table ran behind the card beside it",
    );
    await checkTablesAndRefusals(page, "SET-12D");
  } else {
    check(false, "SET-12D could not be opened — no rule row action found");
  }

  // ── SET-09 · the templates list, then one template open ──────────────────
  await page.goto(`${BASE}/${TENANT}/settings/reference-data/templates`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1400);
  console.log("\n═══ SET-09 · Settings → Configure → Templates (the list) ═══");
  await shoot(page, "set09-templates-list");
  await checkTablesAndRefusals(page, "SET-09 list");


  // ══ CR-048 wave I · SET-09 · PROSE OUT OF THE CELLS ══════════════════════
  //
  // Five PO sentences, one disease, and every one of them is a HEIGHT problem
  // that no source-reading check in this repo can see:
  //   *"why we are showing two names under template name"*
  //   *"autopay - why you are howing text - this is internal not required"*
  //   *"used by - why so much text - just show some status"*
  //   *"past-due reminder - you created email SMS print, you can also do that
  //     by havng action button for each type"*
  //   *"on this screen for KInd - can you use Icons"*
  console.log("\n── CR-048 wave I · the Templates list, column by column");

  // 1 · THE KIND COLUMN. The PO's words are about REAL ESTATE, so width and
  //     wrapping are the evidence and nothing else is.
  const kind = await page.evaluate(COLUMN("Kind"));
  if (kind.missing) {
    check(false, "SET-09 has no «Kind» column to measure");
  } else {
    const worstLines = kind.cells.reduce((w, c) => Math.max(w, c.lineBoxes), 0);
    const tallest = kind.cells.reduce((w, c) => Math.max(w, c.height), 0);
    const withIcons = kind.cells.filter((c) => c.icons > 0).length;
    console.log(
      `     «Kind» ${kind.width}px · ${kind.rows} cells · worst ${worstLines} line box(es) · ` +
        `tallest cell ${tallest}px · ${withIcons} of ${kind.rows} drawn as icons`,
    );
    for (const c of kind.cells.slice(0, 6)) {
      console.log(
        `       "${c.text}" ${c.lineBoxes} line(s) ${c.height}px ${c.icons} icon(s)`,
      );
    }
    // Measured BEFORE wave I at 1728×1080: the column was 172px and the three
    // compound values — "PDF + e-signature", "Certified print + email",
    // "Door hanger print + email" — took 2 and 3 line boxes.
    check(
      worstLines <= 1,
      worstLines <= 1
        ? `no «Kind» cell wraps to a second line (${kind.rows} cells, all one line)`
        : `a «Kind» cell wraps to ${worstLines} lines — that is the real estate the PO asked for back`,
    );
    // ⚠ WIDTH IS THE WRONG EVIDENCE HERE AND THE FIRST DRAFT USED IT. Measured
    //   before wave I the column was 100px WIDE and 235px TALL: the compound
    //   values did not widen the column, they wrapped inside it. So the real
    //   estate the PO is paying for is height, and height is what is asserted —
    //   the whole list table, below.
    console.log(`     (kind column width ${kind.width}px — reported, not asserted: see the table height)`);
    check(
      withIcons === kind.rows,
      withIcons === kind.rows
        ? "…and every delivery format is drawn as an icon, none left as text"
        : `${kind.rows - withIcons} «Kind» cell(s) still print words — a column half-converted reads as a bug`,
    );
  }

  const listTable = await page.evaluate(
    `(() => { const t = document.querySelector("tbody"); if (!t) return null;
      const rows = t.querySelectorAll("tr");
      return { height: Math.round(t.getBoundingClientRect().height), rows: rows.length,
               tallest: Math.max(...[...rows].map((r) => Math.round(r.getBoundingClientRect().height))) }; })()`,
  );
  console.log(
    `     the list body: ${listTable === null ? "(none)" : listTable.rows} rows · ` +
      `${listTable === null ? 0 : listTable.height}px tall · tallest row ${
        listTable === null ? 0 : listTable.tallest
      }px`,
  );
  // Measured before wave I at 1728×1080: 38 rows, 3,247px of table, and a
  // tallest row of 235px — a row the height of a paragraph, four times over.
  check(
    listTable !== null && listTable.tallest <= 80,
    listTable !== null && listTable.tallest <= 80
      ? `no row of the Templates list is taller than a row (tallest ${listTable.tallest}px, was 235px)`
      : `the tallest row of the Templates list is ${listTable?.tallest}px — that is a paragraph deciding how tall a row is`,
  );

  // 2 · THE USED-BY COLUMN. *"just show some status"* — so the assertion is a
  //     LENGTH, because a sentence is what it was.
  const usedBy = await page.evaluate(COLUMN("Used by"));
  if (usedBy.missing) {
    check(false, "SET-09 has no «Used by» column to measure");
  } else {
    const longest = usedBy.cells.reduce((w, c) => Math.max(w, c.chars), 0);
    const worst = usedBy.cells.reduce((w, c) => Math.max(w, c.lineBoxes), 0);
    console.log(
      `     «Used by» ${usedBy.width}px · longest value ${longest} chars · worst ${worst} line box(es)`,
    );
    for (const c of usedBy.cells.slice(0, 4)) console.log(`       "${c.text}"`);
    // Before: 95-character sentences — "Not in use yet — closing an account
    // does not send this." — three and four lines deep in a 260px column.
    check(
      longest <= 24,
      longest <= 24
        ? `every «Used by» value is a short status (longest ${longest} characters, was 95)`
        : `a «Used by» value is ${longest} characters — the PO asked for a status, not a sentence`,
    );
    check(
      worst <= 1,
      worst <= 1
        ? "…and none of them wraps"
        : `a «Used by» value still wraps to ${worst} lines`,
    );
  }

  // 3 · THE NAME COLUMN. *"why we are showing two names under template name"* —
  //     the grouped cell printed the event heading AND the full name, and for a
  //     template with one surface those are the same words twice.
  const name = await page.evaluate(`(() => {
    const th = [...document.querySelectorAll("thead th")]
      .find((h) => (h.innerText || "").trim().split("\\n")[0].trim().toLowerCase()
                   === "template name");
    if (!th) return { missing: true };
    const i = th.cellIndex;
    return {
      rows: [...document.querySelectorAll("tbody tr")].map((tr) => {
        const td = tr.children[i];
        const lines = (td.innerText || "").trim().split("\\n").map((l) => l.trim()).filter(Boolean);
        return { lines, height: Math.round(td.getBoundingClientRect().height) };
      }),
    };
  })()`);
  if (name.missing) {
    check(false, "SET-09 has no «Template name» column to measure");
  } else {
    const doubled = name.rows.filter((r) => r.lines.length > 1 && r.lines[0] === r.lines[1]);
    const tallest = name.rows.reduce((w, r) => Math.max(w, r.height), 0);
    console.log(
      `     «Template name» ${name.rows.length} rows · tallest ${tallest}px · ` +
        `${doubled.length} printing the same name twice`,
    );
    for (const r of doubled.slice(0, 3)) console.log(`       DOUBLED: ${r.lines.join(" / ")}`);
    check(
      doubled.length === 0,
      doubled.length === 0
        ? "no template name is printed twice in its own cell"
        : `${doubled.length} row(s) print the same name on two lines — e.g. «${doubled[0].lines[0]}»`,
    );
    // *"…that way screen and table remain clean"*: one row per template, with a
    // control per surface on it. "Past-due reminder" was three rows.
    const pastDue = name.rows.filter((r) => r.lines.some((l) => l.startsWith("Past-due reminder")));
    console.log(`     rows mentioning «Past-due reminder»: ${pastDue.length}`);
    check(
      pastDue.length <= 1,
      pastDue.length <= 1
        ? `«Past-due reminder» is ONE row with a control per surface (was 3 rows: Print, email, SMS)`
        : `«Past-due reminder» is still ${pastDue.length} rows — one document, one row`,
    );
  }

  // 4 · NO PROSE ANYWHERE IN THE LIST. *"this is internal not required"* — the
  //     autopay placeholder explanation was several sentences in a scrolling
  //     box inside the NAME cell of one row.
  const listRefusals = await page.evaluate(`(() => {
    return [...document.querySelectorAll("tbody [data-refusal]")].map((el) => ({
      testid: el.getAttribute("data-testid"),
      chars: (el.innerText || "").trim().length,
      height: Math.round(el.getBoundingClientRect().height),
    }));
  })()`);
  for (const r of listRefusals) {
    console.log(`     prose in a row [${r.testid}] ${r.chars} chars · ${r.height}px`);
  }
  check(
    listRefusals.length === 0,
    listRefusals.length === 0
      ? "no row of the Templates list holds a paragraph of prose"
      : `${listRefusals.length} row(s) still carry a paragraph — the longest is ${Math.max(
          ...listRefusals.map((r) => r.chars),
        )} characters inside a table cell`,
  );

  // 5 · THE CAPTION UNDER THE TITLE. *"this sentence is too long"* — three
  //     sentences of explanation under a screen heading.
  const caption = await page.evaluate(`(() => {
    const p = document.querySelector("section.panel .panel-hint");
    if (!p) return null;
    const r = document.createRange();
    r.selectNodeContents(p);
    return {
      text: p.innerText.trim(),
      chars: p.innerText.trim().length,
      lineBoxes: r.getClientRects().length,
    };
  })()`);
  console.log(
    `     caption: "${caption === null ? "(none)" : caption.text}" (${
      caption === null ? 0 : caption.chars
    } chars, ${caption === null ? 0 : caption.lineBoxes} line boxes)`,
  );
  check(
    caption !== null && caption.chars <= 60,
    caption !== null && caption.chars <= 60
      ? `the caption is one line of ${caption.chars} characters (was 139)`
      : `the caption is ${caption === null ? "missing" : caption.chars + " characters"} — it is a caption, not a paragraph`,
  );

  const firstRow = page.locator("tbody tr td a, tbody tr td button").first();
  if (await firstRow.count()) {
    await firstRow.click();
    await page.waitForTimeout(1600);
    console.log("\n═══ SET-09 · one template open (the designer) ═══");
    await shoot(page, "set09-template-detail");
    const gridDesigner = await page.evaluate(GEOMETRY(".settings-grid"));
    check(
      gridDesigner.missing === true,
      "the designer renders no `.settings-grid` — one 448px cell of it is where the 108px control rail came from",
    );
    // E1's shape: a control rail and a rendered page, 1fr : 3fr above 1024px.
    const frame = await report(page, "designer frame", "[data-testid='designer-frame']");
    const rail = await report(page, "designer rail", "[data-testid='designer-rail']");
    const output = await report(page, "designer output", "[data-testid='designer-output']");
    // Measured after the repair: 1392 / 344 / 1032. Before it: 448 / 108 / 324,
    // and 108px is the width at which "Save as new version" is four lines.
    // Phrased so a RED line reads as a problem and a GREEN one as a fact —
    // "the designer frame has the page (330px)" beside a ⛔ is a sentence that
    // contradicts itself, which is exactly the shape DEF-182 calls a check
    // whose output cannot distinguish pass from fail.
    check(
      frame !== null && frame.width >= 1200,
      frame !== null && frame.width >= 1200
        ? `the designer frame has the page (${frame.width}px, was 448)`
        : `the designer frame is only ${frame?.width}px of a 1392px page — it is back inside one cell of something`,
    );
    check(
      rail !== null && rail.width >= 300,
      rail !== null && rail.width >= 300
        ? `the control rail is readable (${rail.width}px, was 108)`
        : `the control rail is ${rail?.width}px — at that width its labels break mid-word`,
    );
    check(
      output !== null && output.width >= 900,
      output !== null && output.width >= 900
        ? `the rendered document has the rest (${output.width}px, was 324)`
        : `the rendered document is ${output?.width}px — the page is meant to BE the work, not a thumbnail of it`,
    );
    await checkTablesAndRefusals(page, "SET-09 designer");
  } else {
    check(false, "the designer could not be opened — no clickable template row");
  }

  // ══ SET-10 · wave I — PROSE WHERE A VALUE BELONGS ════════════════════════
  //
  // The PO walked the deployed v2.83.0 and found ONE fault ten times in a
  // sitting: explanatory prose rendered INLINE — inside table cells, under
  // controls, as multi-paragraph helpers — where a value or a short label
  // belongs. *"again too much text content breking the UI"*, *"just use 3 or 4
  // wrods and fix the UI"*.
  //
  // ⚠ **THIS IS MEASURED IN CHARACTERS AS WELL AS PIXELS, AND THE CHARACTER
  // COUNT IS THE HALF THAT ACTUALLY CATCHES IT.** At this 1728px viewport the
  // two disabled-control paragraphs fitted on ONE 18px line, so a
  // height-only check passes over 112 characters of explanation sitting under a
  // button. The wreckage shows up in the NARROW columns — a 344px rail, a
  // merge-field cell — and at every window smaller than the one a check runs
  // at. So each block below is asserted on both, and the count of merge-field
  // BADGES is asserted directly because that one is a fault of repetition
  // rather than of size.
  //
  // Every threshold is a MEASURED number with slack, quoted with the value it
  // replaced, so the next lane can tell a regression from a redesign. The two
  // templates are the ones the PO photographed.
  for (const code of PO_TEMPLATES) {
    await page.goto(`${BASE}/${TENANT}${TEMPLATES_PATH}?template=${code}`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1800);
    console.log(`\n═══ SET-10 · ?template=${code} — prose where a value belongs ═══`);
    await shoot(page, `set10-${code}`);

    const wave = await page.evaluate(WAVE_I);
    if (wave.missing) {
      check(false, `${code}: the template detail page did not open`);
      continue;
    }

    // ── 1 · the disabled-control markers are LABELS ───────────────────────
    // Measured before: `set-default-reason` 112 chars / 18px and
    // `language-note` 114 chars / 18px, each a full sentence under its button.
    // After: 16 and 24 characters, 14px. Slack to 48 characters — four words
    // and a long one — because the rule the PO gave is "3 or 4 wrods".
    for (const note of wave.notes) {
      check(
        note.chars <= 48,
        note.chars <= 48
          ? `${code}: «${note.testid}» is a label, not a paragraph (${note.chars} chars, was up to 114)`
          : `${code}: «${note.testid}» renders ${note.chars} characters of prose under a control — a control holds a LABEL`,
      );
      // …and the sentence is still REACHABLE. A marker with no explanation is
      // a control that refuses silently, which BR-SHL-025 forbids and which is
      // a worse defect than the paragraph. This is the assertion that stops the
      // next lane "fixing" the height by deleting the fact.
      check(
        note.titleChars >= 40,
        note.titleChars >= 40
          ? `${code}: «${note.testid}» still carries its full sentence on hover (${note.titleChars} chars)`
          : `${code}: «${note.testid}» has no reachable explanation (title is ${note.titleChars} chars) — the fact was deleted, not moved`,
      );
    }
    check(
      wave.notes.length >= 3,
      wave.notes.length >= 3
        ? `${code}: ${wave.notes.length} disabled controls carry a short marker`
        : `${code}: ${wave.notes.length} short markers under the disabled controls — the reasons are being rendered as paragraphs again (there are four: set default, language, test send, sample PDF)`,
    );

    // ── 2 · the preview area announces itself ONCE ─────────────────────────
    // Measured before: a 269-character / 54px notice, with the panel hint
    // *"Rendered through the real engine from sample data. Nothing here is
    // sent, queued or charged for."* directly above it and the test-send note
    // in the rail beside it — the same claim three times within a few hundred
    // pixels. After: one 44-character / 18px line, the rest on hover.
    check(
      wave.previewNotice !== null && wave.previewNotice.chars <= 90,
      wave.previewNotice !== null && wave.previewNotice.chars <= 90
        ? `${code}: the preview announces itself in one short line (${wave.previewNotice.chars} chars / ${wave.previewNotice.height}px, was 269 / 54)`
        : `${code}: the preview notice is ${wave.previewNotice?.chars} characters — it is a paragraph again`,
    );
    // The pane must NEVER stop saying it is a preview: a preview that stops
    // announcing itself is one somebody reads as a real customer's letter.
    check(
      wave.previewNotice !== null && wave.previewNotice.chars > 0,
      wave.previewNotice !== null && wave.previewNotice.chars > 0
        ? `${code}: …and it still says it (${JSON.stringify(wave.previewNotice.text)})`
        : `${code}: the preview no longer announces that it is sample data at all`,
    );
    check(
      wave.previewSaysSentOnce <= 1,
      wave.previewSaysSentOnce <= 1
        ? `${code}: "nothing is sent" is claimed once in the preview column (was 2 blocks + the rail)`
        : `${code}: ${wave.previewSaysSentOnce} separate blocks in the preview column say nothing is sent`,
    );

    // ── 3 · the merge-field rows ──────────────────────────────────────────
    // The "engineering spelling" badge rendered under EVERY row of this table:
    // 13 of 13 tokens on this template, 5 of 5 on the other, so it
    // distinguished nothing and doubled each row. Measured before: rows 74–143px
    // with 13 badges. After: 52–80px and none.
    check(
      wave.mergeBadges === 0,
      wave.mergeBadges === 0
        ? `${code}: no per-row badge in the merge-field table (was ${wave.mergeRows} of ${wave.mergeRows})`
        : `${code}: ${wave.mergeBadges} merge-field rows carry a badge — on 31 of the 41 catalogued classes that is every row, which marks nothing`,
    );
    check(
      wave.mergeRowMax <= 100,
      wave.mergeRowMax <= 100
        ? `${code}: the tallest merge-field row is ${wave.mergeRowMax}px (was 143)`
        : `${code}: a merge-field row is ${wave.mergeRowMax}px tall — a cell is holding a sentence`,
    );

    // ── 4 · version history is OFF the edit tab ───────────────────────────
    // PO: *"this may not be required on edit tab - you give a link on top and
    // allow user to open it as seperate page"*. Measured before: an 885px
    // section inside the 344px rail, holding a 470px table in a 312px scroller
    // and a MESSAGES-USING-IT cell **645px tall**.
    check(
      wave.historyOnEditTab === false,
      wave.historyOnEditTab === false
        ? `${code}: the version history is not on the edit tab (was an 885px section in a 344px rail)`
        : `${code}: the version history is back on the edit tab`,
    );
    check(
      wave.historyLink !== null,
      wave.historyLink !== null
        ? `${code}: …and the link to it is at the top of the page (${JSON.stringify(wave.historyLink)})`
        : `${code}: nothing at the top of the page links to the version history — with the panel off the edit tab that leaves it unreachable`,
    );
  }

  // ══ SET-10 · the version history on its OWN page ═════════════════════════
  for (const code of PO_TEMPLATES) {
    await page.goto(`${BASE}/${TENANT}${TEMPLATES_PATH}?template=${code}&view=history`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1800);
    console.log(`\n═══ SET-10 · ?template=${code}&view=history ═══`);
    await shoot(page, `set10-${code}-history`);

    const hist = await page.evaluate(HISTORY_PAGE);
    check(
      hist.page === true,
      hist.page === true
        ? `${code}: the history opens as its own page, with a way back (${hist.back ? "back link present" : "NO BACK LINK"})`
        : `${code}: ?view=history does not render the history page`,
    );
    if (hist.page !== true || hist.table === null) continue;

    // The whole point of moving it: the columns get the width they need.
    check(
      hist.table.width >= 900,
      hist.table.width >= 900
        ? `${code}: the history table has the page (${hist.table.width}px, was a 470px table in a 312px scroller)`
        : `${code}: the history table is only ${hist.table.width}px — it is back inside a rail`,
    );
    // …and it does not escape the card holding it.
    check(
      hist.overflow <= 0,
      hist.overflow <= 0
        ? `${code}: the history panel does not overflow its card (${-hist.overflow}px of margin)`
        : `${code}: the history panel runs ${hist.overflow}px past its card`,
    );
    check(
      hist.sideways === 0,
      hist.sideways === 0
        ? `${code}: the history page does not scroll sideways`
        : `${code}: the history page scrolls sideways by ${hist.sideways}px`,
    );
    // ⚠ THE ONE THE PO CALLED THE WORST THING ON THE PAGE. The MESSAGES USING
    // IT / ACTIONS cells rendered an internal note as a VALUE — *"No column
    // records that an edit changed, and the author's display name is
    // identity's to publish — this module holds a user id, not a name
    // (OQ-255)"* — 249 characters and a 645px-tall row. After: 52 characters,
    // 50px, and the fact ("no change note recorded") survives, because a blank
    // cell would read as "nobody edited this", which is false.
    for (const cell of hist.trail) {
      check(
        cell.height <= 90,
        cell.height <= 90
          ? `${code}: the history trail cell is a value (${cell.height}px / ${cell.chars} chars, was 645px / 249)`
          : `${code}: a history trail cell is ${cell.height}px tall — a code comment is being rendered as a cell value`,
      );
      check(
        !/OQ-\d|BR-[A-Z]{3}-\d|module|user id/.test(cell.text),
        !/OQ-\d|BR-[A-Z]{3}-\d|module|user id/.test(cell.text)
          ? `${code}: …and it names no rule id, module or column (DEF-2479)`
          : `${code}: a history cell is drawing an internal reference: ${JSON.stringify(cell.text.slice(0, 70))}`,
      );
    }
    await checkTablesAndRefusals(page, `SET-10 ${code} history`);
  }

  // ── SET-08 · Numbering, the other half of the same PO report ─────────────
  await page.goto(`${BASE}/${TENANT}/settings/reference-data/number-series`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1400);
  console.log("\n═══ SET-08 · Settings → Configure → Numbering ═══");
  await shoot(page, "set08-numbering");
  const header = await page.evaluate(`(() => {
    const ths = [...document.querySelectorAll(".numbering-table thead th")];
    return ths.map((th) => ({
      label: th.innerText.trim().split("\\n")[0],
      width: Math.round(th.getBoundingClientRect().width),
      height: Math.round(th.getBoundingClientRect().height),
    }));
  })()`);
  for (const h of header) {
    console.log(`     th «${h.label}» ${h.width}px · ${h.height}px tall`);
  }
  const tallest = Math.max(...header.map((h) => h.height));
  // One line of this header is 35px; two lines is 54px, which is what "Next
  // Counter" wrapping did to the WHOLE row.
  check(
    tallest <= 44,
    tallest <= 44
      ? `no column label wraps to a second line (header row ${tallest}px, was 54)`
      : `a column label is wrapping — the header row is ${tallest}px, and one line of it is 35px`,
  );
  await checkTablesAndRefusals(page, "SET-08");

  // ── the tabs that ARE a card grid must be untouched ──────────────────────
  console.log("\n═══ the shared card grid is unchanged ═══");
  for (const tab of ["company", "security", "regional"]) {
    await page.goto(`${BASE}/${TENANT}/settings/${tab}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    const g = await page.evaluate(GEOMETRY(".settings-grid"));
    const tracks = g.missing ? "(absent)" : g.columns;
    console.log(`     ${tab}: ${tracks}`);
    check(
      !g.missing && (tracks.match(/px/g) ?? []).length >= 3,
      `Settings → ${tab} still uses the shared three-track card grid (${tracks})`,
    );
  }

  // ── the numbering rail at a laptop size, where its foot fell off ─────────
  console.log("\n═══ SET-08 · the sticky rail at 1280×720 ═══");
  const small = await browser.newPage({ viewport: LAPTOP });
  await signIn(small);
  await small.goto(`${BASE}/${TENANT}/settings/reference-data/number-series`, {
    waitUntil: "networkidle",
  });
  await small.waitForTimeout(1400);
  const railFit = await small.evaluate(`(() => {
    const sc = document.querySelector("main.view");
    sc.scrollTop = 2000;
    return new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(() => {
      const rail = document.querySelector(".numbering-rail");
      const rr = rail.getBoundingClientRect();
      const sr = sc.getBoundingClientRect();
      res({ railHeight: Math.round(rr.height), scroller: Math.round(sr.height),
            below: Math.round(rr.bottom - sr.bottom), stuck: Math.round(rr.top) });
    })));
  })()`);
  console.log(
    `     rail ${railFit.railHeight}px in a ${railFit.scroller}px window, pinned at ${railFit.stuck}px, ` +
      `${railFit.below > 0 ? railFit.below + "px below the fold" : "fully visible"}`,
  );
  // Before the repair: 729px of rail in a 664px window, 89px of it permanently
  // out of reach. `align-items: start` was NOT the cause — the rail sticks and
  // holds through a 2,154px scroll; it was simply taller than the window.
  check(
    railFit.below <= 0,
    railFit.below <= 0
      ? `the numbering rail is fully reachable on a laptop (${-railFit.below}px of headroom, was 89px past the window)`
      : `${railFit.below}px of the numbering rail is below the window and cannot be scrolled to`,
  );
  await small.close();

  await browser.close();

  console.log("\n════════════════════════════════════════════════════════════");
  if (failures.length === 0) {
    console.log("PASS — every measured shape is where the CR-048 repair left it.");
    process.exit(0);
  }
  console.log(`FAIL — ${failures.length} measurement(s) outside their range:`);
  for (const f of failures) console.log(`  · ${f}`);
  console.log(
    "\nThese are RENDERED measurements. `tsc`, eslint and the DOM suites cannot\n" +
      "see any of them, which is why they are here — see this file's header.",
  );
  process.exit(1);
})().catch((err) => {
  console.error("geometry FAILED:", err.message);
  process.exit(1);
});
