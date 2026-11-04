// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-5427 — the Approve dialog enabled the commit over a blocker
//          only the press could reveal, then saved the outcome and refused the
//          approval.
// Change:  the two PO rulings of 2026-09-16 — *"lets not make it mandetory"*
//          (unchecked documents stop blocking) and *"if you want ywe can show
//          the messge documents will be required"* (the clerk is told anyway).
// Rules:   B14 rule 31 (no database id on screen) · rule 32 (no internal code in
//          clerk-facing copy) · rule 33 (on-screen text capped by what it is
//          for) · BR-CUS-095 (the checklist is keyed on the OUTCOME).
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS IS THE ONLY CHECK IN THIS REPOSITORY THAT READS RENDERED OUTPUT**
// (hard-won law 6). No gate looks at a screen, and the whole of this defect —
// a live button with nothing beside it — is invisible to every one of them.
//
// **WHAT IT WALKS, and it is every kind offered rather than the interesting one**
// (five radios when written; two `SegmentedControl` segments since the
// 2026-09-23 rebuild, read off the screen — updated 2026-10-11).
// The defect's mechanism is that the blocker DEPENDS ON THE PICK, so a walk
// that only tried `move_in` would prove nothing about whether the dialog
// redraws; it has to pick each of the five in turn and print what the clerk is
// told for each. The expected shape on the seeded `brazosbend` tenant is that
// `move_in` is the one outcome with a document checklist, so four outcomes read
// clean and one carries the `Still needed` notice — with the commit LIVE on all
// five, because documents no longer block.
//
// ⚠ **IT ALSO READS THE PRESS.** `--press` picks one outcome, commits, and then
// re-reads the request through the API: the point of the fix is that a REFUSED
// approval leaves no outcome behind, and the only way to see that is to look at
// the row afterwards.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/smartbillhub?sslmode=disable \
//      JOBS_EAGER=false python3 manage.py runserver 127.0.0.1:8110 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8131 \
//      API_PROXY_TARGET=http://127.0.0.1:8110 node server.mjs)
//   REQUEST=<uuid> node 10-scripts/def_cus_5427_approve_walkthrough.mjs
//   REQUEST=<uuid> PRESS=move_in node 10-scripts/def_cus_5427_approve_walkthrough.mjs
const { existsSync, readdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8131";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const REQUEST = process.env.REQUEST;
const PRESS = process.env.PRESS ?? "";
const WIDTH = Number(process.env.WIDTH ?? 1440);
const OUTCOMES = ["new_connection", "move_in"];

if (!REQUEST) {
  throw new Error("REQUEST=<service request uuid> is required — walk a real row, not a fixture");
}

/** The pinned revision is usually absent in this container; any chromium beats
 *  not running at all, and the substitution is printed so nobody is surprised. */
function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error("no chromium found — run `npx playwright install chromium` from 07-frontend");
}

