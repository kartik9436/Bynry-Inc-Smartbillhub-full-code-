// ── DEF-SHL-6347 · NEW REQUEST STEP 4 ATTACHES A FILE WITH NO SCANNER RUNNING ─
//
// PO, verbatim, 2026-09-23: *"please remove virus scan chek user don't wan't
// it. we have ask remove it before why you did not remove it?"*. On the
// deployed build step 4 refused every upload with *"The virus scanner is
// unreachable. Try again shortly."*, no file ever attached, and the review
// showed *No file* for every document.
//
// **WHAT IT PROVES, IN A BROWSER (hard-won law 6).** A clerk walks New Request
// to step 4 by pressing Continue, attaches a real PDF, sees it LISTED with its
// name and size, and then sees it on step 6's review — with the backend
// configured exactly as the deployed host was (a ClamAV scanner named, nothing
// listening). Run the backend with `DJANGO_SETTINGS_MODULE` pointing at a
// module that does `from config.settings.local import *` and then sets:
//
//     MALWARE_SCANNER_BACKEND = "clamav"
//     MALWARE_SCANNER_ALLOW_TEST_DOUBLE = False
//     MALWARE_SCANNER_HOST = "127.0.0.1"
//     MALWARE_SCANNER_PORT = 1
//
// On the code before `DEF-SHL-6347` that reproduces the PO's screen exactly;
// after it, nothing reads those names and the file attaches.
//
// ⚠ **IT PRINTS WHAT IT SAW, PASS OR FAIL, AND EXITS 1 ON ANY FAIL** — the red
// run against the old build must produce the refusal sentence as evidence, not
// a stack trace.
//
// ⚠ **IT WRITES ONE DRAFT REQUEST AND ONE STORED FILE.** Run it against a
// private clone (`10-scripts/proof-db.sh clone <label>`), never a shared
// database: `stored_documents` is write-once by design, so the file stays.
//
//   BASE      default http://127.0.0.1:8954 (the SPA, proxying /api)
//   TENANT    default brazosbend
//   EMAIL     default dana@brazosbendutilities.com
//   PASSWORD  default S3cure!passw0rd
//   SHOTS     default ./ — screenshots land here
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8954";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? ".";
const LABEL = process.env.LABEL ?? "walk";

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const dir of readdirSync("/opt/pw-browsers")) {
    for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
      const candidate = join("/opt/pw-browsers", dir, sub);
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found under /opt/pw-browsers");
}

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok });
  console.log(`  ${ok ? "PASS" : "FAIL"} · ${name}${detail ? " · " + detail : ""}`);
};

