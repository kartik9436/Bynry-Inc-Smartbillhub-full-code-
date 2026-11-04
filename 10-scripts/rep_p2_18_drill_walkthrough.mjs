// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · `P2.18` — drill through to the facts.
// Defect:  DEF-REP-6869 (a group row's `path` is not a filter set) ·
//          DEF-REP-6871 (44 of 71 dimensions cannot be drilled)
// Rules:   PO definition of done — *"do web walkthrough before you sign off"* ·
//          CLAUDE.md hard-won law 6 (no gate looks at rendered output) ·
//          law 7 clause 3 (a check's output must distinguish pass from fail to
//          a READER)
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT NO UNIT TEST CAN: that the number under the subtotal
// and the number of rows it opens are THE SAME REPORT. A DOM test asserts the
// address a link carries; only this follows it, against a real query, and
// counts what came back.
//
// ⚠ **IT TAKES A PAIR OF SHOTS AND BOTH FIGURES ARE LEGIBLE.** A single
// screenshot proves a control renders; a pair proves it works.
//
// ⚠ **THE GROUPING IS REACHED BY URL AND THAT IS STATED RATHER THAN HIDDEN.**
// The slicer bar that turns grouping on is `P2.17`/`P2.26` and is another
// lane's; `?group_by=` is read by `paramsFrom` and is how a clerk reaches it
// today. Nothing here pretends a control exists.
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8081";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/p2-18";
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
const say = (...p) => console.log(...p);
let failures = 0;
const notes = [];
function check(label, ok, detail = "") {
  const line = `${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`;
  say(line);
  notes.push(line);
  if (!ok) failures += 1;
}

for (const width of [1280, 1440]) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ── SHOT 1 · the grouped report, with its subtotals ─────────────────────
  await page.goto(`${BASE}/${TENANT}/reports/ar-aging?group_by=consumer_class`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("table tbody tr", { timeout: 20000 });
  await page.waitForTimeout(600);

  const drills = await page.$$eval("a[data-drill-through]", (ns) =>
    ns.map((n) => ({
      label: n.textContent.trim(),
      href: n.getAttribute("href"),
      // the count sits beside the link, in its own span
      beside: n.parentElement ? n.parentElement.textContent.replace(/\s+/g, " ").trim() : "",
    })),
  );
  check(
    `${width} · the grouped report draws a drill-through per group`,
    drills.length >= 2,
    drills.map((d) => d.beside).join(" | "),
  );
  await page.screenshot({ path: `${OUT}/${width}-01-subtotals.png`, fullPage: true });

  if (drills.length === 0) {
    say(`CANNOT follow a drill-through at ${width} — none was drawn`);
    failures += 1;
    await page.close();
    continue;
  }

  // ── SHOT 2 · the rows behind ONE of them ────────────────────────────────
  const target = drills[0];
  const stated = Number((target.beside.match(/(\d+)\s+rows?/) ?? [0, "0"])[1]);
  await page.click(`a[data-drill-through]`);
  await page.waitForSelector("table tbody tr", { timeout: 20000 });
  await page.waitForTimeout(600);

  const url = page.url();
  check(`${width} · the address carries the group's filter, not its grouping`,
    /f\.class=/.test(url) && !/group_by=/.test(url), url);

  const opened = await page.$$eval("table tbody tr", (rows) => rows.length);
  check(
    `${width} · the subtotal opened the rows that make it`,
    opened === stated,
    `subtotal said ${stated} rows; the drill opened ${opened}`,
  );
  await page.screenshot({ path: `${OUT}/${width}-02-rows-behind.png`, fullPage: true });
  notes.push(`  ${width}: group ${JSON.stringify(target.label)} · stated ${stated} · opened ${opened}`);
  await page.close();
}

writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
say(failures === 0 ? "\nALL PASS" : `\n${failures} FAILURE(S)`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
