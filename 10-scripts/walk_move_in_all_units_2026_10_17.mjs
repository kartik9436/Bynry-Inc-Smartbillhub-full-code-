// Walk of DEF-CUS-10190 — Move-in searches ALL units (PO 2026-10-17, decision
// log "MOVE-IN SEARCHES ALL UNITS, NOT ONLY VACANT ONES" + "Same day").
// Env: WEB (SPA origin), TENANT, OUT, EMAIL, PASSWORD, STEP (which scenario).
// Each STEP drives the real screens and prints what it saw; screenshots land
// in OUT. Data the scenario needs is set up on the private copy beforehand.
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB || "http://127.0.0.1:8108";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "05-prototype/walk-move-in-all-units-2026-10-17";
const STEP = process.env.STEP || "explore";
mkdirSync(OUT, { recursive: true });

const exe = process.env.CHROME || "/opt/pw-browsers/chromium";
const browser = await chromium.launch({
  executablePath: existsSync(exe) ? exe : undefined,
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));
page.on("response", async (r) => {
  if (r.url().includes("/api/") && r.status() >= 400 && !r.url().includes("page-policy")) {
    let body = "";
    try {
      body = (await r.text()).slice(0, 300);
    } catch {
      body = "";
    }
    console.log(`  HTTP ${r.status()} ${r.request().method()} ${r.url().replace(/^.*\/api\//, "/api/")} ${body}`);
  }
});

const shot = async (name, full = true) => {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
  console.log(`  shot ${name}.png`);
};
const api = async (method, path, body) =>
  page.evaluate(
    async ({ method, path, body, T }) => {
      const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
      const r = await fetch(`/api/${T}${path}`, {
        method,
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: body ? JSON.stringify(body) : undefined,
      });
      let data = null;
      try {
        data = await r.json();
      } catch {
        data = null;
      }
      return { status: r.status, data };
    },
    { method, path, body, T },
  );

async function signIn() {
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", process.env.EMAIL || "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.PASSWORD || "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(1500);
}

async function openMoveIn() {
  await page.goto(`${WEB}/${T}/move-ins/new`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-move-in-unit-search]", { timeout: 60000 });
}

async function search(term) {
  const box = page.locator("#mvi_unit_search");
  await box.fill("");
  await box.fill(term);
  await page.waitForTimeout(1200);
  await page.waitForLoadState("networkidle");
  return page.evaluate(() =>
    [...document.querySelectorAll("[data-move-in-unit-row]")].map((tr) => ({
      state: tr.getAttribute("data-move-in-unit-row"),
      selectable: tr.getAttribute("data-selectable"),
      text: tr.innerText.replace(/\s+/g, " ").trim(),
    })),
  );
}

async function useUnit(unitNo) {
  await page.click(`[data-move-in-unit-use="${unitNo}"]`);
  await page.waitForTimeout(1500);
  await page.waitForLoadState("networkidle");
}

async function account(id) {
  const r = await api("GET", `/accounts/${id}`);
  const a = r.data || {};
  return {
    account_no: a.account_no,
    status: a.status,
    opened_at: a.opened_at,
    closed_at: a.closed_at,
    balance: a.balance,
    deposit: a.deposit_on_file,
    unit_id: a.unit_id,
  };
}

const steps = {};

steps.explore = async () => {
  await openMoveIn();
  const rows = await search("");
  console.log(`  first page: ${rows.length} rows; states ${rows.map((r) => r.state).join(",")}`);
  await shot("explore-step1");
};

const MOVE_IN_DAY = process.env.MOVE_IN_DAY || "10/18/2026";

async function setMoveInDate(value = MOVE_IN_DAY) {
  const box = page.locator("#opened_at");
  await box.click();
  await box.fill(value);
  await box.press("Tab");
  await page.waitForTimeout(800);
}

async function clickButton(name) {
  await page.getByRole("button", { name, exact: true }).first().click();
  await page.waitForTimeout(1500);
  await page.waitForLoadState("networkidle");
}

