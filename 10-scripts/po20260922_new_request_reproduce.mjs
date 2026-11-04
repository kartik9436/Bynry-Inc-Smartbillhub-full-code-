// ── Trace ──────────────────────────────────────────────
// Change:  PO report 2026-09-22 — eleven findings on the `New request` wizard
//          (`REQ-03`) and the Requests register (`ACC-01`), plus the
//          Connection-date ruling and the Fees-step change.
// Rules:   `22-product-maintenance-process.md` step 0 (REPRODUCE IT — before
//          you read a line of code) · CLAUDE.md hard-won law 6 (diff the
//          running app; no gate reads rendered output)
// Screens: `ACC-01` (Accounts → Requests tab) · `REQ-03.1`–`REQ-03.5`
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS IS THE *BEFORE* WALK.** It asserts the DEFECTS ARE PRESENT, so it
// is RED-BY-DESIGN once they are fixed. That is deliberate and it is the only
// honest way to prove a maintenance fix: the same script, run after, must flip
// every one of these. `po20260922_new_request_walkthrough.mjs` is the *after*.
//
// ⚠ **IT ATTACHES A REAL FILE.** Item 9 — *the documents table shows no file* —
// has two completely different causes (the attach never happened, or it
// happened and the table does not show it) and only a real file tells them
// apart. A fix proved with no file proves nothing.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/<your db> \
//      JOBS_EAGER=false python manage.py runserver 127.0.0.1:8288 --noreload)
//   (cd 07-frontend && npm run build && PORT=8289 \
//      API_PROXY_TARGET=http://127.0.0.1:8288 node server.mjs)
//   BASE=http://127.0.0.1:8289 node 10-scripts/po20260922_new_request_reproduce.mjs
//
// ⛔ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
// looks exactly like a broken screen. `10-scripts/proof-db.sh clone <label>`.
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8289";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const WIDTH = Number(process.env.WIDTH ?? 1440);
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots";

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

const findings = [];
function found(id, message) {
  findings.push({ id, message });
  console.log(`    ● ${id}  ${message}`);
}
function note(message) {
  console.log(`    · ${message}`);
}

// Every wait carries a DEADLINE and checks the producer is still alive.
async function alive() {
  const res = await fetch(`${BASE}/brazosbend/signin`).catch(() => null);
  if (res === null) throw new Error("the SPA server stopped answering — nothing below is evidence");
}

mkdirSync(SHOTS, { recursive: true });
const SAMPLE = join(SHOTS, "proof-of-identity.pdf");
// A REAL, VALID one-page PDF — `BR-SHL-031`'s allowlist takes PDF, and a file
// whose bytes are not a PDF would be refused for the wrong reason.
writeFileSync(
  SAMPLE,
  "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n" +
    "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n" +
    "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n" +
    "trailer<</Root 1 0 R>>\n%%EOF\n",
);

const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: WIDTH, height: 1200 } });
const page = await context.newPage();
page.setDefaultTimeout(20000);

