// ── Trace ──────────────────────────────────────────────
// Task:    PO, 2026-09-29: *"on step 1 - you provide 5 types of one time bill
//          options you have to check all 5 cases"*. This VERIFIES; it changes
//          no product code. Every difference it finds is a defect row.
// Screens: S82 · the One-time bill tab (`OneTimeBillTab.tsx`, `/billing/
//          one-time`) AND the three-step redraw (`OneTimeWizardShell.tsx`,
//          `/billing/one-time/:step`). There are TWO, which is finding #1.
// Kinds:   `oneTimeWizardContract.ts:158` declares six — interim · first ·
//          final · backbill · penalty · fee.
// Rules:   hard rule 2 (money 4dp stored, 2dp shown) · hard rule 7 (audit) ·
//          B14 rule 31 (no database id on screen) · hard-won laws 1, 2, 6.
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT THE VITEST SUITE CANNOT:
//   1. WHICH SCREEN THE CLERK LANDS ON from the Billing tab strip, and how
//      many kinds THAT screen offers. The suite mounts each component
//      directly and never follows the tab.
//   2. WHETHER A STEP HAS A CONTROL THAT WALKS TO THE NEXT ONE. jsdom renders
//      a missing commit bar and a present one identically to a query that
//      does not ask for it.
//   3. WHAT IS WRITTEN. The suite mocks the API; this presses the real button
//      against a real PostgreSQL and the caller reads the rows back in SQL.
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8902";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/otb";
const ACCOUNT_NO = process.env.ACCOUNT_NO ?? "AC-2026-00032";
mkdirSync(OUT, { recursive: true });

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

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (...p) => console.log(...p);
const record = [];
function note(label, detail) {
  say(`·  ${label}${detail === undefined ? "" : ` — ${detail}`}`);
  record.push({ label, detail });
}

// ⚠ `fullPage: true` DOES NOT CAPTURE THIS APP — `.app-shell` is
// `height:100vh; overflow:hidden` and `.view` scrolls inside it, so fullPage
// silently returns the fold. Measure `.view`, grow the viewport, print the
// dimensions beside the name.
async function shot(name) {
  const need = await page
    .evaluate(() => {
      const view = document.querySelector(".view");
      return view === null ? document.body.scrollHeight : view.scrollHeight;
    })
    .catch(() => 1000);
  const height = Math.min(Math.max(Math.ceil(need) + 120, 900), 6000);
  await page.setViewportSize({ width: 1440, height });
  await page.waitForTimeout(350);
  const file = join(OUT, `${name}.png`);
  await page.screenshot({ path: file });
  say(`   shot ${name}.png  1440x${height}`);
  await page.setViewportSize({ width: 1440, height: 1000 });
  return file;
}

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ── 0 · WHERE DOES THE BILLING TAB STRIP SEND A CLERK? ──────────────────────
say("\n══ 0 · the door: Billing → One-time bill");
await page.goto(`${BASE}/${TENANT}/billing`, { waitUntil: "networkidle" });
const tab = page.locator('[role="tab"], button', { hasText: /^One-time bill$/ }).first();
if ((await tab.count()) > 0) {
  await tab.click();
  await page.waitForTimeout(1200);
}
note("the One-time bill tab lands on", page.url().replace(BASE, ""));
await shot("00-door");

async function kindOptions(selectId) {
  return page.$$eval(`#${selectId} option`, (nodes) =>
    nodes.map((n) => ({ value: n.value, label: n.textContent.trim(), disabled: n.disabled })),
  );
}

