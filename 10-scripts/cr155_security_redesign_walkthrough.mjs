#!/usr/bin/env node
// ── cr155_security_redesign_walkthrough.mjs ─────────────────────────────────
//
// CLICK THE REDESIGNED Settings → Security AND PHOTOGRAPH IT AT THE THREE
// WIDTHS THE PO APPROVED — 1440, 1280, 420.
//
// CLAUDE.md hard-won law 6: *"Diff the running app against `05-prototype/`.
// No gate looks at rendered output. Nine defects were found this way and by
// nothing else."* Eleven DOM cases and a green `tsc` say the markup is what
// this lane meant; only a photograph beside
// `05-prototype/security-redesign-2026-09-29/approved-proposed-1440.png` says
// whether it is what the PO approved.
//
// ⚠ **THE BUNDLE MUST BE BUILT `--mode compose`.** A bare `npx vite build`
// resolves as `production`, bakes `https://api-smart360.bynry.com` into the
// bundle, and sign-in then fails with *"That email or password is
// incorrect."* on correct credentials (`DEF-INF-7802`, after biting three
// lanes). `10-scripts/11-smoke-stack.sh` does this correctly and is what
// boots the stack this script drives; 56 other walkthrough scripts still
// carry the bare line, so check any you copy.
//
// ⚠ **NEVER `npx playwright install`.** The container's chromium is at
// `/opt/pw-browsers/chromium-*/chrome-linux/chrome` and `resolveChromium`
// below finds it, printing which one it took when the pinned revision is
// absent — a mismatch stated rather than silently accepted.
//
// WHAT IT CHECKS, beyond taking the picture:
//   * the four card headings, in the drawn order;
//   * Save is ABOVE the audit card in the DOM, which is the single most
//     visible thing the redesign fixes;
//   * every value control's tag — the PO ruled dropdowns, and the four the
//     server still serves as ranges are REPORTED as text boxes rather than
//     quietly accepted, so the picture and this log say the same thing;
//   * no raw catalogue key and no database id on the page (B14 rule 31);
//   * any 5xx anywhere in the run.
//
//   SMOKE_BASE (http://127.0.0.1:8080) · SMOKE_TENANT · SMOKE_EMAIL ·
//   SMOKE_PASSWORD · SMOKE_OUT
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.SMOKE_BASE ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT =
  process.env.SMOKE_OUT ??
  join(tmpdir(), `cr155-security-${new Date().toISOString().replace(/[:.]/g, "-")}`);

const WIDTHS = [1440, 1280, 420];
const failures = [];
const notes = [];
const fiveHundreds = [];

function fail(message) {
  failures.push(message);
  console.error(`  ✗ ${message}`);
}
function note(message) {
  notes.push(message);
  console.log(`  · ${message}`);
}

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error(`no chromium found (wanted ${wanted}); do NOT run playwright install`);
}

const VALUE_CONTROLS = [
  "pw_min_length",
  "pw_expiry_days",
  "session_timeout_minutes",
  "absolute_session_hours",
  "keep_signed_in_days",
  "lockout_max_failed",
  "lockout_minutes",
];

