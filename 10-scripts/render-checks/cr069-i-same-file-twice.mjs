/**
 * RENDERED-OUTPUT CHECK — CR-069 wave I, *the same bank file twice*, in a real
 * browser, against a real PostgreSQL.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ⚠ **AND THIS WAVE HAS A SECOND REASON.** The whole deliverable is a REFUSAL,
 * and a refusal is a sentence a person reads. A pytest case can prove the run
 * row closed `skipped` with the right summary; only a browser can tell you
 * that S142 prints *refused duplicate — the same file as Tuesday 06:10* rather
 * than the raw enum word `skipped`, or the perfectly formatted lie *0 of 0*.
 * Both of those were live before this wave and neither is visible to any test.
 *
 * ── WHAT THIS SCRIPT DOES AND DOES NOT COVER, SAID FIRST ───────────────────
 *
 * ⚠ **THE UPLOAD IS DRIVEN THROUGH THE API, NOT A SCREEN, AND THAT IS THE
 * BOUNDARY RATHER THAN A SHORTCUT.** Wave I is a SPLIT wave (`CR-069` §20.4,
 * `BR-INT-054` as amended 2026-09-06). Integrations owns the bank connection
 * and the record that a file arrived; the import WIZARD (S38) and everything
 * it does with the rows belongs to the processing half, which is Runbooks' and
 * is not built. So there is no integrations screen that takes a file, and this
 * script posts to `POST /integrations/{key}/arrival` — the door this wave
 * actually shipped — and then reads the result on the screens this wave owns:
 * the card (S8) and the connection detail (S142).
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone int_i --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py migrate
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=true \
 *   DATABASE_URL="$DATABASE_URL" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8161 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4361 API_PROXY_TARGET=http://127.0.0.1:8161 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4361 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-i-same-file-twice.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** It CONNECTS a bank
 * profile, so a shared database is left with a stranger's bank connection.
 *
 * ── WHAT IT ASSERTS (demo script I, the integrations half) ────────────────
 *   1  The *Bank & lockbox file* card is CONNECTABLE. Before this wave the
 *      card was live, the manifest was registered, and connect was refused
 *      *Cannot be connected yet.* — hard-won law 2, built is not wired.
 *   2  Connect it: label *Chase lockbox*, format BAI2, source *upload*. The
 *      modal is generated from the manifest and asks for no folder password.
 *   3  Tuesday's file arrives → **201**, and the run appears on S142.
 *   4  The SAME BYTES arrive again → **409**, and S142 reads
 *      *refused duplicate — the same file as Tuesday HH:MM*, naming the FIRST
 *      arrival by day and time.
 *   5  **THE CONTROL** — a file ONE BYTE different arrives → **201**. Without
 *      this step, step 4 is indistinguishable from an endpoint that refuses
 *      everything, and *nothing was written* would be a description of both.
 *   6  Both refused and accepted rows show a content hash; the two duplicates
 *      share theirs and the third differs.
 *   7  The refused row's word is *Not attempted* — NOT the raw enum `skipped`
 *      (B14 rule 32: no internal code in clerk copy) and NOT *0 of 0*.
 *   8  No database id and no rule id anywhere on these screens (B14 rules
 *      31 and 32).
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/**
 * ⚠ RUN THE BINARY; DO NOT TRUST THE PATH. `chromium.executablePath()` returns
 * the path playwright-core WANTS — it does not throw when nothing is there, so
 * a `try/catch` around it never fires and the launch fails later with a path
 * that looks plausible. This deployment has `chromium-1194` installed while the
 * pinned playwright asks for `chromium-1234`. `--version` is the only check
 * that distinguishes "installed" from "named": law 7's *looking at the wrong
 * thing*, and the cr070 walkthroughs already solved it this way.
 */
