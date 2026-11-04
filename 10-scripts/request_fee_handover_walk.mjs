// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-6376 — *Record what was handed over* on a service request is
//          Record a payment's form, fixed to the application fee. PO, on
//          SR-26-0016: *"this screens takes the payment it should be similar
//          to record payment form so pasting date, type of payment , memo and
//          it will take only application fee"*.
//          DEF-CUS-6374 — cash at that door needs an open till.
// Rules:   CLAUDE.md hard-won law 6 (diff the running app; no gate reads
//          rendered output) · `22-product-maintenance-process.md` (prove the fix
//          against the reproduction, in a browser)
// Screens: S84 (REQ-02) — the request detail and its handover modal
// ───────────────────────────────────────────────────────
//
// TWO PHASES, BECAUSE THE TILL IS THE POINT OF THE FIRST ONE.
//   PHASE=1  the clerk has NO till open: the modal shows Record a payment's
//            fields, the Start-counter door appears for cash, and the server's
//            refusal is shown in words. Nothing is taken.
//   PHASE=2  the clerk HAS a till open: $70.00 cash is recorded, the modal
//            closes, and the request's Fees block reads $70.00 collected.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   10-scripts/proof-db.sh clone reqfee --stale-ok   (then migrate it)
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_reqfee \
//      JOBS_EAGER=false python manage.py runserver 127.0.0.1:8471 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8472 \
//      API_PROXY_TARGET=http://127.0.0.1:8471 node server.mjs)
//   PHASE=1 REQUEST_ID=<uuid of a request quoting $70.00> BASE=http://127.0.0.1:8472 \
//      node 10-scripts/request_fee_handover_walk.mjs
//   …open a till for the clerk, then PHASE=2 with the same REQUEST_ID.
//
// ⛔ RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING. It WRITES money.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8472";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const REQUEST_ID = process.env.REQUEST_ID;
const PHASE = process.env.PHASE ?? "1";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots-reqfee";
if (!REQUEST_ID) throw new Error("REQUEST_ID is required");

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

const failures = [];
function check(label, ok, detail = "") {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures.push(label);
}

mkdirSync(SHOTS, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1200 } })).newPage();
page.setDefaultTimeout(30000);

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  await page.goto(`${BASE}/${TENANT}/requests/${REQUEST_ID}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { level: 1 }).waitFor();
  const title = (await page.getByRole("heading", { level: 1 }).textContent())?.trim();
  console.log(`\n  PHASE ${PHASE} · request page: ${title}`);
  await page.getByRole("button", { name: "Record what was handed over" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  // The served method list arrives after the dialog opens.
  await page.waitForFunction(() =>
    Array.from(document.querySelectorAll("#method option")).some((o) => o.value === "money_order"),
  );

  const amount = await page.inputValue("#amount");
  const postedAt = await page.inputValue("#posted_at");
  const purpose = await page.inputValue("#purpose");
  const purposeReadOnly = await page.$eval("#purpose", (el) => el.readOnly);
  const methods = await page.$$eval("#method option", (os) => os.map((o) => o.value).filter(Boolean));
  console.log(`  amount=${amount} posted_at=${postedAt} purpose=${purpose} methods=${methods.join(",")}`);
  check("the amount still owing is proposed", amount === "70.00", amount);
  check("a posting date is proposed", /^\d{4}-\d{2}-\d{2}$/.test(postedAt), postedAt);
  check("the purpose is the application fee, read-only", purpose === "Application fee" && purposeReadOnly);
  check("the method list is the tenant's served list", methods.includes("money_order") && !methods.includes("cheque"), methods.join(","));
  check("there is a memo", (await page.$("#memo")) !== null);
  await page.screenshot({ path: join(SHOTS, `phase${PHASE}-01-modal.png`) });

  await page.selectOption("#method", "cash");
  await page.fill("#receipt_no", "RCP-26-0016");
  await page.fill("#memo", "Paid by her daughter");

  if (PHASE === "1") {
    const banner = page.locator('[data-counter-banner="none"]');
    await banner.waitFor();
    check("cash with no till shows the Start-counter door", (await banner.locator("a").count()) === 1);
    await page.screenshot({ path: join(SHOTS, "phase1-02-no-till-banner.png") });
    await dialog.getByRole("button", { name: "Record it" }).click();
    // ⚠ **THE BANNER SAYS THE SAME FIVE WORDS AS THE REFUSAL**, so a bare
    // `getByText` passes the moment the banner is drawn — before the POST has
    // even answered. The first run of this walk did exactly that and its
    // screenshot showed `Working…`. The refusal is the FORM MESSAGE — the
    // `p.form-message[role=alert]` FormModal renders from the server envelope.
    const message = dialog.locator('p.form-message[role="alert"]');
    await message.waitFor();
    const said = (await message.textContent())?.trim() ?? "";
    check("the server's refusal is shown in words, as the form's message", said.includes("Start your counter first."), said);
    check("the modal stays open, nothing taken", await dialog.isVisible());
    await page.screenshot({ path: join(SHOTS, "phase1-03-refused.png") });
  } else {
    check("with a till open, no batch sentence is claimed", (await page.locator("[data-counter-banner]").count()) === 0);
    await dialog.getByRole("button", { name: "Record it" }).click();
    await dialog.waitFor({ state: "detached" });
    check("the modal closes on success", true);
    await page.getByText("70.00 collected", { exact: false }).first().waitFor();
    const fees = await page.getByText("70.00 collected", { exact: false }).first().textContent();
    check("the request shows the $70.00 collected", /70\.00 collected/.test(fees ?? ""), fees?.trim());
    await page.screenshot({ path: join(SHOTS, "phase2-02-collected.png"), fullPage: true });
  }
} catch (error) {
  failures.push(String(error).split("\n")[0]);
  console.log(`  FAIL  ${String(error).split("\n")[0]}`);
  await page.screenshot({ path: join(SHOTS, `phase${PHASE}-error.png`) }).catch(() => {});
} finally {
  await browser.close();
}
console.log(failures.length ? `\n${failures.length} FAIL` : "\nALL PASS");
process.exit(failures.length ? 1 : 0);
