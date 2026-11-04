#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-056 W2b — identity is per kind. A person keeps BR-CUS-089's
//           three-part test; a COMPANY is matched on its name and its Tax ID,
//           because a company has no date of birth and the signed rule read
//           literally made every one of them permanently unmatchable.
// Screens:  the customers list (A1 allocates no id — S61-S90 is exhausted and
//           S115 is the PO's to allocate; see routing/screenIds.ts)
// Rules:    BR-CUS-1022 (identity is per kind — PO 2026-09-01) ·
//           BR-CUS-092(c) (LAST FOUR ONLY — the full identifier never reaches a
//           browser) · B14 rules 19, 21, 31, 32 · hard-won law 2 (built is not
//           wired) · law 6 (diff the RUNNING app — no gate reads rendered
//           output) · law 7 (prove a guard RED first)
// ───────────────────────────────────────────────────────
/**
 * Open the customers list in a REAL browser and read the COMPANY row.
 *
 * ⚠ **WHY A SECOND CHECK BESIDE `cr056-customers-list.mjs`.** That one proves
 * the screen draws and that no identifier reaches the wire, and it does that on
 * a PERSON. It cannot answer this wave's question, which is about a row it
 * never had: **before CR-056 W2b every company in the product read *"Nothing
 * on file"* in the identity column**, however completely it had been
 * identified, because a business's only identifier did not exist. A jsdom test
 * proves the component would draw a Tax ID if one were handed to it. Only this
 * proves the SERVER puts one there and the browser paints it.
 *
 * ⚠ **AND THE ABSENCE MATTERS AS MUCH AS THE PRESENCE.** BR-CUS-092(c) governs
 * the Tax ID for the same reason it governs a Social Security number, so every
 * `/customers` response body is searched for the seeded number in each of its
 * spellings. A component that renders only the last four is not evidence that
 * the rest stayed on the server — the full value in a response is in devtools,
 * in a proxy log and in the HAR file attached to a support ticket.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the
 * wrong bytes.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The shared
 * development database is reseeded by other lanes, and every id changes
 * mid-run, which looks exactly like a broken screen.
 *
 * ⚠ **THE DEMO FIXTURE WOULD NOT LOAD ON THE BOX THIS WAS FIRST RUN ON, AND
 * THAT IS `DEF-2870` RATHER THAN A NOTE.** On a database created today,
 * `migrate` then `seed_demo` then `load_sample_data --tenant brazosbend`
 * refuses the premises block with `VAL-002 metering.cycle.code_duplicate`, ten
 * further blocks report `SD-PRECONDITION` waiting on it, and the tenant ends
 * with **0 accounts and 0 customers** — so every customers screen is empty.
 * The cause is NOT diagnosed here and is not guessed: what is recorded is the
 * reproduction. **So the two rows this check reads are opened through the door
 * a clerk uses** — `customers.services.create_account` with a `customer` block,
 * one company and one person — which is stronger evidence than a fixture row
 * anyway: it exercises the validator, the encryptor, the blind index and the
 * link write, and an ORM insert would have proved the column and skipped every
 * rule.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   createdb sbh_cr056w2b
 *   export SBH_FIELD_ENCRYPTION_KEYS='k1:<base64url 32 bytes>'   # the SAME key
 *   DATABASE_URL=…/sbh_cr056w2b python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/sbh_cr056w2b python3 06-backend/manage.py seed_demo
 *
 *   # then two accounts through the real door — a company and a person.
 *   # `SAMPLE_COMPANY_TAX_ID` is `apps/customers/sample_data`'s own constant,
 *   # so the fixture and this check can never disagree about the number:
 *   #   create_account(actor, {..., "customer": {"display_name": …,
 *   #     "kind": "company", "identity": {"tax_id": SAMPLE_COMPANY_TAX_ID}}})
 *   #   create_account(actor, {..., "customer": {"display_name": …,
 *   #     "kind": "person", "identity": {"date_of_birth": …, "ssn": …}}})
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr056w2b?sslmode=disable" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8057 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4257 API_PROXY_TARGET=http://127.0.0.1:8057 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4257 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr056-company-identity.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  A COMPANY ROW EXISTS AND IS DRAWN AS ONE — `data-customer-kind` reads
 *      `company` on at least one row. Hard-won law 2: a kind nothing renders
 *      is a kind that does not exist for the user.
 *   2  THAT ROW'S IDENTITY CELL SAYS `held`, NOT `Nothing on file`, and shows
 *      the seeded Tax ID's LAST FOUR. This is the whole wave, on screen.
 *   3  NO TAX ID ON THE WIRE — every `/customers` response body is searched for
 *      the seeded number in every spelling. The last four is allowed; the nine
 *      digits, the hyphenated form and the seven-digit tail are not.
 *   4  NO TAX ID IN THE RENDERED HTML EITHER.
 *   5  B14 RULE 31 — no uuid is the visible text of any cell on the row.
 *   6  B14 RULE 19 — the search prompt NAMES the Tax ID, because the box now
 *      matches it and a clerk holding one has no other way to know.
 *   7  THE SEARCH REALLY MATCHES IT: typing the whole Tax ID leaves exactly the
 *      company on screen, and typing HALF of it leaves nobody — which is a
 *      property of the encryption (an equality probe over an HMAC) rather than
 *      a bug in the box, and is asserted so a later lane cannot "fix" it into a
 *      prefix search over ciphertext that matches nothing.
 *   8  A PERSON ROW STILL READS AS A PERSON and carries no Tax ID mark, so the
 *      new column has not leaked into the other kind's row.
 *   9  THE PAGE DOES NOT SCROLL SIDEWAYS.
 *
 * ── PROVED RED FIRST (hard-won law 7) ────────────────────────────────────
 * The defect this check exists for was put back and the failure quoted:
 * `selectors.customer_row` was changed to serve `tax_id_held: False` /
 * `tax_id_last4: None`, the server restarted, and assertion 2 went red with
 *
 *     ⛔ BR-CUS-1022: a company draws its Tax ID mark ending 1234 —
 *        identity cells read ["Nothing on file"]
 *
 * which is the exact sentence every company in the product showed before this
 * wave. Restored, restarted, and every assertion held with
 * `identity cells read ["•••• 1234"]`.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4257";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr056-company-identity";
const VIEWPORT = { width: 1440, height: 1000 };

/** `apps/customers/sample_data.SAMPLE_COMPANY_TAX_ID` — the seeded company's
 *  Tax ID. `99-` is the IRS's own reserved-for-fiction prefix, so this number
 *  belongs to nobody. `1234` is deliberately absent from FORBIDDEN: the last
 *  four is exactly what BR-CUS-092(c) allows a read path to disclose. */
