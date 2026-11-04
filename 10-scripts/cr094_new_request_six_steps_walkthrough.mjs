// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 — step 1 MEASUREMENT of blueprint entry 06 "Service
//          request capture", all ELEVEN drawings: the six capture steps
//          (`/:tenant/requests/new?step=1..6`), the register's Requests tab,
//          the request's own screen, and the three decision dialogs (Approve,
//          Refuse, Ask for more).
// Rules:   B14 rule 41 (the product UI matches the blueprint EXACTLY) · rule 42
//          (a screen is built from the drawing AS AN IMAGE) · PO ruling
//          2026-09-15, verbatim: *"document screens are benchmark"* ·
//          hard-won law 6 (no gate looks at rendered output) · hard-won law 2
//          (built is not wired).
// ───────────────────────────────────────────────────────
//
// WHAT THIS IS FOR, AND WHAT IT DELIBERATELY DOES NOT DO.
//
// It READS. It fills nothing, saves nothing, submits nothing and approves
// nothing on the shared demo tenant — the measurement lane was told to read and
// never write, and a wizard that PATCHes on every forward move would write a
// draft simply by being walked. So the six steps are reached by their own URL
// (`?step=N`, which `DEF-CUS-5083` made real URL state) rather than by pressing
// Continue, and the dialogs are opened and closed.
//
// ⚠ **ONE CONSEQUENCE, STATED SO NOBODY READS THIS AS MORE THAN IT IS:**
// reaching step 5 without a saved draft means the Fees step renders its
// no-draft sentence rather than a quote, and step 6's review renders the empty
// form. Both are recorded as what they are. What this script CAN answer is
// which CONTROLS and which LABELS exist on each step, which is what the
// conformance table needs.
//
// It writes one JSON file of per-screen inner text plus a PNG per screen, so a
// later reader can re-check a verdict without re-running anything.
import { existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

// ⚠ CHECK THE PORT IS YOURS BEFORE YOU BELIEVE A WORD OF THE OUTPUT — a sibling
// lane serving the same number answers every request from ITS tree and ITS
// database, and the output looks perfectly healthy.
const BASE = process.env.BASE ?? "http://127.0.0.1:8141";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr094-req";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1280, height: 1400 } });
const say = (...parts) => console.log(...parts);
const record = {};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL, "on", TENANT, "\n");

/** Everything a conformance table needs off one rendered screen, measured in
 *  the DOM rather than counted by reading the source (skill §7). */
async function census(name, url, { waitFor = "h1" } = {}) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForSelector(waitFor, { timeout: 30000 }).catch(() => undefined);
  await page.waitForTimeout(700);
  const data = await page.evaluate(() => {
    const vis = (el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 || r.height > 0;
    };
    const labelOf = (el) => {
      if (el.id) {
        const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
        if (l) return l.innerText.trim();
      }
      const wrap = el.closest("label");
      if (wrap) return wrap.innerText.trim();
      return el.getAttribute("aria-label") ?? el.getAttribute("placeholder") ?? "";
    };
    const controls = [...document.querySelectorAll("input,select,textarea")]
      .filter(vis)
      .map((el) => ({
        tag: el.tagName.toLowerCase(),
        type: el.getAttribute("type") ?? "",
        id: el.id || null,
        label: labelOf(el),
        required: el.required || el.getAttribute("aria-required") === "true",
        disabled: el.disabled,
        options:
          el.tagName.toLowerCase() === "select"
            ? [...el.options].map((o) => o.text)
            : undefined,
      }));
    const buttons = [...document.querySelectorAll("button,a[role='button']")]
      .filter(vis)
      .map((b) => ({ text: b.innerText.trim(), disabled: b.disabled === true, title: b.title || null }));
    const headings = [...document.querySelectorAll("h1,h2,h3,h4")]
      .filter(vis)
      .map((h) => `${h.tagName}:${h.innerText.trim()}`);
    const tables = [...document.querySelectorAll("table")].filter(vis).map((tb) => ({
      headers: [...tb.querySelectorAll("thead th")].map((th) => th.innerText.trim()),
      rows: tb.querySelectorAll("tbody tr").length,
    }));
    const h1 = document.querySelector("h1");
    return {
      title: h1 ? h1.innerText.trim() : null,
      titlePx: h1 ? getComputedStyle(h1).fontSize : null,
      headings,
      controls,
      buttons,
      tables,
      tabs: [...document.querySelectorAll("[role='tab']")].filter(vis).map((t) => t.innerText.trim()),
      text: document.body.innerText,
    };
  });
  record[name] = { url, ...data };
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
  say(
    `── ${name} · ${url}\n   title=${JSON.stringify(data.title)} (${data.titlePx})` +
      `\n   controls=${data.controls.length} buttons=${data.buttons.length} tables=${data.tables.length}`,
  );
  say(
    "   fields: " +
      data.controls
        .map((c) => `${c.label || c.id || c.tag}${c.required ? "*" : ""}[${c.type || c.tag}]`)
        .join(" · "),
  );
  say("   buttons: " + data.buttons.map((b) => `${b.text}${b.disabled ? "(off)" : ""}`).join(" · "));
  say("   headings: " + data.headings.join(" · ") + "\n");
  return data;
}

