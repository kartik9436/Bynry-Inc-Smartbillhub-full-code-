// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-SHL-6377` — the Product Owner, 2026-09-23, pressing *Download
//          error report* on a failed property sale (*"The sale was not
//          recorded. Nothing changed hands."*): *"Unable to download error
//          report"*.
// Rules:   CLAUDE.md hard-won law 6 (diff the running app — no gate reads
//          rendered output) · law 7 (every check below was shown to fail on the
//          unfixed build first) · `22-product-maintenance-process.md` step 4
//          (prove it against the reproduction, in a browser)
// Screens: `TRF-02` — the transfer wizard, all five steps, and its failure
//          panel
// ───────────────────────────────────────────────────────
//
// THE PO'S CASE, REPRODUCED AND THEN PRESSED. It sells an account that has no
// linked customer (`A-11512` in the demo utility, the account the PO used), which
// the server still refuses on step 5, and then presses *Download error report*
// on the failure panel and READS THE FILE that the browser saves.
//
// ⚠ **THE REFUSAL IT LEANS ON IS BEING RETIRED.** The decision log of 2026-09-23
// rules that a seller with no linked customer is recorded by name and the sale
// goes ahead (lane TRANSFER). Once that lands, `A-11512` no longer fails and
// this walk says so at *"the failure panel appears"* rather than passing over
// it — set `ACCOUNT` to anything the server still refuses, or reproduce the
// panel on any other screen: the button is the same component everywhere.
//
// ⚠ **IT PRESSES *COMPLETE THE SALE*.** On a build that refuses the account,
// nothing is written but the refused attempt's audit row; on a build that
// ACCEPTS it (see above) the sale is real. So run it only against a private
// clone that is thrown away afterwards:
//
//   10-scripts/proof-db.sh clone errreport
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_errreport \
//      JOBS_EAGER=false python3 manage.py runserver 127.0.0.1:8691 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8692 \
//      API_PROXY_TARGET=http://127.0.0.1:8691 node server.mjs)
//   BASE=http://127.0.0.1:8692 node 10-scripts/def_shl_6377_error_report_walkthrough.mjs
//
//   BASE      default http://127.0.0.1:8692 — the SPA join (`server.mjs`)
//   TENANT    default brazosbend
//   ACCOUNT   default A-11512 — an account with NO linked customer
//   SHOTS     default /tmp/claude-0/shots/errorreport
const { existsSync, readdirSync, mkdirSync, readFileSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8692";
const TENANT = process.env.TENANT ?? "brazosbend";
const ACCOUNT = process.env.ACCOUNT ?? "A-11512";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots/errorreport";

// What a careless report would copy — typed on step 2 and asserted ABSENT.
const BUYER = "Nadia Okonjo";
const SSN = "123-45-6789";

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

let passes = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    passes += 1;
    console.log(`  ✓ ${what}`);
  } else {
    failures.push(`${what}${detail ? ` — ${detail}` : ""}`);
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
  return cond;
}
const saw = (what) => console.log(`  · ${what}`);

mkdirSync(SHOTS, { recursive: true });
const KILL = setTimeout(() => {
  console.error("GAVE UP: the walk exceeded 10 minutes");
  process.exit(3);
}, 600_000);

