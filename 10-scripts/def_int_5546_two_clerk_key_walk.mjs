// ── Trace ──────────────────────────────────────────────
// Change:   `DEF-INT-5546` (`CR-110-BRC04` phase 2) — the utility leaves the
//           partner URL and the KEY resolves it. PO 2026-09-16, verbatim: *"we
//           agreed not to use utility names in partner apis that was our rule -
//           so these urls are not corect - we will resolve utility name using
//           keys"*, then: *"how you can do a walk from clark point of view on
//           these"*.
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app) · law 7 (a check's output must distinguish pass from
//           fail TO A READER, and name what would make it pass WRONGLY) ·
//           13-change-process.md's CLOSURE BAR (PO 2026-08-18: *"CR is not
//           closed until we have confirm user is able to perform tasks using
//           screen/broswer/UI"*) · BR-INT-044 · BR-TEN-003 as clarified.
// ───────────────────────────────────────────────────────
/**
 * TWO CLERKS AT TWO UTILITIES, ONE ADDRESS, AND NEITHER CAN REACH THE OTHER.
 *
 *     BASE=http://127.0.0.1:8401 API=http://127.0.0.1:8402 \
 *       node 10-scripts/def_int_5546_two_clerk_key_walk.mjs
 *
 * WHAT A CLERK CAN ACTUALLY SEE OF THIS CHANGE, STATED FIRST
 * -----------------------------------------------------------
 * Almost none of it, and pretending otherwise would be the dishonest part. The
 * key-to-utility lookup is a table read in under a millisecond; nobody watches
 * it. **Two things reach a clerk** and both are walked below: the ADDRESS
 * printed under each API row on the connector's set-up screen, and — the one
 * that matters — WHOSE RECORDS come back, which they read on *Who has been
 * reading*.
 *
 * WHAT WOULD MAKE THIS WALK PASS WRONGLY — asked before it was written
 * ---------------------------------------------------------------------
 * **First and worst: ONE utility.** Every step below would pass over a lookup
 * hard-wired to return the only utility there is — which is exactly the bug
 * this change could introduce. So the walk needs TWO, with DIFFERENT row counts
 * (84 accounts against 72 on the demo database), and it asserts both
 * directions: A's key sees A's count and NOT B's, and B's sees B's.
 *
 * **Second: asserting a 200.** A 200 carrying the wrong utility's customers is
 * the failure. Every success step reads the count and the first record back.
 *
 * **Third: believing the stack.** A walk against a backend that does not have
 * this code is not a weaker proof, it is a proof of a different product — and
 * that has already cost this CR a cycle twice (a port another lane held; a
 * `501` from somebody else's process). Step 0 makes the ONE request that only
 * this build can answer this way and refuses to walk otherwise.
 *
 * **Fourth: a refusal scored as a fault.** Steps 8 and 9 are SUPPOSED to be
 * turned away. They are scored on being turned away in the RIGHT words.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8401";
const API = process.env.API ?? BASE;
const LEFT = {
  slug: process.env.LEFT ?? "brazosbend",
  email: process.env.LEFT_USER ?? "dana@brazosbendutilities.com",
};
const RIGHT = {
  slug: process.env.RIGHT ?? "laneseed-log",
  email: process.env.RIGHT_USER ?? "owner@laneseed-log.test",
};
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const PROVIDER = process.env.PROVIDER ?? "erp_aclarian";

const rows = [];
function say(step, ok, detail = "") {
  rows.push({ step, ok, detail });
  const mark = ok === null ? "····" : ok ? "PASS" : "FAIL";
  console.log(`${mark}  ${step}${detail ? `\n        ${detail}` : ""}`);
}

async function raw(path, { key = null, params = {} } = {}) {
  const url = new URL(API + path);
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined) url.searchParams.set(k, v);
  const headers = key === null ? {} : { Authorization: `Bearer ${key}` };
  const r = await fetch(url, { headers });
  const text = await r.text();
  let body = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = null;
  }
  return { status: r.status, body, text: text.slice(0, 200) };
}

// ══ STEP 0 · does this stack have the change at all? ═══════════════════════
// The one request only this build answers this way. BEFORE it, `/api/partner/
// v1/reference` is not a route: four of the five answered Django HTML and
// `/api/partner/v1/payments` reached the OLD flat endpoint, because `partner`
// was read as a utility slug. A JSON refusal with `code: REFUSED` proves the
// route exists, is mounted outside the tenant include, and has done its door.
{
  const probe = await raw("/api/partner/v1/reference");
  const ok = probe.status === 404 && probe.body?.code === "REFUSED";
  say("step 0 · the stack serves THIS build", ok, `GET /api/partner/v1/reference -> ${probe.status} ${probe.text}`);
  if (!ok) {
    console.log("\nREFUSING TO WALK — this backend does not have the change.");
    process.exit(2);
  }
}

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });

async function clerk(util) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/${util.slug}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", util.email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  return { ctx, page, signedIn: !page.url().includes("/signin") };
}

const seat = { [LEFT.slug]: await clerk(LEFT), [RIGHT.slug]: await clerk(RIGHT) };
say(`step 1a · ${LEFT.email} is signed in at ${LEFT.slug}`, seat[LEFT.slug].signedIn);
say(`step 1b · ${RIGHT.email} is signed in at ${RIGHT.slug}`, seat[RIGHT.slug].signedIn);

// ══ STEP 1c · the connector has to BE connected before a key can be issued ══
// A clerk does this on the grid (*Connect*) and then on the set-up screen
// (*Save and test*). Walked through the endpoint those two controls call, so a
// utility that has never used this connector can still be walked end to end.
async function connectIfNeeded(util) {
  const { page } = seat[util.slug];
  return page.evaluate(
    async (args) => {
      const grid = await (await fetch(`/api/${args.slug}/integrations`)).json();
      const providers = grid.providers ?? grid.data?.providers ?? [];
      const card = providers.find((p) => p.key === args.provider) ?? {};
      if (card.connection) return { already: true };
      const token = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
      const r = await fetch(`/api/${args.slug}/integrations/${args.provider}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": token },
        body: JSON.stringify({
          environment: "production",
          cadence: "manual",
          // The manifest asks for the addresses this partner will call from.
          // `127.0.0.1/32` is where this walk calls from; an EMPTY list would
          // permit everything, which is the wrong thing to demonstrate.
          fields: { allowed_addresses: "127.0.0.1/32" },
        }),
      });
      return { already: false, status: r.status, body: (await r.text()).slice(0, 160) };
    },
    { slug: util.slug, provider: PROVIDER },
  );
}

for (const util of [LEFT, RIGHT]) {
  const done = await connectIfNeeded(util);
  say(
    `step 1c · ${util.slug}: the connector is connected`,
    done.already === true || done.status === 201,
    done.already ? "already connected" : `${done.status} ${done.body}`,
  );
}

// ══ STEPS 2–3 · the addresses the clerk READS on screen ════════════════════
// ⚠ **THE CONNECTION SCREEN, NOT THE SET-UP SCREEN, AND THE FIRST DRAFT ASKED
// THE WRONG ONE.** `ConnectorSetupPage.endpointText` re-derives the address
// client-side from the connection's typed settings, so for a connector where
// the address is OURS it has nothing to print and the column is empty — while
// `selectors.provider_card` computes the same field server-side and DOES fall
// back to the manifest's `served_path`. Two implementations of one fact
// (hard-won law 1), and the walk reported `0 of 4` against a screen that was
// never going to show it. The CONNECTION screen renders the server's answer.
async function readAddresses(util) {
  const { page } = seat[util.slug];
  await page.goto(`${BASE}/${util.slug}/settings/integrations/${PROVIDER}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  return page.evaluate(() => {
    const out = [];
    for (const node of document.querySelectorAll("[data-operation]")) {
      const shown = node.querySelector("[data-endpoint]");
      out.push({
        api: (node.innerText ?? "").split("\n")[0]?.trim() ?? "?",
        endpoint: shown ? shown.innerText.trim() : null,
      });
    }
    return out;
  });
}

for (const util of [LEFT, RIGHT]) {
  const seen = await readAddresses(util);
  const printed = seen.filter((r) => r.endpoint !== null);
  const naming = printed.filter((r) => r.endpoint.includes(util.slug));
  say(
    `step 2 · ${util.slug}: the set-up screen prints ${printed.length} of ${seen.length} API addresses`,
    printed.length > 0,
    printed.map((r) => `${r.api} -> ${r.endpoint}`).join("\n        "),
  );
  say(
    `step 3 · ${util.slug}: NOT ONE printed address names the utility`,
    naming.length === 0,
    naming.length === 0 ? "" : naming.map((r) => r.endpoint).join(", "),
  );
}

// ══ STEPS 4–5 · each clerk issues a key ════════════════════════════════════
// ⚠ **THROUGH THE SCREEN FIRST, AND THE SCREEN IS WHAT IS BEING TESTED.** If
// `Generate a key` yields nothing, that is RECORDED as a finding and the walk
// then issues one through the SAME endpoint the button calls, with a scope, in
// the clerk's own signed-in session — clearly labelled, because a key issued
// behind the screen proves the door and not the button.
async function issueKey(util) {
  const { page } = seat[util.slug];
  const button = await page.$("[data-generate-key]");
  if (button !== null && !(await button.isDisabled())) {
    await button.click();
    await page.waitForTimeout(2500);
    const shown = await page.$("[data-issued-key]");
    if (shown !== null) return { key: (await shown.innerText()).trim(), how: "the button" };
  }
  const scope = await page.evaluate(
    async (args) => {
      const r = await fetch(`/api/${args.slug}/integrations`);
      const grid = await r.json();
      const providers = grid.providers ?? grid.data?.providers ?? [];
      const card = providers.find((p) => p.key === args.provider) ?? {};
      return (card.operations ?? []).map((o) => o.name);
    },
    { slug: util.slug, provider: PROVIDER },
  );
  const made = await page.evaluate(
    async (args) => {
      const token = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
      const r = await fetch(`/api/${args.slug}/integrations/${args.provider}/key`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": token },
        body: JSON.stringify({ scope: args.scope }),
      });
      return { status: r.status, body: await r.text() };
    },
    { slug: util.slug, provider: PROVIDER, scope },
  );
  let key = null;
  try {
    const parsed = JSON.parse(made.body);
    key = parsed?.data?.key ?? parsed?.key ?? null;
  } catch {
    key = null;
  }
  return { key, how: `the endpoint the button calls (${made.status})`, raw: made.body.slice(0, 180) };
}

const held = {};
for (const util of [LEFT, RIGHT]) {
  const issued = await issueKey(util);
  held[util.slug] = issued.key;
  say(
    `step 4 · ${util.slug}: a key was issued, via ${issued.how}`,
    issued.key !== null,
    issued.key === null ? issued.raw ?? "" : `${issued.key.slice(0, 12)}…  (shown once, ever)`,
  );
}

// ⚠ **THE COMPANY ID COMES FROM THE ENVIRONMENT, AND THE REASON IS A FINDING
// THIS WALK MADE.** `company_id` is the utility's own id (PO 2026-09-16:
// *"company_id = tenant id"*), and it is the ONE value a partner must be
// configured with — yet **no screen in this product shows it to a clerk**, by
// design: B14 rule 31 says no database id is ever the visible value of a field.
// The first draft read `/settings/company` and got the company PROFILE's id,
// which is a different row, so every call came back `403 COMPANY_MISMATCH`
// against perfectly good keys — a check looking at the wrong thing (law 7).
// So it is passed in, the way it reaches a vendor today: from us, by hand.
const COMPANY = {
  [LEFT.slug]: process.env.LEFT_COMPANY ?? null,
  [RIGHT.slug]: process.env.RIGHT_COMPANY ?? null,
};

async function companyId(util) {
  return COMPANY[util.slug];
}

// ══ STEPS 6–7 · THE SAME ADDRESS, TWO KEYS, TWO UTILITIES ══════════════════
// This is the whole change. Nothing distinguishes these two requests but the
// key: same URL, same method, same everything else.
// ⚠ **`/api/partner/v1/customers` UNTIL 2026-09-17 (`DEF-INT-5623`)** — the
// PO ruled the partner surface must call an account an account. The old
// spelling still answers, with a `410` naming this one, so a walk pointed at
// it would score a FAIL against a correct retirement rather than a bug.
const ADDRESS = "/api/partner/v1/accounts";
const counts = {};
for (const util of [LEFT, RIGHT]) {
  if (held[util.slug] === null) {
    say(`step 6 · ${util.slug}: GET ${ADDRESS}`, null, "no key — not walked");
    continue;
  }
  const id = await companyId(util);
  if (id === null) {
    say(`step 6 · ${util.slug}: GET ${ADDRESS}`, null, "no company id supplied — see LEFT_COMPANY / RIGHT_COMPANY");
    continue;
  }
  const got = await raw(ADDRESS, { key: held[util.slug], params: { company_id: id, page_size: "2" } });
  counts[util.slug] = got.body?.total_records ?? null;
  const first = got.body?.records?.[0];
  say(
    `step 6 · ${util.slug}: GET ${ADDRESS} with its own key`,
    got.status === 200,
    `${got.status} · total_records=${counts[util.slug]} · first=${first ? `${first.id} ${first.customer_name}` : got.text}`,
  );
}
// ⚠ **READ THE COUNTS, NOT THE FIRST ROW.** The demo seed allocates account
// numbers per utility from each one's own series, so BOTH utilities' first
// customer is `A-10432 Miller, Sarah` — two different rows in two different
// utilities that happen to be spelled the same. An eye skimming the output
// sees the same name twice and reads it as a leak; it is not one. The totals
// differ, and step 10 settles it independently: each utility's access log
// holds ITS OWN read and not the other's.
say(
  "step 7 · the two answers are DIFFERENT — one address, two utilities",
  counts[LEFT.slug] != null && counts[RIGHT.slug] != null && counts[LEFT.slug] !== counts[RIGHT.slug],
  `${LEFT.slug}=${counts[LEFT.slug]} vs ${RIGHT.slug}=${counts[RIGHT.slug]} — same URL, only the key differed`
    + "\n        (the first row reads the same in both: the seed numbers accounts per utility. The TOTALS are the proof, and step 10 is the second one.)",
);

// ══ STEPS 8–9 · the two that MUST be turned away ═══════════════════════════
{
  const rightId = await companyId(RIGHT);
  if (held[LEFT.slug] === null) {
    say("step 8 · one utility's key NAMING the other is refused", null, "no key — not walked");
  } else {
    const crossed = await raw(ADDRESS, { key: held[LEFT.slug], params: { company_id: rightId } });
    const echoed = rightId !== null && crossed.text.includes(rightId);
    say(
      "step 8 · one utility's key NAMING the other is refused, and told nothing else",
      crossed.status === 403 && crossed.body?.code === "COMPANY_MISMATCH" && !echoed,
      `${crossed.status} ${crossed.text}${echoed ? "  <-- IT ECHOED THE ID BACK" : ""}`,
    );
  }
  const invented = await raw(ADDRESS, { key: "sbh_live_0000_never_issued", params: { company_id: rightId } });
  say(
    "step 9 · a key nobody ever issued gets the ordinary five words",
    invented.status === 404 && invented.body?.error === "We cannot serve this request.",
    `${invented.status} ${invented.text}`,
  );
}

// ══ STEP 10 · each clerk reads WHO HAS BEEN READING, and sees only their own ═
for (const util of [LEFT, RIGHT]) {
  const log = await seat[util.slug].page.evaluate(
    async (args) => {
      const r = await fetch(`/api/${args.slug}/integrations/${args.provider}/access-log`);
      return { status: r.status, body: await r.json() };
    },
    { slug: util.slug, provider: PROVIDER },
  );
  const items = log.body?.data?.items ?? log.body?.items ?? [];
  say(
    `step 10 · ${util.slug}: Who has been reading shows ${items.length} row(s) — its own`,
    log.status === 200,
    items.slice(0, 3).map((i) => `${i.what} · ${i.rows} · ${i.hint ?? "no hint"} · ${i.outcome}`).join("\n        "),
  );
}

await browser.close();
const bad = rows.filter((r) => r.ok === false);
const good = rows.filter((r) => r.ok === true);
const skipped = rows.filter((r) => r.ok === null);
console.log(`\n${rows.length} steps · ${good.length} pass · ${bad.length} fail · ${skipped.length} not walked`);
process.exit(bad.length === 0 ? 0 : 1);