try {
  await alive();

  // ── SIGN IN ───────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  note(`signed in as ${EMAIL}`);

  // ── ITEM 1 · THE REGISTER'S `+ New request` ───────────────────────────────
  console.log("\n  ACC-01 · the Requests register");
  await page.goto(`${BASE}/${TENANT}/accounts?tab=requests`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  const newBtn = page.locator('button:has-text("New request")').first();
  const count = await newBtn.count();
  if (count === 0) {
    found("item 1", "no `+ New request` control found at all on the Requests tab");
  } else {
    const variant = await newBtn.getAttribute("data-variant");
    const cls = (await newBtn.getAttribute("class")) ?? "";
    note(`label: ${JSON.stringify((await newBtn.textContent())?.trim())}`);
    if (variant !== "primary") {
      found("item 1", `\`+ New request\` renders data-variant="${variant}" — not a button tier`);
    }
    note(`class: ${cls.slice(0, 120)}`);
  }
  await page.screenshot({ path: join(SHOTS, "before-01-register.png") });

  // ── THE WIZARD ────────────────────────────────────────────────────────────
  console.log("\n  REQ-03 · the New request wizard");
  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);

  // Step 1 — fill the minimum so we can walk on.
  await page.fill("#applicant_name", "Repro, Alex");
  await page.screenshot({ path: join(SHOTS, "before-step1.png") });
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1500);

  // ── ITEM 2 · SUB-CATEGORY OFFERS EVERYTHING ───────────────────────────────
  console.log("\n  step 2 · Connection");
  const catOptions = await page.locator("#account_type_code option").allTextContents();
  note(`category offers ${catOptions.length - 1}: ${catOptions.slice(1).join(" · ")}`);

  const perCategory = {};
  for (const value of ["residential", "commercial", "industrial"]) {
    await page.selectOption("#account_type_code", value);
    await page.waitForTimeout(700);
    const subs = await page.locator("#account_subtype_id option").allTextContents();
    perCategory[value] = subs.slice(1); // drop the placeholder
    note(`${value} → sub-category offers ${perCategory[value].length}: ${perCategory[value].join(" · ")}`);
  }
  const sizes = new Set(Object.values(perCategory).map((v) => v.length));
  if (sizes.size === 1) {
    found("item 2", `every category offers the SAME ${[...sizes][0]} sub-categories — the list is not filtered`);
  }

  // clearing on change
  await page.selectOption("#account_type_code", "commercial");
  await page.waitForTimeout(500);
  const allSubs = await page.locator("#account_subtype_id option").all();
  if (allSubs.length > 1) {
    const pick = await allSubs[1].getAttribute("value");
    await page.selectOption("#account_subtype_id", pick);
    await page.waitForTimeout(400);
    await page.selectOption("#account_type_code", "industrial");
    await page.waitForTimeout(700);
    const held = await page.locator("#account_subtype_id").inputValue();
    if (held === pick) {
      found("item 2", "changing the category KEEPS an incompatible sub-category");
    }
  }

  // ── ITEM 3 · GOVERNMENT ───────────────────────────────────────────────────
  const legacyChips = page.locator("[data-legacy-category]");
  const legacyCount = await legacyChips.count();
  if (legacyCount > 0) {
    const labels = await legacyChips.allTextContents();
    found("item 3", `the new-request picker still shows legacy ${labels.join(", ")} as a chip`);
    const note1 = await page.locator('[data-tracks="BR-CUS-094"]').textContent().catch(() => null);
    if (note1) note(`and its sentence: ${JSON.stringify(note1.trim())} (${note1.trim().split(/\s+/).length} words)`);
  }

  // ── ITEM 4 · CONNECTION DATE + PER-SERVICE STARTS ─────────────────────────
  const connDate = await page.locator("#requested_start").inputValue().catch(() => "(absent)");
  if (connDate === "") {
    found("item 4", "`Connection date` opens EMPTY — no default");
  }
  await page.screenshot({ path: join(SHOTS, "before-step2.png"), fullPage: true });

  // ── STEP 3 · addresses, to reach step 4 ───────────────────────────────────
  await page.selectOption("#account_type_code", "residential");
  await page.waitForTimeout(500);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1500);
  console.log("\n  step 3 · Addresses");
  for (const [sel, val] of [
    ["#address_as_given", "212 Balcones Drive"],
    ["#city", "Austin"],
    ["#postal_code", "78704"],
  ]) {
    const el = page.locator(sel);
    if ((await el.count()) > 0) await el.fill(val).catch(() => {});
  }
  await page.waitForTimeout(600);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2500);

  // ── STEP 4 · DOCUMENTS ────────────────────────────────────────────────────
  console.log("\n  step 4 · Documents");
  const onDocs = await page.locator('[data-step-content="documents"]').count();
  if (onDocs === 0) {
    found("blocked", "could not reach step 4 — the walk stops here");
  } else {
    // item 5 — the virus-scan line
    const scanLine = await page.locator("[data-doc-note]").textContent().catch(() => null);
    if (scanLine) {
      found("item 5", `the scan line is on screen: ${JSON.stringify(scanLine.trim())}`);
    }
    // item 10 — the reviewer's chips
    const chips = page.locator('[data-doc-filter], [data-doc-chips] button');
    const chipCount = await chips.count();
    const chipLabels = chipCount ? await chips.allTextContents() : [];
    if (chipCount > 0) {
      found("item 10", `capture shows the reviewer's filters: ${chipLabels.join(" · ")}`);
    }
    await page.screenshot({ path: join(SHOTS, "before-step4-empty.png"), fullPage: true });

    // ── ITEM 9 · ATTACH A REAL FILE AND SEE WHAT THE TABLE DOES ────────────
    const fileInput = page.locator('input[type="file"]').first();
    if ((await fileInput.count()) === 0) {
      found("item 7", "no file input on the step at all");
    } else {
      await fileInput.setInputFiles(SAMPLE);
      await page.waitForTimeout(600);
      const chosen = await page.evaluate(() => {
        const i = document.querySelector('input[type="file"]');
        return i && i.files && i.files.length ? i.files[0].name : "(none)";
      });
      note(`picked: ${chosen}`);
      // item 7 — is it a drop control?
      const dropZone = await page.locator("[data-file-drop]").count();
      if (dropZone === 0) {
        found("item 7", "the attach control is a bare file input — nothing accepts a dropped file");
      }

      const before = await page.locator("[data-doc-file]").count();
      note(`documents table rows BEFORE attach: ${before}`);

      const attach = page.locator("[data-doc-attach]");
      await attach.click();
      // deadline + producer liveness
      const deadline = Date.now() + 25000;
      let after = before;
      while (Date.now() < deadline) {
        await alive();
        after = await page.locator("[data-doc-file]").count();
        if (after !== before) break;
        await page.waitForTimeout(700);
      }
      note(`documents table rows AFTER attach: ${after}`);

      const err = await page.locator("[data-doc-error]").textContent().catch(() => null);
      if (err) note(`the form reported: ${JSON.stringify(err.trim())}`);

      if (after === before) {
        found("item 9", "the attach produced NO new row in the documents table");
      } else {
        const cells = await page.locator("[data-doc-file]").allTextContents();
        note(`FILE column now reads: ${cells.map((c) => JSON.stringify(c.trim())).join(" | ")}`);
        const states = await page.locator("[data-doc-state]").allTextContents();
        note(`STATE column now reads: ${states.map((c) => JSON.stringify(c.trim())).join(" | ")}`);
        if (cells.every((c) => c.trim() === "—")) {
          found("item 9", "a row appeared but its FILE cell is a dash — the file did not land");
        }
      }
      // Was it really stored? Ask the server, not the screen.
      const apiRows = await page.evaluate(async (tenant) => {
        const url = new URL(window.location.href);
        const id = url.searchParams.get("request");
        if (!id) return { id: null };
        const r = await fetch(`/api/${tenant}/service-requests/${id}`, { credentials: "include" });
        const j = await r.json();
        const docs = (j.data ?? j).documents?.documents ?? [];
        return {
          id,
          rows: docs.map((d) => ({
            type: d.doc_type,
            name: d.name,
            file_present: d.file_present,
            size: d.size_bytes,
            state: d.verification_state,
          })),
        };
      }, TENANT);
      note(`the SERVER holds: ${JSON.stringify(apiRows)}`);
    }
    await page.screenshot({ path: join(SHOTS, "before-step4-after-attach.png"), fullPage: true });

    // ── ITEMS 6 + 8 · the section's shape ──────────────────────────────────
    const geom = await page.evaluate(() => {
      const panel = document.querySelector('[data-step-content="documents"]');
      if (!panel) return null;
      const h3 = panel.querySelector("h3");
      const table = panel.querySelector("table");
      const h4 = panel.querySelector("h4");
      const r = (el) => (el ? el.getBoundingClientRect() : null);
      const a = r(h3), b = r(table), c = r(h4);
      return {
        headingToTable: a && b ? Math.round(b.top - a.bottom) : null,
        tableToForm: b && c ? Math.round(c.top - b.bottom) : null,
      };
    });
    note(`spacing — heading→table ${geom?.headingToTable}px · table→form ${geom?.tableToForm}px`);
    if (geom && geom.headingToTable !== null && geom.headingToTable < 12) {
      found("item 6", `only ${geom.headingToTable}px between the heading and the documents table`);
    }

    // ── STEP 5 · FEES ──────────────────────────────────────────────────────
    await page.click('button:has-text("Continue")');
    await page.waitForTimeout(2000);
    console.log("\n  step 5 · Fees");
    const body = (await page.locator("main").innerText().catch(() => "")) || "";
    for (const sentence of [
      "No fee has been raised on this request yet.",
      "No invoice and no account yet.",
    ]) {
      const n = body.split(sentence).length - 1;
      if (n > 0) found("item 11", `"${sentence}" appears ${n}×`);
    }
    const timing = page.locator("#fee_timing");
    if ((await timing.count()) > 0) {
      const opts = await page.locator("#fee_timing option, #fee_timing [role=radio], #fee_timing button").allTextContents();
      note(`Fee timing offers: ${opts.join(" · ")}`);
      if (opts.some((o) => /later/i.test(o))) {
        found("item 11", "`Collect later` is still offered");
      }
    } else {
      const seg = await page.locator('[id^="fee_timing"]').allTextContents();
      note(`fee timing control: ${seg.join(" · ")}`);
    }
    const codePicker = await page.locator("#fee_charge_code").count();
    if (codePicker === 0) {
      found("item 11", "there is no charge-code dropdown on the Fees step");
    }
    const waive = await page.locator('button:has-text("Waive")').count();
    if (waive === 0) {
      found("item 11", "there is no Waive control on the Fees step");
    }
    await page.screenshot({ path: join(SHOTS, "before-step5-fees.png"), fullPage: true });
  }
} catch (error) {
  console.log(`\n  ⚠ the walk stopped: ${error.message}`);
  await page.screenshot({ path: join(SHOTS, "before-ERROR.png"), fullPage: true }).catch(() => {});
} finally {
  console.log(`\n  ── ${findings.length} finding(s) reproduced ──`);
  for (const f of findings) console.log(`     ${f.id}  ${f.message}`);
  console.log(`  screenshots: ${SHOTS}`);
  await browser.close();
}
