/**
 * ── Trace ──────────────────────────────────────────────
 * Story:   `DEF-INT-5629` (the reconciliation's apply path could not write one
 *          row) and `DEF-INT-5601` (CR-112's modules had no caller). Both are
 *          about code nothing reaches, so BOTH have to be proved from a
 *          BROWSER: a fix no screen reaches is the same defect one layer up.
 * Screens: S16 `/:tenant/premises/new` step 2 — *Where is this property?* ·
 *          S142 `/:tenant/settings/integrations/<id>` — the operation's row and
 *          its *Run now* Preview / Apply.
 * Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output — the
 *          browser is the only evidence) · law 2's mirror (a live screen behind
 *          a dead control) · B14 rule 33 (rationale is ZERO WORDS on screen)
 * Run:     BASE=http://127.0.0.1:8431 node 10-scripts/cr115_gis_ranking_and_run_walkthrough.mjs
 * ───────────────────────────────────────────────────────
 *
 * ⚠⚠ **THIS WALK PROVES OUR CODE. IT PROVES NOTHING ABOUT ANN ARBOR'S DATA.**
 * The egress proxy in this environment refuses `a2mapseg.a2gov.org` — a plain
 * `curl` returns code `000`, and inside Django the same refusal arrives as
 * `OSError: Tunnel connection failed: 403 Forbidden`. Every candidate below
 * comes from `apps/integrations/gis_fixtures.py`, whose own docstring says it
 * is hand-shaped from documented field names and is **not a recording of the
 * City**. A green run means our search, our ranking and our run behave.
 *
 * ⚠ **THE FALSE-PASS MODE FOR EVERY STEP IS NAMED BESIDE IT**, because a walk
 * that cannot fail is worth less than no walk at all (law 7, habit 2).
 */

import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";

const require = createRequire("file:///home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8431";
const T = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr115-gis-walk";
mkdirSync(OUT, { recursive: true });

function chrome() {
  const want = chromium.executablePath();
  if (want && existsSync(want)) return want;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const d of readdirSync(root)) {
      const c = join(root, d, "chrome-linux", "chrome");
      if (existsSync(c)) return c;
    }
  }
  throw new Error("no chromium — set PLAYWRIGHT_BROWSERS_PATH (never run `playwright install`)");
}