// ══ 1 · THE SIX CAPTURE STEPS ═════════════════════════════════════════════
for (let n = 1; n <= 6; n += 1) {
  await census(`capture-step-${n}`, `${BASE}/${TENANT}/requests/new?step=${n}`);
}

// ══ 2 · THE REGISTER'S REQUESTS TAB ═══════════════════════════════════════
await census("register-requests-tab", `${BASE}/${TENANT}/accounts?tab=requests`);
await census("requests-standalone", `${BASE}/${TENANT}/requests`);

// ══ 3 · A SUBMITTED REQUEST, READ ONLY ════════════════════════════════════
const list = await page.evaluate(async (t) => {
  const res = await fetch(`/api/${t}/service-requests?limit=50`, { credentials: "include" });
  return { status: res.status, body: await res.text() };
}, TENANT);
say("GET /service-requests →", list.status);
let rows = [];
try {
  rows = JSON.parse(list.body).results ?? [];
} catch {
  /* reported below */
}
say(
  "requests on the tenant:",
  rows.map((r) => `${r.request_no ?? "(no number)"}·${r.state}`).join(", ") || "(none)",
);
record.__list = rows;

const pick = rows.find((r) => r.state !== "draft") ?? rows[0];
if (pick) {
  for (const tab of ["applicant", "location", "documents", "fees", "decision", "history"]) {
    await census(`request-detail-${tab}`, `${BASE}/${TENANT}/requests/${pick.id}?tab=${tab}`);
  }
  // ── the two dialogs that can be OPENED without writing ──────────────────
  await page.goto(`${BASE}/${TENANT}/requests/${pick.id}?tab=decision`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(600);
  const refuseBtn = page.locator("button", { hasText: /^Refuse$/ }).first();
  if ((await refuseBtn.count()) > 0) {
    await refuseBtn.click();
    await page.waitForTimeout(600);
    record["dialog-refuse"] = await page.evaluate(() => {
      const dlg = document.querySelector("[role='dialog']") ?? document.body;
      return {
        text: dlg.innerText,
        controls: [...dlg.querySelectorAll("input,select,textarea")].map((el) => ({
          tag: el.tagName.toLowerCase(),
          id: el.id,
          required: el.required,
          options: el.tagName.toLowerCase() === "select" ? [...el.options].map((o) => o.text) : undefined,
        })),
        buttons: [...dlg.querySelectorAll("button")].map((b) => b.innerText.trim()),
      };
    });
    await page.screenshot({ path: join(OUT, "dialog-refuse.png"), fullPage: true });
    say("── dialog-refuse\n" + JSON.stringify(record["dialog-refuse"], null, 1) + "\n");
    await page.keyboard.press("Escape");
  } else {
    say("── dialog-refuse: NO Refuse button on the decision tab");
  }

  // Park, which is the product's own control with no counterpart in the drawing
  await page.goto(`${BASE}/${TENANT}/requests/${pick.id}?tab=decision`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(500);
  const parkBtn = page.locator("button", { hasText: /Park/ }).first();
  if ((await parkBtn.count()) > 0 && !(await parkBtn.isDisabled())) {
    await parkBtn.click();
    await page.waitForTimeout(500);
    record["dialog-park"] = await page.evaluate(() => {
      const dlg = document.querySelector("[role='dialog']") ?? document.body;
      return { text: dlg.innerText, buttons: [...dlg.querySelectorAll("button")].map((b) => b.innerText.trim()) };
    });
    await page.screenshot({ path: join(OUT, "dialog-park.png"), fullPage: true });
    await page.keyboard.press("Escape");
  }
}

writeFileSync(join(OUT, "census.json"), JSON.stringify(record, null, 1));
say(`\nwrote ${join(OUT, "census.json")} and one PNG per screen`);
await browser.close();
