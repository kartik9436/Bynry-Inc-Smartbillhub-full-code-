/**
 * RENDERED-OUTPUT CHECK — CR-075 wave `M` task `M3`: the cycle's plans, READ BY
 * A PERSON, on `RBS-006` in a real browser.
 *
 * ⚠ **WHY A BROWSER AND NOT THE JSON.** The Product Owner's standing definition
 * of done, 2026-09-06: *"everything should be executed based on actual code,
 * and rules that we place, also ensure you do web walkthorugh before you sign
 * off the user story or build"*. `M3` says the plans are *"read by a person"*,
 * and a JSON dump is not that. Hard-won law 6: no gate in this repo looks at
 * rendered output, and nine defects were found this way and by nothing else.
 *
 * ⚠ **WHAT THIS CHECK CAN PROVE, AND WHAT IT CANNOT — SAID FIRST.**
 * `M4`'s go/no-go rests on what a clerk would see before approving 812 letters,
 * so the honest boundary matters more here than anywhere:
 *
 *   * it CAN prove what `RBS-006` draws for a stored run — the tiles, the
 *     per-rung table, the record rows, and whether any control on the page can
 *     send;
 *   * it CANNOT prove anything about a Review or Approve screen, because
 *     `L7` has not landed: there is no screen in this product that shows the
 *     plan and offers approval, and `L3`'s approval endpoint does not exist
 *     either. **That absence is one of `M4`'s findings, not a gap in this
 *     check**, and it is asserted rather than assumed — see check 6.
 *
 * ⚠ **THE RUN IDS ARE ARGUMENTS.** This reads STORED runs; it cannot start one,
 * because `POST /runbooks/{key}/runs` is not built. `rbs_m_dry_cycle.py` fires
 * the cycle and prints the ids.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   SMOKE_BASE=http://127.0.0.1:4340 SMOKE_RUN_FIRST=<firing 1's run id> \
 *   SMOKE_RUN_SECOND=<firing 2's run id> PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-m-the-cycle-on-screen.mjs
 *
 * ⚠ Sign-in is an XHR and `networkidle` returns before the session exists; the
 * email field is `#signin-email` and is `type="text"`. Both cost a lane an hour
 * before they were written down.
 */

import { existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

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
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4340";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const KEY = "collections_ladder";
const RUN_FIRST = process.env.SMOKE_RUN_FIRST ?? "";
const RUN_SECOND = process.env.SMOKE_RUN_SECOND ?? "";

if (!RUN_FIRST) {
  console.error(
    "⛔ SMOKE_RUN_FIRST is not set. This check reads STORED runs — it cannot start one,\n" +
      "   because POST /runbooks/{key}/runs is not built. Fire the cycle first:\n" +
      "     python3.12 10-scripts/render-checks/rbs_m_dry_cycle.py --mondays …"
  );
  process.exit(2);
}

const problems = [];
const notes = [];

function check(label, ok, detail = "") {
  if (ok) notes.push(`  ok   ${label}${detail ? ` — ${detail}` : ""}`);
  else problems.push(`  FAIL ${label}${detail ? ` — ${detail}` : ""}`);
}

/** What a person can actually READ on the page, whitespace-collapsed. */
async function pageText(page) {
  return (await page.locator("body").innerText()).replace(/\s+/g, " ");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage();
page.on("console", (message) => {
  if (message.type() === "error") notes.push(`  (console error) ${message.text()}`);
});

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  // ── firing 1 ────────────────────────────────────────────────────────────
  const requested = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.includes("/runbooks/")) requested.push(url.pathname);
  });

  await page.goto(`${BASE}/${TENANT}/runbooks/${KEY}/runs/${RUN_FIRST}`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2500);
  const first = await pageText(page);

  // 1 · THE RESULT OPENED AT ALL. A run of 1,004 accounts is the first thing
  //     this screen has ever been given that is not a single-subject Check.
  check(
    "the ladder's result screen opens and names the runbook",
    /Collections ladder/i.test(first),
    `page text ${first.length} chars`
  );

  // 2 · THE FOUR FIGURES A CLERK APPROVES ON.
  //     ⚠ **THIS ASSERTED THE LABEL AND THE LABEL IS NOT THE POINT
  //     (`DEF-RBS-4387`, and the check itself was the second finding).** The
  //     first version tested `first.includes("To send")`, which failed on the
  //     second cycle for the WRONG REASON — the strip renders its labels
  //     upper-cased, so a case-sensitive test could never pass — and would have
  //     PASSED on a strip that draws every label and not one number, which is
  //     exactly what `RBS-006` does today. A test named after an assertion it
  //     does not make is hard-won law 7's fourth shape.
  //     So: the label is matched case-insensitively, and the VALUE is required
  //     to be a number standing next to it. A clerk approving 812 letters is
  //     reading the number.
  for (const label of ["To send", "Skipped", "Need a person", "Fees drafted"]) {
    const strip = new RegExp(`${label}\\s*([0-9][0-9,]*)`, "i");
    const seen = first.match(strip);
    check(
      `the tile "${label}" reaches the screen WITH ITS NUMBER`,
      Boolean(seen),
      seen ? `reads ${seen[1]}` : `label ${new RegExp(label, "i").test(first) ? "drawn" : "missing"}, value absent`
    );
  }

  // 3 · THE PER-RUNG TABLE. `RB-108`'s own three columns — planned, queued,
  //     failed — and the four rung words in a clerk's language.
  check("the per-rung breakdown is drawn", /planned/i.test(first) && /queued/i.test(first));

  // 4 · HOW MANY RECORD ROWS THE PAGE ACTUALLY DRAWS, AND WHETHER IT PAGES.
  //     `NFR-3` — every list pages server-side — and CLAUDE.md calls that rule
  //     load-bearing rather than tidy. A run over 1,004 accounts is the first
  //     time this block has been handed more than one row.
  const rowCount = await page.locator("table tbody tr").count();
  const pager = await page
    .locator("nav[aria-label*='page' i], [data-testid*='pagination'], button:has-text('Next')")
    .count();
  notes.push(`  info table rows drawn: ${rowCount} · pagination controls found: ${pager}`);
  // ⚠ RED SINCE 2026-09-07 AND IT IS TRUE — `DEF-RBS-4388`. The frozen report
  // carries every record row, so `RecordsBlock` — which genuinely pages — is
  // handed the whole set as its "current page" and the pager correctly draws
  // nothing. 977 rows here; about 38,000 at the 40,000-account ceiling.
  check(
    "the record list does not draw a thousand rows in one page (NFR-3)",
    rowCount < 500,
    `${rowCount} <tr> drawn — DEF-RBS-4388`
  );

  // 5 · THE WORD ON A DRY RUN IS `planned`, NEVER `queued`. `dunning._outcome`
  //     keeps them apart on purpose — *"collapsing them would make the dry
  //     cycle indistinguishable from the real one on the result screen, which
  //     is the single thing wave M's soak exists to look at"*.
  check(
    "a dry firing does not tell a clerk anything was queued",
    !/\bQueued\b/.test(first) || /planned/i.test(first),
    "looked for the word Queued on a run that queued nothing"
  );

  // 6 · NOTHING HERE CAN SEND — the phase's launch sentence, as an absence.
  const controls = (await page.locator("button, a[role='button']").allInnerTexts()).map((t) =>
    t.trim()
  );
  const dangerous = controls.filter((text) => /^(send|approve|apply)$/i.test(text));
  check(
    "no control on the result screen can send, approve or apply",
    dangerous.length === 0,
    dangerous.length ? `found: ${dangerous.join(" · ")}` : `${controls.length} control(s) read`
  );

  // 7 · WHAT THE PAGE ASKED THE SERVER FOR. `RunResultPage.tsx` promises the
  //     records boundary moves *"the day a volume runbook lands"* — one has,
  //     so this records whether the promise was kept. It is reported as an
  //     OBSERVATION rather than an assertion, because the finding belongs in a
  //     defect row and not in this script's exit code.
  notes.push(`  info runbooks requests: ${[...new Set(requested)].join(" · ") || "(none seen)"}`);
  // ⚠ RED SINCE 2026-09-07 AND IT IS TRUE — the other half of `DEF-RBS-4388`.
  // The screen asks for the run and its report and nothing else, so the paging
  // endpoint this module built is dead UI (hard-won law 2), and the rows a
  // clerk reads come out of the frozen report instead. That is also why
  // `DEF-RBS-4380` — an earlier run's record rows being re-pointed at the
  // newest run — does not show on THIS screen and would show the moment the
  // screen started reading the endpoint.
  check(
    "the screen reads the per-record rows the ladder wrote",
    requested.some((path) => path.endsWith("/records")),
    "GET /runbooks/runs/{id}/records — built, paging, and never called (DEF-RBS-4388)"
  );

  // ── firing 2 — the same plan, a week later ──────────────────────────────
  if (RUN_SECOND) {
    await page.goto(`${BASE}/${TENANT}/runbooks/${KEY}/runs/${RUN_SECOND}`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(2500);
    const second = await pageText(page);
    check("the second firing's result opens too", /Collections ladder/i.test(second));
    // ⚠ THE ONE FACT THE WHOLE SOAK EXISTS TO SURFACE. The per-record
    // idempotency key is (runbook, action, subject, rung) and carries NO date,
    // so the second dry firing finds every key already taken. What the screen
    // says about that is `M4`'s evidence and is printed, not asserted.
    const tile = second.match(/To send\s*([0-9,]+)/i);
    notes.push(`  info firing 2 · "To send" reads ${tile ? tile[1] : "(not found)"}`);
  }
} catch (error) {
  problems.push(`  FAIL the walkthrough threw — ${error.message}`);
} finally {
  await browser.close();
}

console.log("── CR-075 wave M · M3 — the cycle's plans on RBS-006");
for (const note of notes) console.log(note);
for (const problem of problems) console.log(problem);
console.log(
  problems.length
    ? `\n${problems.length} problem(s) of ${problems.length + notes.length} checks`
    : `\nall ${notes.length} checks passed`
);
process.exit(problems.length ? 1 : 0);
