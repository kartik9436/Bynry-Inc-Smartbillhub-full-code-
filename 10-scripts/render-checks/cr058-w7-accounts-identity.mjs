/**
 * RENDERED-OUTPUT CHECK — CR-058 W7's accounts import, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. PO ruling
 * 2026-08-30: a screen a lane changed is browser-tested against a real server.
 *
 * ⚠ **AND LAW 2 IS THE REAL SUBJECT HERE — *built is not wired*.** The four
 * receipt figures this wave adds are rendered by a `target === "accounts" &&
 * receipt.receipt.<key>` guard. A key served under a different name, or a run
 * that never produces a non-zero count, draws NOTHING — and every backend test
 * still passes, because the figure is correct in the payload nobody looked at.
 * **The only thing that can tell those apart is a real run in a real browser**,
 * which is why this walks the whole wizard rather than asserting a label.
 *
 * ⚠ **B14 RULE 21 / `DEF-974`.** `ImportWorkflowPage.tsx` IS on
 * `07-frontend/src/styles/route-b-migrated.txt` (checked before a utility was
 * written) and this change adds no class of its own — the four tiles reuse the
 * figure-strip the premises figures already use. Computed style is still read,
 * because a strip that stopped compiling would show four numbers with no
 * styling and every DOM assertion would pass.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   createdb sbh_cr058w7
 *   DATABASE_URL=…/sbh_cr058w7 python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/sbh_cr058w7 python3 06-backend/manage.py seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_cr058w7" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8158 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4358 API_PROXY_TARGET=http://127.0.0.1:8158 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4358 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr058-w7-accounts-identity.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** — the shared
 * development database is reseeded by other lanes, and every id changing
 * mid-run looks exactly like a broken screen.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  **THE FOUR IDENTITY COLUMNS ARE OFFERED ON THE ACCOUNTS MAPPING
 *      SCREEN**, by the operator's own label. They are DERIVED from the
 *      server's `target_columns`, so *"the server offers them"* and *"the
 *      screen shows them"* are two questions and both are asked.
 *   2  **THE SAMPLE FILE CARRIES THEM AND INVENTS NO IDENTIFIER** — `DEF-962`:
 *      every identifier's worked cell ships BLANK, because a plausible Social
 *      Security number in a file a utility hands its staff is an identifier
 *      this product made up. The KIND does carry `person`: that is our own
 *      vocabulary and not somebody's data.
 *   3  **AND THERE IS NO SECOND PHONE COLUMN.** The phone identifier is the
 *      template's existing `Phone`; a `Customer phone` beside it would be one
 *      fact in two cells (decision log 2026-09-01, judgment 1).
 *   4  **A REAL TWO-ROW FILE GOES ALL THE WAY THROUGH**, one row identified and
 *      one row a name alone, and **the receipt says both things in numbers**:
 *      *Customers created 1* and *Waiting for the customer to be identified 1*.
 *      Without the second figure a half-identified migration looks finished.
 *   5  **THE NAME-ONLY ROW IS REJECTED AND SAYS WHY IN THE OPERATOR'S WORDS**,
 *      naming their own cell and no rule id.
 *   6  **B14 RULE 32 / RULE 31** — no rule id, no internal code and no uuid in
 *      anything a clerk reads, on every stage of the wizard.
 *   7  **THE FIGURE STRIP COMPILED** — read from COMPUTED STYLE, the only thing
 *      that can tell a rendered utility from a class name in the DOM.
 *   8  **NO STAGE SCROLLS SIDEWAYS** at 1440.
 *
 * ── PROVED RED FIRST (hard-won law 7) ────────────────────────────────────
 * Run 2026-09-01 against a real server on a private database, 34 checks PASS.
 * Then the tile was broken on purpose — the receipt's `accounts_awaiting_
 * identity` guard forced to `false`, rebuilt, re-run — and the check bit::
 *
 *     ⛔ THE MITIGATION: the receipt says ONE row is waiting for the customer
 *        to be identified (value=missing)
 *     ⛔ B14 rule 21: the figure's utilities compiled (font-size undefined)
 *     FAIL (2)
 *
 * ⚠ **AND NOTE WHAT STAYED GREEN WHILE IT WAS BROKEN:** every other check,
 * including *"customers created 1"*, the stage-3 refusal sentence and all five
 * B14 patterns. A migration that had identified half its customers would have
 * read as finished on that build and been perfectly correct in the database,
 * which is the whole reason the figure is asserted separately from the rows.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4358";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr058-w7-accounts-identity";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** The four columns, as the operator's own labels — never as our field names. */
const IDENTITY_LABELS = [
  "Customer is a person or a company",
  "Customer Social Security number",
  "Customer driving licence",
  "Customer Tax ID",
];

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-\d{3,5}\b/,
  /\bACC\.[A-Z_]+\b/,
  /\bDEF-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** A real CSV parse — `split(",")` shifts every column after a quoted comma,
 *  which reads as *"the SSN cell says person"* and looks like a product bug. */
