// ── Trace ──────────────────────────────────────────────
// Change:   CR-126-BRC07 §9 parts 2, 3 and 4 — the PO's acceptance walk beyond
//           the create wizard: *"then also try to create the new conenct request
//           from servcie requesta nd see whether it is working. then complete the
//           new connect request - see at submit does it create premsies, units,
//           services, plan and asete and account of owner a smaster account ,
//           money handling, audit handling, documents are stored etc - then
//           whether request is available in the list view - you can search,
//           filter etc"*
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output) · hard rule
//           2 (money 4dp stored / 2dp displayed, as a string) · hard rule 7
//           (audit_log on every money action) · NFR-3 (server pagination) ·
//           PO ruling 2026-09-21 — an asset's number is GENERATED and ASSIGNED
//           and the asset is NOT installed and NOT activated; `install_date` is
//           written on work-order completion · PO ruling 2026-09-21 — the build
//           *"should not be dependent on applciation #"*
// ───────────────────────────────────────────────────────
//
// ⚠ **IT ASKS THE DATABASE, NOT THE SUCCESS MESSAGE.** §9 names nine separate
// nouns and says each is *"a separate yes or no, checked in the database and on
// the screen, never inferred from a success message"*. So every one of them is
// a read of its own and prints what it found INCLUDING ZERO — a walk that only
// looks for values passes just as happily over a noun that silently stopped
// being written.
//
// RUN: BASE=http://127.0.0.1:8718 PGDB=sbh_walk2 node 10-scripts/cr126_s9_request_to_record_walk.mjs
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE || "http://127.0.0.1:8718";
const T = process.env.TENANT || "brazosbend";
const EMAIL = process.env.EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const OUT = process.env.OUT || "/tmp/claude-0/walk2-shots";
/** ⚠ **`SRID` IS RETIRED — the walk now takes BOTH shapes and picks each by
 *  its EVIDENCE (`DEF-CUS-6109`).** Naming one request meant the answer
 *  depended on which one a reader happened to pass, and the acceptance walk's
 *  whole finding was that the two shapes behave differently. `CONNO` still
 *  names the build parts 3 and 4 report on. */
mkdirSync(OUT, { recursive: true });

const say = (...a) => console.log(...a);
const findings = [];
const note = (s) => { findings.push(s); say("  · " + s); };
let presses = 0;
const press = (w) => { presses += 1; say(`  press ${presses}: ${w}`); };

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1600 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => note(`PAGEERROR ${e.message.slice(0, 150)}`));
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
                   page.click('button[type="submit"]')]);
const api = (p, init) => page.evaluate(async ([pp, ii]) => {
  const r = await fetch(pp, ii || { headers: { accept: "application/json" } });
  return { status: r.status, body: await r.text() };
}, [p, init]);
const shot = async (n) => { await page.waitForTimeout(400); await page.screenshot({ path: `${OUT}/sr-${n}.png`, fullPage: true }); };
const byText = async (label) => {
  for (const b of await page.$$("button")) if ((await b.innerText()).trim() === label) return b;
  return null;
};

// ── PART 2 · AN APPLICATION APPROVED INTO A BUILD, ON BOTH SHAPES ───────────
//
// ⚠ **THIS SECTION WALKED ONE REQUEST AND STOPPED AT THE APPROVAL UNTIL
// 2026-09-21 (`DEF-CUS-6109`).** It picked whichever request happened to be
// under review, pressed `Approve and raise the build`, printed what `outcome_ref`
// said and moved on — and on the PO's acceptance walk that produced **no build
// at all on either shape**: where the address had resolved the option was GREYED
// (*"A premise record already exists here."*) and where it had not the approval
// went through and created nothing.
//
// **So it now walks BOTH SHAPES and it does not stop at the approval.** PO
// ruling 2026-09-21: *"then approve applciation may create a new conenct
// request - as draft request - this request is new work and recognized
// seperately from applcaition and hence we should not make it dependent on
// applciation #"*, and blueprint p089's `WHAT APPROVING WILL DO` says what comes
// next in its own words: *"Next · The build's own wizard asks for units,
// services, plans and charges"*. A walk that ends at the approval cannot see
// whether that sentence is true.
//
// ⚠ **THE TWO SHAPES ARE PICKED BY EVIDENCE AND NEVER BY NUMBER.** `SR-26-0004`
// and `SR-26-0005` are this seed's; naming them here would make the walk pass
// on one database and report a missing request on every other.
say("\n════ PART 2 · an application approved into a build, on BOTH shapes ════");
const list = JSON.parse((await api(`/api/${T}/service-requests?per=50`)).body || "{}");
const rows = list.data ?? list.results ?? [];
const open = rows.filter((r) => ["submitted", "under_review"].includes(r.state));
// ⚠ **THE LIST ROW DOES NOT CARRY THE RESOLUTION AND THE FIRST RUN OF THIS
// BLOCK READ IT OFF ONE ANYWAY.** `service_request_reads`' row serves fourteen
// keys — number, type, applicant, address, channel, age, waiting-on, state —
// and `resolution_kind` is on the DETAIL. So `r.resolution_kind` was
// `undefined` for every row, both `find`s returned nothing, and the walk
// reported *"this seed offers none"* over a database holding both shapes.
// That is hard-won law 7's *looking at the wrong thing*, and it reads exactly
// like a missing fixture. So the detail is asked for, once per open request.
const evidence = [];
for (const r of open) {
  const one = JSON.parse((await api(`/api/${T}/service-requests/${r.id}`)).body || "{}");
  const loc = (one.data ?? one).location_and_services ?? {};
  evidence.push({ ...r, resolution_kind: loc.resolution_kind ?? null,
                  resolved_premises_id: loc.resolved_premises_id ?? null });
}
say(`open requests and what their addresses resolved to: ${evidence.map((e) => `${e.request_no}=${e.resolved_premises_id ? "a premises" : "nothing"}`).join(" · ") || "(none open)"}`);
const unresolved = evidence.find((r) => !r.resolved_premises_id);
const resolved = evidence.find((r) => r.resolved_premises_id);
// ⚠ **`PART=record CONNO=<connection_no>` RUNS PARTS 3 AND 3b ALONE, AND IT
// EXISTS BECAUSE §9 IS WALKED BY TWO LANES AT ONCE (WALK-A, 2026-09-21).**
// Part 2 is one lane's and part 3 is another's, and until now the only way to
// reach part 3's screen half was to approve a service request first — which
// spends an application, moves a sibling's fixture, and reports part 3 about
// whichever build part 2 happened to make. Naming the build is the whole
// point: §9 says each noun is *"a separate yes or no, checked in the database
// and on the screen"*, and a screen read of the WRONG build is law 7's
// *looking at the wrong thing* with a green tick on it.
const PART = process.env.PART || "all";
const shapes = PART === "record" ? [] : [
  ["the address has NOT resolved", unresolved],
  ["the address HAS resolved", resolved],
];
if (PART === "record") say(`PART=record — part 2 skipped on purpose; reading ${process.env.CONNO || "the newest build"}`);
const built = [];

/** Fill and press one step of the New Connect wizard. */
const wizardForward = async (label) => {
  const buttons = await page.$$('[data-wizard="actions"] button');
  const last = buttons[buttons.length - 1];
  if (!last) { note(`${label}: no wizard action buttons at all`); return false; }
  const text = (await last.innerText()).trim();
  if (await last.isDisabled()) { note(`${label}: cannot advance — "${text}" is DISABLED`); return false; }
  await last.click(); press(`${label} → ${text}`);
  await page.waitForTimeout(1600);
  return true;
};
// ⚠ A radio in this kit is visually hidden and often below the fold, so
// `check()` fails with *"outside of the viewport"* however hard it is forced.
// Clicking the input dispatches the event React binds to, which is the user's
// action and not a state poke (`po_new_connect_clerk_walk.mjs` learned this).
const pickRadio = async (name, value) => {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) return false;
  await el.evaluate((n) => n.click());
  await page.waitForTimeout(250);
  return true;
};