const failures = [];
function fail(message) {
  failures.push(message);
  console.log(`  ✗ ${message}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: WIDTH, height: 1000 } });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });

await page.goto(`${BASE}/${TENANT}/requests/${REQUEST}`, { waitUntil: "networkidle" });
await page.waitForSelector("h1", { timeout: 15000 });
// ⚠ **A DISABLED HEAD BUTTON IS AN ANSWER, NOT A CRASH.** `approve` is not an
// available action in every state — a request in `More info` offers
// `info_received` and nothing else — and a walkthrough that threw a Playwright
// timeout there would report a harness fault where the product is correct
// (hard-won law 7: a check's output must distinguish pass from fail to a
// reader).
const head = page.locator('[data-decision-action="approve"]');
if (await head.isDisabled()) {
  console.log(`\nrequest ${REQUEST}: the head's Approve is disabled — this state does not offer it.`);
  console.log("Nothing to walk. Pick a request under review.");
  await browser.close();
  process.exit(0);
}
await head.click();
const modal = page.locator('[role="dialog"]').first();
await modal.waitFor({ timeout: 10000 });

async function read() {
  const submit = modal.getByRole("button", { name: /Approve/ }).last();
  return {
    disabled: await submit.isDisabled(),
    refusal: (await modal.locator("[data-commit-blocked]").allTextContents()).join(" | "),
    // 2026-10-11: the checks are the kit's `CheckList` — one `[data-check]`
    // row each, its state on `data-check-state`; a row that is not `ok` is
    // what the clerk is still asked for.
    stillNeeded: (
      await modal
        .locator('[data-check]:not([data-check-state="ok"])')
        .evaluateAll((rows) =>
          rows.map((r) => `${r.getAttribute("data-check")}=${r.getAttribute("data-check-state")}`),
        )
    ).join(" | "),
    arrearsPointer: (await modal.locator("[data-approve-arrears-search]").allTextContents()).join(" | "),
  };
}

console.log(`\nwidth ${WIDTH} · request ${REQUEST}`);
console.log("— nothing picked —");
console.log("   ", JSON.stringify(await read(), null, 0));

// The Approve window offers what `APPROVE_OUTCOMES` holds (two kinds since the
// 2026-09-23 rebuild: new connection and move-in) — read them off the screen
// rather than a list here that can outlive them.
const offered = await modal
  .locator('[data-segmented="approve-kind"] [data-segment]')
  .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-segment")));
console.log(`kinds offered: ${offered.join(", ")}`);
for (const missing of OUTCOMES.filter((o) => !offered.includes(o))) {
  fail(`the Approve window does not offer ${missing}`);
}
for (const outcome of offered) {
  // 2026-10-11: the outcome is the kit's SegmentedControl, not radios.
  const segment = modal.locator(`[data-segmented="approve-kind"] [data-segment="${outcome}"]`);
  if (await segment.isDisabled()) {
    console.log(`— ${outcome} — refused by the server: ${(await segment.getAttribute("title")) ?? ""}`);
    continue;
  }
  await segment.click();
  await page.waitForTimeout(150);
  const state = await read();
  console.log(`— ${outcome} —`);
  console.log(`    commit ${state.disabled ? "REFUSED" : "live"}${state.refusal ? ` · ${state.refusal}` : ""}`);
  if (state.stillNeeded) console.log(`    still needed: ${state.stillNeeded}`);
  // PO 2026-10-11, option B: the Arrears row POINTS at Search customer and
  // carries no button of its own.
  if (state.arrearsPointer) {
    console.log(`    arrears: ${state.arrearsPointer}`);
    if (state.arrearsPointer.trim() !== "Search customer below.") {
      fail(`the Arrears row reads "${state.arrearsPointer}", not "Search customer below."`);
    }
    if ((await modal.locator('[data-check] [data-approve-arrears-search] button, [data-check-action] [data-action="record-search"]').count()) > 0) {
      fail("the Arrears row still carries a button of its own");
    }
  }
  // ⚠ RULE 32 — an internal code must never be the thing a clerk reads. The
  // doc types travel in the payload and the count is what is rendered.
  const body = (await modal.textContent()) ?? "";
  for (const code of ["proof_of_identity", "signed_service_agreement", "documents_verified", "no_blocking_arrears"]) {
    if (body.includes(code)) fail(`rule 32: the code ${code} is on screen under ${outcome}`);
  }
  if (/\bBR-[A-Z]{3}-\d/.test(body) || /\b(OQ|DEF)-/.test(body)) {
    fail(`rule 32: a rule or register id is on screen under ${outcome}`);
  }
}

if (PRESS) {
  await modal.locator(`[data-segmented="approve-kind"] [data-segment="${PRESS}"]`).click();
  await page.waitForTimeout(150);
  // PO 2026-10-11, option B: an unsearched applicant is answered in Search
  // customer — run the search, then No match (`data-action="record-search"`).
  if ((await modal.locator("[data-approve-arrears-search]").count()) > 0) {
    await modal.locator("[data-customer-search]").click();
    const noMatch = modal.locator('[data-action="record-search"]');
    await noMatch.waitFor({ timeout: 15000 });
    await noMatch.click();
    await page.waitForTimeout(2500);
    if ((await modal.count()) === 0) {
      await head.click();
      await modal.waitFor({ timeout: 10000 });
    }
    await modal.locator(`[data-segmented="approve-kind"] [data-segment="${PRESS}"]`).click();
    await page.waitForTimeout(300);
  }
  const before = await read();
  console.log(`\n— pressing with ${PRESS} —  (commit was ${before.disabled ? "REFUSED" : "live"})`);
  if (before.disabled) {
    console.log("    not pressed: the commit is refused, which is the point of the fix");
  } else {
    await modal.getByRole("button", { name: /Approve/ }).last().click();
    await page.waitForTimeout(2500);
    const answer = await page.evaluate(
      async ([tenant, id]) => {
        const res = await fetch(`/api/${tenant}/service-requests/${id}`, {
          headers: { Accept: "application/json" },
        });
        const body = await res.json();
        return { state: body.header?.state, outcome: body.decision?.commit?.outcome };
      },
      [TENANT, REQUEST],
    );
    console.log(`    the request is now ${answer.state}, outcome ${answer.outcome ?? "(none)"}`);
    // The whole defect: a refused approval must leave NO outcome behind.
    if (answer.state !== "approved" && answer.outcome) {
      fail(`the approval did not complete and the outcome ${answer.outcome} was written anyway`);
    }
  }
}

await browser.close();
console.log(failures.length === 0 ? "\nOK" : `\n${failures.length} finding(s)`);
process.exit(failures.length === 0 ? 0 : 1);
