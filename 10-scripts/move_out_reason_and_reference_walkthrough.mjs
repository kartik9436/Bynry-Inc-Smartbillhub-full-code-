// ── Trace ──────────────────────────────────────────────
// Change:   PO ruling 2026-09-20, "TEN MOVE-OUT RULINGS IN ONE SITTING" —
//           item 3 (the move-out reason gets a column) and item 9 (a parked
//           move-out is allocated a reference).
// Rules:    B14 rule 31 (no database id is a field's visible value) · rule 32
//           (no rule id in clerk-facing copy) · rule 33 (a label is ≤ 3 words)
//           · rule 39 (field → field 20px) · CLAUDE.md hard-won law 6 (diff
//           the running app against the design — the only check that reads
//           rendered output is a person)
// Tests:    06-backend/tests/test_br_cus_030_close_reason.py (the service half)
//           07-frontend/src/features/customers/MoveOutWizard.test.tsx
// ───────────────────────────────────────────────────────
//
//   BASE=http://127.0.0.1:8178 node 10-scripts/move_out_reason_and_reference_walkthrough.mjs
//
// ⚠ **THIS WALK IS READ-ONLY ON THE BETA AND SAYS SO RATHER THAN CLAIMING IT.**
// A move-out COMMITS and there is no undo (hard rule 4), and a park writes a
// row that would move the beta's "1 parked draft". So this walk OPENS the
// screens and reads them; the write paths are proved in
// `10-scripts/move_out_scenarios.sh`, which runs against a separate PostgreSQL
// database and provisions a throwaway tenant per scenario.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// ⚠ **RESOLVED THROUGH `07-frontend`, NOT BARE.** `playwright` is not a
// dependency of the repo root, so a bare import fails with ERR_MODULE_NOT_FOUND
// wherever this is run from. `12-smoke-walkthrough.mjs` solved this already and
// this is its shim verbatim.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8178";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/mvo-reason";
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
let failures = 0;
const check = (label, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
};

// ⚠ **BOTH STAFF WIDTHS.** The skill's §6 table: a clerk screen is verified at
// 1280 and 1440 and at nothing narrower.
for (const width of [1440, 1280]) {
  const page = await browser.newPage({ viewport: { width, height: 1200 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ── An ACTIVE account, found the way a clerk finds one ──────────────────
  await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
  const href = await page.evaluate(() => {
    const a = [...document.querySelectorAll('a[href*="/accounts/"]')]
      .find((x) => /\/accounts\/[0-9a-f-]{20,}$/.test(x.getAttribute("href") ?? ""));
    return a ? a.getAttribute("href") : null;
  });
  if (!href) { check(`${width}: found an account to open`, false); continue; }
  const accountId = href.split("/").pop();

  // ── ITEM 3 · STEP 2 OF THE MOVE-OUT ─────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}/move-out?step=2`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/step2-${width}.png`, fullPage: true });

  const sel = await page.$("#close_reason");
  check(`${width}: step 2 draws a reason control`, sel !== null);
  if (sel) {
    const opts = await page.$$eval("#close_reason option", (os) =>
      os.map((o) => ({ value: o.value, label: o.textContent.trim() })));
    check(`${width}: five reasons plus an empty leading option`, opts.length === 6,
      opts.map((o) => o.value).join(","));
    check(`${width}: nothing is preselected`, (await page.inputValue("#close_reason")) === "",
      "a default here would be the product deciding why somebody left");
    // B14 rule 31 — a clerk reads words, never the stored code.
    check(`${width}: the options read as words, not codes`,
      opts.slice(1).every((o) => o.label !== "" && !o.label.includes("_")),
      opts.slice(1).map((o) => o.label).join(" · "));
    // B14 rule 33 — a LABEL is ≤ 3 words.
    const label = (await page.textContent('label[for="close_reason"]')).replace("*", "").trim();
    check(`${width}: the field label is ≤ 3 words`, label.split(/\s+/).length <= 3, `"${label}"`);
  }

  // B14 rule 32 — no rule id in clerk-facing copy. The absence used to put
  // BR-CUS-030 on this screen; with the control built there is nothing to cite.
  const shown = await page.evaluate(() => document.body.innerText);
  check(`${width}: no rule id is on screen`, !/BR-[A-Z]{3}-\d/.test(shown));
  check(`${width}: the old "Not stored" absence is gone`, !shown.includes("Not stored"));

  // B14 rule 39 — field → field 20px. MEASURED, never assumed: a run of bare
  // `.field`s in a `Panel` is display:block with gap:normal and measures 0.
  const gap = await page.evaluate(() => {
    const stack = document.querySelector("[data-field-stack]");
    if (!stack) return null;
    const f = [...stack.querySelectorAll(":scope > .field")];
    if (f.length < 2) return null;
    return Math.round(f[1].getBoundingClientRect().top - f[0].getBoundingClientRect().bottom);
  });
  check(`${width}: the date and the reason are 20px apart`, gap === 20, `measured ${gap}px`);

  // ── ITEM 9 · THE MOVE RECORD, AND ITS REASON ROW ────────────────────────
  await page.goto(`${BASE}/${TENANT}/moves/mvo-26-0001`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/record-${width}.png`, fullPage: true });
  const rec = await page.evaluate(() => document.body.innerText);
  check(`${width}: the record opens on a LOWERCASE reference`, rec.includes("MVO-26-0001"),
    "the blueprint's own URL is lowercase and the number a clerk quotes is upper");
  check(`${width}: the record draws a Reason row`, /\bReason\b/.test(rec));
  check(`${width}: a close made before the column says the product never asked`,
    rec.includes("Not asked"), "never a dash, and never an invented reason");
  check(`${width}: no rule id on the record either`, !/BR-[A-Z]{3}-\d/.test(rec));

  await page.close();
}

await browser.close();
console.log(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
