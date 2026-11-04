// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 round 2 task 6 (lane PLAN-LIST) — photograph the built
//          Plans list in the three states of images 01–03 and measure it in
//          all eleven languages at 1440 (DEF-RAT-9333; DEF-RAT-9319/9341's
//          lessons: no sideways scroll, no word split over two lines).
// ───────────────────────────────────────────────────────
//
// Expects the API on a PostgreSQL 16 database with `migrate` + `seed_demo` +
// `load_sample_data --tenant brazosbend`, and the SPA built with
// `vite build --mode wolocal` and served by `07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5271 OUT=08-qa/plans-2026-10-03/list \
//     node 10-scripts/cr167_plans_list_after_walk.mjs
//
// It writes one DRAFT plan through `POST /plans` when the tenant has none, so
// image 01's draft row (V1, No end, Draft) has a real counterpart.
// FORCE_SQUEEZE=1 narrows every cell to one character's width, which must turn
// the split-word check RED (law 7: prove the check can fail).
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5271";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr167-list";
const LANGS = (process.env.LANGS ?? "en,de,es,es-MX,fr-FR,hi,id-ID,it-IT,ja-JP,ko-KR,pt-BR").split(",");
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const say = (...parts) => console.log(...parts);
const settle = (ms = 900) => page.waitForTimeout(ms);
let failures = 0;
function check(name, ok, detail) {
  if (!ok) failures += 1;
  say(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
}
async function shot(name, caption) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`\n=== ${name}.png — ${caption}`);
}
async function api(method, path, body) {
  return page.evaluate(
    async ([m, p, b]) => {
      const res = await fetch(`/api/${p}`, {
        method: m,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: b === undefined ? undefined : JSON.stringify(b),
      });
      let data = null;
      try {
        data = await res.json();
      } catch {
        data = null;
      }
      return { status: res.status, data };
    },
    [method, `${TENANT}/${path}`, body],
  );
}
async function tableText() {
  const table = page.locator("main table");
  return (await table.count()) === 0 ? "(no table)" : (await table.innerText()).replace(/\t/g, " | ");
}
const setLang = (code) => page.evaluate((c) => window.__SMARTBILLHUB_I18N__?.changeLanguage(c), code);

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click("button[type=submit]");
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ── a draft, so image 01's draft row has a counterpart ─────────────────────
const before = await api("GET", "plans?f.status=draft&per=50");
if ((before.data?.count ?? 0) === 0) {
  const made = await api("POST", "plans", {
    code: "RUR",
    name: "Rural Draft",
    effective_from: "2026-12-01",
  });
  say("draft plan created:", made.status, made.data?.name ?? JSON.stringify(made.data).slice(0, 200));
}
const served = await api("GET", "plans?per=50");
const first = served.data?.results?.[0] ?? {};
say(
  "GET /plans row keys:",
  Object.keys(first).sort().join(", "),
  "\nround-2 fields served:",
  ["schedules", "units", "upcoming_version", "customer_classes"].map((k) => `${k}=${k in first}`).join(" "),
);

for (const row of served.data?.results ?? []) {
  say(`  ${row.name}: base ${row.base_charges ?? "null"} (${row.base_charges_unavailable ?? "stated"})`);
}

// ── image 01 · all plans ────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates`, { waitUntil: "networkidle" });
await page.locator("main table").waitFor();
await shot("01-list-all", "Plans list, all plans (image 01)");
say(await tableText());
const heads = await page.$$eval("main thead th", (ths) => ths.map((th) => th.textContent.replace(/[▲▼]/g, "").trim()));
check(
  "01 columns in the drawn order",
  JSON.stringify(heads.filter(Boolean)) ===
    JSON.stringify(["Plan", "Version", "Services", "Schedules", "Base charges", "Units", "From", "To", "Status"]),
  heads.join(" · "),
);
const mainText = await page.innerText("main");
check("01 no paragraph above the table", !mainText.includes("A plan is what customers subscribe to"));
check("01 no database id on screen", !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-/.test(mainText));
const rowButtons = await page.$$eval("main tbody tr", (rows) =>
  rows.map((r) => [...r.querySelectorAll("button")].map((b) => b.getAttribute("aria-label") ?? b.textContent.trim())),
);
check(
  "01 each row's one action is Open",
  rowButtons.every((names) => names.length === 1 && names[0] === "Open"),
  JSON.stringify(rowButtons.slice(0, 3)),
);

