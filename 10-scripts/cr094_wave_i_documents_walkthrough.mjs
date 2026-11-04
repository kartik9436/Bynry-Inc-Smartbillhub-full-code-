// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 2 wave I — `ACC-S8`, "An account can hold a
//          document". THE CLICK-THROUGH, which is the only check in this
//          repository that reads rendered output (hard-won law 6).
// Rules:   BR-CUS-036 (the five CONFIRMED types) · BR-SHL-031 (PDF/PNG/JPG/CSV,
//          10 MB) · BR-SHL-010 (no Export — nothing registers this resource) ·
//          B14 rule 16 (the pagination footer) · rule 31 (no database id on
//          screen) · rule 33 (on-screen text capped by what it is for).
// ───────────────────────────────────────────────────────
//
// ⚠ **IT UPLOADS A REAL FILE AND READS THE ROW BACK.** A walkthrough that only
// opened the tab would prove the tab renders; the thing `ACC-S8` commits to is
// that an account can HOLD a document, and the only way to see that is to put
// one there and find it again.
//
// ⚠ **AND IT EXERCISES THE TWO REFUSALS, NOT ONLY THE HAPPY PATH.** A `.txt`
// must come back refused (415) and the sentence must be the catalogue's, not
// silence — which is what an unresolved `message_key` renders as.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
//      DOCUMENT_STORAGE_BACKEND=filesystem DOCUMENT_STORAGE_ALLOW_FILESYSTEM=True \
//      DOCUMENT_STORAGE_DIR=/tmp/sbh-docs JOBS_EAGER=false \
//      python3 manage.py runserver 127.0.0.1:8730 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8731 \
//      API_PROXY_TARGET=http://127.0.0.1:8730 node server.mjs)
//   node 10-scripts/cr094_wave_i_documents_walkthrough.mjs
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8731";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ACCOUNT = process.env.ACCOUNT ?? "01a09540-727d-7b81-a750-49ddd2e237be"; // A-10432
const OUT = process.env.OUT ?? "/tmp/cr094-wave-i";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const results = [];
function check(width, name, ok, detail = "") {
  results.push({ width, name, ok });
  console.log(`  ${ok ? "PASS" : "FAIL"}  [${width}] ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

// A real PDF, small enough to be instant and valid enough to be a PDF.
const PDF = Buffer.from("%PDF-1.7\nthe signed lease for 1408 Elm St\n%%EOF\n");
const TXT = Buffer.from("this is not on the allowlist\n");

const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });

for (const width of [1280, 1440]) {
  const page = await browser.newPage({ viewport: { width, height: 1800 } });
  console.log(`\n══════ ${width}px ══════`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);

  const url = `${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=documents`;
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  let html = await page.content();
  writeFileSync(join(OUT, `documents-${width}-before.html`), html);

  // ── 1 · THE TAB IS NO LONGER A FRAME ────────────────────────────────────
  console.log("\n1 · the tab, opened from its own address");
  check(width, "the stated absence is GONE", !html.includes("no upload endpoint"),
    "the sentence the tab used to draw is still on screen");
  // ⚠ **THE FIVE COLUMN HEADS ARE ASSERTED AFTER THE UPLOAD, NOT HERE, AND THE
  //    FIRST DRAFT OF THIS FILE GOT IT WRONG IN A WAY WORTH RECORDING.** It
  //    checked them on arrival, passed at 1440 and FAILED at 1280 — and the
  //    screen was right both times. `BR-SHL-012` replaces the WHOLE table
  //    region when a list is empty, header included (*"never an empty
  //    header"*), so on the FIRST pass — before this script had filed
  //    anything — there was correctly no header to find, and on the second
  //    pass the first pass's document was there. **A check whose result depends
  //    on which order the widths ran is not a check.** So the empty state is
  //    asserted here and the heads are asserted where rows exist.
  const emptyNow = html.includes("No documents filed yet.");
  if (emptyNow) {
    check(width, "an empty list states the absence rather than drawing bare headers",
      !/<th[^>]*>\s*Document\s*<\/th>/.test(html),
      "BR-SHL-012 forbids an empty header over an empty list");
  } else {
    check(width, "the five drawn column heads are present",
      ["Document", "Type", "Date", "Uploaded by", "Size"].every((h) => html.includes(h)));
  }
  check(width, "BR-SHL-010 — no Export control", !/>\s*Export\s*</.test(html));
  check(width, "the drawing's `Evidence` chip is absent", !html.includes("Evidence"));
  check(width, "Upload document is a LIVE control",
    await page.locator('button:has-text("Upload document")').first().isEnabled());

  // ── 2 · THE REFUSAL, BEFORE THE HAPPY PATH ──────────────────────────────
  console.log("\n2 · a file outside BR-SHL-031's allowlist (415)");
  await page.locator('button:has-text("Upload document")').first().click();
  await page.waitForTimeout(600);
  await page.setInputFiles("#document-file", { name: "notes.txt", mimeType: "text/plain", buffer: TXT });
  await page.selectOption("#document-type", "contract");
  await page.fill("#document-name", "notes.txt");
  await page.locator('form button[type="submit"]').last().click();
  await page.waitForTimeout(1800);
  html = await page.content();
  writeFileSync(join(OUT, `documents-${width}-refused.html`), html);
  check(width, "the 415 reaches the clerk AS A SENTENCE, not as silence",
    html.includes("Only PDF, PNG, JPG or CSV."),
    "an unresolved message_key renders as NOTHING — that is what this asserts against");

  // ── 3 · THE CAPABILITY ──────────────────────────────────────────────────
  console.log("\n3 · filing a real document");
  await page.setInputFiles("#document-file", { name: "signed-lease.pdf", mimeType: "application/pdf", buffer: PDF });
  await page.fill("#document-name", "signed-lease.pdf");
  await page.locator('form button[type="submit"]').last().click();
  await page.waitForTimeout(2500);
  html = await page.content();
  writeFileSync(join(OUT, `documents-${width}-after.html`), html);
  check(width, "the document is FILED and the row is on screen", html.includes("signed-lease.pdf"),
    "the upload did not produce a row");
  check(width, "its TYPE reads in words, not as a code", html.includes("Contract"));
  check(width, "its SIZE reads in a unit a person would say", /\b\d+\s*(B|KB|MB)\b/.test(html));
  check(width, "B14 rule 31 — the row shows no database id", !html.includes(ACCOUNT));
  check(width, "the uploader is named", html.includes("Dana") || html.includes("dana"));
  // The heads, asserted where a row exists — see the note in section 1.
  check(width, "the five drawn column heads are present over the rows",
    ["Document", "Type", "Date", "Uploaded by", "Size"].every((h) => html.includes(h)));

  await page.close();
}

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length} checks, ${failed.length} failed`);
for (const f of failed) console.log(`  FAILED [${f.width}] ${f.name}`);
process.exit(failed.length === 0 ? 0 : 1);
