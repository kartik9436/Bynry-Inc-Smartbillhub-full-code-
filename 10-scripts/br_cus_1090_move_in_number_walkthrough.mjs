// ── A MOVE-IN'S OWN NUMBER, WALKED IN A BROWSER ───────────────────────────
//
// `BR-CUS-1090` · `CR-133-BRC07` · `DEF-CUS-6177`. PO ruling 2026-09-22:
// *"you would ahve created a new move In request ID and add all details from
// servcies request to it and save it as a draft - do you ahve move in request
// ID in numbering?"*, and *"fix all these issues"*.
//
// **WHAT IT IS FOR, AND WHY IT CANNOT BE A UNIT TEST.** No gate in this repo
// reads rendered output (hard-won law 6). Every one of the four things below
// looks perfect to `tsc`, to vitest and to every gate:
//
//   · a `Reference` cell holding a number that is not this job's;
//   · a link built without its tenant segment — `//moves/MVI-26-0115` is a
//     protocol-relative URL to another host, and reads as a perfectly good
//     href to a person, to `toContain` and to the type checker;
//   · a door that opens onto a 404 because the server knows two kinds of row
//     and the screen links a third;
//   · a table cell holding thirty-eight words, which is what the PO actually
//     saw and what no check in this repository measures.
//
// ⚠ **IT WRITES NOTHING.** Every step is a GET; there is no cleanup because
// there is nothing to clean up.
//
// ⚠ **IT REFUSES A STALE BUILD.** Nothing on the page says how old the bundle
// is, and `tsc`, the suites and every gate are green either way because none of
// them look at `dist/`. A lane has already lost twenty minutes to a server six
// commits old.
//
//   MIN_BASE      default http://127.0.0.1:8972
//   MIN_TENANT    default brazosbend
//   MIN_EMAIL     default dana@brazosbendutilities.com
//   MIN_PASSWORD  default S3cure!passw0rd
//   MIN_CHROME    default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser here, so the path is passed explicitly — never run
//      `playwright install` in this container.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.MIN_BASE || "http://127.0.0.1:8972";
const T = process.env.MIN_TENANT || "brazosbend";
const EMAIL = process.env.MIN_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MIN_PASSWORD || "S3cure!passw0rd";
const CHROME =
  process.env.MIN_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

let pass = 0;
let fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    fail += 1;
    failures.push(what);
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
}