// ── the sorts are the SERVER's (NFR-3) ───────────────────────────────────────
for (const [key, pick] of [
  ["units", (r) => r.units],
  ["version", (r) => r.version],
  ["effective_from", (r) => r.effective_from ?? ""],
  ["effective_to", (r) => r.effective_to ?? "9999"],
]) {
  const answer = await api("GET", `plans?per=50&sort=${key}&dir=desc`);
  const values = (answer.data?.results ?? []).map(pick);
  const sorted = [...values].sort((x, y) => (x < y ? 1 : x > y ? -1 : 0));
  check(`server sorts ${key} desc`, JSON.stringify(values) === JSON.stringify(sorted), JSON.stringify(values));
}
await page.getByRole("columnheader", { name: /Units/ }).getByRole("button").click();
await page.getByRole("columnheader", { name: /Units/ }).getByRole("button").click();
await settle(1500);
const unitsCol = await page.$$eval("main tbody tr", (rows) => rows.map((r) => Number(r.children[5]?.textContent ?? "0")));
check(
  "clicking Units twice orders the rows by units, most first",
  page.url().includes("sort=units") && JSON.stringify(unitsCol) === JSON.stringify([...unitsCol].sort((x, y) => y - x)),
  `${page.url()} ${JSON.stringify(unitsCol)}`,
);
await page.goto(`${BASE}/${TENANT}/plans-rates`, { waitUntil: "networkidle" });
await page.locator("main table").waitFor();

// ── image 02 · searched "water" ──────────────────────────────────────────────
const search = page.getByPlaceholder("Search plan name or code");
await search.fill("water");
await settle(1500);
await shot("02-list-search", 'Plans list, searched "water" (image 02)');
say(await tableText());
check("02 the search went to the server", page.url().includes("q=water"), page.url());

// ── image 03 · no results ────────────────────────────────────────────────────
await search.fill("zzz");
await settle(1500);
await shot("03-list-no-results", "Plans list, a search with no results (image 03)");
say((await page.innerText("main")).slice(0, 600));
await search.fill("");
await settle(1200);

// ── eleven languages: width and whole words ──────────────────────────────────
if (process.env.FORCE_SQUEEZE) {
  await page.addStyleTag({ content: "main td span, main th button { display:inline-block; width:14px; word-break:break-all }" });
}
for (const lang of LANGS) {
  await setLang(lang);
  await settle(1200);
  const m = await page.evaluate(() => {
    const doc = document.documentElement;
    const t = document.querySelector("main table");
    const box = document.querySelector("main [data-table-scroll]") ?? t?.parentElement;
    const squeezed = [];
    for (const el of document.querySelectorAll("main th, main td, main button, main [role=tab], main h1")) {
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const text = node.textContent ?? "";
        const re = /\S+/g;
        for (let w = re.exec(text); w; w = re.exec(text)) {
          if (w[0].length < 2) continue;
          const range = document.createRange();
          range.setStart(node, w.index);
          range.setEnd(node, w.index + w[0].length);
          const tops = new Set([...range.getClientRects()].filter((r) => r.width > 0).map((r) => Math.round(r.top)));
          if (tops.size > 1) squeezed.push(w[0].slice(0, 20));
        }
      }
    }
    return {
      page: doc.scrollWidth - doc.clientWidth,
      table: t ? Math.round(t.getBoundingClientRect().width) : null,
      box: box ? box.clientWidth : null,
      squeezed: [...new Set(squeezed)],
    };
  });
  if (lang === "ja-JP" || lang === "ko-KR" || lang === "de") await shot(`lang-${lang}`, `list at 1440 in ${lang}`);
  check(
    `lang ${lang}: fits 1440, no sideways scroll, no word split`,
    m.page <= 0 && (m.table === null || m.box === null || m.table <= m.box) && m.squeezed.length === 0,
    JSON.stringify(m),
  );
}
await setLang("en");

say(`\n${failures === 0 ? "ALL PASS" : `${failures} FAIL`}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