async function main() {
  mkdirSync(OUT, { recursive: true });
  console.log(`CR-155-BRC09 walkthrough: ${BASE} tenant=${TENANT} → ${OUT}`);

  const browser = await chromium.launch({ executablePath: resolveChromium(), headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  page.on("response", (r) => {
    if (r.status() >= 500) fiveHundreds.push(`${r.status()} ${r.request().method()} ${r.url()}`);
  });

  console.log("── sign in");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 });

  console.log("── Settings → Security");
  await page.goto(`${BASE}/${TENANT}/settings/security`, { waitUntil: "networkidle" });
  await page.waitForSelector("section.panel h3", { timeout: 20000 });

  // 1 — the four headings, in the drawn order.
  const headings = await page.$$eval("h3", (hs) => hs.map((h) => h.textContent?.trim() ?? ""));
  const wanted = ["Passwords", "Sessions", "Signing in", "Audit log"];
  if (JSON.stringify(headings) !== JSON.stringify(wanted)) {
    fail(`headings are ${JSON.stringify(headings)}, drawn order is ${JSON.stringify(wanted)}`);
  } else {
    note(`four cards, drawn order: ${headings.join(" · ")}`);
  }

  // 2 — Save before the audit card. The old screen put Save below the fold
  //     under a three-then-two grid; this is the fix, and it is invisible to
  //     every gate in the repo.
  const orderOk = await page.evaluate(() => {
    const save = Array.from(document.querySelectorAll("button")).find((b) =>
      (b.textContent ?? "").includes("Save security settings"),
    );
    const card = document.querySelector("[data-security-audit-card]");
    if (!save || !card) return null;
    return (
      (save.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0
    );
  });
  if (orderOk === null) fail("Save button or audit card not found on the page");
  else if (!orderOk) fail("the audit card is rendered BEFORE the Save row");
  else note("Save renders before the audit log card");

  // 3 — what each value control actually IS. The PO ruled dropdowns; the four
  //     the server still serves as min/max are text boxes today, and this
  //     REPORTS that rather than passing over it. A check that cannot cover
  //     its whole subject prints what it skipped (law 7's fifth shape).
  const kinds = await page.evaluate(
    (ids) =>
      Object.fromEntries(
        ids.map((id) => {
          const el = document.getElementById(id);
          return [id, el === null ? "MISSING" : el.tagName];
        }),
      ),
    VALUE_CONTROLS,
  );
  const selects = Object.entries(kinds).filter(([, tag]) => tag === "SELECT");
  const inputs = Object.entries(kinds).filter(([, tag]) => tag === "INPUT");
  const missing = Object.entries(kinds).filter(([, tag]) => tag === "MISSING");
  note(`dropdowns: ${selects.length}/${VALUE_CONTROLS.length} — ${selects.map(([k]) => k).join(", ")}`);
  if (inputs.length > 0) {
    note(
      `STILL TYPED NUMBERS (the server serves these as min/max ranges; they become ` +
        `dropdowns with no front-end edit the day it publishes their choices): ` +
        `${inputs.map(([k]) => k).join(", ")}`,
    );
  }
  for (const [id] of missing) fail(`value control ${id} is not on the page`);

  // 4 — the three tick boxes are tick boxes (PO: "(a) Keep them as checkboxes").
  const boxes = await page.$$eval('input[type="checkbox"]', (els) => els.map((e) => e.id));
  const wantedBoxes = ["pw_require_mixed", "pw_require_symbol", "keep_signed_in_offered"];
  for (const id of wantedBoxes) {
    if (!boxes.includes(id)) fail(`${id} is not a checkbox on the rendered page`);
  }
  note(`tick boxes: ${boxes.filter((b) => wantedBoxes.includes(b)).join(", ")}`);

  // 5 — what the audit card is actually showing today.
  const auditState = await page.evaluate(() => {
    const card = document.querySelector("[data-security-audit-card]");
    if (!card) return "NO CARD";
    if (card.querySelector("[data-security-audit-empty]")) return "empty state";
    const rows = card.querySelectorAll("[data-security-audit-row]").length;
    if (rows > 0) return `${rows} row(s)`;
    return `no rows and no empty state — text: ${(card.textContent ?? "").slice(0, 160)}`;
  });
  note(`audit card: ${auditState}`);

  // 6 — B14 rule 31 and a raw catalogue key, on the rendered page.
  const body = await page.evaluate(() => document.body.innerText);
  if (/\bsettings\.security\.[a-zA-Z]/.test(body)) {
    fail("a raw catalogue key is visible on the page");
  }
  if (/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/.test(body)) {
    fail("a UUID is visible on the page (B14 rule 31)");
  }
  for (const column of ["lockout_minutes", "session_timeout_minutes", "ip_allowlist"]) {
    if (body.includes(column)) fail(`the column name ${column} is visible on the page`);
  }

  // 6b — CHANGE SOMETHING AND WATCH THE CARD RECORD IT. Everything above is
  //      a screen READ; this is the only step that proves the loop a clerk
  //      actually lives in — save → the server audits it → the card below
  //      the Save button shows what you just did, named the way the control
  //      names it. It is also the one thing that can tell an empty card that
  //      is honest from an empty card that is broken.
  const before = await page.evaluate(() => {
    const el = document.getElementById("session_timeout_minutes");
    return el instanceof HTMLSelectElement ? el.value : null;
  });
  if (before === null) {
    fail("cannot exercise the audit card: the idle-timeout control is not a select");
  } else {
    const other = await page.evaluate(() => {
      const el = document.getElementById("session_timeout_minutes");
      const opt = Array.from(el.options).find((o) => o.value !== el.value);
      return opt ? opt.value : null;
    });
    if (other === null) {
      note("only one timeout is offered, so nothing can be changed — audit step skipped");
    } else {
      await page.selectOption("#session_timeout_minutes", other);
      await page.click('button:has-text("Save security settings")');
      await page.waitForTimeout(1500);
      await page.reload({ waitUntil: "networkidle" });
      await page.waitForSelector("[data-security-audit-card]", { timeout: 20000 });
      const recorded = await page.evaluate(() => {
        const card = document.querySelector("[data-security-audit-card]");
        const rows = Array.from(card.querySelectorAll("[data-security-audit-row]"));
        return rows.map((r) =>
          Array.from(r.querySelectorAll("td")).map((c) => (c.textContent ?? "").trim()),
        );
      });
      if (recorded.length === 0) {
        fail(`saved ${before} → ${other} and the audit card recorded nothing`);
      } else {
        note(`after saving, the card's top row reads: ${recorded[0].join(" | ")}`);
        // No raw value and no column name in the row the clerk just caused.
        const text = recorded[0].join(" ");
        if (text.includes("session_timeout_minutes")) {
          fail("the SETTING column printed the column name");
        }
        if (new RegExp(`\\b${other}\\b(?! (minute|hour))`).test(text)) {
          fail(`the CHANGE column printed the raw value ${other}`);
        }
      }
      // Put it back, so the walkthrough leaves the tenant as it found it.
      await page.selectOption("#session_timeout_minutes", before);
      await page.click('button:has-text("Save security settings")');
      await page.waitForTimeout(1500);
      await page.reload({ waitUntil: "networkidle" });
      await page.waitForSelector("[data-security-audit-card]", { timeout: 20000 });
    }
  }

  // 7 — the photographs, one per approved width.
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: width === 420 ? 1400 : 1000 });
    await page.waitForTimeout(400);
    const path = join(OUT, `built-security-${width}.png`);
    await page.screenshot({ path, fullPage: true });
    console.log(`  shot: ${path}`);
  }

  await browser.close();

  console.log("\n── notes");
  for (const n of notes) console.log(`  ${n}`);
  if (fiveHundreds.length > 0) {
    console.log("\n── 5xx seen");
    for (const f of fiveHundreds) console.log(`  ${f}`);
  }
  if (failures.length > 0) {
    console.error(`\nFAILED (${failures.length})`);
    for (const f of failures) console.error(`  ${f}`);
    process.exit(1);
  }
  console.log("\nPASSED");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