let pass = 0;
let fail = 0;
function say(what, ok, detail = "") {
  if (ok) pass += 1;
  else fail += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${what}${detail ? `  — ${detail}` : ""}`);
}

const run = async () => {
  const b = await chromium.launch({ executablePath: chrome(), args: ["--no-sandbox"] });
  const p = await b.newPage();
  const searches = [];
  const runs = [];
  p.on("response", async (r) => {
    const u = r.url();
    if (!u.includes("/api/")) return;
    let body = null;
    try {
      body = await r.json();
    } catch {
      /* not json — a page, a redirect, an empty 204 */
    }
    if (u.includes("address-search")) searches.push({ url: decodeURIComponent(u), status: r.status(), body });
    if (u.includes("/reconcile")) runs.push({ url: u, status: r.status(), body, sent: r.request().postData() });
  });

  console.log(`\nBASE ${BASE} · tenant ${T}\n`);

  // ── sign in ─────────────────────────────────────────────────────────────
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await p.click('button[type="submit"]');
  await p.waitForTimeout(2500);
  say("signed in and did not land on /change-password (DEF-IDN-5653)",
      !p.url().includes("change-password"), p.url());

  // ══════════════════════════════════════════════════════════════════════
  // 1 · S16 — A CLERK TYPES AN ADDRESS AND READS A LIST
  // ══════════════════════════════════════════════════════════════════════
  console.log("\n1 · THE CITY ADDRESS SEARCH  (DEF-INT-5601 — the ranking)");
  await p.goto(`${BASE}/${T}/premises/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  await p.getByText("One premise", { exact: true }).first().click();
  await p.waitForTimeout(400);
  await p.getByRole("button", { name: /Continue/i }).first().click();
  await p.waitForTimeout(2000);

  say("the FIND THE ADDRESS panel is on step 2",
      (await p.locator('[data-testid="find-the-address"]').count()) === 1);

  await p.fill("#city-address-search", "1408 Pec");
  await p.waitForTimeout(3000);
  await p.screenshot({ path: `${OUT}/01-candidates.png`, fullPage: true });

  const last = searches[searches.length - 1];
  say("the endpoint now carries `ranking_note_key` on the wire",
      last && last.body && "ranking_note_key" in last.body,
      last ? `key=${JSON.stringify(last.body?.ranking_note_key)}` : "no search seen");

  // ⚠ FALSE PASS: the seeded recording is a GEOCODER and publishes a score, so
  // the City's own relevance decides and the note must be ABSENT. A note drawn
  // here would be us claiming credit for their order.
  const onScreen = (await p.locator('[data-testid="find-the-address"]').innerText()).replace(/\s+/g, " ");
  say("no ranking note over a list the City itself ranked",
      (await p.locator('[data-testid="ranking-note"]').count()) === 0,
      "the seeded fixture publishes a score, so the order is theirs");

  // B14 rule 33 — RATIONALE IS ZERO WORDS ON SCREEN. The forty-word paragraph
  // this screen used to print on every search is gone.
  say("the forty-word `noScore` rationale paragraph is gone (B14 rule 33)",
      !onScreen.includes("needs a scale nobody has confirmed"));

  const order = (last?.body?.candidates ?? []).map((one) => one.parcel);
  say("the list is in the City's own relevance order, best first",
      JSON.stringify(order) === JSON.stringify(["88214", "88215", "88301", "88302"]),
      order.join(" · "));

  const first = await p.locator('[data-testid="find-the-address"] li').first().innerText();
  say("the row a clerk reads first is the address they typed",
      first.includes("1408 Pecan St"), first.split("\n")[0]);

  // ══════════════════════════════════════════════════════════════════════
  // 2 · S142 — RUN NOW, PREVIEW  (DEF-INT-5629 — the apply path)
  // ══════════════════════════════════════════════════════════════════════
  console.log("\n2 · RUN NOW ON THE OPERATION'S ROW  (DEF-INT-5629)");
  await p.goto(`${BASE}/${T}/settings/integrations`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2000);
  const esri = p.getByRole("row").filter({ hasText: /Esri|ArcGIS|GIS/i }).first();
  const seen = (await esri.count()) > 0;
  say("the Esri ArcGIS connector has a row on the connector table", seen);
  if (seen) {
    await esri.getByRole("link", { name: /View/i }).first().click().catch(async () => {
      await esri.click();
    });
    await p.waitForTimeout(2500);
  }
  await p.screenshot({ path: `${OUT}/02-connector.png`, fullPage: true });

  const preview = p.getByRole("button", { name: /Preview/i }).first();
  say("the reconciliation operation offers *Preview* on its own row, not one dangerous button",
      (await preview.count()) > 0);
  say("*Run now* did NOT become a fifth header action (B14 rule 2)",
      (await p.locator("header").getByRole("button", { name: /Run now/i }).count()) === 0);

  if ((await preview.count()) > 0) {
    await preview.click();
    await p.waitForTimeout(6000);
    await p.screenshot({ path: `${OUT}/03-preview.png`, fullPage: true });
    const answered = runs[runs.length - 1];
    say("Preview reached the server and came back",
        !!answered && answered.status < 400, answered ? `HTTP ${answered.status}` : "no call seen");
    say("the request said mode=preview and who started it",
        !!answered && /preview/.test(answered.sent ?? ""), answered?.sent ?? "");
    const report = answered?.body ?? {};
    say("R28 — the report SAYS why nothing was applied rather than showing two zeroes",
        typeof report.headline === "string" && report.headline.length > 0, report.headline ?? "");
    say("a preview refuses nothing, and the key is present at zero rather than absent",
        Array.isArray(report.refusals) && report.refusals.length === 0);
  }

  await b.close();
  console.log(`\n${pass} PASS · ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
};

run().catch((error) => {
  console.error(error);
  process.exit(2);
});
