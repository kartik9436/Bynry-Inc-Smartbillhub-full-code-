/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  CR-083 (the Integrations block of the sample set) · CR-077 (parts
 *          becomes the seventh target of the one importer). PO standing rule:
 *          *"everything should be executed based on actual code … also ensure
 *          you do web walkthorugh before you sign off the user story or build"*.
 * Rules:   CLAUDE.md hard-won law 6 (no gate in this repo looks at rendered
 *          output) · law 1 (a comment claiming a guarantee is not the
 *          guarantee) · law 2 and its mirror (a live screen behind a dead
 *          control — the Import door is asserted to be a real link that
 *          NAVIGATES, not a span)
 * ───────────────────────────────────────────────────────
 *
 * WHAT IT WALKS, ON A TENANT PROVISIONED THROUGH THE REAL SIGN-UP PATH
 * ════════════════════════════════════════════════════════════════════
 *   1. Settings → Integrations — three connection cards, and NONE of them
 *      claiming to work.
 *   2. The Billing mailbox's own screen — five runs, newest first, each with
 *      the outcome BR-INT-018 computed and the support reference the demo is
 *      read down the telephone.
 *   3. Work → Parts — the Import door, and that it opens the five-stage runner.
 *
 * ⚠ **THE ASSERTIONS ARE THE SCREEN'S OWN WORDS, NOT THE DATABASE'S, AND THE
 * FIRST DRAFT OF THIS FILE GOT THAT WRONG.** It looked for *Untested*,
 * *Succeeded* and *Partial* — the STORED vocabulary — and three checks failed
 * over a product that was correct: the card says *Not tested yet*, the run list
 * says *93 of 93* and *86 of 93 · 7 bad addresses*, and a connection whose last
 * run failed reads *Not working*, computed from that run rather than from the
 * stored column. A walkthrough that asserts the schema is not walking the
 * screen.
 *
 * ⚠ **AND THE STORED `untested` IS STILL THE POINT.** `operation_state` answers
 * `untested` until a run finishes, so a seeded connection can never read
 * *Working* — which is the law-1 guarantee the fixture exists to keep. *Not
 * working* is a report about a run that happened; it is not a claim that the
 * product can dial a provider.
 *
 * RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING — a mid-run reseed looks
 * exactly like a broken screen. And REBUILD THE BUNDLE FIRST: `server.mjs`
 * serves whatever is in the `dist/` it was pointed at when it booted.
 *
 *     10-scripts/proof-db.sh clone cr083 --export        # a private database
 *     manage.py migrate                                   # the clone may be behind
 *     <provision a tenant through provision_tenant + the plant>
 *     (cd 07-frontend && ./node_modules/.bin/vite build)
 *     STATIC_DIR=$PWD/07-frontend/dist API_PROXY_TARGET=http://127.0.0.1:8399 \
 *       PORT=4399 node 07-frontend/server.mjs
 *     WT_TENANT=<slug> node 10-scripts/cr083_integrations_and_parts_walkthrough.mjs
 */
import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";