async function stepTitle() {
  return page.evaluate(
    () => document.querySelector('[data-wizard-step][data-state="active"]')?.textContent?.trim() ?? "",
  );
}

async function bodyText() {
  return page.evaluate(() => document.querySelector("main")?.innerText?.replace(/\s+/g, " ") ?? "");
}

/** The move-in → move-out handover, up to the move-out wizard's step 1. */
async function handover(term, unitNo, prefix) {
  await openMoveIn();
  const rows = await search(term);
  console.log(`  search "${term}": ${rows.map((r) => `${r.state}/${r.selectable} ${r.text.slice(0, 90)}`).join(" | ")}`);
  await shot(`${prefix}-1-search`);
  await useUnit(unitNo);
  const warn = await page.evaluate(() => document.querySelector("[data-move-in-unit-occupied]")?.innerText ?? "");
  console.log(`  warning: ${warn.replace(/\s+/g, " ")}`);
  await setMoveInDate();
  await shot(`${prefix}-2-warning`);
  await page.click("[data-move-in-start-move-out]");
  await page.waitForURL((u) => /move-outs\/new|close-out/.test(u.pathname), { timeout: 60000 });
  await page.waitForTimeout(2500);
  await page.waitForLoadState("networkidle");
  console.log(`  landed: ${page.url()}`);
  await shot(`${prefix}-3-settle-opened`);
}

steps.w2a = async () => {
  await handover(process.env.Q || "Miller", process.env.UNIT || "SCW-U-201", process.env.PREFIX || "w2");
  console.log(`  step: ${await stepTitle()}`);
  console.log(`  body: ${(await bodyText()).slice(0, 1500)}`);
};

async function moveOutParkFor(accountNo) {
  const r = await api("GET", "/wizard-parks?flow=move_out");
  const rows = (r.data && (r.data.results || r.data)) || [];
  return rows.find((row) => (row.subject_label || "").includes(accountNo)) || null;
}

/** W13 — the unit while its move-out is unfinished: shown, blocked, reason. */
steps.blocked = async () => {
  await openMoveIn();
  const rows = await search(process.env.Q || "Miller");
  console.log(`  rows: ${rows.map((r) => `${r.state}/${r.selectable} ${r.text.slice(0, 140)}`).join(" | ")}`);
  await shot(`${process.env.PREFIX || "w13"}-blocked`, false);
};