mkdirSync(SHOTS, { recursive: true });
const FILE_NAME = "proof-of-identity.pdf";
const SAMPLE = join(SHOTS, FILE_NAME);
writeFileSync(SAMPLE, `%PDF-1.4\n% DEF-SHL-6347 walk ${Date.now()}\n%%EOF\n`);

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1200 } })).newPage();
page.setDefaultTimeout(20000);

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ── STEPS 1–3, BY PRESSING CONTINUE (a `?step=4` URL makes no draft) ────
  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await page.fill("#applicant_name", "Walker, Dana");
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1500);
  await page.selectOption("#account_type_code", "residential");
  await page.waitForTimeout(500);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1500);
  for (const [sel, val] of [
    ["#address_as_given", "212 Balcones Drive"],
    ["#city", "Austin"],
    ["#postal_code", "78704"],
  ]) {
    const el = page.locator(sel);
    if ((await el.count()) > 0) await el.fill(val).catch(() => {});
  }
  await page.waitForTimeout(600);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2500);

  // ── STEP 4 · ATTACH ─────────────────────────────────────────────────────
  check("reached step 4 by pressing Continue", (await page.locator('[data-step-content="documents"]').count()) === 1, page.url());
  await page.locator('input[type="file"]').first().setInputFiles(SAMPLE);
  await page.waitForTimeout(500);
  await page.locator("[data-doc-attach]").click();
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if ((await page.locator("[data-doc-file]").count()) > 0) break;
    if ((await page.locator("[data-doc-error]").count()) > 0) break;
    await page.waitForTimeout(500);
  }
  await page.waitForTimeout(800);
  const refusal = ((await page.locator("[data-doc-error]").textContent().catch(() => null)) ?? "").trim();
  const step4Text = (await page.locator("main").innerText()).trim();
  const fileCells = (await page.locator("[data-doc-file]").allTextContents()).map((c) => c.trim());
  const stateCells = (await page.locator("[data-doc-state]").allTextContents()).map((c) => c.trim());
  console.log(`    refusal on screen: ${JSON.stringify(refusal)}`);
  console.log(`    FILE column: ${JSON.stringify(fileCells)} · STATE column: ${JSON.stringify(stateCells)}`);
  await page.screenshot({ path: join(SHOTS, `${LABEL}-step4-after-attach.png`), fullPage: true });

  check("no refusal after pressing Attach", refusal === "", refusal);
  check("nothing on step 4 names a virus scanner", !/virus|malware|scanner/i.test(step4Text));
  check(
    "the file is LISTED by name with its size",
    fileCells.length === 1 && fileCells[0].startsWith(FILE_NAME) && fileCells[0] !== "—",
    JSON.stringify(fileCells),
  );
  check(
    "STATE is empty until a reviewer decides — no third word",
    stateCells.length === 1 && stateCells[0] === "",
    JSON.stringify(stateCells),
  );

  // Ask the SERVER, not the screen: a row is not a file.
  const server = await page.evaluate(async (tenant) => {
    const id = new URL(window.location.href).searchParams.get("request");
    if (!id) return null;
    const r = await fetch(`/api/${tenant}/service-requests/${id}/documents`, { credentials: "include" });
    const j = await r.json();
    return (j.data ?? j).documents.map((d) => ({ name: d.name, file_present: d.file_present, size: d.size_bytes, state: d.verification_state }));
  }, TENANT);
  console.log(`    the server holds: ${JSON.stringify(server)}`);
  check(
    "the server holds the file behind the row",
    Array.isArray(server) && server.length === 1 && server[0].file_present === true,
  );

  // ── STEP 5 → STEP 6 · THE REVIEW ────────────────────────────────────────
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2000);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2500);
  const review = (await page.locator("main").innerText()).trim();
  await page.screenshot({ path: join(SHOTS, `${LABEL}-step6-review.png`), fullPage: true });
  // ⚠ **THE REVIEW NAMES THE DOCUMENT BY TYPE AND SAYS WHETHER A FILE IS
  // HELD — it does not print the file name** (that is the review's own
  // drawing, owned by another lane). So the row is read as the clerk reads
  // it: `Proof of identity · A file is held`, and never `No file`, which is
  // what the PO saw for every document on the deployed build.
  const reviewRows = await page.evaluate(() =>
    [...document.querySelectorAll("tr")]
      .map((tr) => [...tr.querySelectorAll("td")].map((td) => (td.textContent || "").trim()))
      .filter((cells) => cells.length >= 2 && /Proof of identity/.test(cells[0])),
  );
  console.log(`    review's Documents row: ${JSON.stringify(reviewRows)}`);
  check(
    "the review shows the document with a file held",
    reviewRows.length === 1 && reviewRows[0][1] === "A file is held",
    JSON.stringify(reviewRows),
  );
  check("the review does not say No file", !/No file/.test(review));
} catch (error) {
  console.log(`  ⚠ the walk stopped: ${error.message}`);
  results.push({ name: "walk completed", ok: false });
  await page.screenshot({ path: join(SHOTS, `${LABEL}-ERROR.png`), fullPage: true }).catch(() => {});
} finally {
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n  ${results.length - failed} passed · ${failed} failed · screenshots in ${SHOTS}`);
  await browser.close();
  process.exitCode = failed === 0 ? 0 : 1;
}
