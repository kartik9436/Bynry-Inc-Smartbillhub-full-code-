// ── Trace ──────────────────────────────────────────────
// Task:    P3.10 (row actions on the batch lines) · P3.11 (say when a locked
//          batch no longer sums) · P3.12 (multi-line resolve, running residual)
//          Finance blueprint p016, p049–p055 · screens 3·2 Batch and 3·4 Resolve
// Defects: DEF-PAY-6651 (the drift cannot be derived from `members`) ·
//          DEF-PAY-6652 (`.fin-num` out-ranked by `PlainTable`'s own variant)
// Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//          running app yourself) · hard-won law 7 (a check's output must
//          distinguish pass from fail TO A READER, and a check reporting zero
//          over a scope it excludes is indistinguishable from an empty one)
// ───────────────────────────────────────────────────────
/**
 * Walk the deposit-batch screen and MEASURE it, then photograph it.
 *
 * ⚠ **THE ALIGNMENT CHECK IS THE REASON THIS FILE EXISTS.** `DEF-PAY-6652` is a
 * class that IS in the DOM and renders as nothing, because `PlainTable` writes
 * `[&_td]:text-left` on the table at specificity (0,1,1) and `.fin-num` is
 * (0,1,0). **`expect(className).toContain("text-right")` passes over it**, and
 * so does every gate in the repo. Only `getComputedStyle` can see it, and only
 * in a real browser with the built stylesheet — so it is measured here and NOT
 * asserted in vitest, where the answer would be meaningless.
 *
 * ⚠ **`fullPage: true` IS A NO-OP ON THIS PRODUCT.** The shell scrolls an inner
 * `main.view`, not the document, so Playwright is told the page is 900px tall,
 * believes it, and returns a viewport crop with no error and no warning. This
 * walk measures the scroller and GROWS THE VIEWPORT to it before each capture,
 * and prints each shot's height so a short screen and a cropped one can be told
 * apart.
 *
 * ⚠ **EVERY COUNT IS PRINTED BESIDE WHAT IT WAS COUNTED OVER.** A walk that
 * says "row actions: present" over a table it never found is hard-won law 7's
 * fifth shape, so each line names its denominator.
 *
 * RUN, against your OWN database and your OWN ports:
 *   BASE=http://127.0.0.1:<web> SHOTS=<dir> DRIFT=<batch uuid> SHORT=<batch uuid> \
 *     node 10-scripts/p3_batch_line_walkthrough.mjs
 *
 * `DRIFT` is a LOCKED batch with a reversed member (P3.11); `SHORT` is an
 * unlocked batch matched to a bank line that is short (P3.10 · P3.12).
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import fs from "node:fs";

const BASE = process.env.BASE ?? "http://127.0.0.1:8478";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/p3-batch";
const DRIFT = process.env.DRIFT ?? "";
const SHORT = process.env.SHORT ?? "";
fs.mkdirSync(SHOTS, { recursive: true });

const lines = [];
const say = (m) => {
  console.log(m);
  lines.push(m);
};
let failures = 0;
const check = (ok, what, detail) => {
  if (!ok) failures += 1;
  say(`  ${ok ? "PASS" : "FAIL"} · ${what}${detail === undefined ? "" : ` — ${detail}`}`);
};

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => {
  failures += 1;
  say(`  !! page error: ${e.message}`);
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
say("signed in");

// ⚠ **WAIT FOR IT, DO NOT SNAPSHOT IT.** A first version of this read the
// version straight after `waitForURL` and printed "(none on screen)" while the
// sidebar was still rendering — which reads exactly like a version that is
// MISSING, and change-process §7 exists because a build nobody can name is a
// defect nobody can place. A check that cannot tell *absent* from *not drawn
// yet* is hard-won law 7, so this one waits and then says which it found.
let version = "(none on screen)";
try {
  await page.waitForSelector('[data-testid="app-version"]', { timeout: 20000 });
  version = (await page.evaluate(
    () => document.querySelector('[data-testid="app-version"]')?.textContent?.trim() ?? "",
  )) || "(element present but empty)";
} catch {
  version = "(NOT ON SCREEN after 20s — this is a finding, not a slow render)";
  failures += 1;
}
say(`VERSION ON SCREEN: ${version}`);

async function grow(width) {
  await page.setViewportSize({ width, height: 900 });
  const needed = await page.evaluate(() => {
    const main = document.querySelector("main.view") || document.body;
    const chrome = window.innerHeight - main.clientHeight;
    return Math.min(9000, Math.ceil(main.scrollHeight + chrome + 24));
  });
  if (needed > 900) {
    await page.setViewportSize({ width, height: needed });
    await page.waitForTimeout(700);
  }
  return needed;
}

async function shoot(name, width) {
  const height = await grow(width);
  const file = `${SHOTS}/${name}${width === 1440 ? "" : `-${width}`}.png`;
  await page.screenshot({ path: file, fullPage: true });
  say(`  shot ${name} @${width} — page ${height}px`);
}

async function openBatch(batchId) {
  await page.goto(`${BASE}/${TENANT}/finance/deposits/${batchId}`, {
    waitUntil: "domcontentloaded",
  });
  // ⚠ **WAIT FOR THE CONTENT, NOT FOR A CLOCK.** A fixed `waitForTimeout(3000)`
  // here made the whole P3.11 block report four failures on one run in three:
  // the page had not finished its first fetch, every tile was missing, and the
  // walk said so as though the tiles did not exist. A check that reports a slow
  // render as an absence is hard-won law 7, and it is worse than no check
  // because the next reader believes it.
  await page.waitForSelector(".kpi-grid .kpi", { timeout: 30000 });
  await page.waitForSelector("[data-plaintable] tbody tr", { timeout: 30000 });
  await page.waitForTimeout(400); // let the last paint settle before measuring styles
}

// ═══════════════════════════════════════════════════════════════════════════
// P3.11 — the locked batch that no longer sums
// ═══════════════════════════════════════════════════════════════════════════
if (DRIFT !== "") {
  say("\nP3.11 · a LOCKED batch with a returned cheque");
  await openBatch(DRIFT);
  const tiles = await page.evaluate(() =>
    [...document.querySelectorAll(".kpi")].map((k) => ({
      label: k.querySelector(".k")?.textContent?.trim() ?? "",
      value: k.querySelector(".v")?.textContent?.trim() ?? "",
      detail: k.querySelector(".d")?.textContent?.trim() ?? "",
    })),
  );
  say(`  KPI tiles found: ${tiles.length}`);
  for (const tile of tiles) say(`    · ${tile.label} = ${tile.value} — ${tile.detail}`);
  const live = tiles.find((tile) => tile.label.startsWith("Live payments"));
  check(live !== undefined, "a Live payments tile exists", `over ${tiles.length} tiles`);
  check(
    live !== undefined && live.detail.includes("Since the cut"),
    "the drift is NAMED on a batch that drifted",
    live?.detail,
  );
  const recorded = tiles.find((tile) => tile.label.startsWith("We recorded"));
  check(
    live !== undefined && recorded !== undefined && live.value !== recorded.value,
    "live and recorded genuinely differ on screen",
    `${recorded?.value} vs ${live?.value}`,
  );
  const marked = await page.evaluate(() => {
    const rows = [...document.querySelectorAll("[data-plaintable] tbody tr")];
    return {
      rows: rows.length,
      flagged: rows.filter((r) => (r.textContent || "").includes("Reversed")).length,
    };
  });
  check(
    marked.flagged === 1,
    "exactly ONE member line is marked reversed",
    `${marked.flagged} of ${marked.rows} rows`,
  );
  await shoot("p3-11-locked-batch-drift", 1440);
  await shoot("p3-11-locked-batch-drift", 1280);
}

// ═══════════════════════════════════════════════════════════════════════════
// P3.10 — the three acts, and DEF-PAY-6652's measured alignment
// ═══════════════════════════════════════════════════════════════════════════
if (SHORT !== "") {
  say("\nP3.10 · row actions on the batch lines");
  await openBatch(SHORT);

  const actions = await page.evaluate(() => {
    const rows = [...document.querySelectorAll("[data-plaintable] tbody tr")];
    const first = rows[0];
    if (!first) return { rows: 0 };
    const cell = first.querySelector("td:last-child");
    return {
      rows: rows.length,
      headers: [...document.querySelectorAll("[data-plaintable] thead th")].map((th) =>
        (th.textContent || "").trim(),
      ),
      // ⚠ The `…` is a `<summary>`, NOT a button — `RowActionsMore` is a
      // native `<details>` disclosure. A first version of this check counted
      // `a, button` and expected three, which made a correct screen FAIL: the
      // check was wrong, not the screen.
      visible: [...(cell?.querySelectorAll(":scope > span > a, :scope > span > button") ?? [])].map(
        (el) => el.getAttribute("aria-label"),
      ),
      moreTrigger: cell?.querySelector("[data-row-more] > summary")?.getAttribute("aria-label") ?? null,
      overflow: [...(cell?.querySelectorAll("[data-row-more] button") ?? [])].map((el) =>
        (el.textContent || "").trim(),
      ),
      openHref: cell?.querySelector("a")?.getAttribute("href") ?? null,
    };
  });
  say(`  member rows: ${actions.rows}`);
  say(`  columns: ${JSON.stringify(actions.headers)}`);
  say(`  visible row actions: ${JSON.stringify(actions.visible)}`);
  say(`  the … trigger: ${JSON.stringify(actions.moreTrigger)}`);
  say(`  behind the …: ${JSON.stringify(actions.overflow)}`);
  check(actions.headers?.includes("Actions"), "the table has an ACTIONS column");
  check(
    actions.visible?.length === 2 && actions.moreTrigger !== null,
    "B14 rule 15 — exactly TWO acts are visible, then a … disclosure",
    `${actions.visible?.length} visible + ${actions.moreTrigger === null ? "no" : "a"} …`,
  );
  check(actions.overflow?.includes("Reverse"), "Reverse lives behind the …");
  check(
    actions.openHref !== null && !/[0-9a-f]{8}-[0-9a-f]{4}/.test(actions.openHref),
    "B14 rule 31 — the open link carries the PMT number, not a uuid",
    actions.openHref,
  );

  // ⚠ DEF-PAY-6652 — MEASURED, never asserted by class name.
  const money = await page.evaluate(() => {
    const cells = [...document.querySelectorAll("[data-plaintable] td")].filter((td) =>
      (td.textContent || "").includes("$"),
    );
    return cells.slice(0, 4).map((td) => ({
      className: td.className,
      computed: getComputedStyle(td).textAlign,
      text: (td.textContent || "").trim().slice(0, 14),
    }));
  });
  say(`  money cells measured: ${money.length}`);
  for (const cell of money) {
    say(`    · ${cell.text} — computed text-align: ${cell.computed}`);
  }
  check(
    money.length > 0 && money.every((cell) => cell.computed === "right"),
    "DEF-PAY-6652 — every money cell is RIGHT-aligned in the browser",
    `${money.filter((c) => c.computed === "right").length} of ${money.length}`,
  );

  await shoot("p3-10-row-actions", 1440);
  await shoot("p3-10-row-actions", 1280);

  // The … opens, so the reverse is reachable.
  await page.evaluate(() => {
    const d = document.querySelector("[data-plaintable] [data-row-more]");
    if (d) d.setAttribute("open", "");
  });
  await page.waitForTimeout(400);
  await shoot("p3-10-overflow-open", 1440);

  // ═════════════════════════════════════════════════════════════════════════
  // P3.12 — the multi-line resolve, driven to $0.00
  // ═════════════════════════════════════════════════════════════════════════
  say("\nP3.12 · the resolve modal, driven");
  await openBatch(SHORT);
  const resolve = page.getByRole("button", { name: "Resolve difference" });
  const hasResolve = (await resolve.count()) > 0;
  check(hasResolve, "the Resolve difference door is on the page head");
  if (hasResolve) {
    await resolve.click();
    await page.waitForTimeout(700);

    const readResidual = () =>
      page.evaluate(
        () => document.querySelector('[data-testid="resolve-residual"]')?.textContent ?? "",
      );
    const commitBlocked = () =>
      page.evaluate(() => document.body.innerText.includes("Explain the whole difference first."));

    say(`  opens with: ${await readResidual()}`);
    await shoot("p3-12-resolve-opened", 1440);

    // The blueprint's worked case: the shortfall is a FEE and a CHARGEBACK.
    await page.fill("#resolutions\\.0\\.reason_code", "processor_fee");
    await page.fill("#resolutions\\.0\\.gl_account_id", "bank_fees");
    await page.fill("#resolutions\\.0\\.amount", "-147.50");
    await page.fill("#resolutions\\.0\\.note", "Sep settlement");
    await page.waitForTimeout(300);
    const partial = await readResidual();
    say(`  after the fee alone: ${partial}`);
    check(partial.includes("25.00"), "the residual names what is still unexplained", partial);
    check(await commitBlocked(), "Record is blocked while a residual stands");
    await shoot("p3-12-residual-outstanding", 1440);

    await page.getByRole("button", { name: "+ Add explanation" }).click();
    await page.waitForTimeout(300);
    await page.fill("#resolutions\\.1\\.reason_code", "returned_item");
    await page.fill("#resolutions\\.1\\.gl_account_id", "accounts_receivable");
    await page.fill("#resolutions\\.1\\.amount", "-25.00");
    await page.fill("#resolutions\\.1\\.note", "Case 55120");
    await page.waitForTimeout(400);
    const settled = await readResidual();
    say(`  after the chargeback: ${settled}`);
    check(settled.includes("0.00"), "the residual reaches $0.00", settled);
    check(!(await commitBlocked()), "Record is offered once the residual is zero");

    const rows = await page.evaluate(
      () => document.querySelectorAll('[id^="resolutions."][id$=".amount"]').length,
    );
    check(rows === 2, "two explanation rows, each with its own reason and GL", `${rows} rows`);
    await shoot("p3-12-residual-zero", 1440);
    await shoot("p3-12-residual-zero", 1280);
  }
}

say(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`);
fs.writeFileSync(`${SHOTS}/walkthrough.txt`, lines.join("\n") + "\n");
await browser.close();
process.exit(failures === 0 ? 0 : 1);
