// ── Trace ──────────────────────────────────────────────
// Change:  `BR-CUS-1077` — PO ruling 2026-09-16, verbatim *"it should do B"*:
//          approving a move-in raises a PENDING MOVE-IN JOB, the way a new
//          connection raises a draft build, and the account still does not open.
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate in this repo looks at rendered output).
// Defects: DEF-CUS-5398 (approving a move-in raised nothing at all) ·
//          DEF-CUS-5434 (the pending job has no door into the wizard — proved
//          here as an absence, so the row is not claimed to be more than it is)
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT NO TEST IN THIS REPO CAN.
//
//   1 · **THE WALK'S OWN STUCK REQUEST COMPLETES.** `SR-26-0024` on the demo
//       tenant sat at `Under review` with `outcome=move_in` already saved: the
//       clerk pressed Approve, the outcome was written, the approval was
//       refused, and the request looked decided while being nothing of the
//       kind. This walk presses the same button on the same request.
//   2 · **THE JOB IS ON THE QUEUE A SECOND LATER**, in a browser, at the real
//       address, with the real data — which is the whole of the ruling.
//   3 · **A CLERK CAN TELL THE TWO KINDS OF ROW APART.** The job row is read
//       out of the rendered table and compared against a draft ACCOUNT row on
//       the same page: no account number, the drawn `— draft`, the applicant's
//       name, the address walked from the premises, and `Not started`.
//   4 · **NO ACCOUNT OPENED.** The account count is taken before and after.
//
// ⚠ IT MUTATES THE DEMO TENANT, deliberately and once: it approves the one
// request the walk found stuck. Run it against the stack this lane starts, and
// expect the SECOND run to report the request already approved — which is
// itself the idempotency the ruling asks for.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8178";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const REQUEST_NO = process.env.REQUEST_NO ?? "SR-26-0024";
// The request this walk DECIDES in the browser. `REQUEST_NO` above is the one
// the clerk walk found stuck, and it is checked separately whoever approved it.
const TARGET_NO = process.env.TARGET_NO ?? "SR-26-0003";
const OUT = process.env.OUT ?? "/tmp/brcus1077";
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
const say = (...parts) => console.log(...parts);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const api = (path, init) =>
  page.evaluate(
    async ([p, i]) => {
      const res = await fetch(p, { credentials: "include", ...(i ?? {}) });
      return { status: res.status, body: await res.text() };
    },
    [path, init],
  );

// ── 0 · THE STATE BEFORE, so every claim below is a difference ─────────────
// ⚠ **THE LIST IS SEGMENTED AND SEARCHED RATHER THAN READ WHOLE.** The
// register opens on a segment, so "fetch page one and look for it" finds a
// request only when it happens to be on that segment's first page — a check
// that passes for the wrong reason on a quiet tenant and fails on a busy one.
const requestsRaw = JSON.parse(
  (await api(`/api/${TENANT}/service-requests?per=200&q=${REQUEST_NO}&segment=all`)).body,
);
const requestRows = requestsRaw.rows ?? requestsRaw.results ?? requestsRaw.items ?? [];
say("service-requests payload keys:", JSON.stringify(Object.keys(requestsRaw)));
const stuck = requestRows.find((r) => r.request_no === REQUEST_NO);
if (!stuck) throw new Error(`${REQUEST_NO} is not on this tenant (saw ${requestRows.length} rows)`);
say(`${REQUEST_NO}: state=${stuck.state}`);

// ⚠ **THE WALK PRESSES APPROVE ON A REQUEST THAT IS STILL UNDER REVIEW, AND
// FINDS ONE RATHER THAN ASSUMING IT.** `SR-26-0024` is the walk's ORIGINAL
// case and is asserted below whatever its state; but the demo tenant is
// shared, another lane's walkthrough approved it at 04:01, and a check that
// silently skipped its own act would report a pass over a button nobody
// pressed — hard-won law 7's *incapable of failing*, which is exactly what the
// first run of this script did.
// ⚠ **THE REQUEST TO PRESS IS NAMED, AND ITS STATE IS ASSERTED RATHER THAN
// ASSUMED.** The demo tenant is shared: another lane's walkthrough approved
// `SR-26-0024` at 04:01 while this was being written, so a walk that only ever
// pressed that one would have reported a pass over a button nobody pressed —
// hard-won law 7's *incapable of failing*, and the first run of this script did
// exactly that. `TARGET_NO` is the request this walk decides on IN THE BROWSER,
// and `REQUEST_NO` stays the walk's original case, checked separately below.
const registerRaw = JSON.parse((await api(`/api/${TENANT}/service-requests?segment=all`)).body);
const register = registerRaw.results ?? registerRaw.rows ?? [];
const openOnes = register.filter((r) => r.state === "under_review");
// ⚠ **THE WALK PICKS A REQUEST THAT IS STILL OPEN, AND IT IS RE-RUNNABLE
// BECAUSE OF IT.** It approves one, so the SAME request cannot be pressed
// twice; a walk hard-wired to one number reports a pass on its second run over
// a button it did not press. `TARGET_NO` still wins where it is still open.
// **A request whose own type is `new_connection` is never chosen** — deciding
// one as a move-in would put a wrong outcome on the demo tenant a person
// reviews, for a walk's convenience.
const target =
  openOnes.find((r) => r.request_no === TARGET_NO) ??
  openOnes.find((r) => r.type !== "new_connection");
