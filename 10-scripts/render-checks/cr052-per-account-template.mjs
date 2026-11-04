#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-052 task 18 — "Render checks for the bill document — the
//           twelve-month block, the message, ways-to-pay, and the PER-ACCOUNT
//           TEMPLATE". The first three were already covered; this is the fourth.
// Screens:  S30 → "View the bill as sent"
// Rules:    BR-BIL-025 (the template resolves per ACCOUNT: account override →
//           category default → tenant fallback) · BR-BIL-026 (template AND
//           version are pinned at issue; publishing affects only future bills) ·
//           BR-BIL-027 (publishing is the System Admin's narrow right) ·
//           B14 rule 31 (no database id is the visible value of a field) ·
//           hard-won law 1 (a comment claiming a guarantee is not the
//           guarantee) · law 6 (no gate in this repo reads rendered output)
// Defects:  DEF-2826 (this check found it) · DEF-2701 (no door writes
//           accounts.template_override_id)
// ───────────────────────────────────────────────────────
/**
 * TWO BILLS, TWO PINS, ONE SCREEN — does the page draw the layout it names?
 *
 * ⚠ **WHAT THE OTHER THREE ITEMS OF TASK 18 ARE COVERED BY, so nobody writes a
 * second harness for them.** A second check asserting what a first one asserts
 * is worse than none: both have to be maintained and neither is trusted.
 *
 *   · **the twelve-month block** → `cr052-usage-history.mjs`, 9 assertions —
 *     twelve slots per service, a measured month drawing real pixels in the
 *     ratio of its figure, an absent month drawing NO bar (never a zero one),
 *     no database id, a bill without a block drawing no panel, and the same
 *     months on the printable PDF.
 *   · **the message** and **ways to pay** → `cr053-bill-surface.mjs` §15 and
 *     its CR-052 task 11 section — the block is present, it is drawn as PROSE
 *     at a real reading measure with computed `white-space: pre-line`, an
 *     unwritten message states its consequence in one sentence, and no bill
 *     whose tenant has written nothing contains `1.5%`, `$5.00`, `greater of`
 *     or `late fee of`.
 *
 * **THE FOURTH — the per-account template — was covered by nothing**, and this
 * is it.
 *
 * ── WHAT "PER-ACCOUNT" CAN AND CANNOT BE CHECKED TODAY, STATED UP FRONT ────
 * `issue._pin_for_account` runs BR-BIL-025's three legs per draft. **Two of the
 * three cannot be reached through any door**, and that is a fact about the
 * product rather than a limit of this file:
 *
 *   · the **account override** leg has no writer — `accounts.template_override_id`
 *     is built (migration `customers 0034`) and nothing writes it (`DEF-2701`);
 *   · the **category default** leg has no writer either — `templates_service
 *     .create_template` takes a `category` and has NO CALLER in the product.
 *     `templates_api` says so in its own words and calls it deliberate: *"a
 *     second category-less template is the two-fallback collision
 *     `TEMPLATES_UNAVAILABLE` reports, and closing it is a unique index."* So
 *     no tenant can hold two templates, and every account resolves the
 *     fallback.
 *
 * **What IS reachable, and it is the half that reaches a customer:** a bill is
 * pinned to a template AND VERSION at issue, and the page must draw THAT pin —
 * not the tenant's current choice. That is the observable consequence of
 * resolving per account, and it is what breaks first: `_layout_key_of`'s own
 * docstring names the failure as *"a 2026 bill starts printing on a 2031
 * template"*.
 *
 * ── WHY A BROWSER AND NOT A DOM TEST ──────────────────────────────────────
 * Every band on this page renders for every layout, so a `toContain` case
 * asserting a band is present passes on the bug. The question is not *is the
 * band there* but **do two bills on two layouts LOOK DIFFERENT**, and only two
 * real pages side by side can answer it. `DEF-2826` was found exactly here.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is looking at an
 * old app (`cr049-bill-document.mjs`, 2026-08-30).
 *
 * ⚠ **THE DOCUMENT STORE IS ON DISK AND IS NOT SHARED BETWEEN WORKTREES.** A
 * bill issued under one `DOCUMENT_STORAGE_DIR` answers `409
 * billing.document.bytesMissing` under another — a DATA fault that reads
 * exactly like a code fault. Issue the two bills below from the same checkout
 * that serves them.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 * The fixture is two ISSUED bills pinned to DIFFERENT published versions of the
 * tenant's template, made through the product's own doors:
 *
 *   1. `POST /bill-templates/layout {"layout_key": "standard-letter-v1"}`
 *      (System Admin — BR-BIL-027), then issue a bill;
 *   2. `POST /bill-templates/layout {"layout_key": "compact-letter-v1"}`
 *      — this publishes a NEW version — then issue a second bill.
 *
 *   Any issuing door will do. The cheapest is the fee bill the disconnect
 *   flow already uses (`billing.fee_bill.raise_and_issue_charge_fee`), because
 *   it needs no meter read: a seeded tenant usually has reads for one month
 *   only, and a bill run for any other period is refused account by account
 *   with *"water still has no usable read and no decision"* (BR-BIL-015, and
 *   correctly).
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://…/sbh_cr052t18" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8042 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4242 API_PROXY_TARGET=http://127.0.0.1:8042 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4242 \
 *   SMOKE_BILL_A=<bill pinned to standard-letter-v1> \
 *   SMOKE_BILL_B=<bill pinned to compact-letter-v1> \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr052-per-account-template.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  BOTH DOCUMENTS OPEN. A `409 bytesMissing` is reported as the DATA fault
 *      it is and the run stops, rather than every later assertion failing and
 *      being read as a code fault.
 *   2  EACH PAGE NAMES ITS OWN PIN — the version number and the layout key on
 *      screen are the ones the server pinned to THAT bill, and the two bills
 *      name DIFFERENT ones. This is the per-account resolution, visible.
 *   3  THE OLDER BILL DOES NOT FOLLOW THE TENANT'S CURRENT CHOICE. Bill A was
 *      issued before the layout changed and must still name its own version
 *      (BR-BIL-026 — publishing affects only future bills).
 *   4  ⚠ **THE PAGES ACTUALLY DIFFER IN THE WAY THE TWO LAYOUTS SAY.**
 *      `compact-letter-v1` sets `services_band=False` and
 *      `detail_columns=False`, so the compact page must NOT draw a services
 *      band and its charge table must NOT carry Usage and Rate columns. **This
 *      is the assertion that is RED today — `DEF-2826`** — and it is the reason
 *      the file exists: assertions 2 and 3 pass on a page that names a layout
 *      and draws another.
 *   5  THE KEPT COPY IS THE CONTROL AND PROVES THE SERVER IS RIGHT. The frozen
 *      HTML behind each page is fetched and the same question asked of it; it
 *      answers correctly, which is what makes 4 a screen defect and not a
 *      pricing one.
 *   6  NO DATABASE ID IS THE VISIBLE VALUE OF A FIELD on either page (B14
 *      rule 31) — the template and version are named as a version NUMBER and a
 *      layout KEY, never as the template's uuid.
 *   7  NEITHER PAGE SCROLLS SIDEWAYS.
 *
 * ── WHY IT EXITS 0 WHILE `DEF-2826` IS OPEN ──────────────────────────────
 * See `KNOWN_OPEN` below. A check that can only fail stops being read; one that
 * tolerates a growing list stops being a check. This list may only ever get
 * SHORTER, and the run FAILS if a listed assertion starts passing — so the day
 * the page is repaired, this file tells the next lane to tighten it rather than
 * sitting quietly tolerant of the defect it was written to catch.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4242";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const BILL_A = process.env.SMOKE_BILL_A ?? "";
const BILL_B = process.env.SMOKE_BILL_B ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr052-per-account-template";
const VIEWPORT = { width: 1440, height: 1000 };

//: The two LayoutSpecs this file contrasts, as the switches `documents.py`
//: declares for them. Named here so a reader can check the expectation against
//: `LAYOUT_SPECS` rather than take this file's word for it.
const SPECS = {
  "standard-letter-v1": { servicesBand: true, detailColumns: true },
  "compact-letter-v1": { servicesBand: false, detailColumns: false },
};

//: ⚠ **KNOWN-OPEN DEFECTS THIS CHECK ALREADY FOUND, AND THE ONLY REASON IT
//: EXITS 0 TODAY.** A harness that can only ever fail is not a guard — nobody
//: reads its output after the second week — and one that quietly tolerates a
//: growing list is not a guard either. So this list follows the
//: `tenant-scoping-unproven.txt` precedent: it MAY ONLY EVER GET SHORTER, and
//: the check itself enforces that in both directions.
//:
//:   · a listed assertion that FAILS  → reported loudly, does not fail the run;
//:   · a listed assertion that PASSES → **FAILS THE RUN**, saying the defect
//:     appears fixed and the entry must be deleted, so the day somebody repairs
//:     the page this check becomes a real guard instead of staying permanently
//:     tolerant of the thing it was written for;
//:   · anything NOT listed that fails → fails the run, as normal.
//:
//: Keys are matched as a PREFIX of the assertion's message.
// ⚠ **EMPTIED 2026-09-01 — `DEF-2826` IS FIXED, SO ITS TWO ENTRIES ARE GONE
// RATHER THAN LEFT TOLERATED.** This file's own rule is that a listed assertion
// which starts PASSING fails the run, precisely so the list cannot outlive the
// defect it describes; leaving these two would have made that mechanism fire on
// the next lane for no reason, which is how a check earns a skip instead of a
// fix. Both entries read:
//
//   "4 · B (compact-letter-v1): charge table has NO Usage/Rate columns"
//     DEF-2826 — BillDocumentPage draws every band unconditionally;
//     `layout_source` appears once in that file and only inside the sentence
//     naming the layout
//   "4 · the two pages are actually DIFFERENT"
//     DEF-2826 — same cause: two layouts draw one page
//
// What closed them: `documents._layout_for` now returns the resolved
// `LayoutSpec`, `documents_api` serves its switches, and `BillDocumentPage`
// branches on them (v2.110.1). Assertion 4 is now a live assertion like any
// other and must stay green.
//
// **EMPTY IS THE CORRECT STATE and it must be kept empty by DELETION, never by
// addition:** the list may only ever get shorter. A new tolerated entry here is
// a defect being decorated rather than fixed.
const KNOWN_OPEN = {};

const failures = [];
const notes = [];
const tolerated = [];
const unexpectedlyFixed = [];
function knownOpen(message) {
  return Object.entries(KNOWN_OPEN).find(([prefix]) => message.startsWith(prefix));
}
function check(ok, message) {
  const known = knownOpen(message);
  if (known && !ok) {
    console.log(`   ⚠ ${message}   [known open: ${known[1]}]`);
    tolerated.push(`${message}   [${known[1]}]`);
    return;
  }
  if (known && ok) {
    console.log(`   ⛔ ${message}  — THIS NOW PASSES. Delete its KNOWN_OPEN entry.`);
    unexpectedlyFixed.push(message);
    failures.push(`${message} — passes now; remove it from KNOWN_OPEN (${known[1]})`);
    return;
  }
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}
function note(message) {
  console.log(`   ⊘ ${message}`);
  notes.push(message);
}

/** Everything this check needs from one document page, read from the DOM. */
const READ_PAGE = () => {
  const text = document.body.innerText || "";
  const heads = [...document.querySelectorAll("h1,h2,h3,h4")].map((e) =>
    (e.textContent || "").trim(),
  );
  const ths = [...document.querySelectorAll("th")].map((e) =>
    (e.textContent || "").trim().toLowerCase(),
  );
  // The provenance line: "Bill <no> · layout version <n> · <k> printed page(s)"
  const version = /layout version\s+(\d+)/i.exec(text);
  // "Rendered from platform-layout-<key>."
  const layout = /platform-layout-([a-z0-9-]+)/i.exec(text);
  const uuid = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;
  // Only VALUES a reader sees, never attributes: B14 rule 31 is about the
  // visible value of a field, and an id riding on `title` is allowed.
  const visibleIds = [...document.querySelectorAll("dd,td,p,span,div")]
    .map((e) => (e.childElementCount === 0 ? (e.textContent || "").trim() : ""))
    .filter((v) => uuid.test(v));
  return {
    version: version ? Number(version[1]) : null,
    layoutKey: layout ? layout[1] : null,
    heads,
    ths,
    servicesBand: heads.some((h) => /^services?$/i.test(h)),
    unavailable: /has no document yet|can no longer be read/i.test(text),
    visibleIds,
    scrollsSideways: document.documentElement.scrollWidth > window.innerWidth + 1,
  };
};