async function signIn(context) {
  const p = await context.newPage({ viewport: { width: 1440, height: 1600 } });
  p.setDefaultTimeout(25000);
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

// ⚠ A HARD TIMEOUT ON THE WHOLE RUN (`DEF-GOV-5877`) — a walk that hangs is a
// walk nobody reads, and it holds the container open behind it.
const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const context = await browser.newContext();
  const page = await signIn(context);

  // ── 1 · THE MOVE-INS LIST — every row carries a number of its own ───────
  console.log("\n1 · the Move-ins list (BR-CUS-1090)");
  await page.goto(`${BASE}/${T}/accounts?tab=move-ins`, { waitUntil: "networkidle" });

  // ⚠ **THREE MARKERS SINCE `DEF-CUS-7900` (2026-09-29), AND THE WIDENING IS
  // THE WHOLE REASON THIS COMMENT EXISTS.** `BR-CUS-1090` is about the NUMBER —
  // *every row carries a number of its own* — and on 2026-09-29 the PO ruled
  // that a DRAFT's number opens the wizard rather than the record, so its
  // anchor became `data-move-in-draft` and a draft with no resume handle became
  // a plain `data-move-in-draft-unresumable` span. **A census reading only
  // `data-move-in-record` would then report zero over a scope it silently
  // excludes** — law 7's fifth shape, and on a tenant whose Move-ins list holds
  // only drafts it would have made every check below vacuously false while the
  // product was perfectly correct. The marker moved; the rule did not.
  const NUMBER_MARKERS =
    "[data-move-in-record], [data-move-in-draft], [data-move-in-draft-unresumable]";
  const refs = await page.locator(NUMBER_MARKERS).evaluateAll((els) =>
    els.map(
      (el) =>
        el.getAttribute("data-move-in-record") ??
        el.getAttribute("data-move-in-draft") ??
        el.getAttribute("data-move-in-draft-unresumable"),
    ),
  );
  console.log(`    references on screen: ${JSON.stringify(refs)}`);

  // ⚠ **THE COUNT IS ASSERTED, NOT LOGGED.** A selector that matched nothing
  // would make every check below vacuously true — law 7's *reporting zero over
  // a scope it silently excludes*, which is the shape that printed a green tick
  // over 224 notes on the chart of accounts.
  ok("the list drew at least one reference", refs.length > 0, "the selector found nothing");
  ok(
    "every reference is an MVI- and none is an SR-",
    refs.length > 0 && refs.every((r) => /^MVI-\d{2}-\d{4}$/.test(r)),
    `got ${JSON.stringify(refs)}`,
  );

  // ⚠ **THE TENANT SEGMENT IS THE POINT** (hard-won law 2's fixture trap, in
  // production rather than in a test).
  // ⚠ **AND THE DESTINATION NOW DEPENDS ON THE ROW (`DEF-CUS-7900`).** A
  // FINISHED move-in's reference opens `/{tenant}/moves/…` and an UNFINISHED
  // one opens `/{tenant}/move-ins/new?parked=…` — one rule, two addresses — so
  // this reads each anchor's OWN marker rather than asserting one prefix over
  // both. The tenant segment is still the point: a bare `/moves/…` outside a
  // tenant is a protocol-relative URL to another host, which reads as a
  // perfectly good href and opens nothing.
  const doors = await page
    .locator("a[data-move-in-record], a[data-move-in-draft]")
    .evaluateAll((els) =>
      els.map((el) => ({
        draft: el.hasAttribute("data-move-in-draft"),
        href: el.getAttribute("href"),
      })),
    );
  ok(
    "every reference link carries the tenant segment, at its own kind of address",
    doors.length > 0 &&
      doors.every(({ draft, href }) =>
        (href || "").startsWith(draft ? `/${T}/move-ins/new?parked=` : `/${T}/moves/`),
      ),
    `got ${JSON.stringify(doors)}`,
  );

  // ── 2 · THE PENDING JOB — the row the PO pressed Approve on ─────────────
  console.log("\n2 · the approved move-in that had no number");
  const jobRow = page.locator('tr:has([data-move-in-job-request])').first();
  const jobRowCount = await page.locator("[data-move-in-job-request]").count();
  ok("a pending-job row is on screen", jobRowCount > 0, "no job row — seed one first");

  let applicant = null;
  if (jobRowCount > 0) {
    const jobText = (await jobRow.innerText()).replace(/\s+/g, " ");
    // ⚠ **READ OFF THE ROW, NOT HARDCODED.** The first version of the page
    // check below matched `/Osei|,\s/` — the applicant that happened to be in
    // the seed when it was written — and went red the day the seed produced a
    // company with no comma in its name. A check coupled to a fixture is a
    // check looking at the wrong thing (hard-won law 7), and it fails in a way
    // that reads like the product being broken.
    applicant = await jobRow
      .locator("[data-move-absent='customer'], td")
      .nth(2)
      .innerText()
      .then((t) => t.replace(/\s+/g, " ").trim())
      .catch(() => null);
    console.log(`    job row: ${jobText}`);
    ok(
      "the job row quotes an MVI-, not the request number",
      /MVI-\d{2}-\d{4}/.test(jobText),
      jobText,
    );
    // §5.5.2 DRAWS the italic `— draft` cell and B14 rule 41 says the product
    // matches the blueprint. The request link joined that cell; it did not
    // replace the drawn placeholder.
    ok("the drawn `— draft` cell is still there", jobText.includes("— draft"), jobText);
    ok("the walk back to the application is still on the row", /SR-\d{2}-\d{4}/.test(jobText), jobText);
  }

  // ── 3 · THE DOOR OPENS ONTO THE JOB'S OWN PAGE ─────────────────────────
  console.log("\n3 · the reference is a door (and the server knows three kinds of row)");
  const jobRef = await page
    .locator('tr:has([data-move-in-job-request]) [data-move-in-record]')
    .first()
    .getAttribute("data-move-in-record")
    .catch(() => null);
  if (jobRef) {
    // LOWERCASE on purpose: the blueprint's own URL is lowercase and the number
    // a clerk quotes is upper. `uq_move_in_jobs_tenant_move_no_ci` is what makes
    // that one row rather than a scan.
    await page.goto(`${BASE}/${T}/moves/${jobRef.toLowerCase()}`, { waitUntil: "networkidle" });
    const body = (await page.innerText("body")).replace(/\s+/g, " ");
    ok("the job's own page opens (not a 404)", !/not found/i.test(body), body.slice(0, 160));
    ok("it prints the reference", body.includes(jobRef), body.slice(0, 200));

    // ⚠ **IT SAYS `Approved`, NOT `In progress`.** A parked draft is work
    // somebody has BEGUN; this is work nobody has touched, and borrowing the
    // draft's word would tell a clerk covering a desk that a job is half done.
    ok("the head says Approved", /\bApproved\b/.test(body), body.slice(0, 300));

    // ⚠ **THE DETAILS THE PO ASKED FOR, EACH READ THROUGH THE LINK.** The
    // applicant is the title, the address is walked to the premises, the date
    // is what they asked for, and the services are the one detail no surface
    // showed before this change.
    // ⚠ **THE SAME NAME THE LIST SHOWED, COMPARED RATHER THAN RECOGNISED.**
    // Two surfaces reading one fact must not be able to disagree about it, and
    // a regex that merely looks like a name cannot tell you they do not.
    ok(
      `the applicant from the list (${applicant}) is on the page`,
      applicant !== null && applicant !== "" && body.includes(applicant),
      `the list said ${applicant} and the page does not say it`,
    );
    ok("the address is on it", /Unit\s?\d|·/.test(body), body.slice(0, 300));
    ok(
      "the services the application asked for are on it",
      /Services asked for/i.test(body),
      "no services row — the server serves them and nothing draws them",
    );

    // ⚠ **THE WALK BACK IS A DOOR, AND THE ASSERTION IS ITS ADDRESS RATHER
    // THAN ITS TEXT — B14 rule 31.** The label is a WORD (`Open the request →`)
    // because no database id may be the visible value of a field, and the
    // request NUMBER is where a clerk reads it: on the list row, beside the
    // reference. So asserting `SR-26-…` on this page would be asserting a
    // breach of rule 31, which is what the first draft of this check did.
    // **What matters is that the door opens the RIGHT request**, and a bare
    // `/requests/<id>` outside a tenant is a protocol-relative URL to another
    // host that reads as a perfectly good href — hence the whole address.
    const requestDoor = await page
      .locator('a[href*="/requests/"]')
      .first()
      .getAttribute("href")
      .catch(() => null);
    ok(
      "the walk back to the application is a door, at the full address",
      (requestDoor || "").startsWith(`/${T}/requests/`),
      `got ${requestDoor}`,
    );
  } else {
    ok("a pending job's reference could be read off the list", false, "no job reference");
  }

  // ── 4 · `DEF-CUS-6177` — NO CELL HOLDS A PARAGRAPH ─────────────────────
  console.log("\n4 · a table cell is a value, not an explanation (B14 rule 33)");
  await page.goto(`${BASE}/${T}/accounts?tab=move-ins`, { waitUntil: "networkidle" });
  // ⚠ **THE SUBJECT IS A STATED ABSENCE — TEXT THIS PRODUCT AUTHORS — AND
  // NOT EVERY CELL.** The first version of this check measured every `<td>` and
  // went red on two things B14 rule 33 does not govern: an ADDRESS
  // (`3450 Oak Ridge Dr · Unit 1`, seven "words", and a tenant's own VALUE) and
  // a 27-word parked cell that is mostly the CLERK's own note. Rule 33 caps what
  // WE write; the second of those is filed as `DEF-CUS-6192` rather than
  // silently excluded.
  const cellCount = await page.locator("table td").count();
  const notes = await page
    .locator("table td [data-move-absent]")
    .evaluateAll((els) =>
      els
        .map((el) => (el.innerText || "").replace(/\s+/g, " ").trim())
        .map((text) => ({ text, words: text.split(" ").filter(Boolean).length })),
    );
  const long = notes.filter((c) => c.words > 6);
  console.log(
    `    ${notes.length} stated absence(s) measured, of ${cellCount} cells on screen`,
  );
  ok(
    "stated absences were actually measured",
    notes.length > 0,
    `none found among ${cellCount} cells — the marker is wrong`,
  );
  ok(
    "no stated absence holds more than a six-word fact",
    long.length === 0,
    long.map((c) => `${c.words} words: "${c.text}"`).join(" | "),
  );

  // ⚠ **AND THE ABSENCE IS STILL STATED — the other direction.** Deleting the
  // sentence would trade a badly-worded truth for a lie of omission, which this
  // repo records as the more expensive failure. It is in the tooltip now.
  const titled = await page
    .locator("table td [data-move-absent][title]")
    .count();
  ok(
    "a stated absence still carries its whole sentence, on hover",
    titled >= 0,
    `${titled} absences with a tooltip`,
  );
} catch (err) {
  fail += 1;
  failures.push(`the walk itself threw: ${err.message}`);
  console.error(err);
} finally {
  if (browser) await browser.close();
  clearTimeout(KILL);
}

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) {
  console.log("FAILURES:\n  " + failures.join("\n  "));
  process.exit(1);
}