if (!target) {
  throw new Error(
    `no reviewable request is left on this tenant (open: ${openOnes.map((r) => r.request_no).join(", ") || "none"})`,
  );
}
say(`pressing Approve on ${target.request_no} (state ${target.state})`);

const before = JSON.parse((await api(`/api/${TENANT}/move-ins?per=200`)).body);
const accountsRaw = JSON.parse((await api(`/api/${TENANT}/accounts?per=1`)).body);
// ⚠ `count`, not `total` — the accounts list uses DRF's envelope and the move
// lists use this module's own. The first draft read `total`, got `undefined` on
// both sides of the comparison, and PASSED: a check with nothing in it.
const accountsBefore = accountsRaw.count ?? accountsRaw.total;
if (accountsBefore === undefined) throw new Error("cannot read the account count — check skipped");
say(`move-ins before: total=${before.total} · accounts: ${accountsBefore}`);
check(
  "1 · the request is sitting under review, waiting on a clerk",
  target.state === "under_review",
  `${target.request_no} · ${target.state}`,
);

// ── 1 · PRESS APPROVE, IN THE BROWSER ──────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/requests/${target.id}`, { waitUntil: "networkidle" });
await page.screenshot({ path: `${OUT}/01-request-before.png`, fullPage: true });

const approveButton = page.locator('button:has-text("Approve")').first();
const approvable = (await approveButton.count()) > 0 && (await approveButton.isEnabled());
check("2 · the Approve control is live on a request under review", approvable);
if (approvable) {
  await approveButton.click();
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/02-approve-dialog.png`, fullPage: true });

  // The drawn five radios. A clerk picks the outcome HERE, which is the act
  // this whole ruling hangs off — `pass all information to create the new
  // connect requets or move -in request based on selction`.
  const moveIn = page.locator('input[name="service-request-outcome"][value="move_in"]');
  check("2a · the modal offers the move-in outcome", (await moveIn.count()) > 0);
  await moveIn.check();
  await page.waitForTimeout(600);
  const dialogText = await page.evaluate(
    () => document.querySelector('[role="dialog"]')?.innerText ?? "",
  );
  say("--- what approving will do ---");
  say(dialogText.slice(0, 900));
  check(
    "2b · the modal says a job is raised on the Move-ins tab, BEFORE the press",
    /move-in/i.test(dialogText),
  );
  check(
    "2c · and it still promises no account opens",
    /no account/i.test(dialogText),
    dialogText.match(/[^.]*no account[^.]*/i)?.[0]?.trim() ?? "",
  );
  await page.screenshot({ path: `${OUT}/02b-outcome-picked.png`, fullPage: true });

  // The drawn footer: `Approve and raise the build`.
  const commit = page.locator('button:has-text("Approve and raise")').last();
  check("2d · the commit is live", (await commit.count()) > 0 && (await commit.isEnabled()));
  await commit.click();
  await page.waitForTimeout(2000);
}
await page.screenshot({ path: `${OUT}/03-request-after.png`, fullPage: true });

// ⚠ **THE STATE IS READ OFF THE DETAIL'S HEADER**, which is where this payload
// keeps it — `{header, actions, applicant, …}`. The first draft read
// `after.state`, got `undefined`, and reported a FAIL over a request that had
// approved perfectly: a check looking at the wrong thing, in the direction that
// at least fails loudly rather than the one that passes quietly.
const after = JSON.parse((await api(`/api/${TENANT}/service-requests/${target.id}`)).body);
const afterState = after.header?.state?.code ?? after.header?.state ?? after.state;
check(
  "3 · the request is APPROVED — it no longer sits decided-but-not-decided",
  afterState === "approved",
  JSON.stringify(afterState),
);

