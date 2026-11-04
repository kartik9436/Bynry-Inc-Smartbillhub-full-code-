// DEF-SHL-10001 / DEF-CUS-10002 (lane LEAVE-GUARD, 2026-10-07) — the leave-page
// popup walked in a browser at 1440: the draft popup on a move-in opened from a
// service request (save, toast, resumed value, autosave after Leave without
// saving), the no-draft popup on Add premises, reload and Back, New connection,
// and the regressions (Park, Save draft & exit, a request's last-step save) that
// must NOT ask. Needs a seeded world with SR-26-0001 an undecided move-in request.
//   LG_BASE=http://127.0.0.1:5617 node 10-scripts/leave_guard_walkthrough.mjs <outdir>
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");
const BASE = process.env.LG_BASE || "http://127.0.0.1:5617";
const T = process.env.LG_TENANT || "brazosbend";
const OUT = process.argv[2];
mkdirSync(OUT, { recursive: true });
const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
p.setDefaultTimeout(20000);
const R = [];
const ok = (name, cond, detail = "") => R.push(`${cond ? "PASS" : "FAIL"} · ${name}${detail ? " · " + detail : ""}`);
const shot = (n) => p.screenshot({ path: `${OUT}/${n}.png` });
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", "dana@brazosbendutilities.com");
await p.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }), p.click('button[type="submit"]')]);

const dlg = () => p.locator('[role="alertdialog"]');
const sideNav = async (label) => {
  await p.locator("nav a", { hasText: label }).first().click();
  await p.waitForTimeout(900);
};
const cont = async () => {
  await p.locator('[data-wizard="actions"] button', { hasText: "Continue" }).last().click();
  await p.waitForTimeout(900);
};
async function openRequestEdit() {
  await p.goto(`${BASE}/${T}/moves/SR-26-0001`, { waitUntil: "networkidle" });
  const more = p.locator("[data-move-more] summary");
  if (await more.count()) await more.click();
  await p.locator('[data-testid="move-action-edit"], a:has-text("Edit"), button:has-text("Edit")').first().click();
  await p.waitForSelector('[data-wizard="frame"]');
  await p.waitForLoadState("networkidle");
  await p.waitForTimeout(1200);
}
const step = () => new URL(p.url()).searchParams.get("step");