const TAX_ID = process.env.SMOKE_TAX_ID ?? "99-0001234";
const TAX_ID_DIGITS = TAX_ID.replace(/[^0-9]/g, "");
const TAX_ID_LAST4 = TAX_ID_DIGITS.slice(-4);
const FORBIDDEN = [TAX_ID, TAX_ID_DIGITS, TAX_ID_DIGITS.slice(2), TAX_ID.slice(0, 6)];

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/**
 * ⚠ **THE LIST'S OWN SEARCH BOX IS THE LAST ONE, NOT THE FIRST — AND THIS
 * CHECK GOT IT WRONG ON ITS FIRST RUN.** The page carries TWO
 * `input[type="search"]`: the app shell's global box in the header (*"Search
 * accounts, premises, bills…"*) and the list's own in its toolbar. A bare
 * `querySelector` takes the shell's, so the prompt assertion read the wrong
 * control and the two search assertions typed into the wrong box — three
 * failures that looked like screen defects and were defects in the check.
 * Found by proving this check RED first (hard-won law 7), which is the whole
 * reason that law exists: a check whose output cannot tell pass from fail is
 * worse than no check, because it is trusted.
 */
const OWN_SEARCH = `[...document.querySelectorAll('input[type="search"]')].at(-1)`;

/** Every row, with the two facts this wave is about: the kind and the mark. */
const READ_ROWS = `(() => {
  const rows = [...document.querySelectorAll('table.data-table tbody tr')];
  const search = ${OWN_SEARCH};
  return {
    rowCount: rows.length,
    rows: rows.map((tr) => {
      const kindCell = tr.querySelector('[data-customer-kind]');
      const identity = tr.querySelector('[data-identity]');
      return {
        kind: kindCell ? kindCell.getAttribute('data-customer-kind') : null,
        identityState: identity ? identity.getAttribute('data-identity') : null,
        identityText: identity ? (identity.textContent || "").replace(/\\s+/g, " ").trim() : null,
        cells: [...tr.querySelectorAll('td')].map((td) =>
          (td.textContent || "").replace(/\\s+/g, " ").trim(),
        ),
      };
    }),
    searchPlaceholder: search ? search.getAttribute('placeholder') : null,
    html: document.body.innerHTML,
    body: document.body.innerText || "",
  };
})()`;

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // Captured rather than inferred: BR-CUS-092(c) is a promise about the
  // RESPONSE, and a component that renders only the last four is not evidence
  // that the number stayed on the server.
  const wire = [];
  page.on("response", async (response) => {
    if (!response.url().includes("/customers")) return;
    try {
      wire.push(await response.text());
    } catch {
      // A redirect or a non-body response has nothing to read.
    }
  });

  console.log(`cr056-w2b: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  console.log("\n── the customers list, read for the COMPANY row ──");
  await page.goto(`${BASE}/${TENANT}/customers`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "list.png"), fullPage: true });
  const list = await page.evaluate(READ_ROWS);

  // ── 1 · A COMPANY EXISTS AND IS DRAWN AS ONE ────────────────────────────
  const companies = list.rows.filter((row) => row.kind === "company");
  const people = list.rows.filter((row) => row.kind === "person");
  check(list.rowCount > 0, `the list has rows (${list.rowCount})`);
  check(
    companies.length > 0,
    `hard-won law 2: at least one row draws as a COMPANY (${companies.length} of ${list.rowCount})`,
  );

  // ── 2 · THE COMPANY'S IDENTITY CELL — the whole wave, on screen ─────────
  const withTaxId = companies.filter(
    (row) => row.identityState === "held" && (row.identityText || "").includes(TAX_ID_LAST4),
  );
  check(
    withTaxId.length > 0,
    `BR-CUS-1022: a company draws its Tax ID mark ending ${TAX_ID_LAST4} — ` +
      `identity cells read ${JSON.stringify(companies.map((r) => r.identityText))}`,
  );

  // ── 3 · NO TAX ID ON THE WIRE (BR-CUS-092(c)) ───────────────────────────
  const bodies = wire.join("\n");
  check(wire.length > 0, `the list really called the server (${wire.length} response(s))`);
  for (const spelling of FORBIDDEN) {
    check(
      !bodies.includes(spelling),
      `BR-CUS-092(c): "${spelling}" is in no /customers response body`,
    );
  }

  // ── 4 · NOR IN THE RENDERED PAGE ────────────────────────────────────────
  for (const spelling of FORBIDDEN) {
    check(!list.html.includes(spelling), `BR-CUS-092(c): "${spelling}" is not in the page either`);
  }

  // ── 5 · B14 RULE 31 — no uuid is a visible value ────────────────────────
  const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  check(
    list.rows.every((row) => row.cells.every((cell) => !UUID.test(cell))),
    "B14 rule 31: no uuid is the value of any cell",
  );

  // ── 6 · B14 RULE 19 — the prompt names what the box matches ─────────────
  const prompt = list.searchPlaceholder ?? "";
  check(
    /tax/i.test(prompt) ||
      /steuer/i.test(prompt) ||
      /fiscal/i.test(prompt) ||
      /NIF|RFC|CNPJ|NPWP/.test(prompt),
    `B14 rule 19: the search prompt names the Tax ID ("${prompt}")`,
  );

  // ── 7 · AND IT REALLY MATCHES IT, EXACTLY ───────────────────────────────
  const ownSearch = page.locator('input[type="search"]').last();
  await ownSearch.fill(TAX_ID);
  await page.waitForTimeout(1200);
  const exact = await page.evaluate(READ_ROWS);
  check(
    exact.rowCount === 1 && exact.rows[0].kind === "company",
    `the whole Tax ID finds exactly the company (${exact.rowCount} row(s))`,
  );
  await page.screenshot({ path: join(OUT, "search-tax-id.png"), fullPage: true });

  await ownSearch.fill(TAX_ID.slice(0, 6));
  await page.waitForTimeout(1200);
  const partial = await page.evaluate(READ_ROWS);
  check(
    partial.rowCount === 0,
    `half a Tax ID finds nobody (${partial.rowCount} row(s)) — an equality probe over an HMAC, ` +
      "which is a property of the encryption and not a bug in the box",
  );

  // ── 8 · THE OTHER KIND IS UNCHANGED ─────────────────────────────────────
  await ownSearch.fill("");
  await page.waitForTimeout(1200);
  const back = await page.evaluate(READ_ROWS);
  const persons = back.rows.filter((row) => row.kind === "person");
  check(persons.length > 0, `people are still listed (${persons.length} of ${back.rowCount})`);
  check(
    persons.every((row) => !(row.identityText || "").includes(TAX_ID_LAST4)),
    "the Tax ID mark has not leaked onto a person's row",
  );
  check(people.length > 0, `people were drawn on the first read too (${people.length})`);

  // ── 9 · NO SIDEWAYS SCROLL ──────────────────────────────────────────────
  const overflow = await page.evaluate(SIDEWAYS);
  check(overflow === 0, `the page does not scroll sideways (${overflow}px)`);

  await browser.close();

  console.log(`\nscreenshots in ${OUT}`);
  if (failures.length) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const line of failures) console.log(`   - ${line}`);
    process.exit(1);
  }
  console.log("\n✓ every assertion held");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