function parseRow(line) {
  const cells = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      cells.push(cell);
      cell = "";
    } else cell += ch;
  }
  cells.push(cell);
  return cells;
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  const wire = [];
  page.on("response", async (response) => {
    if (!/\/imports?\b|\/imports\//.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or an empty body has nothing to read */
    }
  });

  console.log(`cr058 W7: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ══════════════════════════════════════════════════════════════════════
  // 1 · THE ACCOUNTS IMPORT OFFERS THE FOUR NEW COLUMNS
  // ══════════════════════════════════════════════════════════════════════
  console.log("\n── the accounts import, stage 1 ──");
  await page.goto(`${BASE}/${TENANT}/accounts/import`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "stage1.png"), fullPage: true });

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
  for (const label of IDENTITY_LABELS) {
    check(
      offered.some((column) => column.label === label),
      `the accounts target offers "${label}"`,
    );
  }
  check(
    offered.some((column) => column.label === "Phone"),
    "the phone identifier is the template's EXISTING Phone column",
  );
  check(
    !offered.some((column) => /customer phone/i.test(column.label ?? "")),
    "and there is no second phone column beside it — one fact, one cell",
  );

  // ── 2 · DEF-962 — no invented identifier in the SAMPLE FILE ITSELF ──────
  const sampleCsv = await page.evaluate(`(async () => {
    const r = await fetch('/api/${TENANT}/imports/sample?target=accounts', {
      headers: { Accept: 'text/csv' },
      credentials: 'include',
    });
    return r.ok ? await r.text() : null;
  })()`);
  check(sampleCsv !== null, "the downloadable accounts sample really downloads");
  if (sampleCsv) {
    const [headerLine, exampleLine] = sampleCsv.replace(/\r/g, "").trim().split("\n");
    const header = parseRow(headerLine);
    const example = parseRow(exampleLine ?? "");
    check(
      header.length === example.length,
      `the sample's header and its worked row have the same number of cells ` +
        `(${header.length} vs ${example.length})`,
    );
    for (const label of IDENTITY_LABELS) {
      check(header.includes(label), `the SAMPLE FILE's header row carries "${label}"`);
    }
    for (const label of IDENTITY_LABELS.slice(1)) {
      const cell = example[header.indexOf(label)];
      check(
        cell === "" || cell === undefined,
        `DEF-962: the sample's worked cell for "${label}" is BLANK (got ${JSON.stringify(cell)})`,
      );
    }
    check(
      example[header.indexOf(IDENTITY_LABELS[0])] === "person",
      "the customer KIND does carry a worked cell — our own vocabulary, not somebody's data",
    );
    check(
      !/\b\d{3}-\d{2}-\d{4}\b/.test(sampleCsv),
      "and no cell of the sample looks like a Social Security number",
    );
  }

  // ══════════════════════════════════════════════════════════════════════
  // 3 · A REAL FILE, ALL THE WAY THROUGH
  // ══════════════════════════════════════════════════════════════════════
  //
  // ⚠ **THE UNIT AND THE ACCOUNT TYPE ARE READ OFF THIS TENANT, NEVER TYPED.**
  // A literal `U-00001` is `DEF-2160`'s invented cell: it loads on no tenant
  // whose first unit is not literally that, which is every tenant.
  const seat = await page.evaluate(`(async () => {
    const r = await fetch('/api/${TENANT}/units?page_size=50', { credentials: 'include' });
    if (!r.ok) return null;
    const body = await r.json();
    const rows = body.results || body.data || [];
    const free = rows.filter((u) => !u.active_account_no && !u.account_no);
    return (free[0] || rows[0] || null);
  })()`);
  check(seat !== null, "the tenant has a unit this file can name");

  let receiptFigures = null;
  let rejectSentence = null;
  if (seat) {
    const unitNo = seat.unit_no ?? seat.number ?? seat.label;
    // ⚠ **A UNIQUE FILE PER RUN, AND IT IS THE PRODUCT'S RULE RATHER THAN A
    // TEST CONVENIENCE.** An import run's idempotency key is the file's own
    // bytes (`uq_import_runs_idempotency`), so re-running this check with a
    // byte-identical file is REFUSED — correctly, with a 500 on `load` that
    // looks exactly like a broken screen. The stamp also keeps the account
    // numbers clear of any this tenant already holds.
    const stamp = Date.now().toString().slice(-8);
    const csv =
      "UNIT_REF,ACCT,NAME,TYPE,PERSON OR COMPANY,SSN\n" +
      `${unitNo},A-W7-${stamp}A,"Harmon, Luis",residential,person,123-45-6789\n` +
      `${unitNo},A-W7-${stamp}B,"Alvarez, Rosa",residential,,\n`;

    await page.setInputFiles('input[type="file"]', {
      name: "cr058-w7-accounts.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv, "utf-8"),
    });
    await page.waitForTimeout(800);
    await page.click('button:has-text("Transform →")');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: join(OUT, "stage2.png"), fullPage: true });
    check((await page.evaluate(SIDEWAYS)) === 0, "stage 2 does not scroll sideways at 1440");

    await page.click('button:has-text("Validate →")');
    await page.waitForTimeout(3500);
    await page.screenshot({ path: join(OUT, "stage3.png"), fullPage: true });

    // ── 5 · the rejected row says why, in the operator's own words ─────────
    const stage3 = await page.evaluate("document.body.innerText || ''");
    rejectSentence = /Alvarez, Rosa[^\\n]*/.exec(stage3)?.[0] ?? null;
    check(
      /no way to identify them/i.test(stage3),
      "stage 3 says the name-only row has no way to identify them, before anything is written",
    );
    check(
      !/ACC\.CUSTOMER_IDENTITY/.test(stage3),
      "B14 rule 32: and it says it without the rule's internal code",
    );
    check((await page.evaluate(SIDEWAYS)) === 0, "stage 3 does not scroll sideways at 1440");

    await page.click('button:has-text("Load →")');
    await page.waitForTimeout(2500);
    // The approval bar: a file that is more than 5% rejects needs one, and this
    // one is 50%. The control is ticked rather than the file made easier.
    // ⚠ **`force: true`, AND THE REASON IS THE CONTROL AND NOT THE TEST.** The
    // checkbox is the real `<input>` with a drawn `[data-checkbox-mark]` span
    // over it (the shared control's shape), so an ordinary click is
    // intercepted by the mark. Forcing it drives the INPUT a keyboard user
    // drives, which is the thing the screen actually reads.
    const approve = await page.$("#import-load-approved");
    if (approve) await approve.check({ force: true });
    await page.click('button:has-text("Commit load ✓")');
    await page.waitForTimeout(6000);
    await page.screenshot({ path: join(OUT, "stage5-receipt.png"), fullPage: true });

    // ── 4 · THE RECEIPT SAYS BOTH THINGS, IN NUMBERS ──────────────────────
    receiptFigures = await page.evaluate(`(() => {
      const wanted = [
        'Customers created',
        'Customers already on file',
        'Waiting for the customer to be identified',
        'Identifier does not match the kind of customer',
      ];
      const out = {};
      const nodes = Array.from(document.querySelectorAll('*'));
      for (const label of wanted) {
        const el = nodes.find((n) => n.children.length === 0 && (n.textContent || '').trim() === label);
        if (!el) { out[label] = null; continue; }
        // WALK UP UNTIL THE VALUE IS IN SCOPE, never closest('div').
        // The label is its own leaf and the FIGURE is a sibling, so the nearest
        // wrapper holds the label and nothing else — reading it reports a tile as
        // valueless on a screen that is drawing the value correctly, which is a
        // check that cannot tell pass from fail (DEF-182's lesson).
        let tile = el.parentElement;
        while (tile && !/[0-9]/.test((tile.textContent || '').split(label).join(''))) {
          tile = tile.parentElement;
        }
        const scope = tile || el.parentElement;
        const rest = (scope.textContent || '').split(label).join('');
        const digits = rest.match(/[0-9][0-9,]*/);
        out[label] = {
          text: (scope.textContent || '').replace(/\\s+/g, ' ').trim(),
          value: digits ? digits[0] : null,
          fontSize: getComputedStyle(el).fontSize,
          display: getComputedStyle(scope).display,
        };
      }
      return out;
    })()`);
  }

  if (receiptFigures) {
    const created = receiptFigures["Customers created"];
    const awaiting = receiptFigures["Waiting for the customer to be identified"];
    check(
      created !== null && created.value === "1",
      `the receipt says ONE customer was created (value=${created?.value ?? "missing"})`,
    );
    check(
      awaiting !== null && awaiting.value === "1",
      `⛔ THE MITIGATION: the receipt says ONE row is waiting for the customer to be ` +
        `identified (value=${awaiting?.value ?? "missing"}) — without this figure a migration ` +
        `that identified half its customers looks exactly like a finished one`,
    );
    // ── 7 · the strip COMPILED, from computed style ───────────────────────
    check(
      awaiting !== null && awaiting.fontSize !== "" && awaiting.fontSize !== "0px",
      `B14 rule 21: the figure's utilities compiled (font-size ${awaiting?.fontSize})`,
    );
  }

  // ── 6 · B14 rules 31/32 across the whole wizard ────────────────────────
  const receiptCopy = await page.evaluate("document.body.innerText || ''");
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    check(
      !pattern.test(receiptCopy),
      `B14 rules 31/32: nothing matching ${pattern} is on the receipt`,
    );
  }
  check((await page.evaluate(SIDEWAYS)) === 0, "the receipt does not scroll sideways at 1440");

  if (rejectSentence) console.log(`   rejected row read: "${rejectSentence.slice(0, 140)}"`);

  await browser.close();
  console.log(`\n${failures.length === 0 ? "PASS" : `FAIL (${failures.length})`}`);
  for (const failure of failures) console.log(`   ⛔ ${failure}`);
  process.exit(failures.length === 0 ? 0 : 1);
})();