const browser = await chromium.launch({ executablePath: resolveChromium() });
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1300 },
    acceptDownloads: true,
    timezoneId: "America/Chicago",
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);

  console.log(`\n══ DEF-SHL-6377 · Download error report · ${BASE}/${TENANT} · ${ACCOUNT} ══`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 45000 }),
    page.click('button[type="submit"]'),
  ]);
  const version = ((await page.textContent('[data-testid="app-version"]').catch(() => "")) || "").trim();
  saw(`signed in; the footer reads ${JSON.stringify(version)}`);

  console.log("\n1 · THE PO'S SALE — an account with no linked customer, walked to step 5");
  await page.goto(`${BASE}/${TENANT}/transfers/new`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-r10="TRF-02"]');
  await page.fill("#trf_account_q", ACCOUNT);
  await page.waitForTimeout(2500);
  const options = await page.$$eval("#trf_account option", (os) =>
    os.filter((o) => o.value).map((o) => ({ v: o.value, t: o.textContent.trim() })),
  );
  const hit = options.find((o) => o.t.includes(ACCOUNT));
  ok(`step 1 finds ${ACCOUNT}`, hit !== undefined, JSON.stringify(options));
  await page.selectOption("#trf_account", hit.v);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(SHOTS, "01-step1.png"), fullPage: true });

  const next = async (n) => {
    await page.click('[data-wizard="actions"] button:has-text("Continue")');
    await page.waitForTimeout(1800);
    ok(`Continue lands on step ${n}`, page.url().endsWith(`?step=${n}`), page.url());
  };

  await next(2);
  for (const l of await page.$$('[data-wizard="content"] label')) {
    if ((await l.textContent()).trim() === "Person") {
      await l.click();
      break;
    }
  }
  await page.waitForTimeout(800);
  await page.fill("#trf_buyer_name", BUYER);
  if (await page.$("#trf_buyer_ssn")) await page.fill("#trf_buyer_ssn", SSN);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(SHOTS, "02-step2-buyer-typed.png"), fullPage: true });

  await next(3);
  if (await page.$("#trf_sold_on")) await page.fill("#trf_sold_on", "2026-09-18");
  await page.waitForTimeout(800);

  await next(4);
  const ticks = await page.$$eval('[data-wizard="content"] input[type=checkbox]', (ns) =>
    ns.map((n) => n.id),
  );
  for (const id of ticks) {
    await page.click(`label[for=${id}]`);
    await page.waitForTimeout(300);
  }

  await next(5);
  await page.screenshot({ path: join(SHOTS, "03-step5-review.png"), fullPage: true });

  console.log("\n2 · THE COMMIT — refused, as the PO saw it");
  await page.click('[data-wizard="actions"] button:has-text("Complete the sale")');
  const panel = await page.waitForSelector(".state-failed", { timeout: 45000 }).catch(() => null);
  ok("the failure panel appears", panel !== null);
  const panelText = panel === null ? "" : (await panel.textContent()).replace(/\s+/g, " ").trim();
  saw(`the panel reads: ${JSON.stringify(panelText)}`);
  ok(
    "it is the PO's panel — The sale was not recorded. Nothing changed hands.",
    panelText.includes("The sale was not recorded. Nothing changed hands."),
  );
  await page.screenshot({ path: join(SHOTS, "04-failure-panel.png"), fullPage: true });

  console.log("\n3 · DOWNLOAD ERROR REPORT — pressed, and the file READ");
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 15000 }).catch(() => null),
    page.click('.state-failed button:has-text("Download error report")'),
  ]);
  ok("pressing it starts a download", download !== null, "no download event within 15s");
  if (download !== null) {
    const name = download.suggestedFilename();
    const saved = join(SHOTS, name);
    await download.saveAs(saved);
    const text = readFileSync(saved, "utf8");
    saw(`saved ${saved} (${text.length} bytes)`);
    console.log("\n──── the file, verbatim ────");
    console.log(text);
    console.log("────────────────────────────");
    const line = (label) => {
      const m = new RegExp(`^\\s*${label}:\\s*(.*)$`, "m").exec(text);
      return m === null ? null : m[1].trim();
    };
    ok("its name is <screen>-error-<yyyymmdd-hhmm>.txt", /^TRF-02-error-\d{8}-\d{4}\.txt$/.test(name), name);
    ok("Screen: TRF-02", line("Screen") === "TRF-02", String(line("Screen")));
    ok("Page: the wizard's address, step kept", line("Page") === `/${TENANT}/transfers/new?step=5`, String(line("Page")));
    ok("Time: in the utility's zone, named", / America\/Chicago$/.test(line("Time") ?? ""), String(line("Time")));
    ok(`Version: the footer's ${version}`, `v${line("Version")}` === version, `${line("Version")} vs ${version}`);
    ok("What failed: the panel's title", line("What failed") === "The sale was not recorded. Nothing changed hands.");
    ok("Reason: the panel's sentence", (line("Reason") ?? "").length > 0 && panelText.includes(line("Reason")), String(line("Reason")));
    ok("Method: POST", line("Method") === "POST", String(line("Method")));
    ok("Path: /transfers/commit", line("Path") === "/transfers/commit", String(line("Path")));
    ok("Status: a 4xx refusal", /^4\d\d$/.test(line("Status") ?? ""), String(line("Status")));
    ok("Message key: the refusal's key", (line("Message key") ?? "").startsWith("customers.transfer."), String(line("Message key")));
    ok("Reference: a readable support reference", /^[0-9A-F]{4}-[0-9A-F]{4}$/.test(line("Reference") ?? ""), String(line("Reference")));
    ok("the header says what it leaves out", /leaves out/.test(text));
    for (const secret of [BUYER, "Okonjo", SSN, "sessionid", "csrftoken"]) {
      ok(`it does NOT carry ${JSON.stringify(secret)}`, !text.includes(secret));
    }
    writeFileSync(join(SHOTS, "report-path.txt"), `${saved}\n`);
  }
  await page.screenshot({ path: join(SHOTS, "05-after-download.png"), fullPage: true });
} finally {
  clearTimeout(KILL);
  await browser.close();
}

console.log(`\n${passes} passed · ${failures.length} failed`);
for (const f of failures) console.log(`  ✗ ${f}`);
process.exit(failures.length === 0 ? 0 : 1);

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-SHL-6377 (lane ERROR-REPORT)
// generated: 2026-09-23 by lane ERROR-REPORT
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