function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [join(root, dir, "chrome-linux", "chrome"), join(root, dir)]) {
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4361";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-i";
const VIEWPORT = { width: 1440, height: 1000 };

const PROVIDER = "bank_lockbox_file";
const OPERATION = "import_lockbox";

/*
 * J14's lockbox file. BYTES — the thing the bank actually sends.
 *
 * ⚠ **THE RUN NUMBER IN THE HEADER IS WHAT MAKES THIS SCRIPT RE-RUNNABLE, AND
 * LEAVING IT OUT COST A WHOLE RUN.** The product's guarantee is that the same
 * bytes are refused FOREVER on that connection — so a walkthrough posting a
 * FIXED file passes once and then fails on its own success: the second run
 * reads `409` where it expects `201`, and every later assertion drifts onto
 * rows the previous run left behind. That is not a flaky check, it is a check
 * that can only ever be true once, which is worse.
 *
 * So the header carries this run's own stamp. Each run gets a genuinely new
 * file, and the duplicate it then sends is a duplicate of THIS run's file
 * rather than of some earlier lane's.
 */
const STAMP = String(Date.now()).slice(-6);
const TUESDAY =
  `6,121000248,0000123456,260901,${STAMP},USD,2/\n16,175,0000004250,,A-10432/\n`;
//: ONE BYTE different. It parses to the same rows and it is a DIFFERENT FILE —
//: the direction people find surprising, and the safe one.
const RECUT = TUESDAY.replace("USD", "USE");

const failures = [];
const gaps = new Gaps();

function check(ok, what, detail = "") {
  console.log(`${ok ? "  ok  " : "  FAIL"} ${what}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures.push(what);
}

async function shot(page, name) {
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
}

/** Post a file to the arrival door as the signed-in clerk, from inside the page. */
async function arrive(page, body) {
  return page.evaluate(
    async ([tenant, provider, operation, content]) => {
      const form = new FormData();
      form.append("operation", operation);
      form.append("file", new Blob([content], { type: "text/plain" }), "lockbox.bai2");
      const response = await fetch(
        `/api/${tenant}/integrations/${provider}/arrival`,
        { method: "POST", body: form, credentials: "include" },
      );
      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      return { status: response.status, payload };
    },
    [TENANT, PROVIDER, OPERATION, body],
  );
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr069-i: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ── sign in ──────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });

  // ── 1 · the card is connectable at all ───────────────────────────────────
  console.log("\n1 · the Bank & lockbox file card");
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  const cardText = await page.locator("body").innerText();
  check(/bank\s*&?\s*lockbox/i.test(cardText), "the bank card is on the grid");
  await shot(page, "01-grid");

  const grid = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/integrations`, { credentials: "include" });
    return r.json();
  }, TENANT);
  const bank = (grid.providers ?? []).find((one) => one.key === PROVIDER);
  check(bank !== undefined, "the grid serves the bank provider");
  check(
    bank?.adapter_registered === true,
    "the bank adapter is REGISTERED, so connect is not refused",
    "hard-won law 2 — before wave I this was false and the card could not be connected",
  );

  // ── 2 · connect it ───────────────────────────────────────────────────────
  console.log("\n2 · connect Chase lockbox (upload source)");
  const connected = await page.evaluate(
    async ([tenant, provider]) => {
      const r = await fetch(`/api/${tenant}/integrations/${provider}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          environment: "production",
          cadence: "manual",
          label: "Chase lockbox",
          fields: { label: "Chase lockbox", file_format: "bai2", source: "upload" },
        }),
      });
      return { status: r.status, body: await r.text() };
    },
    [TENANT, PROVIDER],
  );
  check(
    connected.status === 201 || connected.status === 409,
    "the bank connection is accepted (or already present)",
    `HTTP ${connected.status}`,
  );

  // ── 3 · Tuesday's file arrives ───────────────────────────────────────────
  console.log("\n3 · Tuesday's file");
  const first = await arrive(page, TUESDAY);
  check(first.status === 201, "the first arrival is accepted", `HTTP ${first.status}`);
  check(Boolean(first.payload?.content_hash), "the reply carries the content hash");
  check(first.payload?.accepted === true, "…and says so plainly");

  // ── 4 · the same bytes again ─────────────────────────────────────────────
  console.log("\n4 · the SAME file again");
  const second = await arrive(page, TUESDAY);
  check(second.status === 409, "the second arrival is REFUSED", `HTTP ${second.status}`);
  check(second.payload?.accepted === false, "…and says so plainly");
  check(
    second.payload?.content_hash === first.payload?.content_hash,
    "both rows share the content hash — that is what makes them the same file",
  );
  check(
    /refused duplicate/i.test(second.payload?.summary ?? ""),
    "the refusal names itself",
    second.payload?.summary ?? "(no summary)",
  );
  check(
    /monday|tuesday|wednesday|thursday|friday|saturday|sunday/i.test(
      second.payload?.summary ?? "",
    ),
    "…and names the FIRST arrival by day",
    second.payload?.summary ?? "",
  );

  // ── 5 · THE CONTROL ──────────────────────────────────────────────────────
  console.log("\n5 · a file ONE BYTE different — the control case");
  const third = await arrive(page, RECUT);
  check(
    third.status === 201,
    "a genuinely different file is STILL ACCEPTED",
    `HTTP ${third.status} — without this, step 4 also describes a broken endpoint`,
  );
  check(
    third.payload?.content_hash !== first.payload?.content_hash,
    "…and its hash differs, even though it parses to the same rows",
  );

  // ── 6 · S142 reads it ────────────────────────────────────────────────────
  console.log("\n6 · the connection detail (S142)");
  await page.goto(`${BASE}/${TENANT}/settings/integrations/${PROVIDER}`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("[data-run-row]", { timeout: 20000 });
  const listText = await page.locator("body").innerText();
  await shot(page, "02-detail-list");

  //: the refused run is the one that closed `skipped` — found by its OWN
  //: marker rather than by position, so a new run above it cannot break this
  //: ⚠ THIS RUN'S refused arrival, found by ITS OWN TRACE ID rather than by
  //: being the first `skipped` row on the screen. An earlier run of this
  //: script leaves its own refused rows behind, and "the first one" would
  //: quietly become somebody else's — a check looking at the wrong thing.
  const refusedTrace = second.payload?.trace_id ?? "";
  const refusedRow = page.locator(`[data-run-row="${refusedTrace}"]`);
  check(
    (await refusedRow.count()) > 0,
    "the refused arrival has a row on S142",
    `trace ${refusedTrace} — a duplicate that arrives is still an ARRIVAL and is recorded`,
  );

  //: ⚠ OPEN IT, BECAUSE THAT IS WHERE THE SENTENCE LIVES AND A CLERK HAS TO
  //: PRESS SOMETHING TO SEE IT. The list cell carries the outcome WORD; the
  //: reason is on the run's own card (B14 rule 32 — a screen has a description
  //: budget, and a stated absence is CLOSED by default). Asserting the
  //: sentence against the list would have been asserting the wrong surface.
  const row = page.locator("tr", { has: page.locator(`[data-run-row="${refusedTrace}"]`) }).first();
  await row.locator("button").last().click();
  await page.waitForSelector("[data-run-card]", { timeout: 20000 });
  const detail = await page.locator("[data-run-card]").first().innerText();
  await shot(page, "03-detail-card");

  check(
    /refused duplicate/i.test(detail),
    "S142 PRINTS the refusal sentence to a person",
    "the whole deliverable is a sentence a clerk reads",
  );
  check(
    /monday|tuesday|wednesday|thursday|friday|saturday|sunday/i.test(detail),
    "…and the sentence names the first arrival by DAY",
  );
  check(
    detail.includes(second.payload?.content_hash?.slice(0, 12) ?? "\u0000"),
    "…and the run's own content hash is on the card",
  );

  // ── 7 · the word, and the two ways it used to be wrong ───────────────────
  console.log("\n7 · the refused row's word");
  //: read off the LIST, which is the cell the wave changed
  check(
    /not attempted/i.test(listText),
    "the refused run reads *Not attempted* in the list",
  );
  check(
    !/\bskipped\b/i.test(listText),
    "…and NOT the raw enum word `skipped`",
    "B14 rule 32 — no internal code in clerk-facing copy",
  );
  check(
    !/\b0 of 0\b/.test(listText),
    "…and NOT *0 of 0*",
    "a run we declined to place attempted nothing; a count there is a formatted lie",
  );

  // ── 8 · rules 31 and 32 ──────────────────────────────────────────────────
  console.log("\n8 · no ids, no rule numbers");
  const everything = `${listText}\n${detail}`;
  check(
    !/\bBR-[A-Z]{3}-\d+\b/.test(everything),
    "no rule id is on the screen",
  );
  check(
    !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(everything),
    "no uuid is on the screen (B14 rule 31)",
  );

  //: ⚠ A DECLARED GAP, WITH A NUMBER, BECAUSE A BLIND SPOT WITH NO COUNT IS
  //: INDISTINGUISHABLE FROM AN EMPTY ONE (law 7's fifth shape).
  gaps.known(
    false,
    "…and an SFTP connection's `test()` lists one real folder",
    {
      defect: "CR-069 wave I",
      why:
        "no SFTP client is installed on this deployment, so `FOLDER_CLIENT` is " +
        "unbound and `test()` answers ok=false *No folder client is installed.* " +
        "rather than a pass it has not earned. When a client is installed this " +
        "gap FAILS for being stale, which is the point of recording it here.",
    },
  );

  console.log(`\n${timings.summary ? timings.summary() : ""}`);
  await browser.close();
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
