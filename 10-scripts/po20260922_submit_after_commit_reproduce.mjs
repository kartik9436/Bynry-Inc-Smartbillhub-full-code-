// ── Trace ──────────────────────────────────────────────
// Change:  PO report 2026-09-22, PRIORITY 0 — step 6 of `REQ-03` answers
//          *"We could not submit this request / Something went wrong. Nothing
//          was saved — try again."* AND THE REQUEST IS SUBMITTED. The state
//          chip reads `Submitted` and the Submit button is disabled.
// Rules:   `22-product-maintenance-process.md` step 1 (REPRODUCE IT FIRST —
//          never fix what you have not seen) · CLAUDE.md hard-won law 6 ·
//          hard-won law 7 (what would make this check PASS WRONGLY?)
// Screens: `REQ-03.6`
// ───────────────────────────────────────────────────────
//
// ⚠ **A BARE DRAFT SUBMITS FINE — THAT IS WHY THIS SCRIPT IS LONG.** LANE REQ's
// `po20260922_submit_step6_reproduce.mjs` walks the wizard filling the minimum
// and the submit goes through. The failure needs a draft that has SERVICES, a
// DOCUMENT and a FEE on it, which is what a real application has and what a
// four-field draft does not. Building it through the SCREEN rather than through
// the API is the point: the API path is the one we are about to change.
//
// ⚠ **IT READS THE NETWORK, NOT THE SENTENCE.** The screen's words are what is
// being reported, so a check that only read the screen could not tell a 500
// from a validation refusal — and could not see that the request had moved
// anyway. So: every `/api/` response is captured with its status and body, and
// AFTER the press the request is re-read from the server. **The two together
// are the finding** — a failing HTTP call over a state that moved.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/<db> \
//      JOBS_EAGER=false python manage.py runserver 127.0.0.1:8291 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8292 \
//      API_PROXY_TARGET=http://127.0.0.1:8291 node server.mjs)
//   BASE=http://127.0.0.1:8292 node 10-scripts/po20260922_submit_after_commit_reproduce.mjs
//
// ⛔ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** —
// `10-scripts/proof-db.sh clone <label>`.
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8292";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots-reqa";

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
  throw new Error("no chromium found");
}

mkdirSync(SHOTS, { recursive: true });
const SAMPLE = join(SHOTS, "proof-of-identity.pdf");
writeFileSync(
  SAMPLE,
  "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n" +
    "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n" +
    "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n" +
    "trailer<</Root 1 0 R>>\n%%EOF\n",
);

const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);

const calls = [];
page.on("response", async (r) => {
  const u = r.url();
  if (!u.includes("/api/")) return;
  let body = "";
  if (r.status() >= 400) body = (await r.text().catch(() => "")).slice(0, 900);
  calls.push({ status: r.status(), method: r.request().method(), url: u.replace(BASE, ""), body });
});

const note = (m) => console.log(`    · ${m}`);
const found = (m) => console.log(`    ● ${m}`);

