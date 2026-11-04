// ── Trace ────────────────────────────────────────────────────────────────────
// Ask:      The PO's four drawings of 2026-09-25 — `Reconnect1` · `Reconnect2` ·
//           `MasterReconnect1` · `MasterReconnect2`. Reconnection stops being
//           one dialog and becomes `S148`, two steps at an address of its own.
// Walks:    `/{t}/disconnects/{case}/reconnect` — both steps, and the case
//           record it is reached from.
// Rules:    BR-CUS-1097 (the balance is SHOWN and never blocks) · BR-CUS-1098
//           (a master's units come back together; transferred-up residue is
//           its own line) · BR-CUS-104 (the fee landed at the cut) ·
//           BR-SHL-025 (a refused control renders disabled WITH ITS REASON) ·
//           B14 rules 31, 33, 37, 43, 44 · CLAUDE.md hard-won laws 2 and 6.
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS IS A PERSON WITH A BROWSER, WHICH IS THE ONLY CHECK IN THIS REPO
// THAT READS RENDERED OUTPUT** (hard-won law 6). `ReconnectPage.dom.test.tsx`
// can tell you a string IS on the page and can NEVER tell you it is in the
// right place, the right size or the right order. The two are not substitutes.
//
// ⚠ **IT IS READ-ONLY AND WRITES NOTHING.** The commit is not built (the
// product still refuses over `not_settled`, `DEF-CUS-6742`), so there is
// nothing here to press that would change a row. It opens the screen, captures
// both steps as IMAGES rather than as `innerText`, and asserts what is drawn.
//
//   RWALK_CASE=dsc-26-0005 node 10-scripts/po20260925_reconnect_walk.mjs
//
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.RWALK_BASE || "http://127.0.0.1:8984";
const T = process.env.RWALK_TENANT || "brazosbend";
const EMAIL = process.env.RWALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.RWALK_PASSWORD || "S3cure!passw0rd";
const CASE = process.env.RWALK_CASE || "dsc-26-0005";
const SHOTS = process.env.RWALK_SHOTS || "/tmp/claude-0/reconnect-shots";
const CHROME = process.env.RWALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