// ⚠ Node resolves a bare import from the SCRIPT's directory upward, never from
// `cwd`, and the repo root has no `node_modules` — so playwright is resolved
// against the frontend's own package.json explicitly.
const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:4399";
const TENANT = process.env.WT_TENANT ?? "cr083proof";
const EMAIL = process.env.WT_EMAIL ?? `alex@${TENANT}.example`;
const PASSWORD = process.env.WT_PASSWORD ?? "S3cure!passw0rd";
const CHROME = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
page.on("response", (r) => {
  if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`);
});

let failed = 0;
function say(label, ok, detail = "") {
  console.log(`${ok ? "  ✓" : "  ✗"} ${label}${detail ? " — " + detail : ""}`);
  if (!ok) failed += 1;
}
async function go(path) {
  await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  return page.locator("body").innerText();
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForTimeout(2500);
console.log(`signed in at ${page.url()}`);

console.log("\nS8 · Settings → Integrations");
let body = await go("/settings/integrations");
for (const name of ["Custom SMTP", "Water meter cloud", "Bank & lockbox file"]) {
  say(`the ${name} card is connected`, body.includes(name));
}
say(
  "the two untried connections say so in a clerk's words",
  (body.match(/Not tested yet/g) || []).length >= 4,
  `${(body.match(/Not tested yet/g) || []).length} × "Not tested yet"`,
);
// The law-1 check, and it is the one that matters: no seeded connection may
// tell an operator that it WORKS, because no provider can be dialled in this
// release. A run that failed may say so; nothing may claim success.
say("no seeded connection claims to be working", !/\bWorking\b/.test(body));

console.log("\nINT-02 · the Billing mailbox and everything that has run on it");
body = await go("/settings/integrations/email_smtp");
say("all five runs are listed", /1–5 of 5/.test(body), "1–5 of 5");
say("the send that got through reads as counts", /93 of 93/.test(body));
say("the partial send names how many were bad", /86 of 93 · 7 bad addresses/.test(body));
say("the unconfirmed send says the provider did not say", /provider did not say/.test(body));
say("the failed test is there and is not hidden", /Failed/.test(body));
say("the support reference is on the screen", body.includes("A7F3C9E1"));
say("the runs are described as never edited", /never edited/i.test(body));

console.log("\nWRK-10 · Work → Parts, and the door to the upload");
body = await go("/work/parts");
say("the parts register loads", !/could not|went wrong/i.test(body));
const door = page.locator('a:has-text("Import parts")').first();
say("the Import door is a real link, not a dead control", (await door.count()) > 0);
if (await door.count()) {
  await door.click();
  await page.waitForTimeout(2500);
  say("it navigates to the import runner", page.url().includes("/work/parts/import"), page.url());
  body = await page.locator("body").innerText();
  say("the runner names Parts as its target", /WORKFLOW · PARTS/i.test(body));
  say("stage 1 offers the sample file", /Download a sample CSV/i.test(body));
  say("the blurb is the parts one, not another target's", /Upload your parts list/.test(body));

  // ── the upload itself, which is the half a screenshot cannot prove ───────
  // CR-077's acceptance is *"generate the sample file and upload it through the
  // real screen, and confirm every column is already mapped"*. The file below
  // carries the sample template's own headers plus two ordinary rows, and
  // nothing here types a mapping: stage 2's MAPS TO column is the server's own
  // alias detection, and every row of it must read `Matched`.
  const file = `${tmpdir()}/cr083-parts-walkthrough.csv`;
  writeFileSync(
    file,
    "Part #,Name,Category,Unit,Unit cost\n" +
      "PT-9001,2 in. brass elbow,Fittings,each,31.2500\n" +
      "PT-9002,Meter box lid,Consumables,each,7.9000\n",
  );
  await page.setInputFiles('input[type="file"]', file);
  await page.waitForTimeout(1200);
  body = await page.locator("body").innerText();
  say("the file is taken", /cr083-parts-walkthrough\.csv/.test(body));
  await page.locator('button:has-text("Transform →")').first().click();
  await page.waitForTimeout(3000);
  body = await page.locator("body").innerText();
  const matched = (body.match(/Matched/g) || []).length;
  say("every column mapped itself — nothing typed by hand", matched >= 5, `${matched} × "Matched"`);
  say("no column came back unmapped", !/Unmapped/i.test(body));
  say("the category column explains itself", /categories on your parts register/i.test(body));
  say("stage 2 counted the rows it read", /Rows in\s*\n?\s*2/.test(body));
}

console.log(`\nJS errors and 4xx/5xx: ${errors.length ? errors.slice(0, 12).join(" | ") : "none"}`);
console.log(failed === 0 ? "\nWALKTHROUGH PASSED" : `\nWALKTHROUGH FAILED — ${failed} check(s)`);
await browser.close();
process.exit(failed === 0 && errors.length === 0 ? 0 : 1);