// ── 1 · THE OLD TAB'S STEP 1 ────────────────────────────────────────────────
say("\n══ 1 · the OLD tab (/billing/one-time) step 1");
await page.goto(`${BASE}/${TENANT}/billing/one-time`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
const oldKinds = await kindOptions("one_time_kind").catch(() => []);
note("old tab kind options", JSON.stringify(oldKinds));
await shot("01-oldtab-step1");

// ── 2 · THE WIZARD'S STEP 1 ─────────────────────────────────────────────────
say("\n══ 2 · the WIZARD (/billing/one-time/who) step 1");
await page.goto(`${BASE}/${TENANT}/billing/one-time/who`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
const wizKinds = await kindOptions("one_time_who_kind").catch(() => []);
note("wizard kind options", JSON.stringify(wizKinds));
note("wizard kind options rendered", String(wizKinds.length));
note("wizard kind options DISABLED", JSON.stringify(wizKinds.filter((o) => o.disabled)));
await shot("02-wizard-step1");

// ── 3 · SIX WALKS THROUGH THE WIZARD ────────────────────────────────────────
// Each kind gets the window its own engine can price. `first` needs a window
// that contains the move-in; `fee` derives its window from the bill date.
const WALKS = [
  { kind: "interim", from: "2026-09-01", to: "2026-09-20" },
  { kind: "first", from: "2026-07-01", to: "2026-07-20" },
  { kind: "final", from: "2026-09-01", to: "2026-09-20" },
  { kind: "backbill", from: "2026-09-01", to: "2026-09-20" },
  { kind: "penalty", from: "2026-09-01", to: "2026-09-20" },
  { kind: "fee", from: "2026-09-29", to: "2026-09-29" },
];

async function pickAccount(selectId, queryId) {
  await page.fill(`#${queryId}`, ACCOUNT_NO);
  await page.waitForTimeout(1400);
  const opts = await page.$$eval(`#${selectId} option`, (n) =>
    n.map((o) => ({ value: o.value, label: o.textContent.trim() })),
  );
  const hit = opts.find((o) => o.value !== "" && o.label.includes(ACCOUNT_NO)) ?? opts.find((o) => o.value !== "");
  if (hit === undefined) throw new Error(`no account option matched ${ACCOUNT_NO}`);
  await page.selectOption(`#${selectId}`, hit.value);
  return hit;
}

const results = [];
for (const walk of (process.env.SKIP_WIZARD === "1" ? [] : WALKS)) {
  say(`\n══ 3.${walk.kind} · the wizard, end to end`);
  const row = { kind: walk.kind, step2: false, step3: false, createPressed: false, refusals: [] };

  await page.goto(`${BASE}/${TENANT}/billing/one-time/who`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const account = await pickAccount("one_time_who_account", "one_time_who_account_query");
  note(`${walk.kind} · account picked`, account.label);
  await page.selectOption("#one_time_who_kind", walk.kind).catch((e) => {
    row.refusals.push(`step 1 would not accept the kind: ${e.message.slice(0, 120)}`);
  });
  await page.fill("#one_time_who_billed_from", walk.from);
  await page.fill("#one_time_who_billed_to", walk.to);
  await page.fill("#one_time_who_bill_date", "2026-09-29");
  await page.fill("#one_time_who_due_days", "21");
  await page.waitForTimeout(600);
  await shot(`03-${walk.kind}-step1`);

  // What does step 1 then REQUIRE? Read every required control on the screen.
  const required = await page.$$eval("[required]", (n) =>
    n.map((e) => e.id || e.getAttribute("name") || e.tagName.toLowerCase()),
  );
  note(`${walk.kind} · step 1 required fields`, required.join(", "));

  const cont = page.locator('[data-testid="one-time-who-continue"] button, [data-testid="one-time-who-continue"]').first();
  const contText = (await cont.count()) > 0 ? (await cont.innerText()).trim() : "(no control)";
  note(`${walk.kind} · step 1 commit`, contText);
  if ((await cont.count()) > 0) {
    await cont.click().catch(() => {});
    await page.waitForTimeout(1800);
  }
  row.step2 = page.url().includes("/one-time/what");
  note(`${walk.kind} · after Continue the address is`, page.url().replace(BASE, ""));
  if (row.step2) {
    await page.waitForTimeout(1200);
    await shot(`03-${walk.kind}-step2`);
    const body2 = await page.locator("main.view, body").first().innerText();
    row.step2Text = body2;
    // Does step 2 carry ANY control that walks on?
    const buttons2 = await page.$$eval("button, a[href]", (n) =>
      n.map((e) => e.textContent.trim()).filter((t) => t.length > 0 && t.length < 40),
    );
    row.step2Buttons = buttons2;
    note(`${walk.kind} · step 2 controls`, JSON.stringify(buttons2.slice(0, 24)));
    // B14 rule 31 — any uuid rendered as a VALUE?
    const uuids = (body2.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi) ?? []);
    row.step2Uuids = uuids;
    note(`${walk.kind} · step 2 uuids on screen`, uuids.length === 0 ? "none" : JSON.stringify(uuids));
  }

  // Step 3 — by the address, because the contract says every step is one.
  const query = page.url().split("?")[1] ?? "";
  await page.goto(`${BASE}/${TENANT}/billing/one-time/confirm${query === "" ? "" : `?${query}`}`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2200);
  row.step3 = page.url().includes("/one-time/confirm");
  note(`${walk.kind} · step 3 address held?`, `${row.step3} (${page.url().replace(BASE, "")})`);
  if (row.step3) {
    await shot(`03-${walk.kind}-step3`);
    const body3 = await page.locator("main.view, body").first().innerText();
    row.step3Text = body3;
    const buttons3 = await page.$$eval("button", (n) =>
      n.map((e) => ({ text: e.textContent.trim(), disabled: e.disabled })).filter((b) => b.text.length > 0),
    );
    row.step3Buttons = buttons3;
    note(`${walk.kind} · step 3 buttons`, JSON.stringify(buttons3.slice(0, 24)));
    const uuids3 = (body3.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi) ?? []);
    row.step3Uuids = uuids3;
    note(`${walk.kind} · step 3 uuids on screen`, uuids3.length === 0 ? "none" : JSON.stringify(uuids3));
    const create = buttons3.find((b) => /create/i.test(b.text));
    if (create !== undefined) {
      await page.locator("button", { hasText: new RegExp(create.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).first().click();
      row.createPressed = true;
      await page.waitForTimeout(3000);
      await shot(`03-${walk.kind}-step3-after-create`);
      row.afterCreate = await page.locator("main.view, body").first().innerText();
    } else {
      note(`${walk.kind} · NO Create control on step 3`, "the wizard cannot write");
    }
  }
  results.push(row);
}

// ── 4 · THE OLD TAB, WHICH IS THE ONE THAT CAN WRITE ────────────────────────
say("\n══ 4 · the OLD tab, all the kinds it offers, with Create pressed");
const oldResults = [];
for (const walk of WALKS) {
  if (!oldKinds.some((o) => o.value === walk.kind)) {
    note(`old tab · ${walk.kind}`, "NOT OFFERED on this screen");
    oldResults.push({ kind: walk.kind, offered: false });
    continue;
  }
  say(`\n── old tab · ${walk.kind}`);
  const row = { kind: walk.kind, offered: true, refusals: [] };
  await page.goto(`${BASE}/${TENANT}/billing/one-time`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await pickAccount("one_time_account_id", "one_time_account_query");
  await page.selectOption("#one_time_kind", walk.kind);
  await page.fill("#one_time_bill_date", "2026-09-29");
  await page.waitForTimeout(400);
  if (await page.locator("#one_time_reason_code").count()) {
    await page.fill("#one_time_reason_code", walk.kind === "penalty" ? "THEFT" : "MISSED");
  }
  for (const [id, value] of [
    ["one_time_period_start", walk.from],
    ["one_time_period_end", walk.to],
    ["one_time_sub_period_start_0", walk.from],
    ["one_time_sub_period_end_0", walk.to],
  ]) {
    if (await page.locator(`#${id}`).count()) await page.fill(`#${id}`, value);
  }
  // the sub-period fields are labelled, not id'd, on some kinds — fall back
  const dates = await page.$$eval('input[type="date"]', (n) => n.map((e) => e.id));
  for (const id of dates) {
    if (/sub|period/i.test(id) && (await page.inputValue(`#${id}`)) === "") {
      await page.fill(`#${id}`, /end/i.test(id) ? walk.to : walk.from);
    }
  }
  await shot(`04-oldtab-${walk.kind}-step1`);
  const next = page.locator("button", { hasText: /^(Continue|Next)/ }).first();
  if (await next.count()) {
    await next.click();
    await page.waitForTimeout(2600);
  }
  const t2 = await page.locator("main.view, body").first().innerText();
  row.step2 = /See what|Step 2|would owe|Window|Plan/i.test(t2) && !/Step 1 of/i.test(t2);
  row.step2Text = t2;
  await shot(`04-oldtab-${walk.kind}-step2`);
  const alert = await page.locator('[role="alert"]').allInnerTexts();
  if (alert.length > 0) row.refusals.push(...alert);
  const next2 = page.locator("button", { hasText: /^(Continue|Next)/ }).first();
  if (await next2.count()) {
    await next2.click();
    await page.waitForTimeout(1600);
  }
  const t3 = await page.locator("main.view, body").first().innerText();
  row.step3Text = t3;
  await shot(`04-oldtab-${walk.kind}-step3`);
  const createBtn = page.locator("button", { hasText: /Create/i }).first();
  if (await createBtn.count()) {
    row.createLabel = (await createBtn.innerText()).trim();
    await createBtn.click();
    row.createPressed = true;
    await page.waitForTimeout(3500);
    row.afterCreate = await page.locator("main.view, body").first().innerText();
    const alerts2 = await page.locator('[role="alert"]').allInnerTexts();
    if (alerts2.length > 0) row.refusals.push(...alerts2);
    await shot(`04-oldtab-${walk.kind}-after-create`);
  } else {
    note(`old tab · ${walk.kind}`, "no Create control reached");
  }
  oldResults.push(row);
}

writeFileSync(join(OUT, "walk.json"), JSON.stringify({ oldKinds, wizKinds, results, oldResults, record }, null, 1));
say(`\nwrote ${join(OUT, "walk.json")}`);
await browser.close();