// ══════════════════════════════════════════════════════════════════════════
// PHASE=abandon · THE FOUR QUESTIONS §9 PART 2 ASKS THAT THE LOOP BELOW
//                 CANNOT ANSWER (WALK-B, 2026-09-21)
// ══════════════════════════════════════════════════════════════════════════
// The loop below walks an approval straight through to a finished build, and
// that is the happy path. Four of §9 part 2's claims are only visible OFF it,
// and each one fails SILENTLY if it is wrong:
//
//  1 · **ABANDONING THE WIZARD LEAVES A DRAFT BUILD AND NO PROPERTY.**
//      `create_connection`'s own docstring makes that promise in those words
//      (`BR-MET-112`, `DEF-CUS-6109`). A walk that reads the screen cannot see
//      it: nothing is DRAWN when a property is not created. So this counts
//      premises, units and connections before and after — hard-won law 7's
//      *print what you found INCLUDING ZERO*.
//  2 · **THE WIZARD OPENS PREFILLED.** `draftFromRaisedBuild` pours eleven
//      values in. The loop below overtypes most of them before reading them,
//      so it measures its own fixture. This reads every control on steps 1
//      and 2 BEFORE touching one, and names what the application holds and
//      the wizard still asks for.
//  3 · **FINISHING A RESUMED DRAFT FINISHES THAT DRAFT.** `commitPlanOf` sends
//      `connection_id`, so the commit should CLOSE the draft rather than open
//      a second build beside it. `state=requested` on the id you already had
//      cannot tell those apart — only a COUNT can.
//  4 · **A RULE REFUSAL ON THE RESUMED PATH REACHES THE CLERK AS WORDS.**
//      `DEF-MET-6110`/`6111` proved that for a build started at
//      `/connections/new`. The resumed path is a different door onto the same
//      wizard and nothing had ever driven a refusal through it.
//
// RUN: PHASE=abandon BASE=http://127.0.0.1:8731 node 10-scripts/cr126_s9_request_to_record_walk.mjs
if (process.env.PHASE === "abandon") {
  // ⚠ **THE CENSUS ASKS FOR `count`, NEVER `results.length`.** Every list in
  // this product clamps `per` through `core.pagination.clamp_page_size`, whose
  // vocabulary STARTS at 50 — so `?per=1` returns fifty rows and a census
  // written as `results.length` would report 50 for a tenant of 79 premises
  // and read as a stable number while the thing it counts moved.
  const countOf = async (path) => {
    const r = await api(path);
    try { const j = JSON.parse(r.body || "{}"); return j.count ?? j.total ?? null; }
    catch { return null; }
  };
  const census = async () => ({
    premises: await countOf(`/api/${T}/premises?per=50`),
    units: await countOf(`/api/${T}/units?per=50`),
    connections: await countOf(`/api/${T}/connections?per=50`),
  });
  // ⚠ **`connections` IS ROWS ON THE NEW CONNECTS LIST, NOT BUILDS**, because
  // that list draws parked wizards as rows too (`connection_reads` merges
  // `wizard_parks` in). It is exact while nothing is parked — which is true of
  // this phase — and the label says what it counts so the next lane does not
  // read a park as a build, which `PHASE=park` below did once.
  const showCensus = (label, c) =>
    say(`  ${label}: ${c.premises} premises · ${c.units} units · ${c.connections} rows on the New connects list`);

  // Every commit this phase drives, with the status the server answered. A
  // refusal and a fall-over are both "the build did not happen" on screen and
  // they are opposite defects (`DEF-MET-6110`).
  const commits = [];
  page.on("response", async (r) => {
    if (!r.url().includes("/connections/commit")) return;
    let body = ""; try { body = (await r.text()).slice(0, 500); } catch { /* consumed */ }
    commits.push({ status: r.status(), body });
  });

  /** Every control a clerk can see on the step in front of them, with what is
   *  already in it. Reading the DOM rather than the draft, because the promise
   *  §9 makes is about what the clerk SEES. */
  const controlsOnStep = async () =>
    page.$$eval("input, select, textarea", (ns) =>
      ns.filter((n) => n.offsetParent !== null && n.type !== "hidden" && n.type !== "search")
        .map((n) => {
          const label = document.querySelector(`label[for="${n.id}"]`)?.textContent?.trim()
            ?? n.closest("label")?.textContent?.trim() ?? n.getAttribute("aria-label") ?? "";
          const value = n.type === "checkbox" || n.type === "radio"
            ? (n.checked ? n.value || "on" : "")
            : String(n.value ?? "");
          return { id: n.id || n.name || "(unnamed)", type: n.type, label: label.slice(0, 40), value: value.slice(0, 60) };
        }));

  const filled = (cs) => cs.filter((c) => c.value !== "" && c.value !== "on");
  const empty = (cs) => cs.filter((c) => c.value === "");

  const baseline = await census();
  say("\n════ PHASE abandon · the census before anything is approved ════");
  showCensus("baseline", baseline);

  for (const [what, target] of shapes) {
    say(`\n──── ${what} ────`);
    if (!target) { note(`no open request where ${what} — this seed offers none`); continue; }
    say(`request ${target.request_no} · ${target.state} · resolution=${target.resolution_kind}`);

    // ── approve, and land on the wizard ────────────────────────────────────
    await page.goto(`${BASE}/${T}/requests/${target.id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    const approve = await byText("Approve");
    if (!approve) { note(`${target.request_no}: no Approve button`); continue; }
    await approve.click(); press("Approve"); await page.waitForTimeout(1400);
    let took = false;
    for (const r of await page.$$('input[name="service-request-outcome"]')) {
      const txt = (await r.evaluate((n) => n.closest("label")?.innerText || "")).replace(/\n/g, " ");
      if (!/new connection/i.test(txt)) continue;
      if (await r.evaluate((n) => n.disabled)) { note(`"A new connection" is DISABLED on ${target.request_no}`); break; }
      await r.evaluate((n) => n.click()); press('pick "A new connection"'); took = true;
      await page.waitForTimeout(800); break;
    }
    if (!took) continue;
    const raise = await byText("Approve and raise the build");
    if (!raise || await raise.isDisabled()) { note("cannot raise the build from this request"); continue; }
    await raise.click(); press("Approve and raise the build");
    await page.waitForURL((u) => u.pathname.includes("/connections/new"), { timeout: 20000 })
      .catch(() => note(`${target.request_no}: approving did NOT open the build's wizard`));
    await page.waitForTimeout(2600);
    const buildId = new URL(page.url()).searchParams.get("build");
    if (!buildId) { note("no ?build= on the wizard's address — nothing to abandon"); continue; }
    const draft0 = (JSON.parse((await api(`/api/${T}/connections/${buildId}`)).body || "{}")).data
      ?? JSON.parse((await api(`/api/${T}/connections/${buildId}`)).body || "{}");
    const connNo = draft0.connection_no;
    note(`the draft is ${connNo} · state=${draft0.state} · premises=${draft0.premises ? draft0.premises.premise_no : "(none yet)"}`);
    await shot(`ab-01-wizard-opened-${target.request_no}`);

    // ── 2 · WHAT THE WIZARD ALREADY KNOWS, READ BEFORE ANYTHING IS TYPED ───
    const step1 = await controlsOnStep();
    say(`  step 1 offers ${step1.length} control(s); ${filled(step1).length} arrive already answered:`);
    filled(step1).forEach((c) => say(`      ${c.id} = "${c.value}"`));
    const blanks1 = empty(step1).map((c) => c.id).join(" · ");
    say(`  step 1 still blank: ${blanks1 || "(nothing)"}`);
    // What the APPLICATION holds, beside what the wizard put on screen. A field
    // the request answers and the wizard leaves blank is a clerk retyping
    // something the product already has — §9's *"asks for nothing it already
    // knows"*.
    const full = JSON.parse((await api(`/api/${T}/service-requests/${target.id}`)).body || "{}");
    const F = full.data ?? full;
    const held = {
      applicant: F.applicant?.name ?? null,
      email: F.applicant?.email ?? null,
      phone: F.applicant?.phone ?? null,
      kind: F.applicant?.person_or_company ?? null,
      category: F.applicant?.customer_category?.account_type?.code ?? null,
      address: F.location_and_services?.address_as_given ?? null,
      property_type: F.location_and_services?.property_type ?? null,
      services: (F.location_and_services?.services ?? []).map((s) => s.code).join("+") || null,
      requested_start: (F.location_and_services?.services ?? []).map((s) => s.requested_start).filter(Boolean).join("+") || null,
      units_on_property: F.location_and_services?.units_on_property ?? null,
    };
    say(`  the application holds: ${Object.entries(held).filter(([, v]) => v !== null && v !== "").map(([k, v]) => `${k}="${v}"`).join(" · ")}`);
    const onScreen = filled(step1).map((c) => c.value.toLowerCase()).join(" | ");
    for (const [k, v] of Object.entries(held)) {
      if (v === null || v === "") continue;
      if (["address", "property_type", "services", "requested_start", "units_on_property"].includes(k)) continue;
      if (!onScreen.includes(String(v).toLowerCase().slice(0, 8)))
        note(`the application holds ${k}="${v}" and step 1 does not show it`);
    }

    // ── 1 · ABANDON IT. Nothing else is pressed; the clerk leaves. ─────────
    await page.goto(`${BASE}/${T}/accounts?tab=new-connects`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1800);
    press("walk away from the wizard (open the list instead)");
    const afterAbandon = await census();
    showCensus("after abandoning", afterAbandon);
    const dP = afterAbandon.premises - baseline.premises;
    const dU = afterAbandon.units - baseline.units;
    const dC = afterAbandon.connections - baseline.connections;
    note(`abandoning ${connNo} left ${dC > 0 ? `${dC} more build(s)` : "no new build"}, ${dP} new propert${dP === 1 ? "y" : "ies"} and ${dU} new unit(s)`);
    if (what.includes("NOT resolved") && dP !== 0)
      note(`⛔ abandoning created ${dP} propert(y/ies) — BR-MET-112 says nothing is written until the last button`);

    // ── 3 · FIND IT AGAIN AND RESUME IT, THROUGH THE LIST ──────────────────
    // The clerk's own way back: the list, the number, the row's door. Not a
    // hand-built URL, which would prove a route rather than a product.
    const link = await page.$(`a:has-text("${connNo}")`);
    if (!link) {
      note(`⛔ ${connNo} has no row a clerk can click in the New connects list (\`DEF-CUS-6132\`)`);
    } else {
      const href = await link.getAttribute("href");
      note(`the list offers ${connNo} at ${href}`);
      await link.click(); press(`open ${connNo} from the list`);
      await page.waitForTimeout(3000);
      const resumedAt = new URL(page.url());
      const resumedBuild = resumedAt.searchParams.get("build");
      note(`clicking ${connNo} lands on ${resumedAt.pathname}${resumedAt.search} — ${resumedBuild === buildId ? "the SAME draft" : `NOT the wizard (build=${resumedBuild ?? "none"})`}`);
      await shot(`ab-02-resumed-${target.request_no}`);
    }
    // ⚠ **THE REST OF THIS PHASE RE-ENTERS THE WIZARD BY ITS ADDRESS, AND THAT
    // IS NOT A CLERK'S PATH (`DEF-CUS-6132`).** Questions 3 and 4 below are
    // about the COMMIT on a resumed draft, and they are worth answering even
    // while the door to it is missing — so the walk says out loud that it typed
    // the address rather than pretending it found one.
    if (new URL(page.url()).searchParams.get("build") !== buildId) {
      note(`re-entering ${connNo}'s wizard by its address — a clerk has no way to do this today`);
      await page.goto(`${BASE}/${T}/connections/new?build=${buildId}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(2600);
      await shot(`ab-02-resumed-by-address-${target.request_no}`);
    }

    // ── 4 · BREAK A RULE ON THE RESUMED PATH ──────────────────────────────
    // Two rules, one per shape, each chosen because the server — not the
    // screen — is the only thing that can refuse it:
    //   * a DUPLICATE UNIT LABEL, which `uq_units_tenant_premises_label`
    //     refuses at the commit, on a property that already has those labels;
    //   * an UNPRICEABLE CHARGE CODE, which `charge_by_code` answers `null`
    //     for and the commit refuses by name.
    const wizardText = async () => page.evaluate(() => document.querySelector("main")?.innerText || "");
    // ⚠ **THE STEP IS READ FROM THE WORDS THE WIZARD PRINTS**, `Step n of m`,
    // because that is the fact `DEF-MET-6111` is about: the clerk has to be
    // left on the step where the thing they chose LIVES. Counting rendered
    // step markers would answer a different question.
    const stepNow = async () => {
      const m = (await wizardText()).match(/Step (\d+) of (\d+)/);
      return m ? Number(m[1]) : -1;
    };
    const collide = what.includes("HAS resolved");

    await page.selectOption("#nc_owner_subcategory", "permanent").catch(() => {});
    await pickRadio("nc_party_kind", (held.kind === "business" ? "company" : "person"));
    const stampX = Date.now().toString().slice(-6);
    for (const sel of ["#nc_tax_id", "#nc_owner_tax_id", "#nc_ssn"]) {
      if (await page.$(sel)) { await page.fill(sel, sel === "#nc_ssn" ? `4${stampX.slice(-2)}-11-${stampX}`.slice(0, 11) : `TX-${stampX}`).catch(() => {}); break; }
    }
    await pickRadio("nc_mode", "our_crew");
    // The prefix is asked on STEP 1 and it names the units step 3 makes
    // (`DEF-CUS-5435`), so a label collision has to be set up here.
    if (collide) await page.fill("#nc_prefix", "Unit").catch(() => {});
    await wizardForward("step 1 · Owner & scope");

    const addrNow = await page.$eval("#nc_address", (n) => n.value).catch(() => "");
    note(`the resumed step 2 opens on "${addrNow || "(empty)"}"`);
    if (addrNow === "") await page.fill("#nc_address", `${stampX} Abandon Way`).catch(() => {});
    for (const [sel, v] of [["#nc_city", "Austin"], ["#nc_postal_code", "78704"], ["#nc_state", "TX"]]) {
      if (await page.$(sel)) { const cur = await page.$eval(sel, (n) => n.value); if (cur === "") await page.fill(sel, v).catch(() => {}); }
    }
    const step2 = await controlsOnStep();
    say(`  step 2 arrives with ${filled(step2).length} of ${step2.length} control(s) answered`);
    const ptypes2 = await page.$$eval("#nc_premise_type option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
    const ptypeNow = await page.$eval("#nc_premise_type", (n) => n.value).catch(() => "");
    if (ptypeNow === "" && ptypes2.length) await page.selectOption("#nc_premise_type", ptypes2[0]).catch(() => {});
    await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => {});
    const offered2 = await page.$$eval("#services_available-add option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
    // ⚠ **THE APPLICATION NAMED ITS SERVICES AND STEP 2 ASKS AGAIN.** Reported
    // rather than silently worked around, because it is one of §9's own words.
    if (held.services) note(`the application asked for ${held.services}; step 2 offers ${offered2.length} service(s) with none of them ticked`);
    for (const code of offered2.slice(0, 1)) { await page.selectOption("#services_available-add", code).catch(() => {}); await page.waitForTimeout(250); }
    const plans2 = await page.$$eval("#nc_plan option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
    if (plans2.length) await page.selectOption("#nc_plan", plans2[0]).catch(() => {});
    await wizardForward("step 2 · Premise");

    if (collide) {
      await page.fill("#nc_from", "1").catch(() => {});
      await page.fill("#nc_to", "2").catch(() => {});
      note('step 3 asks for units "Unit 1" and "Unit 2" — labels this property already has');
    } else {
      await page.fill("#nc_from", "1").catch(() => {});
      await page.fill("#nc_to", "1").catch(() => {});
    }
    await page.waitForTimeout(800);
    await wizardForward("step 3 · Units");
    await wizardForward("step 4 · Services");
    await wizardForward("step 5 · Work orders");

    // step 6 — the charge. On the shape that is not colliding on labels, put a
    // code on and then take its price away on Settings, mid-build, which is
    // the only way to reach `charge_by_code → amount: null` through the
    // product's own doors.
    let depriced = null;
    if (!collide) {
      const codes = await page.$$eval("#nc_quote_charge_code option", (ns) => ns.map((o) => ({ v: o.value, t: (o.textContent || "").trim() }))).catch(() => []);
      const want = codes.find((c) => /CONN/.test(c.v) || /CONN/.test(c.t));
      if (!want) note(`step 6 offers no connection-fee code (${codes.length} offered)`);
      else {
        await page.selectOption("#nc_quote_charge_code", want.v).catch(() => {}); press("pick a charge code");
        const bases = await page.$$eval("#nc_quote_charge_basis option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
        if (bases.length) await page.selectOption("#nc_quote_charge_basis", bases[0]).catch(() => {});
        // ⚠ **`nc_quote_due_days` IS A CLIENT-SIDE GATE AND THE FIRST RUN OF
        // THIS PROBE DIED ON IT.** The wizard refused to leave step 6 with
        // *"Say when this charge is due."*, so `POST /connections/commit` was
        // never called and the probe reported *(never called)* over a door it
        // had not reached — law 7's *looking at the wrong thing*. The probe is
        // about the SERVER's refusal, so the client's own question is answered
        // first.
        if (await page.$("#nc_quote_due_days")) { await page.fill("#nc_quote_due_days", "14"); press("Due in days"); }
        for (const b of await page.$$("button")) if ((await b.innerText()).trim().startsWith("+ Charge")) { await b.click(); press("+ Charge"); break; }
        await page.waitForTimeout(900);
        if (await page.$("#nc_quote_due_days")) {
          const due = await page.$eval("#nc_quote_due_days", (n) => n.value);
          if (due === "") { await page.fill("#nc_quote_due_days", "14"); press("Due in days"); }
        }
        const chargeList = JSON.parse((await api(`/api/${T}/charges?per=200`)).body || "{}");
        const row = (chargeList.results ?? chargeList.data ?? []).find((c) => c.code === "CONN");
        if (row) {
          const patched = await api(`/api/${T}/charges/${row.id}`, {
            method: "PATCH",
            headers: { "content-type": "application/json", accept: "application/json" },
            body: JSON.stringify({ amount_rule: "percent", amount: null, percent: "0.015",
                                   reason: "WALK-B: a tenant reprices a connection fee while a resumed draft holds it" }),
          });
          depriced = patched.status;
          note(`CONN was repriced to a percent rule mid-build through Settings → HTTP ${patched.status}`);
        }
      }
    }
    await wizardForward("step 6 · Charges");
    await wizardForward("step 7 · Communication");
    await page.waitForTimeout(700);
    const beforePress = await census();
    commits.length = 0;
    await wizardForward("step 8 · Create connection");
    await page.waitForTimeout(7000);
    await shot(`ab-03-after-the-press-${target.request_no}`);

    // ⚠ **THREE FACTS, AND EACH ANSWERS A DIFFERENT QUESTION.** The HTTP status
    // says whether a rule refused or the product fell over; the words on the
    // page say whether the clerk was told anything; the census says whether the
    // work survived. A walk that printed only one of them could report a 500 as
    // "refused correctly" (`DEF-MET-6110`).
    const seenCommit = commits[commits.length - 1] ?? null;
    say(`  POST /connections/commit answered ${seenCommit ? seenCommit.status : "(never called)"}`);
    if (seenCommit) say(`     body: ${seenCommit.body.replace(/\s+/g, " ").slice(0, 300)}`);
    const alerts = await page.$$eval('[role="alert"]', (ns) => ns.map((n) => n.innerText.trim()).filter(Boolean)).catch(() => []);
    const footer = await page.$$eval('[data-wizard="actions"] button', (ns) => ns.map((n) => n.innerText.trim())).catch(() => []);
    const text = await wizardText();
    const raw500 = /server error|internal server|traceback|<!doctype|uncaught|undefined is not/i.test(text);
    const landedOn = await stepNow();
    say(`  the clerk is left on step ${landedOn === -1 ? "(no wizard step — the done panel is showing)" : landedOn}`);
    say(`  what the clerk reads: ${alerts.length ? alerts.map((a) => JSON.stringify(a.slice(0, 160))).join(" · ") : "(no alert on screen)"}`);
    say(`  the wizard's footer still offers: ${footer.length ? footer.join(" · ") : "(nothing — the done panel or a failure card took the row)"}`);
    if (raw500) note("⛔ the page shows a RAW SERVER ERROR rather than a sentence");
    // A raw server code — `unit_label_taken`, `charge_unpriceable` — reaching a
    // clerk as a word is the same defect the list's filter had. CASE is the
    // test, not underscores (`parked` passed an underscore test).
    const rawWord = (alerts.join(" ").match(/\b[a-z][a-z0-9]*(?:[._][a-z0-9]+)+\b/g) ?? []);
    if (rawWord.length) note(`⛔ the refusal reaches the clerk carrying a raw code: ${[...new Set(rawWord)].join(" · ")}`);
    if (seenCommit && seenCommit.status >= 500) note(`⛔ the commit answered HTTP ${seenCommit.status} — a fall-over, not a refusal`);
    if (seenCommit && seenCommit.status >= 400 && seenCommit.status < 500 && alerts.length === 0)
      note(`⛔ the server refused with HTTP ${seenCommit.status} and the clerk is told NOTHING`);
    const afterPress = await census();
    showCensus("after the last press", afterPress);
    note(`the last press moved: ${afterPress.connections - beforePress.connections} build(s) · ${afterPress.premises - beforePress.premises} propert(y/ies) · ${afterPress.units - beforePress.units} unit(s)`);

    // ── 3 · DID IT FINISH THE DRAFT, OR OPEN A SECOND BUILD BESIDE IT? ─────
    const nowDraft = JSON.parse((await api(`/api/${T}/connections/${buildId}`)).body || "{}");
    const nd = nowDraft.data ?? nowDraft;
    const all = JSON.parse((await api(`/api/${T}/connections?per=50`)).body || "{}");
    const mine = (all.results ?? all.data ?? []).filter((r) => r.request_no === target.request_no);
    note(`${connNo} now reads state=${nd.state}; builds naming ${target.request_no}: ${mine.length} (${mine.map((m) => m.connection_no).join(" · ") || "none"})`);
    if (mine.length > 1) note(`⛔ finishing the resumed draft left ${mine.length} builds on one application`);
    if (depriced !== null) {
      // Put the price back, so the clone is not left mid-experiment for the
      // next thing that reads it.
      const chargeList2 = JSON.parse((await api(`/api/${T}/charges?per=200`)).body || "{}");
      const row2 = (chargeList2.results ?? chargeList2.data ?? []).find((c) => c.code === "CONN");
      if (row2) await api(`/api/${T}/charges/${row2.id}`, {
        method: "PATCH", headers: { "content-type": "application/json", accept: "application/json" },
        body: JSON.stringify({ amount_rule: "flat", amount: "45.0000", percent: null, reason: "WALK-B: restore the seeded connection fee" }),
      });
    }
  }
  say(`\n════ PHASE abandon · ${findings.length} findings · ${presses} presses ════`);
  findings.forEach((f) => say("  · " + f));
  await browser.close();
  process.exit(0);
}


// ══════════════════════════════════════════════════════════════════════════
// PHASE=park · THE DOOR THE PARK PANEL PROMISES, AND WHAT COMES BACK THROUGH IT
//                                                     (WALK-B, 2026-09-21)
// ══════════════════════════════════════════════════════════════════════════
// `PHASE=abandon` above walks a clerk who WALKS AWAY. This walks the clerk who
// leaves the way the product tells them to, and it is a different answer.
//
// The park panel's own words: *"Parked at step 1 of 8. Reopening this from your
// Waiting on list brings you back to this step with everything you have typed.
// Nothing is created or changed until you finish the wizard."* Every clause of
// that is true of the TYPING and none of it is true of the BUILD — `wizardPark`
// stores what was typed and `BR-SHL-048(c)` says a parked wizard holds nothing,
// which was written before a build could exist before its wizard finished.
//
// ⚠ **SO THE THING TO COUNT IS BUILDS, NOT FIELDS.** A walk that checked the
// marker came back would pass: it does. `DEF-CUS-6135`.
if (process.env.PHASE === "park") {
  const countOf = async (p) => { const r = await api(p); try { const j = JSON.parse(r.body || "{}"); return j.count ?? j.total ?? null; } catch { return null; } };
  const census = async () => ({ premises: await countOf(`/api/${T}/premises?per=50`), units: await countOf(`/api/${T}/units?per=50`), connections: await countOf(`/api/${T}/connections?per=50`) });
  const MARK = `WALKB-PARK-${Date.now().toString().slice(-4)}`;
  const LIST = `${BASE}/${T}/accounts?tab=new-connects`;
  const byLabel = async (label) => { for (const b of await page.$$("button")) if ((await b.innerText()).trim() === label) return b; return null; };

  // A DRAFT this tenant already carries that an application raised. Never a
  // number: naming one would make the walk pass on one database only.
  const list = JSON.parse((await api(`/api/${T}/connections?per=50`)).body || "{}");
  const draft = (list.results ?? list.data ?? []).find((r) => r.state === "draft" && r.request_no);
  if (!draft) { note("no DRAFT build raised from an application on this database — run PHASE=abandon first"); await browser.close(); process.exit(0); }
  say(`\n════ PHASE park · ${draft.connection_no}, raised by ${draft.request_no} ════`);
  const before = await census();
  say(`  before: ${before.premises} premises · ${before.units} units · ${before.connections} builds`);

  await page.goto(`${BASE}/${T}/connections/new?build=${draft.id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2600);
  await page.fill("#nc_owner_name", MARK).catch(() => {});
  press("type into the owner name");
  const park = await byLabel("Park");
  if (!park) { note("the wizard offers no Park control"); await browser.close(); process.exit(0); }
  await park.click(); press("press Park");
  await page.waitForTimeout(1800);
  await shot("park-01-panel");
  // ⚠ **THE PANEL IS INLINE, NOT A `[role="dialog"]`**, and a probe that looked
  // for a dialog reported *"(no dialog)"* over a panel that was on screen —
  // law 7's *looking at the wrong thing*, and it reads like a dead control.
  // ⚠ **THE PICKER IS FOUND BY WHAT IT OFFERS, NEVER BY POSITION.** The first
  // run of this block took the first `<select>` on the page — which is step 1's
  // OWNER TYPE, still mounted behind the panel — set it to `builder_developer`,
  // pressed `Park it` with `Waiting on` unanswered, and printed a cheerful
  // `waiting on = builder_developer`. The park never happened and the line read
  // like it had.
  let waitingSet = null;
  for (const sel of await page.$$("select")) {
    const opts = await sel.$$eval("option", (ns) => ns.map((o) => ({ v: o.value, t: (o.textContent || "").trim() })).filter((o) => o.v));
    const wanted = opts.find((o) => /^waiting on/i.test(o.t));
    if (!wanted) continue;
    await sel.selectOption(wanted.v).catch(() => {});
    waitingSet = wanted.t; press(`Waiting on = ${wanted.t}`);
    break;
  }
  if (waitingSet === null) note("the park panel offers no `Waiting on` picker — the park cannot be completed");
  await page.waitForTimeout(600);
  const parkIt = await byLabel("Park it");
  if (!parkIt || await parkIt.isDisabled()) { note('"Park it" is missing or disabled — the park cannot be completed'); await browser.close(); process.exit(0); }
  await parkIt.click(); press('press "Park it"');
  await page.waitForTimeout(3200);
  // ⚠ **`?park=1` STILL ON THE ADDRESS MEANS THE PANEL IS STILL OPEN**, which is
  // what a refused park looks like. Said out loud, because every line after this
  // one would otherwise describe a park that never happened.
  const afterPark = new URL(page.url());
  note(`after parking, the clerk is at ${afterPark.pathname}${afterPark.search}`);
  if (afterPark.searchParams.get("park") === "1") {
    note("⛔ the park panel is STILL OPEN — `Park it` did not take, so nothing below was walked");
    say(`\n════ PHASE park · ${findings.length} findings · ${presses} presses ════`);
    findings.forEach((f) => say("  · " + f));
    await browser.close(); process.exit(0);
  }

  await page.goto(LIST, { waitUntil: "networkidle" });
  await page.waitForTimeout(2400);
  const rows = await page.$$eval("tbody tr", (ns) => ns.map((tr) => ({
    cells: [...tr.querySelectorAll("td")].map((td) => td.innerText.trim()),
    href: tr.querySelector("a")?.getAttribute("href") ?? null })));
  const parkedRow = rows.find((r) => r.href && r.href.includes("parked="));
  if (!parkedRow) { note("⛔ the park left no row a clerk can reopen on the New connects list"); await browser.close(); process.exit(0); }
  note(`the parked row's CONNECTION cell reads ${JSON.stringify(parkedRow.cells[0])} and it opens ${parkedRow.href}`);
  if (parkedRow.cells[0] === "") note("⛔ the parked row carries NO connection number, so it names nothing a clerk can cite");
  if (!/[?&]build=/.test(parkedRow.href)) note(`⛔ the parked row's door carries no build — it is ${parkedRow.href}, so the wizard cannot know which build it is finishing`);
  await shot("park-02-list");

  await page.goto(`${BASE}${parkedRow.href}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  const resumed = new URL(page.url());
  note(`reopening it lands on ${resumed.pathname}${resumed.search} · build=${resumed.searchParams.get("build") ?? "(NOTHING)"}`);
  note(`the owner name came back as ${JSON.stringify(await page.$eval("#nc_owner_name", (n) => n.value).catch(() => "(no field)"))} — the TYPING is restored, which is what the panel promised`);

  // ── AND NOW THE THING THE PANEL DID NOT PROMISE ───────────────────────────
  // ⚠ **THE VERDICT IS THE ID THE COMMIT ANSWERS WITH, NOT A COUNT.** The first
  // version of this block counted `/connections`'s envelope — which is the
  // LIST's count, and the list draws parked wizards as rows too, so parking
  // twice moved it by two and the walk announced *"a SECOND build was created"*
  // over a run in which nothing committed at all. A false sentence in exactly
  // the shape of the defect. `commit.id` needs no denominator: same id means the
  // draft was finished, a different one means a second build stands beside it.
  const commits = [];
  page.on("response", async (r) => {
    if (!r.url().includes("/connections/commit")) return;
    try { commits.push({ status: r.status(), body: await r.text() }); } catch { /* consumed */ }
  });
  // The minimum a commit needs that a park does not restore — the plan on
  // step 2 and a unit range on step 3.
  await wizardForward("step 1");
  const plansP = await page.$$eval("#nc_plan option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
  if (plansP.length && (await page.$eval("#nc_plan", (n) => n.value).catch(() => "")) === "") await page.selectOption("#nc_plan", plansP[0]).catch(() => {});
  await wizardForward("step 2");
  await page.fill("#nc_from", "1").catch(() => {}); await page.fill("#nc_to", "1").catch(() => {});
  await page.waitForTimeout(600);
  for (const l of ["step 3", "step 4", "step 5", "step 6", "step 7", "step 8"]) await wizardForward(l);
  await page.waitForTimeout(7000);
  await shot("park-03-after-the-press");
  const said = commits[commits.length - 1] ?? null;
  if (said === null) {
    note("POST /connections/commit was never called — the reopened park did not reach the last button, so nothing below is an answer");
  } else {
    let answered = {}; try { answered = JSON.parse(said.body || "{}"); } catch { /* not json */ }
    note(`the commit answered HTTP ${said.status} with ${answered.connection_no ?? "(no connection_no)"} (${answered.id ?? "no id"})`);
    const still = JSON.parse((await api(`/api/${T}/connections/${draft.id}`)).body || "{}");
    const sd = still.data ?? still;
    note(`${draft.connection_no} now reads state=${sd.state} (it was draft)`);
    if (answered.id && answered.id !== draft.id) {
      note(`⛔ DEF-CUS-6135 — the commit made ${answered.connection_no}, a DIFFERENT build from ${draft.connection_no}, which is still ${sd.state}`);
      const all2 = JSON.parse((await api(`/api/${T}/connections?per=50`)).body || "{}");
      const named = (all2.results ?? []).filter((r) => r.request_no === draft.request_no);
      note(`builds naming ${draft.request_no}: ${named.length} — ${named.map((n) => `${n.connection_no}(${n.state})`).join(" · ") || "none"}; ${answered.connection_no} names no request at all`);
    } else if (answered.id === draft.id) {
      note(`the commit finished ${draft.connection_no} itself — the park carried the build through`);
    }
  }
  const after = await census();
  // ⚠ Printed as LIST ROWS, which is what this endpoint counts, so the figure
  // says what it is rather than being read as builds.
  say(`  after:  ${after.premises} premises · ${after.units} units · ${after.connections} rows on the New connects list (builds AND parked wizards)`);
  say(`\n════ PHASE park · ${findings.length} findings · ${presses} presses ════`);
  findings.forEach((f) => say("  · " + f));
  await browser.close();
  process.exit(0);
}

for (const [what, target] of shapes) {
  say(`\n──── ${what} ────`);
  if (!target) { note(`no open request where ${what} — this seed offers none`); continue; }
  say(`request ${target.request_no} · ${target.state} · resolution=${target.resolution_kind}`);
  await page.goto(`${BASE}/${T}/requests/${target.id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  await shot(`01-request-${target.request_no}`);
  const approve = await byText("Approve");
  if (!approve) { note(`${target.request_no}: no Approve button on the request`); continue; }
  await approve.click(); press("Approve"); await page.waitForTimeout(1500);
  await shot(`02-approve-dialog-${target.request_no}`);

  // ⛔ **THE HALF THE PO's WALK FOUND GREYED.** Blueprint p089 draws
  // `A new connection` LIVE on `SR-26-0001`, whose address matched `PR-0731 ·
  // exact` — *"the resolver matched this address to PR-0731 exactly, and that
  // is EVIDENCE — not the decision"*. So a DISABLED radio here is the defect.
  const radios = await page.$$('input[name="service-request-outcome"]');
  let took = false;
  for (const r of radios) {
    const txt = (await r.evaluate((n) => n.closest("label")?.innerText || "")).replace(/\n/g, " ");
    if (!/new connection/i.test(txt)) continue;
    if (await r.evaluate((n) => n.disabled)) {
      note(`"A new connection" is DISABLED on ${target.request_no} where ${what}: ${txt.slice(0, 120)}`);
      break;
    }
    note(`"A new connection" is OFFERED on ${target.request_no} where ${what}`);
    await r.evaluate((n) => n.click()); press('pick "A new connection"');
    took = true; await page.waitForTimeout(900);
    break;
  }
  if (!took) continue;
  await shot(`03-kind-picked-${target.request_no}`);
  const dialogText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || "");
  writeFileSync(`${OUT}/sr-approve-dialog-${target.request_no}.txt`, dialogText);
  const money = [...dialogText.matchAll(/\$\s?-?[\d,]+\.\d+/g)].map((m) => m[0]);
  const bad = money.filter((m) => !/\.\d{2}$/.test(m));
  if (bad.length) note(`money NOT at 2dp on the approve dialog: ${bad.join(" · ")}`);

  const raise = await byText("Approve and raise the build");
  if (!raise) { note("no 'Approve and raise the build' button"); continue; }
  if (await raise.isDisabled()) {
    note(`"Approve and raise the build" is DISABLED — ${(dialogText.match(/Not yet:[^\n]*/g) ?? []).join(" / ") || "no reason on screen"}`);
    continue;
  }
  await raise.click(); press("Approve and raise the build");
  // ⚠ **THE ASSERTION IS THE ADDRESS THE BROWSER LANDED ON, NOT A SUCCESS
  // MESSAGE.** p089's fourth THEN/WHAT row promises the build's own wizard; a
  // walk that read a toast could not tell that promise from a toast.
  await page.waitForURL((u) => u.pathname.includes("/connections/new"), { timeout: 20000 })
    .catch(() => note(`${target.request_no}: approving did NOT open the build's wizard`));
  await page.waitForTimeout(2500);
  const buildId = new URL(page.url()).searchParams.get("build");
  note(`after approving ${target.request_no} the clerk is at ${new URL(page.url()).pathname} carrying build=${buildId ?? "(none)"}`);
  if (!buildId) continue;
  const draft = JSON.parse((await api(`/api/${T}/connections/${buildId}`)).body || "{}");
  const dd = draft.data ?? draft;
  note(`the draft is ${dd.connection_no} · state=${dd.state} · premises=${dd.premises ? dd.premises.premise_no : "(none yet)"} · from ${dd.request_no}`);
  await shot(`04-wizard-step1-${target.request_no}`);

  // ── THE EIGHT STEPS, FROM WHAT THE APPLICATION ALREADY ANSWERED ─────────
  const stamp = Date.now().toString().slice(-6);
  await page.selectOption("#nc_owner_kind", "builder_developer").catch(() => {});
  if (await page.$("#nc_owner_name")) {
    const prefilled = await page.$eval("#nc_owner_name", (n) => n.value).catch(() => "");
    note(`step 1 opens with the owner name "${prefilled || "(empty)"}" — the applicant, offered`);
    if (prefilled === "") await page.fill("#nc_owner_name", `Willow Bend Developments ${stamp}`);
  }
  await page.selectOption("#nc_owner_subcategory", "permanent").catch(() => {});
  await pickRadio("nc_party_kind", "company");
  for (const sel of ["#nc_tax_id", "#nc_owner_tax_id"]) {
    if (await page.$(sel)) await page.fill(sel, `TX-${stamp}`).catch(() => {});
  }
  await page.fill("#nc_prefix", "Apt").catch(() => {});
  await pickRadio("nc_mode", "our_crew");
  await shot(`05-step1-filled-${target.request_no}`);
  await wizardForward("step 1 · Owner & scope");

  // Step 2 — the ADDRESS. On the unresolved shape it opens on what the
  // applicant typed; on the resolved shape it opens on the property on file.
  const addr = await page.$eval("#nc_address", (n) => n.value).catch(() => "");
  note(`step 2 opens on the address "${addr || "(empty)"}"`);
  if (addr === "") await page.fill("#nc_address", `${stamp} Willow Bend`).catch(() => {});
  for (const [sel, v] of [["#nc_city", "Austin"], ["#nc_postal_code", "78704"], ["#nc_state", "TX"]]) {
    if (await page.$(sel)) { const cur = await page.$eval(sel, (n) => n.value); if (cur === "") await page.fill(sel, v).catch(() => {}); }
  }
  const ptypes = await page.$$eval("#nc_premise_type option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
  if (ptypes.length) await page.selectOption("#nc_premise_type", ptypes[0]).catch(() => {});
  await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => {});
  const offered = await page.$$eval("#services_available-add option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
  for (const code of offered.slice(0, 2)) {
    await page.selectOption("#services_available-add", code).catch(() => {});
    await page.waitForTimeout(250);
  }
  const plans = await page.$$eval("#nc_plan option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
  if (plans.length === 0) note("step 2: #nc_plan offered no plan — the commit will refuse later");
  else await page.selectOption("#nc_plan", plans[0]);
  await shot(`06-step2-premise-${target.request_no}`);
  await wizardForward("step 2 · Premise");

  await page.fill("#nc_from", "1").catch(() => {});
  await page.fill("#nc_to", "2").catch(() => {});
  await page.waitForTimeout(700);
  await shot(`07-step3-units-${target.request_no}`);
  await wizardForward("step 3 · Units");
  await page.waitForTimeout(900);
  await shot(`08-step4-services-${target.request_no}`);
  await wizardForward("step 4 · Services");
  await wizardForward("step 5 · Work orders");
  await wizardForward("step 6 · Charges");
  await wizardForward("step 7 · Communication");
  await page.waitForTimeout(900);
  await shot(`09-step8-review-${target.request_no}`);
  await wizardForward("step 8 · Create connection");
  await page.waitForTimeout(6000);
  await shot(`10-after-the-press-${target.request_no}`);

  // ⚠ **THE DATABASE, NOT THE DONE PANEL.** A walk that read the success screen
  // could not tell *the draft was finished* from *a second build was created
  // beside it*, which is the one way this change could go wrong invisibly.
  const after = JSON.parse((await api(`/api/${T}/connections/${buildId}`)).body || "{}");
  const ad = after.data ?? after;
  // ⚠ **`units` ON THE DETAIL COUNTS UNITS THIS BUILD TOOK A SERVICE AT, NOT
  // UNITS THE COMMIT CREATED**, so a walk that ticks no service grid reads `0`
  // over a property that has just gained two units. The property is asked
  // separately rather than the figure being reported as a gap.
  // ⚠ **`/premises/{id}/units` IS NOT A ROUTE AND THE FIRST DRAFT OF THIS LINE
  // ASKED FOR IT** — the SPA's catch-all answered with HTML and `JSON.parse`
  // took the whole walk down at the last read. The units list is `GET /units`
  // filtered by premises, which is what the property's own screen calls.
  const prem = ad.premises
    ? JSON.parse((await api(`/api/${T}/units?f.premises_id=${ad.premises.id}&per=50`)).body || "{}")
    : {};
  const premUnits = (prem.results ?? prem.data ?? []).length;
  note(`${dd.connection_no} after the press: state=${ad.state} · premises=${ad.premises ? ad.premises.premise_no : "(none)"} · units on that property=${premUnits} · serviced units on the build=${ad.units} · owner account=${ad.owner_account_no ?? "(none)"} · from ${ad.request_no}`);
  // ⚠ **`outcome_ref` IS ON `decision.commit`, NOT ON `header` — AND THE FIRST
  // RUN OF THIS LINE READ `header.outcome_ref` AND PRINTED `(none)` OVER A
  // REQUEST THAT NAMED ITS BUILD CORRECTLY.** The same trap this file's part-2
  // comment already records one field over, made again on the field beside it;
  // `(none)` reads exactly like the defect being walked for. Both places are
  // asked, and the value is COMPARED with the build rather than merely printed:
  // a non-empty `outcome_ref` pointing at the WRONG build would pass a check
  // that only asked whether it was set (law 7, habit 2).
  const srAfter = JSON.parse((await api(`/api/${T}/service-requests/${target.id}`)).body || "{}");
  const sd = srAfter.data ?? srAfter;
  const sh = sd.header ?? {};
  const ref = sd.decision?.commit?.outcome_ref ?? sh.outcome_ref ?? null;
  note(`${target.request_no} now reads state=${sh.state} outcome_ref=${ref ?? "(none)"} — ${ref === dd.connection_no ? "it names THIS build" : `IT DOES NOT NAME ${dd.connection_no}`}`);
  built.push({ shape: what, request_no: target.request_no, connection_no: dd.connection_no, id: buildId, state: ad.state });
}

say(`\n════ PART 2 RESULT: ${built.length} of 2 shapes reached a finished build ════`);
built.forEach((b) => say(`  ${b.shape}: ${b.request_no} → ${b.connection_no} (${b.state})`));

// Parts 3 and 4 report on the build this walk just made, never on whatever
// happened to be newest — otherwise a part-3 answer is about a different build.
let connectionNo = built[0]?.connection_no ?? "";
let connectionId = built[0]?.id ?? "";
const conns = JSON.parse((await api(`/api/${T}/connections?per=50`)).body || "{}");
const crows = conns.data ?? conns.results ?? [];
say(`\nconnections on file: ${crows.length} (envelope total ${conns.total ?? conns.count ?? "?"})`);
const picked = crows.find((r) => r.id === (process.env.CONNO || connectionId))
  ?? crows.find((r) => r.connection_no === process.env.CONNO)
  ?? crows.find((r) => r.id === connectionId)
  ?? crows[0];
if (picked) { connectionNo = picked.connection_no; connectionId = picked.id; }
say(`walking the build ${connectionNo} (${connectionId})`);

// ── PART 3 · WHAT THE BUILD LEFT BEHIND ─────────────────────────────────────
say("\n════ PART 3 · what a committed build leaves behind ════");
const det = JSON.parse((await api(`/api/${T}/connections/${connectionId}`)).body || "{}");
const d = det.data ?? det;
writeFileSync(`${OUT}/sr-connection-detail.json`, JSON.stringify(d, null, 2));
const rec = await api(`/api/${T}/connections/${connectionId}/record`);
writeFileSync(`${OUT}/sr-build-record.json`, rec.body);
const r2 = JSON.parse(rec.body || "{}");
const R = r2.data ?? r2;
say(`  GET /connections/{id}/record → ${rec.status}`);
const seen = {
  premises: d.premises ?? null,
  units: d.units ?? (d.unit_rows || []).length,
  unit_rows: (d.unit_rows || []).length,
  services: (d.services || []).length,
  assets: (d.assets || []).length,
  work_orders: (d.work_orders || []).length,
  owner_account_no: d.owner_account_no ?? null,
  quote_total: d.quote_total ?? null,
  charges: d.charges ?? null,
  outstanding: (d.outstanding || []).length,
  history: (d.history || []).length,
  state: d.state,
};
for (const [k, v] of Object.entries(seen)) say(`  ${k.padEnd(18)} ${JSON.stringify(v)}`);
// The SCREEN half — §9 says database AND screen.
if (d.premises && (d.premises.id || d.premises.premises_id)) {
  const pid = d.premises.id ?? d.premises.premises_id;
  await page.goto(`${BASE}/${T}/premises/${pid}?tab=build`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2600);
  await shot("05-build-tab");
  // ⚠ **THE SIX SECTIONS ARE BEHIND `Expand`, AND A WALK THAT DID NOT PRESS IT
  // REPORTED ON A THIRD OF THE SCREEN (WALK-3, 2026-09-21).** The Build tab
  // opens showing the tiles, live state, owner and scope, the premise and where
  // it came from, and then stops at `More actions · Expand▾`. §9 part 3 asks
  // about UNITS, CHARGES, WORK ORDERS, COMMUNICATION, AUDIT and OUTSTANDING —
  // every one of which is inside that fold. So open everything that opens, then
  // read.
  const opened = await page.evaluate(() => {
    let n = 0;
    for (const d of document.querySelectorAll("details")) if (!d.open) { d.open = true; n += 1; }
    return n;
  });
  for (const b of await page.$$("button")) {
    const t = (await b.innerText()).trim();
    // ⚠ The button reads `Expand▾` with NO SPACE before the caret, and an
    // anchored equality test on `Expand` misses it — which is how the first run
    // of this block reported four sections absent over a fold it never opened.
    if (/^(expand|show all|more actions)/i.test(t)) { await b.click().catch(() => {}); await page.waitForTimeout(700); }
  }
  await page.waitForTimeout(1800);
  note(`the Build tab opened with ${opened} folded section(s); they are read below`);
  await shot("05b-build-tab-expanded");
  const bt = await page.evaluate(() => document.body.innerText);
  writeFileSync(`${OUT}/sr-build-tab.txt`, bt);
  // §9's nine nouns, asked of the SCREEN one at a time and printed including
  // zero — the same discipline the database half already uses.
  for (const [noun, re] of [["units", /\bUNITS\b/], ["charges", /\bCHARGES\b/], ["work orders", /\bWORK ORDERS\b/],
                            ["communication", /\bCOMMUNICATION\b/], ["audit", /\bAUDIT\b/], ["outstanding", /\bOUTSTANDING\b/],
                            ["documents", /\bDOCUMENTS?\b/]]) {
    note(`the Build tab ${re.test(bt) ? "shows" : "does NOT show"} a ${noun} section`);
  }
  const m2 = [...bt.matchAll(/\$\s?-?[\d,]+\.\d+/g)].map((x) => x[0]);
  note(`the Build tab shows ${m2.length} money figures: ${[...new Set(m2)].slice(0, 10).join(" · ") || "(none)"}`);
  const b2 = m2.filter((x) => !/\.\d{2}$/.test(x));
  if (b2.length) note(`money NOT at 2dp on the Build tab: ${b2.join(" · ")}`);
  for (const raw of ["builder_developer", "property_owner", "new_premise", "new_units", "new_service",
                     "our_crew", "storm_water", "vacant_service_off", "thermal_heat"]) {
    if (bt.includes(raw)) note(`RAW SERVER CODE ON SCREEN (Build tab): "${raw}"`);
  }
} else note("the build names no premises, so there is no Build tab to look at");

// ── PART 3b · THE OWNER'S MASTER ACCOUNT, AND THE DOCUMENTS ON IT ───────────
// ⚠ **§9 NAMES BOTH AND THIS SCRIPT ASKED FOR NEITHER (WALK-3, 2026-09-21).**
// *"an account exists with the owner as its master account"* and *"the files
// taken at step 1 actually stored and READABLE AFTERWARDS"* are two of the nine
// nouns, and a record read that prints `owner_account_no` answers only the
// first half of the first one. So: open the account, read its kind off the
// screen, then open its Documents tab and try to GET the file back.
if (d.owner_account_no) {
  const acc = JSON.parse((await api(`/api/${T}/accounts?q=${encodeURIComponent(d.owner_account_no)}&per=5`)).body || "{}");
  const arow = (acc.data ?? acc.results ?? [])[0];
  note(`the owner's account ${d.owner_account_no} reads kind=${arow?.kind ?? "(not published on the list row)"}`);
  if (arow?.id) {
    await page.goto(`${BASE}/${T}/accounts/${arow.id}?tab=documents`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2400);
    await shot("07-account-documents");
    const at = await page.evaluate(() => document.body.innerText);
    writeFileSync(`${OUT}/sr-account-documents.txt`, at);
    note(`the account screen ${/\bmaster\b/i.test(at) ? "says MASTER on it" : "does NOT say master anywhere"}`);
    const docs = JSON.parse((await api(`/api/${T}/accounts/${arow.id}/documents`)).body || "{}");
    const drows = docs.results ?? docs.data ?? [];
    note(`the account holds ${drows.length} document(s): ${drows.map((x) => `${x.name} (${x.content_type}, ${x.size_bytes}B)`).join(" · ") || "(none)"}`);
    for (const one of drows) {
      const item = JSON.parse((await api(`/api/${T}/accounts/${arow.id}/documents/${one.id}`)).body || "{}");
      // ⚠ A URL IS NOT A READ. The item carries a link; whether a browser on
      // this page can follow it is the question §9 actually asks, and a
      // `file://` link answers NO however correct the row behind it is.
      const scheme = String(item.url || "").split(":")[0];
      note(`  "${one.name}" is served as a ${scheme}: link${scheme === "file" ? " — a path on the SERVER's disk, which no browser may open from an http page" : ""}`);
    }
  }
} else note("the build opened no owner account, so there is none to read documents from");

// ── PART 3c · THE THREE NOUNS THAT ARE ONLY EVER ON ANOTHER SCREEN ──────────
//
// ⚠ **§9 SAYS *"checked in the database AND on the screen"*, AND THREE OF ITS
// NINE NOUNS HAVE NO PLACE ON THE BUILD TAB AT ALL (WALK-A, 2026-09-21).** The
// OWNER is a premises fact and lives on the premise register; the ASSETS are
// the meter registry's; the CHARGES are the bill's. A part-3 answer read only
// off the build read therefore says nothing about the screens a clerk would
// actually open to check any of them, and the build read can be perfectly
// right while the register a utility runs on is empty.
const pid3 = d.premises?.id ?? d.premises?.premises_id ?? null;
if (pid3) {
  // (a) THE OWNER ON THE PREMISE REGISTER. Step 1 marks *Owner or developer*
  // REQUIRED, so the one thing this screen must not say is nothing.
  await page.goto(`${BASE}/${T}/premises/${pid3}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  await shot("08-premises-overview");
  const ov = await page.evaluate(() => document.body.innerText);
  writeFileSync(`${OUT}/sr-premises-overview.txt`, ov);
  const ownerLine = ov.split("\n").map((l) => l.trim())
    .findIndex((l) => /^owner\b/i.test(l));
  note(`the premise register's Overview ${ownerLine >= 0
    ? `says "${ov.split("\n").map((l) => l.trim()).slice(ownerLine, ownerLine + 2).join(" → ")}"`
    : "carries NO owner line at all"}`);

  // (b) THE METERS ON THE ASSET REGISTER — PO ruling 2026-09-21: a number is
  // GENERATED and ASSIGNED and the asset is NOT installed and NOT activated.
  // Read the words a clerk reads, never the enum.
  await page.goto(`${BASE}/${T}/premises/${pid3}?tab=assets`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2400);
  await shot("09-premises-assets");
  const at3 = await page.evaluate(() => document.body.innerText);
  writeFileSync(`${OUT}/sr-premises-assets.txt`, at3);
  const nos = [...at3.matchAll(/\bM-\d{5}\b/g)].map((m) => m[0]);
  note(`the asset register shows ${new Set(nos).size} generated meter number(s) for this build`);
  for (const word of ["Installed", "In service", "Active", "Inventory", "Not installed"]) {
    if (at3.includes(word)) note(`  the asset register says "${word}" on this screen`);
  }
}
// (c) THE BILL ITSELF. §9's money clause names *"the charges raised"*, and the
// build record's `money.invoice_no` is a NUMBER — whether a clerk can open the
// document behind it, and whether the figures on it add up, is the question.
const recMoney = (R && R.money) || {};
if (recMoney.invoice_no) {
  const inv = JSON.parse((await api(`/api/${T}/invoices?q=${encodeURIComponent(recMoney.invoice_no)}&per=5`)).body || "{}");
  const irow = (inv.data ?? inv.results ?? [])[0];
  if (!irow) note(`the bill ${recMoney.invoice_no} cannot be found through the bills list`);
  else {
    await page.goto(`${BASE}/${T}/billing/bills/${irow.id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2400);
    await shot("10-quote-bill");
    const bt3 = await page.evaluate(() => document.body.innerText);
    writeFileSync(`${OUT}/sr-quote-bill.txt`, bt3);
    const figs = [...bt3.matchAll(/\$\s?-?[\d,]+\.\d+/g)].map((m) => m[0]);
    note(`the quote bill ${recMoney.invoice_no} shows ${figs.length} money figure(s): ${[...new Set(figs)].slice(0, 8).join(" · ") || "(none)"}`);
    const sub = bt3.match(/Subtotal[^\n]*\n\s*([^\n]+)/i);
    note(`the quote bill's Subtotal line reads ${sub ? JSON.stringify(sub[1].trim()) : "(no Subtotal line on screen)"}`);
  }
} else note("the build record names no invoice, so there is no bill to open");

// ── PART 4 · FIND IT AGAIN ──────────────────────────────────────────────────
say("\n════ PART 4 · find it again in the list ════");
await page.goto(`${BASE}/${T}/accounts?tab=new-connects`, { waitUntil: "networkidle" });
await page.waitForTimeout(2600);
await shot("06-list");
const listText = await page.evaluate(() => document.body.innerText);
writeFileSync(`${OUT}/sr-list.txt`, listText);
note(`the list ${listText.includes(connectionNo) ? "SHOWS" : "does NOT show"} ${connectionNo} on its first page`);
const pager = listText.match(/\b\d+\s*[–-]\s*\d+\s+of\s+[\d,]+/);
note(`pager line: ${pager ? pager[0] : "(none found on screen)"}`);
// NFR-3 — the SERVER must paginate, so ask it.
// ⚠ **`per=2` PROVES NOTHING HERE AND A WALK THAT USED IT WOULD REPORT A FALSE
// BREACH.** `core/pagination.clamp_page_size` clamps any `per` below the
// smallest declared size UP to 50 (`PAGE_SIZES = 50,100,200,500,1000`), and
// `_page_number` clamps a page past the end back to the last one — both by
// `BR-SHL-011`'s *never error*. So `per=2&page=2` on a nine-row list returns
// all nine rows twice, which reads exactly like an unpaginated endpoint and is
// not one. Ask the question the server can answer instead: does the envelope
// carry page/per/total, and does a page past the end come back clamped rather
// than unbounded?
// The envelope is DRF's four keys — count / next / previous / results — built
// by hand in `_connections_envelope` because the SELECTOR does the slicing.
const p1 = JSON.parse((await api(`/api/${T}/connections?per=50&page=1`)).body || "{}");
const pN = JSON.parse((await api(`/api/${T}/connections?per=50&page=99`)).body || "{}");
const n1 = (p1.results ?? p1.data ?? []).length;
note(`server pagination: envelope carries count=${p1.count ?? "(absent)"} next=${p1.next ?? "null"} previous=${p1.previous ?? "null"}, page 1 returned ${n1} rows`);
note(`page=99 returned ${(pN.results ?? pN.data ?? []).length} rows with next=${pN.next ?? "null"} — a page past the end clamps rather than erroring, which is BR-SHL-011`);
note(`the list read slices in SQL (connection_reads.list_connections: combined[start : start + size]), so NFR-3's server pagination is real on this list; with ${p1.count ?? p1.total ?? "?"} rows on file a second page cannot be walked in a browser today`);
// SEARCH, five ways, through the server the screen uses.
const target2 = picked ?? {};
const terms = [["connection number", connectionNo],
               ["premise", target2.premises?.premise_no ?? target2.premises?.premises_no ?? target2.premises_no ?? ""],
               ["address", (target2.premises?.address ?? target2.address ?? "").split(",")[0]],
               ["applicant", target2.applicant ?? ""],
               ["request number", target2.request_no ?? ""]];
for (const [what, term] of terms) {
  if (!term) { note(`search by ${what}: nothing to search with — the row carries no value`); continue; }
  const res = JSON.parse((await api(`/api/${T}/connections?q=${encodeURIComponent(term)}&per=10`)).body || "{}");
  const got = (res.data ?? res.results ?? []);
  note(`search by ${what} ("${term}") → ${got.length} row(s)${got.some((g) => g.id === connectionId) ? ", ours among them" : ", OURS NOT AMONG THEM"}`);
}
// ── FILTERS AND THE COLUMN SELECTOR, USED RATHER THAN COUNTED ───────────────
// ⚠ **NEITHER CONTROL IS A `<button>` AND A WALK THAT LOOKED FOR ONE REPORTED
// BOTH MISSING.** The filter is a `<details>` whose summary reads `+ Filter ▾`;
// the column chooser is a `<summary aria-label="Show or hide columns">` holding
// an icon. The first run of this walk searched `button` text for /filter/ and
// /column/, found neither, and printed two empty arrays over two controls that
// work — law 7's *looking at the wrong thing*. So open them and USE them: the
// only answer to *does the filter narrow it* is a row count before and after.
const searchBox = await page.$('input[placeholder*="Connection"]');
note(`the search box ${searchBox ? `is there and reads "${await searchBox.getAttribute("placeholder")}"` : "is MISSING"}`);
const countRows = () => page.evaluate(() => document.querySelectorAll("tbody tr").length);
const atRest = await countRows();
await page.evaluate(() => { const d = [...document.querySelectorAll("details")].find((x) => /Filter/.test(x.textContent)); if (d) d.open = true; });
await page.waitForTimeout(700);
const options = await page.evaluate(() => {
  const d = [...document.querySelectorAll("details")].find((x) => /Filter/.test(x.textContent));
  return d ? [...d.querySelectorAll("label")].map((n) => n.innerText.trim()) : [];
});
note(`the Show filter offers ${options.length} states: ${options.join(" · ") || "(none)"}`);
// A raw code reads as one lower-case token or a snake_case one; a word a clerk
// was meant to read is Capitalised. Both spellings are checked because `parked`
// carries no underscore and a test looking only for `_` would miss half of it.
for (const raw of options) if (/^[a-z][a-z_]*$/.test(raw)) note(`RAW SERVER CODE IN THE FILTER LIST: "${raw}"`);
if (options.length) {
  await page.evaluate(() => { const d = [...document.querySelectorAll("details")].find((x) => /Filter/.test(x.textContent));
    const l = [...d.querySelectorAll("label")].find((n) => /^Draft$/i.test(n.innerText.trim())) ?? d.querySelector("label"); l.click(); });
  await page.waitForTimeout(2400);
  const narrowed = await countRows();
  note(`filtering narrowed the list from ${atRest} rows to ${narrowed}`);
  note(`the choice ${/f\.state=/.test(page.url()) ? "is in the address" : "is NOT in the address, so a reload loses it and the view cannot be shared"}`);
  await page.goto(`${BASE}/${T}/accounts?tab=new-connects`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
}
const chooser = await page.$('summary[aria-label="Show or hide columns"]');
if (!chooser) note("the column selector is MISSING");
else {
  const headsBefore = await page.evaluate(() => [...document.querySelectorAll("thead th")].map((n) => n.innerText.trim()).join(" | "));
  await chooser.click(); await page.waitForTimeout(1100);
  for (const c of await page.$$('input[type="checkbox"]')) {
    const lbl = await c.evaluate((n) => (n.closest("label")?.innerText || "").trim());
    if (/^target$/i.test(lbl)) { await c.evaluate((n) => n.click()); break; }
  }
  await page.waitForTimeout(1500);
  const headsAfter = await page.evaluate(() => [...document.querySelectorAll("thead th")].map((n) => n.innerText.trim()).join(" | "));
  note(`the column selector ${headsBefore === headsAfter ? "DID NOT change the table" : "took a column out of the table"}`);
  await page.reload({ waitUntil: "networkidle" }); await page.waitForTimeout(2000);
  const headsReload = await page.evaluate(() => [...document.querySelectorAll("thead th")].map((n) => n.innerText.trim()).join(" | "));
  note(`after a reload the column choice ${headsReload === headsAfter ? "survived" : "was lost"}`);
}
say(`\n════ ${findings.length} findings · ${presses} presses ════`);
writeFileSync(`${OUT}/sr-findings.json`, JSON.stringify({ findings, presses, connectionNo, connectionId, seen }, null, 2));
await browser.close();
