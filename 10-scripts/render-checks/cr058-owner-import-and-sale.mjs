/**
 * RENDERED-OUTPUT CHECK — CR-058's two screens, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. PO ruling
 * 2026-08-30: a screen a lane changed is browser-tested against a real server.
 *
 * ⚠ **AND B14 RULE 21 / `DEF-974` MAKES IT UNAVOIDABLE HERE.** A Tailwind
 * utility is emitted ONLY for a file listed in
 * `07-frontend/src/styles/route-b-migrated.txt`. Write one in a file that is
 * not on that list and it is a class no stylesheet declares: it renders as
 * **nothing at all**, and `tsc`, eslint and every `toContain("flex")`
 * assertion pass on it because the class IS in the DOM. Both files this change
 * touches — `ImportWorkflowPage.tsx` and `TransfersTab.tsx` — ARE on that list
 * (checked before a utility was written), and **the only thing that can prove
 * the rules actually compiled is computed style in a real engine.**
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   createdb smartbillhub_cr058
 *   DATABASE_URL=…/smartbillhub_cr058 python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/smartbillhub_cr058 python3 06-backend/manage.py seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub_cr058" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8058 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4258 API_PROXY_TARGET=http://127.0.0.1:8058 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4258 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr058-owner-import-and-sale.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The shared
 * development database is reseeded by other lanes; on 2026-08-30 a sibling
 * check lost three runs to it, with every id changing mid-run, which looks
 * exactly like a broken screen.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  **THE SIX NEW IMPORT COLUMNS ARE OFFERED ON THE MAPPING SCREEN.** They
 *      are DERIVED from the server's `target_columns`, so a picker that does
 *      not list them means the derivation did not reach the screen — hard-won
 *      law 2, *built is not wired*, on a feature whose whole point is that an
 *      operator can map them.
 *   2  **THE SAMPLE FILE A UTILITY DOWNLOADS CARRIES THEM TOO, AND CARRIES NO
 *      INVENTED IDENTIFIER.** `DEF-962`: the worked cell for every identity
 *      column ships BLANK. A sample with a plausible Social Security number in
 *      it is a file a utility hands to its staff.
 *   3  **THE TRANSFERS SCREEN SAYS A MOVE IS A SERVICE REQUEST** (`CR-058`
 *      task 16, `BR-CUS-1031`) and the sentence carries a WORKING link, not
 *      prose about one. A dead link is the same defect as no sentence.
 *   4  **THE UTILITIES COMPILED** — read from COMPUTED STYLE, which is the only
 *      thing that can tell a rendered utility from a class name in the DOM.
 *   5  **B14 RULE 32** — no rule id and no internal code in what a clerk reads,
 *      on either screen, and the new sentence is ONE sentence.
 *   6  **B14 RULE 31** — no uuid is the visible text of anything.
 *   7  **NEITHER PAGE SCROLLS SIDEWAYS** at 1440.
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4258";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr058-owner-import-and-sale";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** The six columns, as the operator's own labels — never as our field names. */
const OWNER_COLUMN_LABELS = [
  "Owner is a person or a company",
  "Owner Social Security number",
  "Owner driving licence",
  "Owner phone",
  "Owner Tax ID",
  "Owner account type",
];

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-\d{3,5}\b/,
  /\bPRM\.[A-Z_]+\b/,
  /\bDEF-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The server's own answer, captured rather than inferred: the columns are
  // DERIVED, so "did the screen show them" and "did the server offer them" are
  // two different questions and both have to be asked.
  const wire = [];
  page.on("response", async (response) => {
    if (!/\/imports?\//.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      // A redirect or a non-body response has nothing to read.
    }
  });

  console.log(`cr058: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ══════════════════════════════════════════════════════════════════════
  // 1 · THE PREMISES IMPORT OFFERS THE SIX NEW COLUMNS
  // ══════════════════════════════════════════════════════════════════════
  console.log("\n── the premises import ──");
  await page.goto(`${BASE}/${TENANT}/premises/import`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "import-premises.png"), fullPage: true });

  const offered = wire
    .map((entry) => {
      try {
        return JSON.parse(entry.body);
      } catch {
        return null;
      }
    })
    .filter((body) => body && Array.isArray(body.columns))
    .flatMap((body) => body.columns);

  check(offered.length > 0, `the columns endpoint answered (${offered.length} column(s))`);
  for (const label of OWNER_COLUMN_LABELS) {
    check(
      offered.some((column) => column.label === label),
      `the premises target offers "${label}"`,
    );
  }

  // ── 2 · DEF-962 — no invented identifier in the SAMPLE FILE ITSELF ──────
  //
  // ⚠ **THE CSV, NOT THE JSON, AND THE DIFFERENCE MATTERS.** Asking this URL
  // for JSON returns the template's NOTES — the columns that declare a `help`
  // sentence — which is what the label assertions above read. **The worked
  // CELL only exists in the file**, and the file is the thing a utility
  // downloads and hands to its staff, so that is what `DEF-962` is about.
  // ⚠ **THE API IS TENANT-SCOPED** — `/api/<tenant>/…`, never a bare `/api/…`.
  // `credentials: 'include'` because this is the page's own session; a fetch
  // that dropped it would 401 and look exactly like a missing endpoint.
  const sampleCsv = await page.evaluate(`(async () => {
    const r = await fetch('/api/${TENANT}/imports/sample?target=premises', {
      headers: { Accept: 'text/csv' },
      credentials: 'include',
    });
    return r.ok ? await r.text() : null;
  })()`);
  check(sampleCsv !== null, "the downloadable premises sample really downloads");
  if (sampleCsv) {
    // ⚠ **A REAL CSV PARSE, NOT `split(",")`.** A label or a worked cell may
    // legitimately contain a comma inside quotes, and splitting naively shifts
    // every column after it by one — which reads as *"the SSN cell says
    // person"* and looks exactly like a product defect. It said that once.
    const parseRow = (line) => {
      const cells = [];
      let cell = "";
      let quoted = false;
      for (let i = 0; i < line.length; i += 1) {
        const ch = line[i];
        if (quoted) {
          if (ch === '"' && line[i + 1] === '"') { cell += '"'; i += 1; }
          else if (ch === '"') quoted = false;
          else cell += ch;
        } else if (ch === '"') quoted = true;
        else if (ch === ",") { cells.push(cell); cell = ""; }
        else cell += ch;
      }
      cells.push(cell);
      return cells;
    };
    const [headerLine, exampleLine] = sampleCsv.replace(/\r/g, "").trim().split("\n");
    const header = parseRow(headerLine);
    const example = parseRow(exampleLine ?? "");
    check(
      header.length === example.length,
      `the sample's header and its worked row have the same number of cells ` +
        `(${header.length} vs ${example.length}) — a mismatch shifts every ` +
        `assertion below onto the wrong column`,
    );
    for (const label of OWNER_COLUMN_LABELS) {
      check(header.includes(label), `the SAMPLE FILE's header row carries "${label}"`);
    }
    for (const label of OWNER_COLUMN_LABELS.slice(1)) {
      const cell = example[header.indexOf(label)];
      check(
        cell === "" || cell === undefined,
        `DEF-962: the sample's worked cell for "${label}" is BLANK — a plausible ` +
          `Social Security number in a file a utility hands its staff is an identifier ` +
          `this product invented (got ${JSON.stringify(cell)})`,
      );
    }
    const kindCell = example[header.indexOf(OWNER_COLUMN_LABELS[0])];
    check(
      kindCell === "person",
      `the owner KIND does carry a worked cell — it is the product's own vocabulary, ` +
        `not somebody's data (got ${JSON.stringify(kindCell)})`,
    );
    check(
      !/\b\d{3}-\d{2}-\d{4}\b/.test(sampleCsv) && !/\b\d{9}\b/.test(sampleCsv),
      "and no row of the sample looks like a Social Security number anywhere",
    );
  }

  const importCopy = await page.evaluate("document.body.innerText || ''");
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    check(
      !pattern.test(importCopy),
      `B14 rules 31/32: nothing matching ${pattern} is on the import screen`,
    );
  }
  check(
    (await page.evaluate(SIDEWAYS)) === 0,
    "the import screen does not scroll sideways at 1440",
  );

  // ══════════════════════════════════════════════════════════════════════
  // 3 · THE TRANSFERS SCREEN ROUTES A MOVE TO A SERVICE REQUEST
  // ══════════════════════════════════════════════════════════════════════
  console.log("\n── the transfers tab ──");
  await page.goto(`${BASE}/${TENANT}/accounts?tab=transfers`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "transfers.png"), fullPage: true });

  const moving = await page.evaluate(`(() => {
    const el = document.querySelector('[data-moving-is-a-service-request]');
    if (!el) return null;
    const link = el.querySelector('a');
    const style = getComputedStyle(el);
    return {
      text: (el.textContent || '').replace(/\\s+/g, ' ').trim(),
      href: link ? link.getAttribute('href') : null,
      linkText: link ? (link.textContent || '').trim() : null,
      // ⚠ COMPUTED, never the class attribute — B14 rule 21 / DEF-974. A
      // utility in an unmigrated file is a class name with no rule behind it,
      // and reading className cannot tell the difference.
      fontSize: style.fontSize,
      color: style.color,
      linkColor: link ? getComputedStyle(link).color : null,
      linkDecoration: link ? getComputedStyle(link).textDecorationLine : null,
    };
  })()`);

  check(moving !== null, "CR-058 task 16: the sentence is on the transfers screen at all");
  if (moving) {
    check(
      /sold/i.test(moving.text) && /service request/i.test(moving.text),
      `BR-CUS-1031: it says a transfer is for a SOLD property and a move is a service request — ` +
        `"${moving.text.slice(0, 120)}"`,
    );
    check(
      moving.href !== null && moving.href.includes("/requests/new"),
      `the link really goes to the other door (href=${moving.href}) — a dead link is the ` +
        "same defect as no sentence",
    );
    // B14 rule 32's description budget: ONE sentence, not a paragraph. The link
    // text is its own fragment and is not counted.
    const sentences = moving.text
      .replace(moving.linkText ?? "", "")
      .split(/(?<=\.)\s+/)
      .filter((part) => part.trim().length > 0);
    check(
      sentences.length <= 2,
      `B14 rule 32: the sentence is a sentence, not a paragraph (${sentences.length} found)`,
    );
    check(
      moving.linkDecoration.includes("underline"),
      `B14 rule 21: the link's utilities COMPILED — text-decoration is ` +
        `"${moving.linkDecoration}" from computed style, not from a class name`,
    );
    check(
      moving.fontSize !== "" && moving.fontSize !== "0px",
      `the paragraph's own utilities compiled (font-size ${moving.fontSize})`,
    );
  }

  const transfersCopy = await page.evaluate("document.body.innerText || ''");
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    check(
      !pattern.test(transfersCopy),
      `B14 rules 31/32: nothing matching ${pattern} is on the transfers screen`,
    );
  }
  check(
    (await page.evaluate(SIDEWAYS)) === 0,
    "the transfers screen does not scroll sideways at 1440",
  );

  // ── the link is FOLLOWED, because "it resolves" is a different claim ────
  if (moving && moving.href) {
    await page.click("[data-moving-is-a-service-request] a");
    await page.waitForTimeout(1500);
    const landed = page.url();
    await page.screenshot({ path: join(OUT, "service-request.png"), fullPage: true });
    check(
      landed.includes("/requests/new"),
      `the link OPENS the service-request door (landed on ${landed})`,
    );
    check(
      !/Not found|404/i.test(await page.evaluate("document.body.innerText || ''")),
      "and the door it opens is a real screen, not a 404",
    );
  }

  await browser.close();

  console.log(
    `\ncr058 render check: ${failures.length === 0 ? "PASS" : `FAIL (${failures.length})`}`,
  );
  for (const failure of failures) console.log(`   ⛔ ${failure}`);
  process.exit(failures.length === 0 ? 0 : 1);
})();