/** Walk the move-out wizard opened from the handover, step by step. */
steps.moveout = async () => {
  const prefix = process.env.PREFIX || "w2";
  const park = await moveOutParkFor(process.env.ACCOUNT || "A-10432");
  if (!park) throw new Error("no move-out draft");
  console.log(`  draft ${park.id} values ${JSON.stringify(park.values)}`);
  await page.goto(`${WEB}/${T}/move-outs/new?parked=${park.id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  // READS="M-4021=16210,M-4022=852" — the closing reading per meter.
  const reads = (process.env.READS || "").split(",").filter(Boolean).map((p) => p.split("="));
  for (let n = 1; n <= 4; n += 1) {
    console.log(`  step: ${await stepTitle()}`);
    if (n === 2) {
      await page.getByLabel("Reason").selectOption({ label: process.env.REASON || "Lease ended" });
      for (const [meter, value] of reads) {
        const input = page.locator("tr", { hasText: meter }).locator("input").first();
        await input.fill(value);
      }
      // DELTA=120 — every meter's closing read = its last reading + DELTA.
      if (process.env.DELTA) {
        const rows = page.locator("tbody tr", { has: page.locator("input") });
        for (let i = 0; i < (await rows.count()); i += 1) {
          const row = rows.nth(i);
          const cells = await row.locator("td").allInnerTexts();
          const last = cells.map((c) => c.match(/^([\d,]+(?:\.\d+)?)\s/)).find(Boolean);
          if (!last) continue;
          const next = Number(last[1].replace(/,/g, "")) + Number(process.env.DELTA);
          await row.locator("input").first().fill(String(next));
          console.log(`  closing read ${cells[0]} = ${next} (last ${last[1]})`);
        }
      }
      const none = page.getByLabel("No visit needed");
      if ((await none.count()) > 0 && !(await none.isChecked())) await none.check({ force: true });
      await page.waitForTimeout(800);
    }
    console.log(`  body: ${(await bodyText()).slice(0, 2200)}`);
    await shot(`${prefix}-4-moveout-step${n}`);
    if (n < 4) await clickButton("Continue");
  }
  if (process.env.COMMIT === "1") {
    const commit = page.getByRole("button", { name: /Close the account|Complete|Close account|Finish/ }).last();
    console.log(`  commit button: ${await commit.textContent()}`);
    await commit.click();
    await page.waitForTimeout(6000);
    await page.waitForLoadState("networkidle");
    console.log(`  done: ${(await bodyText()).slice(0, 2500)}`);
    await shot(`${prefix}-5-moveout-done`);
    const back = page.locator("[data-move-out-back-to-move-in] a");
    console.log(`  back-to-move-in buttons: ${await back.count()}`);
    if ((await back.count()) > 0) {
      await back.first().click();
      await page.waitForTimeout(6000);
      await page.waitForLoadState("networkidle");
      console.log(`  resumed at: ${page.url()}`);
      const reads = await page.evaluate(() =>
        [...document.querySelectorAll("[data-meter-reading-entry]")].map((el) => {
          const inputs = [...el.querySelectorAll("input")].map((i) => i.value);
          return `${el.getAttribute("data-meter-reading-entry")}=${inputs.join("/")}`;
        }),
      );
      const date = await page.locator("#opened_at").inputValue().catch(() => "");
      const chosen = await page.evaluate(
        () => document.querySelector('[data-move-in-unit-search="chosen"]')?.innerText?.replace(/\s+/g, " ") ?? "",
      );
      console.log(`  move-in date ${date} · unit ${chosen} · opening reads ${reads.join(" ")}`);
      await shot(`${prefix}-6-back-to-move-in`);
    }
  }
};

steps.debug = async () => {
  page.on("response", async (r) => {
    const u = r.url();
    if (/accounts\?|accounts\/[0-9a-f-]+$|move-ins\/units/.test(u)) {
      let body = "";
      try {
        body = (await r.text()).slice(0, 400);
      } catch {
        body = "";
      }
      console.log(`  ${r.status()} ${u.replace(/^.*\/api\//, "")} ${body}`);
    }
  });
  await page.goto(`${WEB}/${T}/move-ins/new?parked=${process.env.MOVE_IN_PARK}&carry=reads`, { waitUntil: "networkidle" });
  await page.waitForTimeout(6000);
};

/** Finish the resumed move-in: Continue through the four steps with a new
 *  customer and commit; prints the answer. */
