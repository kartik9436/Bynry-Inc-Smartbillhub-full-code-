// Walk — DEF-MET-10164 (PO 2026-10-17): Premises and Units lists show Created
// and Age; imports carry the old system's Created date; a dates-only
// re-import corrects it, audited old → new.
// Env: WEB (SPA origin), TENANT, OUT, STEP (one scenario id, or "all"),
// EMAIL, PASSWORD. Each scenario prints the figures it read and saves a shot.
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB || "http://127.0.0.1:8102";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "05-prototype/walk-def-met-10164-2026-10-17";
const STEP = process.env.STEP || "all";
const TMP = process.env.TMPDIR_WALK || "/tmp";
mkdirSync(OUT, { recursive: true });

const exe = process.env.CHROME || "/opt/pw-browsers/chromium";
const browser = await chromium.launch({
  executablePath: existsSync(exe) ? exe : undefined,
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));
page.setDefaultTimeout(45000);

const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false });

async function signIn(email, password) {
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(1500);
}

/** The visible list table: header names + every row's cells, by column. */
async function readTable() {
  await page.locator("table tbody tr").first().waitFor({ timeout: 45000 });
  return page.evaluate(() => {
    const t = document.querySelector("table");
    const heads = [...t.querySelectorAll("thead th")].map((th) => th.innerText.replace(/[▲▼]/g, "").trim());
    const rows = [...t.querySelectorAll("tbody tr")].map((tr) =>
      [...tr.querySelectorAll("td")].map((td) => td.innerText.replace(/\s+/g, " ").trim()),
    );
    return { heads, rows };
  });
}

function col(table, name) {
  const want = name.toLowerCase();
  return table.heads.findIndex((h) => h.toLowerCase() === want || h.toLowerCase().startsWith(want));
}

function summary(table, keyCol, n = 5) {
  const k = col(table, keyCol);
  const c = col(table, "Created");
  const a = col(table, "Age");
  return table.rows.slice(0, n).map((r) => `${r[k]} | Created ${r[c]} | Age ${r[a]}`);
}