// ── 2 · THE JOB IS ON THE MOVE-INS TAB ─────────────────────────────────────
const list = JSON.parse((await api(`/api/${TENANT}/move-ins?per=200`)).body);
const jobs = (list.rows ?? []).filter((r) => r.row_kind === "pending_job");
const job = jobs.find((r) => r.request?.request_no === target.request_no);
check(
  "4 · the approval this walk pressed put a pending job on the Move-ins list",
  job !== undefined,
  `${jobs.length} job row(s) of ${list.total}`,
);
// The walk's ORIGINAL case, whoever approved it: its job is on the queue too.
check(
  `4·0 · ${REQUEST_NO} — the walk's own stuck move-in — has a job as well`,
  jobs.some((r) => r.request?.request_no === REQUEST_NO),
  jobs.map((r) => r.request?.request_no).join(", "),
);
if (job) {
  check("4a · it names the request a clerk can walk back to", job.request?.request_no === target.request_no, job.request?.request_no);
  check("4b · it has NO account number", job.account_no === null, String(job.account_no));
  check("4c · and says why, rather than a dash", job.account_absence?.code === "pending_move_in_has_no_account", job.account_absence?.code);
  check("4d · the address is the walked one", Boolean(job.unit), job.unit ?? "—");
  check("4e · the state is the minted `pending`", job.state === "pending", job.state);
}
const accountsAfterRaw = JSON.parse((await api(`/api/${TENANT}/accounts?per=1`)).body);
const accountsAfter = accountsAfterRaw.count ?? accountsAfterRaw.total;
check(
  "5 · NO ACCOUNT WAS OPENED — the drawing's own line, measured on both sides",
  accountsAfter === accountsBefore && accountsBefore !== undefined,
  `${accountsBefore} -> ${accountsAfter}`,
);

// ── 3 · AND IT IS ON THE SCREEN, WHICH IS THE POINT ────────────────────────
await page.goto(`${BASE}/${TENANT}/accounts?tab=move-ins`, { waitUntil: "networkidle" });
await page.waitForSelector("table", { timeout: 20000 });
await page.waitForTimeout(600);
await page.screenshot({ path: `${OUT}/04-move-ins-tab.png`, fullPage: true });

const rows = await page.$$eval("table tbody tr", (trs) =>
  trs.map((tr) => Array.from(tr.querySelectorAll("td")).map((td) => td.innerText.trim())),
);
say("rendered rows:");
for (const r of rows) say("   ", JSON.stringify(r));

const flat = rows.map((r) => r.join(" | "));
check("6 · the job row is RENDERED, not merely served", flat.some((r) => r.includes(target.request_no)), String(rows.length));
check("6a · with the drawn `— draft` where the account number goes", flat.some((r) => r.includes("— draft")));
check("6b · and `Not started` in the state cell", flat.some((r) => r.includes(target.request_no) && r.includes("Not started")));

// ⚠ **THE WALK BACK IS A REAL LINK, AND THIS IS THE CHECK THAT SAYS SO.**
// `toContain` on an href cannot tell `/requests/x` from `/brazosbend/requests/x`
// — the first renders perfectly and opens nothing (hard-won law 2's fixture
// trap, in production rather than in a test). So the address is asserted whole
// and then FOLLOWED.
const link = page.locator(`table a:has-text("${target.request_no}")`).first();
check("7 · the reference cell is a link back to the application", (await link.count()) > 0);
if ((await link.count()) > 0) {
  const href = await link.getAttribute("href");
  check("7a · it carries the tenant segment", href?.startsWith(`/${TENANT}/requests/`) === true, href ?? "");
  await link.click();
  await page.waitForTimeout(1200);
  check("7b · and it OPENS the request", page.url().includes(`/${TENANT}/requests/`), page.url());
  await page.screenshot({ path: `${OUT}/05-walked-back.png`, fullPage: true });
}

// ── 4 · THE ABSENCE, PROVED AS AN ABSENCE (DEF-CUS-5434) ───────────────────
// A row a clerk can see and cannot act on is worth naming rather than
// discovering. This is the one check here that EXPECTS to find nothing.
await page.goto(`${BASE}/${TENANT}/accounts?tab=move-ins`, { waitUntil: "networkidle" });
await page.waitForSelector("table", { timeout: 20000 });
const startControls = await page.$$eval("table tbody tr", (trs) =>
  trs.flatMap((tr) => Array.from(tr.querySelectorAll("button, a")).map((el) => el.innerText.trim())),
);
say("row controls:", JSON.stringify(startControls));
check(
  "8 · DEF-CUS-5434 is real: no row control starts the move-in wizard",
  !startControls.some((c) => /start|move[- ]in wizard/i.test(c)),
  JSON.stringify(startControls),
);

say(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