steps.finish = async () => {
  const prefix = process.env.PREFIX || "w2";
  const parkId = process.env.MOVE_IN_PARK;
  await page.goto(`${WEB}/${T}/move-ins/new?parked=${parkId}${process.env.CARRY === "0" ? "" : "&carry=reads"}`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(6000);
  await finishMoveIn(prefix);
};

async function finishMoveIn(prefix) {
  const name = process.env.NEWNAME || "Jordan Newcomb";
  const phone = process.env.NEWPHONE || "(281) 555-0199";
  const fillIf = async (label, value) => {
    const box = page.getByLabel(label, { exact: false }).first();
    if ((await box.count()) > 0) {
      try {
        await box.fill(value, { timeout: 3000 });
      } catch {
        /* not a text box */
      }
    }
  };
  const pick = async (choice) => {
    const radio = page.getByRole("radio", { name: choice, exact: true });
    if ((await radio.count()) > 0) await radio.first().evaluate((el) => el.click());
    await page.waitForTimeout(400);
  };
  for (let guard = 0; guard < 6; guard += 1) {
    const now = await stepTitle();
    console.log(`  step: ${now}`);
    if (now.includes("Review")) break;
    if (now.includes("Unit")) {
      // No crew is booked on this walk: answer the field visit "not needed".
      const visit = page.getByLabel("Visit needed", { exact: true });
      if ((await visit.count()) > 0 && (await visit.isChecked())) await visit.evaluate((el) => el.click());
      await page.waitForTimeout(500);
    }
    if (now.includes("Customer")) {
      await pick("Person");
      await pick(process.env.CLASS || "Residential");
      await fillIf("Full name", name);
      await fillIf("Phone", phone);
      await fillIf("Email", `${name.split(" ")[0].toLowerCase()}@example.com`);
      // W9 — a returning customer's old balance: carried onto the reopened account.
      await pick("Carry it");
      await page.waitForTimeout(1500);
      await shot(`${prefix}-7-customer`);
    }
    if (now.includes("Billing")) {
      await pick("Add to bill");
      await shot(`${prefix}-7b-billing`);
    }
    await clickButton("Continue");
    if ((await stepTitle()) === now) {
      console.log(`  held: ${(await bodyText()).slice(0, 1500)}`);
      await shot(`${prefix}-7-held`);
      return;
    }
  }
  await shot(`${prefix}-8-review`);
  const commit = page.getByRole("button", { name: /Complete move-in|Complete/ }).last();
  console.log(`  commit: ${await commit.textContent().catch(() => "none")}`);
  await commit.click();
  await page.waitForTimeout(9000);
  await page.waitForLoadState("networkidle");
  console.log(`  done: ${(await bodyText()).slice(0, 2500)}`);
  await shot(`${prefix}-9-move-in-done`);
}

/** *Back to move-in* from the move-out's done screen (or a direct resume). */
steps.back = async () => {
  const prefix = process.env.PREFIX || "w2";
  const parkId = process.env.MOVE_IN_PARK;
  await page.goto(`${WEB}/${T}/move-ins/new?parked=${parkId}&carry=reads`, { waitUntil: "networkidle" });
  await page.waitForTimeout(5000);
  console.log(`  body: ${(await bodyText()).slice(0, 2500)}`);
  await shot(`${prefix}-6-back-to-move-in`);
};

/** W2–W6 end to end: search → warning → Start move-out → closing reads →
 *  Complete → Back to move-in → finish the move-in with a new customer. */
steps.full = async () => {
  const prefix = process.env.PREFIX || "wx";
  await handover(process.env.Q, process.env.UNIT, prefix);
  await steps.moveout();
  if (!page.url().includes("/move-ins/new")) {
    console.log("  did not return to the move-in");
    return;
  }
  await finishMoveIn(prefix);
};

/** Fill each opening read with the meter's last reading (+ OPEN_DELTA). */
async function fillOpeningReads() {
  const entries = page.locator("[data-meter-reading-entry]");
  for (let i = 0; i < (await entries.count()); i += 1) {
    const entry = entries.nth(i);
    const input = entry.locator("input").first();
    if ((await input.inputValue()) !== "") continue;
    const rowText = await entry.evaluate((el) => el.closest("tr")?.innerText ?? "");
    const last = rowText.match(/([\d,]+(?:\.\d+)?)\s+(kWh|kgal|gal|ccf|therm|m3|kW)/);
    const value = last ? Number(last[1].replace(/,/g, "")) + Number(process.env.OPEN_DELTA || 0) : 0;
    await input.fill(String(value));
    console.log(`  opening read ${await entry.getAttribute("data-meter-reading-entry")} = ${value}`);
  }
}

/** W1 / W8 / W9 — a unit the move-in may take straight away. */
steps.direct = async () => {
  const prefix = process.env.PREFIX || "w1";
  await openMoveIn();
  const rows = await search(process.env.Q);
  console.log(`  search "${process.env.Q}": ${rows.map((r) => `${r.state}/${r.selectable} ${r.text.slice(0, 120)}`).join(" | ")}`);
  await shot(`${prefix}-1-search`, false);
  await useUnit(process.env.UNIT);
  await setMoveInDate();
  await page.waitForTimeout(3000);
  await fillOpeningReads();
  console.log(`  step 1: ${(await bodyText()).slice(0, 1800)}`);
  await shot(`${prefix}-2-unit`);
  await finishMoveIn(prefix);
};

/** W7 — a disconnected unit: close-out first, then back to the move-in. */
steps.cut = async () => {
  const prefix = process.env.PREFIX || "w7";
  await handover(process.env.Q, process.env.UNIT, prefix);
  /** `RESUME=1` — the close-out was already opened by an earlier run. */
  const scope = page.getByRole("dialog").last();
  await scope.locator('input[type="date"]').first().fill(process.env.CUT_DAY || "2026-10-17");
  await scope.locator("textarea").first().fill("Customer left; new occupant moving in.");
  await page.waitForTimeout(800);
  await shot(`${prefix}-4-close-out-filled`);
  await scope.getByRole("button", { name: /Close out this account/ }).click();
  await page.waitForTimeout(1500);
  await page.waitForTimeout(6000);
  await page.waitForLoadState("networkidle");
  console.log(`  after close-out: ${page.url()}`);
  await shot(`${prefix}-5-after-close-out`);
  if (page.url().includes("/move-ins/new")) {
    await page.waitForTimeout(3000);
    await fillOpeningReads();
    await shot(`${prefix}-6-back-to-move-in`);
    await finishMoveIn(prefix);
  }
};

/** W9 — a returning customer on their own closed unit: the reopen offer. */
steps.returning = async () => {
  const prefix = process.env.PREFIX || "w9";
  await openMoveIn();
  const rows = await search(process.env.Q);
  console.log(`  search: ${rows.map((r) => `${r.state}/${r.selectable} ${r.text.slice(0, 120)}`).join(" | ")}`);
  await useUnit(process.env.UNIT);
  await setMoveInDate();
  await page.waitForTimeout(3000);
  await fillOpeningReads();
  const visit = page.getByLabel("Visit needed", { exact: true });
  if ((await visit.count()) > 0 && (await visit.isChecked())) await visit.evaluate((el) => el.click());
  await clickButton("Continue");
  const pick = async (choice) => {
    const radio = page.getByRole("radio", { name: choice, exact: true });
    if ((await radio.count()) > 0) await radio.first().evaluate((el) => el.click());
  };
  await pick("Person");
  await pick("Residential");
  await page.getByLabel("Full name", { exact: false }).first().fill(process.env.NEWNAME);
  await page.getByLabel("Phone", { exact: false }).first().fill(process.env.NEWPHONE);
  await page.click("[data-search-customer-id]");
  await page.waitForTimeout(4000);
  await page.waitForLoadState("networkidle");
  await shot(`${prefix}-2-match`);
  const same = page.getByRole("button", { name: /Same person/ });
  if ((await same.count()) > 0) {
    await same.first().click();
    await page.waitForTimeout(2500);
  }
  const reopen = page.getByRole("button", { name: /Reopen/ });
  console.log(`  reopen offers: ${await reopen.count()}`);
  console.log(`  customer step: ${(await bodyText()).slice(0, 1600)}`);
  await shot(`${prefix}-3-returning-offer`);
  if ((await reopen.count()) > 0) {
    await reopen.first().click();
    await page.waitForTimeout(2000);
    await shot(`${prefix}-4-reopen-chosen`);
  }
  await finishMoveIn(prefix);
};

/** W14 / W15 — searches only. Q is a "|"-separated list. */
steps.searches = async () => {
  const prefix = process.env.PREFIX || "w14";
  await openMoveIn();
  for (const [index, q] of (process.env.Q || "").split("|").entries()) {
    const rows = await search(q);
    console.log(`  "${q}": ${rows.length} row(s) — ${rows.slice(0, 4).map((r) => `${r.state}/${r.selectable} ${r.text.slice(0, 110)}`).join(" | ")}`);
    await shot(`${prefix}-${index + 1}`, false);
  }
};

export { steps, page, api, shot, search, useUnit, openMoveIn, account, signIn, clickButton, stepTitle, bodyText };

try {
  await signIn();
  const fn = steps[STEP];
  if (!fn) throw new Error(`no step ${STEP}`);
  await fn();
} finally {
  await browser.close();
}