try {
  // ── A · Move-in from an undecided request: popup (draft), Save as draft, resumed ──
  await openRequestEdit();
  const DATE = process.env.LG_DATE || "11/03/2026";
  ok("A0 opened untouched: side nav would not ask", (await dlg().count()) === 0);
  await p.fill("#opened_at", DATE);
  await p.press("#opened_at", "Tab");
  await p.waitForTimeout(300);
  await cont();
  await cont();
  ok("A1 two Continues, no popup on the step changes", (await dlg().count()) === 0, `step=${step()}`);
  await shot("01-move-in-from-request-filled");
  await sideNav("Accounts");
  ok("A2 side nav while dirty -> popup", (await dlg().count()) === 1, p.url());
  const text = (await dlg().count()) ? await dlg().innerText() : "";
  ok("A3 draft variant has Save as draft / Leave without saving / Stay", /Save your work as a draft\?/.test(text) && /Save as draft/.test(text) && /Leave without saving/.test(text) && /Stay/.test(text), JSON.stringify(text));
  await shot("02-popup-save-as-draft-move-in-from-request");
  await p.locator('[data-leave-guard-action="stay"]').click();
  await p.waitForTimeout(400);
  ok("A4 Stay keeps the clerk on the wizard", p.url().includes("/move-ins/new"), p.url());
  await sideNav("Accounts");
  await p.locator('[data-leave-guard-action="save"]').click();
  await p.waitForTimeout(400);
  await shot("03-toast-saved-as-draft");
  const toast = await p.evaluate(() => document.body.innerText.includes("Saved as draft. Find it on Move-ins."));
  ok("A5 toast says where the draft is", toast);
  await p.waitForURL((u) => u.pathname.endsWith("/accounts"), { timeout: 8000 });
  ok("A6 navigation carried on to Accounts", p.url().endsWith("/accounts"), p.url());
  await openRequestEdit();
  const again = await p.inputValue("#opened_at");
  ok("A7 reopened Edit shows the saved date", again === DATE, `${again} vs ${DATE}`);
  await shot("04-move-in-resumed-with-saved-value");

  // ── A' · autosave alone (no popup save): change, leave without saving, reopen ──
  const DATE2 = process.env.LG_DATE2 || "11/04/2026";
  await p.fill("#opened_at", DATE2);
  await p.press("#opened_at", "Tab");
  await p.waitForTimeout(2200); // settle + the autosave's own pause
  await sideNav("Accounts");
  await p.locator('[data-leave-guard-action="leave"]').click();
  await p.waitForURL((u) => u.pathname.endsWith("/accounts"), { timeout: 8000 });
  await openRequestEdit();
  ok("A8 autosave kept the change even after Leave without saving", (await p.inputValue("#opened_at")) === DATE2, await p.inputValue("#opened_at"));
  await shot("05-move-in-autosaved-after-leave-without-saving");

  // ── B · Add property: no-draft popup ───────────────────────────────────────
  await p.goto(`${BASE}/${T}/premises/new`, { waitUntil: "networkidle" });
  await sideNav("Accounts");
  ok("B0 untouched Add property: no popup", (await dlg().count()) === 0 && p.url().endsWith("/accounts"), p.url());
  await p.goto(`${BASE}/${T}/premises/new`, { waitUntil: "networkidle" });
  await cont();
  await p.fill("#address_line", "12 Leave Guard Lane");
  await shot("10-add-property-filled");
  await sideNav("Accounts");
  const t2 = (await dlg().count()) ? await dlg().innerText() : "";
  ok("B1 Add property step 2 -> popup, no-draft words", /Leave without saving\?/.test(t2) && /Your work will not be saved\./.test(t2) && !/Save as draft/.test(t2), JSON.stringify(t2));
  await shot("11-popup-leave-without-saving-add-property");
  await p.locator('[data-leave-guard-action="stay"]').click();
  await p.waitForTimeout(300);
  ok("B2 Stay keeps the typed address", (await p.inputValue("#address_line")) === "12 Leave Guard Lane");
  // Reload / tab close: the browser's own prompt (beforeunload). Dismissing it
  // is "stay".
  const native = [];
  let acceptNative = false;
  p.on("dialog", (d) => {
    native.push(d.type());
    void (acceptNative ? d.accept() : d.dismiss());
  });
  await p.reload().catch(() => {});
  await p.waitForTimeout(700);
  ok("B3a reload while dirty -> the browser's own leave-site prompt", native.includes("beforeunload"), JSON.stringify(native));
  ok("B3b dismissing it stays, typing intact", (await p.inputValue("#address_line").catch(() => "")) === "12 Leave Guard Lane");
  acceptNative = true;
  // Browser Back inside the app: arrive at the wizard by an in-app link first.
  // (the move-in Edit is opened by an in-app click from the request's page)
  await openRequestEdit();
  await p.fill("#opened_at", "11/06/2026");
  await p.press("#opened_at", "Tab");
  await p.goBack();
  await p.waitForTimeout(500);
  if ((await dlg().count()) === 0 && new URL(p.url()).searchParams.get("step") !== null) {
    // the first Back undid the ?step= change (the wizard's own); the next leaves
    await p.goBack();
    await p.waitForTimeout(700);
  }
  ok("B3 browser Back out of the wizard while dirty -> popup", (await dlg().count()) === 1, p.url());
  await p.locator('[data-leave-guard-action="stay"]').click();
  // top menu / header search is a router nav? use the page-head back link (a link out)
  await p.locator("a", { hasText: "Premises" }).first().click();
  await p.waitForTimeout(700);
  ok("B4 a second side-nav item (Premises) while dirty -> popup", (await dlg().count()) === 1);
  await p.locator('[data-leave-guard-action="leave"]').click();
  await p.waitForTimeout(800);
  ok("B5 Leave without saving leaves to Premises", p.url().endsWith("/premises"), p.url());

  // ── C · New connection: draft variant, from a later step ────────────────────
  await p.goto(`${BASE}/${T}/connections/new`, { waitUntil: "networkidle" });
  await p.fill("#nc_owner_name", "Leave Guard Bakery");
  await shot("20-new-connection-filled");
  await sideNav("Accounts");
  const t3 = (await dlg().count()) ? await dlg().innerText() : "";
  ok("C1 New connection -> draft popup", /Save as draft/.test(t3), JSON.stringify(t3));
  await shot("21-popup-new-connection");
  await p.locator('[data-leave-guard-action="stay"]').click();

  // ── D · Regression: Complete / Park / Save & exit never ask ───────────────────
  // Park on New connection (the wizard's own exit): opens its panel, parks, leaves.
  const park = p.locator('[data-wizard="actions"] button', { hasText: /^Park$/ });
  if (await park.count()) {
    await park.first().click();
    await p.selectOption("#wizard_park_reason", "customer");
    await p.locator("button", { hasText: "Park it" }).click();
    await p.waitForTimeout(1500);
    ok("D1 Park on New connection leaves with NO popup", (await dlg().count()) === 0 && !p.url().includes("/connections/new"), p.url());
    await shot("30-after-park-new-connection");
  } else {
    ok("D1 Park button present on New connection", false);
  }
  // Save draft & exit on Move-in (page head) — the request's own save, no popup.
  await openRequestEdit();
  await p.fill("#opened_at", "11/05/2026");
  await p.press("#opened_at", "Tab");
  await p.locator("[data-move-in-save-draft]").click();
  await p.waitForTimeout(1500);
  ok("D2 Move-in Save draft & exit leaves with NO popup", (await dlg().count()) === 0 && !p.url().includes("/move-ins/new"), p.url());
  // Save draft & exit on a standalone New move-in (park autosave route)
  await p.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(800);
  const anyInput = p.locator('[data-wizard="content"] input[type="text"]:visible, [data-wizard="content"] input[type="search"]:visible').first();
  if (await anyInput.count()) {
    await anyInput.fill("Unit");
  }
  await p.locator("[data-move-in-save-draft]").click();
  await p.waitForTimeout(1500);
  ok("D3 standalone Move-in Save draft & exit, NO popup", (await dlg().count()) === 0 && !p.url().includes("/move-ins/new"), p.url());
  // Complete on a request Edit (its last step SAVES the request and returns).
  await openRequestEdit();
  await p.fill("#opened_at", "11/07/2026");
  await p.press("#opened_at", "Tab");
  for (let i = 0; i < 6 && (await p.locator('[data-wizard="actions"] button', { hasText: "Continue" }).count()); i++) await cont();
  await shot("31-move-in-request-last-step");
  await p.locator('[data-wizard="actions"] button').last().click();
  await p.waitForTimeout(2000);
  ok("D4 Move-in last-step commit (Save changes) leaves with NO popup", (await dlg().count()) === 0 && !p.url().includes("/move-ins/new"), p.url());
} catch (error) {
  R.push(`FAIL · crashed · ${String(error).split("\n")[0]}`);
  await shot("99-crash");
}
console.log(R.join("\n"));
await b.close();