async function openBill(page, id, label) {
  console.log(`\n── ${label}: ${id.slice(0, 8)} ──`);
  await page.goto(`${BASE}/${TENANT}/billing/bills/${id}/document`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const read = await page.evaluate(READ_PAGE);
  await page.screenshot({ path: join(OUT, `${label}.png`), fullPage: true });
  writeFileSync(join(OUT, `${label}.json`), JSON.stringify(read, null, 2));
  return read;
}

/** The KEPT COPY — the server's own output, this check's control.
 *
 * `serviceCount` rides along because one assertion below is UNMEASURABLE
 * without it: a bill with no per-service charges draws no services band no
 * matter what its layout says, so asserting the band's absence on such a bill
 * would pass on the bug and fail on a fee bill. A check that cannot tell those
 * two apart is worse than no check, because it is trusted (DEF-182). */
async function frozenHtml(page, id) {
  return page.evaluate(
    async ([tenant, invoiceId]) => {
      const r = await fetch(`/api/${tenant}/invoices/${invoiceId}/document`);
      if (!r.ok) return { status: r.status, html: null, serviceCount: null };
      const j = await r.json();
      return {
        status: r.status,
        html: j.original_html ?? j.body ?? null,
        serviceCount: Array.isArray(j.services) ? j.services.length : null,
      };
    },
    [TENANT, id],
  );
}

async function main() {
  if (!existsSync(OUT)) mkdirSync(OUT, { recursive: true });
  if (!BILL_A || !BILL_B) {
    console.log("⛔ SMOKE_BILL_A and SMOKE_BILL_B are required — see HOW TO RUN IT above.");
    console.log("   Two ISSUED bills pinned to DIFFERENT published versions of the template.");
    process.exit(2);
  }

  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 160)}`);
  });

  console.log(`cr052 per-account template: ${BASE} tenant=${TENANT}`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  const a = await openBill(page, BILL_A, "A-standard");
  const b = await openBill(page, BILL_B, "B-compact");

  // ── 1 · BOTH DOCUMENTS OPEN ──────────────────────────────────────────────
  console.log("\n── 1 · both documents open ──");
  for (const [label, read] of [
    ["A", a],
    ["B", b],
  ]) {
    if (read.unavailable) {
      note(
        `bill ${label}'s kept copy cannot be read — this is a DATA fault ` +
          "(the document store is per-checkout), not a code fault. Issue both bills from " +
          "the checkout that serves them and re-run.",
      );
    }
  }
  if (a.unavailable || b.unavailable) {
    console.log("\n⛔ no readable document — nothing further can be measured");
    await browser.close();
    process.exit(1);
  }
  check(true, "1 · both bill documents rendered");

  // ── 2 · EACH PAGE NAMES ITS OWN PIN ─────────────────────────────────────
  console.log("\n── 2 · each page names its own pin ──");
  check(a.version !== null && b.version !== null, `2 · both name a layout version (A=v${a.version}, B=v${b.version})`);
  check(a.layoutKey !== null && b.layoutKey !== null, `2 · both name a layout key (A=${a.layoutKey}, B=${b.layoutKey})`);
  check(a.version !== b.version, `2 · the two bills carry DIFFERENT pins (v${a.version} vs v${b.version})`);
  check(a.layoutKey !== b.layoutKey, `2 · …and different layouts (${a.layoutKey} vs ${b.layoutKey})`);

  // ── 3 · THE OLDER BILL KEEPS ITS OWN PIN (BR-BIL-026) ───────────────────
  console.log("\n── 3 · publishing affects only future bills ──");
  const live = await page.evaluate(async (t) => {
    const r = await fetch(`/api/${t}/bill-templates`);
    const j = await r.json();
    const rows = j.versions ?? j.template?.versions ?? [];
    const published = rows.find((v) => v.status === "published") ?? null;
    return { liveVersion: published?.version_no ?? null, liveKey: published?.layout_key ?? null };
  }, TENANT);
  if (live.liveKey === null) {
    note("3 · the library response names no published version — skipped rather than guessed");
  } else {
    check(
      a.layoutKey !== live.liveKey || a.version === live.liveVersion,
      `3 · bill A keeps its own layout (${a.layoutKey}) while the tenant now prints on ${live.liveKey}`,
    );
  }

  // ── 4 · THE PAGES DIFFER THE WAY THE LAYOUTS SAY ────────────────────────
  //
  // The kept copy is fetched FIRST because it carries the one fact assertion 4
  // cannot be measured without: how many per-service groups this bill has.
  const frozen = {
    A: await frozenHtml(page, BILL_A),
    B: await frozenHtml(page, BILL_B),
  };

  console.log("\n── 4 · the page draws the layout it names (DEF-2826) ──");
  for (const [label, read] of [
    ["A", a],
    ["B", b],
  ]) {
    const spec = SPECS[read.layoutKey];
    if (!spec) {
      note(`4 · ${label}: no expectation recorded for '${read.layoutKey}' — add it to SPECS`);
      continue;
    }
    const hasDetail = read.ths.includes("usage") && read.ths.includes("rate");
    check(
      hasDetail === spec.detailColumns,
      `4 · ${label} (${read.layoutKey}): charge table ${spec.detailColumns ? "HAS" : "has NO"} ` +
        `Usage/Rate columns — drawn: ${hasDetail}`,
    );
    // ⚠ ONLY MEASURABLE ON A BILL THAT HAS SERVICES. A fee bill has none and
    // draws no band whatever its layout says, so asserting here would report a
    // pass for the wrong reason on one bill and a failure for the wrong reason
    // on the other. Reported as a stated absence instead.
    if (frozen[label].serviceCount === null) {
      note(`4 · ${label}: the document response served no services array — band not measured`);
    } else if (frozen[label].serviceCount === 0) {
      note(
        `4 · ${label}: this bill has NO per-service charges, so the services band is absent ` +
          "as DATA and not as layout — not measured (use a metered bill to measure it)",
      );
    } else {
      check(
        read.servicesBand === spec.servicesBand,
        `4 · ${label} (${read.layoutKey}): services band ${spec.servicesBand ? "present" : "absent"} ` +
          `— drawn: ${read.servicesBand}`,
      );
    }
  }
  // THE ASSERTION THE WHOLE FILE IS FOR. Two bills on two layouts whose specs
  // differ must not produce the same page. Compared on the SWITCHES, never on
  // the whole heading list — 'Usage history' is present or absent for reasons
  // of DATA, and a comparison that counted it would go green on the bug the
  // day somebody issued two bills with different history.
  const switchesOf = (read) => ({
    detail: read.ths.includes("usage") && read.ths.includes("rate"),
    services: read.servicesBand,
  });
  const specsDiffer = JSON.stringify(SPECS[a.layoutKey]) !== JSON.stringify(SPECS[b.layoutKey]);
  if (!specsDiffer) {
    note("4 · the two bills are on layouts with identical switches — nothing to contrast");
  } else {
    check(
      JSON.stringify(switchesOf(a)) !== JSON.stringify(switchesOf(b)),
      "4 · the two pages are actually DIFFERENT — two layouts must not draw one page",
    );
  }

  // ── 5 · THE KEPT COPY IS THE CONTROL ────────────────────────────────────
  console.log("\n── 5 · the kept copy, which is the server's own answer ──");
  for (const [label, read] of [
    ["A", a],
    ["B", b],
  ]) {
    const spec = SPECS[read.layoutKey];
    if (!frozen[label].html || !spec) {
      note(`5 · ${label}: no kept HTML to compare (status ${frozen[label].status})`);
      continue;
    }
    const hasDetail =
      /\bRate\b/.test(frozen[label].html) && /\bUsage\b/.test(frozen[label].html);
    check(
      hasDetail === spec.detailColumns,
      `5 · ${label}: the KEPT COPY ${spec.detailColumns ? "has" : "has no"} Usage/Rate ` +
        `(${frozen[label].html.length} bytes) — the server honours the pin`,
    );
  }

  // ── 6 · B14 RULE 31 ─────────────────────────────────────────────────────
  console.log("\n── 6 · no database id is the visible value of a field ──");
  check(a.visibleIds.length === 0, `6 · A shows no uuid as a field value (${a.visibleIds.length})`);
  check(b.visibleIds.length === 0, `6 · B shows no uuid as a field value (${b.visibleIds.length})`);

  // ── 7 · NO SIDEWAYS SCROLL ──────────────────────────────────────────────
  console.log("\n── 7 · neither page scrolls sideways ──");
  check(!a.scrollsSideways, "7 · A does not scroll sideways");
  check(!b.scrollsSideways, "7 · B does not scroll sideways");

  await browser.close();
  console.log(
    `\n${failures.length === 0 ? "PASS" : "FAIL"} — ${failures.length} failure(s), ` +
      `${tolerated.length} known-open, ${notes.length} not-measured`,
  );
  for (const f of failures) console.log(`   ⛔ ${f}`);
  for (const t of tolerated) console.log(`   ⚠ ${t}`);
  for (const n of notes) console.log(`   ⊘ ${n}`);
  if (unexpectedlyFixed.length > 0) {
    console.log(
      "\n   ⚑ A KNOWN-OPEN ASSERTION NOW PASSES. That is good news and it is also a task: " +
        "delete the entry from KNOWN_OPEN so this check starts guarding it.",
    );
  }
  console.log(`   artefacts: ${OUT}`);
  process.exit(failures.length === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