let requestId = null;
try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  note(`signed in as ${EMAIL}`);

  // ── STEP 1 · the applicant ────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await page.fill("#applicant_name", "Submit, Priority Zero");
  for (const [sel, val] of [["#applicant_email", "p0@example.com"], ["#applicant_phone", "5125550188"]]) {
    const el = page.locator(sel);
    if ((await el.count()) > 0) await el.fill(val).catch(() => {});
  }
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1800);

  // ── STEP 2 · the connection AND ITS SERVICES ──────────────────────────────
  await page.selectOption("#account_type_code", "residential").catch(() => {});
  await page.waitForTimeout(800);
  // ⚠ **THE SERVICES ARE A `ChipMultiSelect`, NOT TICK BOXES** — the first
  // draft of this script looked for checkboxes, found none, picked NOTHING,
  // and reported *"the submit went through cleanly"* over a draft with zero
  // services. That is law 7's *incapable of failing* in a reproduce script:
  // the condition it exists to create was never created.
  const adder = page.locator('[data-chip-add="capture-services"]');
  if ((await adder.count()) > 0) {
    const values = (await adder.locator("option").evaluateAll((o) => o.map((x) => x.value))).filter(
      (v) => v !== "",
    );
    note(`services offered: ${values.join(" · ")}`);
    for (const value of values.slice(0, 3)) {
      await page.selectOption('[data-chip-add="capture-services"]', value).catch(() => {});
      await page.waitForTimeout(400);
    }
  }
  note(`services picked: ${await page.locator("[data-services-selected]").getAttribute("data-services-selected")}`);
  note(`connection date opens on: ${await page.locator("#requested_start").inputValue().catch(() => "(absent)")}`);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1800);

  // ── STEP 3 · the address ──────────────────────────────────────────────────
  for (const [sel, val] of [
    ["#address_as_given", "212 Balcones Drive"],
    ["#address_unit_as_given", "Unit 4"],
    ["#city", "Austin"],
    ["#postal_code", "78704"],
  ]) {
    const el = page.locator(sel);
    if ((await el.count()) > 0) await el.fill(val).catch(() => {});
  }
  await page.waitForTimeout(700);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2500);

  requestId = new URL(page.url()).searchParams.get("request");
  note(`draft: ${requestId}`);

  // ── STEP 4 · A REAL DOCUMENT ──────────────────────────────────────────────
  const fileInput = page.locator('input[type="file"]').first();
  if ((await fileInput.count()) > 0) {
    await fileInput.setInputFiles(SAMPLE);
    await page.waitForTimeout(600);
    const attach = page.locator("[data-doc-attach]");
    if ((await attach.count()) > 0) {
      await attach.click();
      await page.waitForTimeout(3000);
    }
    const rows = await page.locator("[data-doc-file]").count();
    note(`documents table rows after attach: ${rows}`);
  } else {
    note("no file input on step 4");
  }
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2500);

  // ── STEP 5 · A FEE, TAKEN AT THE COUNTER ──────────────────────────────────
  // `fee_timing` is a segmented control and `Collect now` is what puts money
  // on the request; the tender fields appear for the METHOD chosen and for no
  // other, so the method has to be set before they can be filled.
  const timing = page.locator('#fee_timing [value="collect_now"], #fee_timing button:has-text("now")').first();
  if ((await timing.count()) > 0) {
    await timing.click().catch(() => {});
    await page.waitForTimeout(800);
  }
  const method = page.locator("#fee_method");
  if ((await method.count()) > 0) {
    await method.selectOption("cash").catch(() => {});
    await page.waitForTimeout(800);
  }
  for (const [sel, val] of [["#fee_receipt_no", "1187"], ["#receipt_no", "1187"]]) {
    const el = page.locator(sel);
    if ((await el.count()) > 0) await el.fill(val).catch(() => {});
  }
  note(`fee step: timing control ${await page.locator("#fee_timing").count()} · method ${await page.locator("#fee_method").count()}`);
  await page.screenshot({ path: join(SHOTS, "p0-step5-fees.png"), fullPage: true });
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2500);

  // ── STEP 6 · THE PRESS ────────────────────────────────────────────────────
  console.log("\n  step 6 · Check & submit");
  await page.screenshot({ path: join(SHOTS, "p0-step6-before.png"), fullPage: true });
  calls.length = 0;
  // ⚠ THE EXACT LABEL. A loose `has-text("Submit")` resolves to the STEPPER's
  // "6 Check & submit" item, clicks a step, makes no API call, and then reads
  // as a pass — law 7's *incapable of failing*, in a reproduce script.
  const submit = page.locator('button:has-text("Submit the request")').first();
  if ((await submit.count()) === 0) {
    found("no `Submit the request` control on step 6 — the walk cannot press anything");
  } else {
    await submit.click();
    const deadline = Date.now() + 40000;
    while (Date.now() < deadline) {
      if (calls.some((c) => /\/submit$/.test(c.url))) break;
      await page.waitForTimeout(700);
    }
    await page.waitForTimeout(2500);
    const after = await page.locator("main").innerText().catch(() => "");
    const screenRefused = /could not submit|Something went wrong/i.test(after);
    console.log(`\n  SCREEN: ${screenRefused ? "● refuses" : "✓ accepts"}`);
    console.log(after.split("\n").slice(0, 22).map((l) => `      ${l}`).join("\n"));
    await page.screenshot({ path: join(SHOTS, "p0-step6-after.png"), fullPage: true });

    console.log(`\n  API calls during the press:`);
    for (const c of calls) {
      console.log(`      ${c.status}  ${c.method} ${c.url}`);
      if (c.body) console.log(`             ${c.body.replace(/\n/g, " ").slice(0, 700)}`);
    }

    // ── THE OTHER HALF: DID THE STATE MOVE ANYWAY? ─────────────────────────
    const server = await page.evaluate(async ([tenant, id]) => {
      if (!id) return { id: null };
      const r = await fetch(`/api/${tenant}/service-requests/${id}`, { credentials: "include" });
      const j = await r.json();
      const d = j.data ?? j;
      return {
        id,
        http: r.status,
        state: d.header?.state ?? null,
        submitted_at: d.header?.submitted_at ?? null,
        services: (d.location_and_services?.services ?? []).length,
        documents: (d.documents?.documents ?? []).length,
        fee_lines: (d.fees?.lines ?? []).length,
      };
    }, [TENANT, requestId]);
    console.log(`\n  THE SERVER, read back after the press: ${JSON.stringify(server)}`);

    const submitCall = calls.find((c) => /\/submit$/.test(c.url));
    if (screenRefused && server.state && server.state !== "draft") {
      found(
        `REPRODUCED — the screen says nothing was saved and the request is '${server.state}'` +
          (submitCall ? ` (POST …/submit answered ${submitCall.status})` : ""),
      );
    } else if (!screenRefused) {
      note("the submit went through cleanly on this draft — not reproduced here");
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // THE SECOND PATH TO THE SAME SENTENCE, AND IT IS IN THE SCREEN
  //
  // `onCommit` does THREE things inside ONE `try`: submit, re-read, and show.
  // The submit is a WRITE and the re-read is a READ, and a failure of the
  // second is reported with the words that belong to the first — *"Nothing was
  // saved — try again."* over a request that is already `submitted`.
  //
  // ⚠ **THIS IS NOT A SYNTHETIC CASE.** The server answers the re-read with
  // the WHOLE detail payload — every tab, every fee line, every document — so
  // it has an order of magnitude more ways to fail than the submit it follows,
  // and it runs after the state has already moved. Failing the re-read is how
  // that is proved without having to find which of them fired on the PO's
  // tenant.
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n  the re-read, failed on purpose · does the screen still say 'nothing was saved'?");
  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await page.fill("#applicant_name", "Refetch, Fails");
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1800);
  await page.selectOption("#account_type_code", "residential").catch(() => {});
  await page.waitForTimeout(700);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1800);
  await page.fill("#address_as_given", "9 Refetch Lane").catch(() => {});
  await page.waitForTimeout(600);
  for (let step = 0; step < 3; step += 1) {
    await page.click('button:has-text("Continue")');
    await page.waitForTimeout(2200);
  }
  const secondId = new URL(page.url()).searchParams.get("request");
  note(`draft: ${secondId}`);

  // Fail ONLY the detail GET, and only after the submit has been pressed.
  let submitSeen = false;
  // ⚠ **THE GLOB MATTERS.** `*` does not cross a `/` in Playwright, so a
  // pattern ending `service-requests/*` never matches `…/{id}/submit` — the
  // first draft of this block therefore never set `submitSeen`, let the
  // re-read through, and reported *"this half is fixed"* over a check that had
  // done nothing. Law 7: ask what would make it pass WRONGLY.
  await page.route(`**/service-requests/**`, async (route) => {
    const req = route.request();
    if (req.method() === "POST" && req.url().endsWith("/submit")) {
      submitSeen = true;
      await route.continue();
      return;
    }
    if (req.method() === "GET" && submitSeen) {
      console.log(`      (failing the re-read: ${req.url().replace(BASE, "")})`);
      await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
      return;
    }
    await route.continue();
  });

  const submit2 = page.locator('button:has-text("Submit the request")').first();
  if ((await submit2.count()) === 0) {
    note("no Submit control on the second draft — this half could not be walked");
  } else {
    await submit2.click();
    await page.waitForTimeout(6000);
    const text = await page.locator("main").innerText().catch(() => "");
    const lies = /Nothing was saved|could not submit|Something went wrong/i.test(text);
    const shown = text
      .split("\n")
      .filter((l) => /could not submit|Nothing was saved|Something went wrong/i.test(l));
    await page.screenshot({ path: join(SHOTS, "p0-refetch-failed.png"), fullPage: true });
    // ⚠ **READ THE STATE WITH THE INTERCEPT OFF.** The first draft asked the
    // server through the SAME page, whose route handler was still failing every
    // GET, so it answered "(unreadable)" and the check could never conclude.
    await page.unroute(`**/service-requests/**`);
    const state = await page.evaluate(async ([tenant, id]) => {
      const r = await fetch(`/api/${tenant}/service-requests/${id}`, { credentials: "include" });
      const j = await r.json().catch(() => ({}));
      return (j.data ?? j).header?.state ?? "(unreadable)";
    }, [TENANT, secondId]);
    console.log(`      the screen says: ${shown.map((l) => JSON.stringify(l.trim())).join(" + ") || "(no refusal line)"}`);
    console.log(`      the server holds state: ${state}`);
    if (lies && state === "submitted") {
      found(`REPRODUCED — the screen says nothing was saved and the request is '${state}'`);
    } else if (!lies) {
      note("the screen did not claim nothing was saved — this half is fixed");
    }
  }
} catch (error) {
  console.log(`\n  ⚠ the walk stopped: ${error.message}`);
  await page.screenshot({ path: join(SHOTS, "p0-ERROR.png"), fullPage: true }).catch(() => {});
  for (const c of calls.slice(-12)) console.log(`      ${c.status}  ${c.method} ${c.url}`);
} finally {
  console.log(`\n  screenshots: ${SHOTS}`);
  await browser.close();
}