async function list(path, query = "") {
  await page.goto(`${WEB}/${T}${path}${query}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
}

async function sortBy(header) {
  // The address bar carries the request state (BR-SHL-011); a page already
  // fetched in this direction may be served from the query cache with no new
  // request, so wait on the URL and the header's state, not on the network.
  const th = page.locator("thead th", { hasText: header }).first();
  const before = page.url();
  await th.locator("button").click();
  await page.waitForFunction((prev) => window.location.href !== prev, before);
  await page.waitForTimeout(1500);
  return `${new URL(page.url()).search} aria-sort=${await th.getAttribute("aria-sort")}`;
}

async function apiJson(path, init = {}) {
  return page.evaluate(
    async ([url, init]) => {
      const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1];
      const res = await fetch(url, {
        credentials: "include",
        ...init,
        headers: { "content-type": "application/json", ...(csrf ? { "X-CSRFToken": csrf } : {}), ...(init.headers || {}) },
      });
      return { status: res.status, body: await res.json().catch(() => null) };
    },
    [`/api/${T}${path}`, init],
  );
}

const results = {};
const want = (id) => STEP === "all" || STEP.split(",").includes(id);

try {
  await signIn(process.env.EMAIL || "dana@brazosbendutilities.com", process.env.PASSWORD || "S3cure!passw0rd");

  if (want("W1")) {
    await list("/premises");
    const t = await readTable();
    console.log("W1 heads:", t.heads.join(" | "));
    console.log(summary(t, "Premise").join("\n"));
    results.W1 = { heads: t.heads, first: summary(t, "Premise", 3) };
    await shot("w1-premises-after");
  }

  if (want("W2")) {
    await list("/premises");
    const a1 = await sortBy("Created");
    const asc = summary(await readTable(), "Premise", 3);
    await shot("w2-premises-created-oldest-first");
    const a2 = await sortBy("Created");
    const desc = summary(await readTable(), "Premise", 3);
    await shot("w2-premises-created-newest-first");
    const a3 = await sortBy("Age");
    const ageAsc = summary(await readTable(), "Premise", 3);
    await shot("w2-premises-age-header-oldest-first");
    const a4 = await sortBy("Age");
    const ageDesc = summary(await readTable(), "Premise", 3);
    await shot("w2-premises-age-header-newest-first");
    console.log("W2 created asc", a1, asc, "\n   created desc", a2, desc, "\n   age asc", a3, ageAsc, "\n   age desc", a4, ageDesc);
    results.W2 = { asc, desc, ageAsc, ageDesc, url: page.url() };
  }

  if (want("W3")) {
    await list("/premises/units");
    const t = await readTable();
    console.log("W3 heads:", t.heads.join(" | "));
    await shot("w3-units-list");
    const a1 = await sortBy("Created");
    const asc = summary(await readTable(), "Unit", 3);
    await shot("w3-units-created-oldest-first");
    const a2 = await sortBy("Created");
    const desc = summary(await readTable(), "Unit", 3);
    await shot("w3-units-created-newest-first");
    console.log("W3 asc", a1, asc, "\n   desc", a2, desc);
    results.W3 = { heads: t.heads, asc, desc };
  }

  if (want("W4")) {
    // A new premise on the S16 wizard, today, then a unit under it.
    const street = process.env.W4_STREET || "4417 Walk Created Ln";
    await page.goto(`${WEB}/${T}/premises/new`, { waitUntil: "networkidle" });
    await page.fill("#address_line", street);
    await page.fill("#city", "Katy");
    await page.fill("#state", "TX");
    await page.fill("#postal_code", "77494");
    for (let step = 0; step < 6; step += 1) {
      const buttons = await page.locator("main button:visible").allInnerTexts();
      console.log(`  W4 step ${step}:`, buttons.map((b) => b.replace(/\s+/g, " ").trim()).filter(Boolean).join(" · "));
      const finish = page.locator("main button:visible", { hasText: /^(Create|Save|Add) (premise|property)/i });
      if (await finish.count()) {
        await finish.first().click();
        break;
      }
      await page.locator("main button:visible", { hasText: /^Continue/ }).last().click();
      await page.waitForTimeout(1500);
    }
    await page.waitForTimeout(3000);
    console.log("  W4 after create url", page.url());
    await list("/premises", `?q=${encodeURIComponent(street.split(" ").slice(1, 3).join(" "))}`);
    const t = await readTable();
    const s = summary(t, "Premise", 3);
    console.log("W4 premise:", s);
    await shot("w4-new-premise-today");
    results.W4 = { premise: s };
  }

  if (want("W4U")) {
    // …then New unit under it (premises id from env), on the Add units screen.
    const pid = process.env.W4_PREMISES_ID;
    await page.goto(`${WEB}/${T}/premises/units/new?premises=${pid}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await page.fill("#units_per_floor", "1");
    for (let step = 0; step < 5; step += 1) {
      const buttons = await page.locator("main button:visible").allInnerTexts();
      console.log(`  W4U step ${step}:`, buttons.map((b) => b.replace(/\s+/g, " ").trim()).filter(Boolean).join(" · "));
      const finish = page.locator("main button:visible", { hasText: /^(Add|Create|Save) \d* ?units?/i });
      if (await finish.count()) {
        await finish.first().click();
        break;
      }
      await page.locator("main button:visible", { hasText: /^Continue/ }).last().click();
      await page.waitForTimeout(1500);
    }
    await page.waitForTimeout(3000);
    await list("/premises/units", `?q=${encodeURIComponent(process.env.W4_PREMISE_NO || "P-00080")}`);
    const s = summary(await readTable(), "Unit", 3);
    console.log("W4U unit:", s);
    await shot("w4-new-unit-today");
    results.W4U = { unit: s };
  }

  /** Drive WFL-01 end to end on `route` with `csv`, in `mode`. Shots per stage. */
  async function runImport(id, route, csv, mode) {
    const file = `${TMP}/${id}.csv`;
    writeFileSync(file, csv);
    await page.goto(`${WEB}/${T}${route}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await page.locator('input[type="file"]').setInputFiles(file);
    await page.locator("label", { hasText: mode === "upsert" ? "Insert & update" : "Insert new only" }).click();
    await page.waitForTimeout(800);
    const seen = [];
    for (let step = 0; step < 8; step += 1) {
      await page.waitForTimeout(2500);
      const buttons = (await page.locator("main button:visible").allInnerTexts()).map((b) => b.replace(/\s+/g, " ").trim()).filter(Boolean);
      const heading = (await page.locator("main h2:visible").allInnerTexts()).join(" / ");
      console.log(`  ${id} stage ${step}: ${heading} :: ${buttons.join(" · ")}`);
      seen.push(heading);
      await shot(`${id.toLowerCase()}-stage-${step}`);
      const approve = page.locator("label", { hasText: /approve/i });
      if (await approve.count()) {
        const box = approve.first().locator("input[type=checkbox]");
        if ((await box.count()) && !(await box.isChecked())) await box.check({ force: true });
      }
      const next = page.locator("main button:visible:enabled", { hasText: /→|Commit load/ });
      if (!(await next.count())) break;
      await next.last().click();
    }
    return seen;
  }

  async function rejectsText() {
    return page.evaluate(() =>
      [...document.querySelectorAll("main table tbody tr")].map((tr) => tr.innerText.replace(/\s+/g, " ").trim()).slice(0, 12),
    );
  }

  if (want("W5")) {
    await runImport(
      "W5",
      "/premises/import",
      [
        "Address,City,State,Zip,Created",
        "101 Silver Creek Rd,Katy,TX,77494,03/14/1996",
        "102 Silver Creek Rd,Katy,TX,77494,",
        "103 Silver Creek Rd,Katy,TX,77494,2001-06-01",
      ].join("\n") + "\n",
      "insert",
    );
    console.log("  W5 result rows:", await rejectsText());
  }
  if (want("W5") || want("W5L")) {
    // The demo utility already has a "101 Silver Creek Rd" in the town of
    // Silver Creek; the imported three are in Katy, so search the town.
    await list("/premises", "?q=Katy&sort=created&dir=asc");
    const s = summary(await readTable(), "Address", 12);
    console.log("W5 list:", s);
    await shot("w5-imported-premises-list");
    results.W5 = { list: s };
  }

  if (want("W6")) {
    await runImport(
      "W6",
      "/premises/import",
      [
        "Address,City,State,Zip,Created",
        "201 Refusal Way,Katy,TX,77494,11/30/2026",
        "202 Refusal Way,Katy,TX,77494,14/03/1996",
        "203 Refusal Way,Katy,TX,77494,05/05/2005",
      ].join("\n") + "\n",
      "insert",
    );
    console.log("  W6 rows:", await rejectsText());
    await list("/premises", "?q=Refusal%20Way");
    const s = summary(await readTable(), "Address", 5);
    console.log("W6 list:", s);
    await shot("w6-refusals-list");
    results.W6 = { list: s };
  }

  if (want("W7")) {
    const pno = process.env.W7_PREMISE_NO;
    await runImport(
      "W7",
      "/premises/units/import",
      [`Premise,Unit label,Created`, `${pno},Apt 1A,06/01/2015`, `${pno},Apt 1B,`].join("\n") + "\n",
      "insert",
    );
    await list("/premises/units", `?q=${encodeURIComponent(pno)}`);
    const s = summary(await readTable(), "Unit", 5);
    console.log("W7 units:", s);
    await shot("w7-units-own-age");
    results.W7 = { units: s };
  }

  if (want("W8")) {
    const pno = process.env.W8_PREMISE_NO;
    await runImport("W8", "/premises/import", [`Premise ID,Created`, `${pno},07/04/1999`].join("\n") + "\n", "upsert");
    await list("/premises", `?q=${encodeURIComponent(pno)}`);
    const s = summary(await readTable(), "Premise", 3);
    console.log("W8 list:", s);
    await shot("w8-reimport-date-corrected");
    results.W8 = { list: s };
  }

  async function exportFrom(path, id) {
    await list(path, "?sort=created&dir=asc");
    // The toolbar's icon control, named "Download CSV" (a glyph, `CR-045 A.3`).
    const button = page.getByRole("button", { name: "Download CSV" }).first();
    await button.click();
    await page.waitForTimeout(4000);
    await shot(`${id.toLowerCase()}-export-ready`);
    const link = page.locator("main a[download]:visible, main a:visible", { hasText: /Download|\.csv/i }).first();
    const [download] = await Promise.all([page.waitForEvent("download", { timeout: 60000 }), link.click()]);
    const file = `${TMP}/${id}.export.csv`;
    await download.saveAs(file);
    const text = (await import("node:fs")).readFileSync(file, "utf8").split("\n");
    console.log(`  ${id} header: ${text[0]}`);
    console.log(`  ${id} rows: ${text.slice(1, 4).join("\n             ")}`);
    return text.slice(0, 4);
  }

  if (want("W9")) {
    results.W9 = {
      premises: await exportFrom("/premises", "W9P"),
      units: await exportFrom("/premises/units", "W9U"),
    };
  }

  if (want("W10")) {
    // Edit premise and Edit unit: list every field label; Created must not be one.
    for (const [path, id] of [
      [`/premises/${process.env.W10_PREMISES_ID}`, "W10P"],
      [`/premises/units/${process.env.W10_UNIT_ID}`, "W10U"],
    ]) {
      await page.goto(`${WEB}/${T}${path}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(2000);
      await page.locator("main button:visible", { hasText: /^Edit$/ }).first().click();
      await page.waitForTimeout(1500);
      const labels = (await page.locator("[role=dialog] label:visible, form label:visible").allInnerTexts()).map((l) =>
        l.replace(/\s+/g, " ").trim(),
      );
      const created = labels.filter((l) => /created/i.test(l));
      console.log(`  ${id} labels: ${labels.join(" · ")}`);
      console.log(`  ${id} Created field present: ${created.length > 0}`);
      await shot(`${id.toLowerCase()}-edit-form-no-created`);
      results[id] = { labels, createdField: created };
    }
  }

  writeFileSync(`${OUT}/walk-results-${STEP.replace(/,/g, "-")}.json`, JSON.stringify(results, null, 2));
} finally {
  await browser.close();
}