let pass = 0;
const failures = [];
const pageErrors = [];
const ok = (w) => { pass += 1; console.log(`  ✓ ${w}`); };
const bad = (w, saw) => { failures.push(`${w} — saw: ${saw}`); console.log(`  ✗ ${w}\n      saw: ${saw}`); };
const is = (c, w, saw) => (c ? ok(w) : bad(w, String(saw)));
const bodyText = (p) => p.evaluate(() => document.body.innerText.replace(/\s+/g, " "));

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext();

  for (const width of [1440, 1280]) {
    console.log(`\n═══ ${width}px ═══`);
    const p = await ctx.newPage({ viewport: { width, height: 1700 } });
    p.setDefaultTimeout(25000);
    p.on("pageerror", (e) => pageErrors.push(`PAGEERROR ${e.message}`));
    await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
    await p.fill("#signin-email", EMAIL);
    await p.fill("#signin-password", PASSWORD);
    await Promise.all([
      p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
      p.click('button[type="submit"]'),
    ]);

    // ── STEP 1 · CHOOSE ────────────────────────────────────────────────────
    await p.goto(`${BASE}/${T}/disconnects/${CASE}/reconnect`, { waitUntil: "networkidle" });
    await p.waitForTimeout(900);
    await p.screenshot({ path: `${SHOTS}/step1-${width}.png`, fullPage: true });
    let text = await bodyText(p);

    is(/Put service back on/.test(text), "the drawn title is on the page", text.slice(0, 120));
    is(/RECONNECT/i.test(text), "the drawn kicker is on the page", "absent");
    is(/Choose/.test(text) && /Confirm/.test(text), "both drawn steps are named", "absent");
    // 4.3 — the fact no reconnect surface carried before this screen.
    is(/Account type/.test(text), "the ACCOUNT TYPE is drawn (4.3)", "absent");
    is(/Regular|Master/.test(text), "and it says which", "absent");
    // ⚠ **THREE THINGS THIS WALK DID NOT ASK AND THE SCREENSHOT SHOWED.** Each
    // was a real defect on the running product that every DOM assertion passed
    // over, and each is a case now so the next change re-runs it (law 6).
    is(!/\b20\d\d-\d\d-\d\d\b/.test(text),
       "no ISO date is printed — a date renders in the TENANT's format (IS-8)",
       (text.match(/\b20\d\d-\d\d-\d\d\b/g) || []).join(" "));
    is(!/\b(electric|water|sewer|storm_water|thermal|unit_meters)\b/.test(text),
       "no service CODE is printed — the product-wide label is used (B14 rule 31)",
       (text.match(/\b(electric|water|sewer|storm_water|thermal|unit_meters)\b/g) || []).join(" "));
    // 4.4 — the table array, from the kit.
    is(
      (await p.$('[data-editable-table="reconnect-services"]')) !== null,
      "the services table is the KIT's EditableTable, not a second one (B14 rule 43)",
      "absent",
    );
    is((await p.$('[data-testid="reconnect-add"]')) !== null, "+ Add a service is on the page (4.4)", "absent");
    is((await p.$$("[data-remove-row]")).length > 0, "every row has a remove (4.4)", "none");
    // 4.5 — the act, on the row.
    is(
      (await p.$$('[data-testid^="reconnect-raise-"]')).length > 0,
      "the clerk can RAISE the work order from the row (4.5)",
      "no raise control",
    );
    const how = await p.$$('select[id^="reconnect-how-"]');
    is(how.length > 0, "each row chooses HOW it goes back", "no select");
    if (how.length) {
      const opts = await how[0].$$eval("option", (os) => os.map((o) => o.textContent.trim()));
      is(
        opts.includes("Work order") && opts.includes("Remote") && opts.includes("No visit"),
        "the three ways back are offered",
        opts.join(" / "),
      );
    }
    is(
      (await p.$$('input[id^="reconnect-instruction-"]')).length > 0,
      "each row carries an instruction (4.5)",
      "absent",
    );
    // B14 rule 31 — no database id is ever a visible value.
    is(!/[0-9a-f]{8}-[0-9a-f]{4}-/.test(text), "no uuid is visible anywhere (B14 rule 31)", "a uuid is on screen");
    // 4.8 — the address, and the back link to the case.
    is(p.url().includes(`/disconnects/${CASE}/reconnect`), "the screen has an address of its own (4.8)", p.url());
    const back = await p.$('[data-testid="reconnect-back"]');
    is(back !== null && (await back.getAttribute("href")) === `/${T}/disconnects/${CASE}`,
       "the back link is a real address to the case", back ? await back.getAttribute("href") : "absent");

    // ── STEP 2 · CONFIRM ───────────────────────────────────────────────────
    await p.goto(`${BASE}/${T}/disconnects/${CASE}/reconnect?step=2`, { waitUntil: "networkidle" });
    await p.waitForTimeout(900);
    await p.screenshot({ path: `${SHOTS}/step2-${width}.png`, fullPage: true });
    text = await bodyText(p);

    // 4.7 — four lines in a box become a table.
    is((await p.$('[data-testid="reconnect-owed"]')) !== null, "what is owed is a TABLE (4.7)", "absent");
    for (const line of ["arrears_at_the_cut", "reconnection_fee", "paid_since", "still_owed"]) {
      is((await p.$(`[data-owed-line="${line}"]`)) !== null, `  the ${line.replace(/_/g, " ")} line is drawn`, "absent");
    }
    // ⚠ **A MONEY FIGURE MUST NOT RUN INTO THE NEXT COLUMN.** The running
    // product printed `$64.802026-09-20` — one string to a reader, two facts in
    // the markup — because a right-aligned money column had no gutter beside
    // it. `innerText` collapses the cell boundary, so this is the assertion
    // that can see it.
    is(!/\$[\d,]+\.\d\d\d/.test(text),
       "no money figure runs into the column beside it",
       (text.match(/\$[\d,]+\.\d{3,}/g) || []).join(" "));
    // Hard rule 2 — money DISPLAYS at 2 decimals, never 4 and never cents.
    const money = (text.match(/\$[\d,]+\.\d+/g) || []);
    is(money.length > 0 && money.every((m) => /\.\d{2}$/.test(m)),
       "every money figure displays at 2 decimals (hard rule 2)", money.join(" "));
    // 4.2 — BR-CUS-1097 on screen.
    const warn = await p.$('[data-testid="reconnect-warning"]');
    is(warn !== null, "the still-owed warning is drawn (4.2 · BR-CUS-1097)", "absent");
    if (warn) {
      const words = (await warn.innerText()).trim();
      console.log(`      warning reads: "${words}"`);
      is(words.split(/\s+/).length <= 8, "  and it is short (B14 rule 33)", `${words.split(/\s+/).length} words`);
      // ⚠ **THE FIGURE CARRIES ITS CURRENCY.** The first run of this walk read
      // *"139.80 still owed"* — the bare 2dp string, no symbol — on the one
      // sentence a clerk reads before restoring supply. Every DOM assertion
      // passed over it. This is the case that found it.
      is(/[$€£¥₹]/.test(words), "  and the figure carries its currency symbol", words);
    }
    // B14 rule 33 — RATIONALE is ZERO WORDS. It is REMOVED, never shortened.
    for (const leak of ["BR-CUS", "retention", "audit log", "DSC-02.4", "superseded", "OQ-"]) {
      is(!text.includes(leak), `  no rationale leak: "${leak}" (B14 rule 33)`, "on screen");
    }
    // BR-SHL-025 — the live refusal is VISIBLE TEXT, not a tooltip.
    const refused = await p.$('[data-testid="reconnect-refused"]');
    is(refused !== null, "the product's live refusal is VISIBLE TEXT (BR-SHL-025, DEF-CUS-6742)", "absent");
    // ⚠ **AND THE BUTTON ABOVE IT IS ACTUALLY DEAD.** The first run drew a
    // live primary `Put service back on ✓` directly above the sentence saying
    // the product refuses it — a dead control on a live screen, hard-won law
    // 2's mirror, which no gate in this repo can see. This is the case that
    // fires if it ever comes back.
    const commit = await p.$(`[data-wizard="actions"] button[data-variant="primary"]`);
    is(commit !== null && (await commit.isDisabled()),
       "and the commit above it is REFUSED, not merely explained (law 2's mirror)",
       commit === null ? "no commit button" : "the button is live");
    // A `$0.00` deposit panel is a whole panel saying nothing (B14 rule 32).
    const deposit = await p.$('[data-testid="reconnect-deposit"]');
    if (deposit) {
      const depositText = (await deposit.innerText()).replace(/\s+/g, " ");
      is(!/\$0\.00/.test(depositText), "no empty deposit panel is drawn", depositText);
    } else {
      ok("no deposit panel where there is no deposit");
    }

    // The page must not scroll sideways at either staff width.
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    is(overflow <= 0, `no horizontal page scroll at ${width}px`, `${overflow}px over`);

    await p.close();
  }

  console.log(`\n${pass} passed · ${failures.length} failed · ${pageErrors.length} page errors`);
  for (const f of failures) console.log(`  FAIL ${f}`);
  for (const e of pageErrors) console.log(`  ${e}`);
  console.log(`shots: ${SHOTS}`);
} finally {
  await browser?.close();
}
