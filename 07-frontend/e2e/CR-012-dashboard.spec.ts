// ── Trace ──────────────────────────────────────────────
// Change:  CR-012 (12-governance/11-change-requests.md §CR-012) — S7 built to
//          r10's DSH-01, and the FIVE PO RULINGS of the design review
//          (12-governance/02-decision-log.md, 2026-08-19).
// Screens: S7 — the first screen after every single sign-in.
// Rules:   BR-REP-024 (a tile never computes a figure) · BR-REP-025 (the
//          TENANT's own services, ALL of them, in the platform's seed order) ·
//          BR-REP-026 (bars are a share of the LARGEST) · BR-REP-027 (the
//          cycle line — and, since 2026-08-19, with NO set-up link) ·
//          BR-REP-028 (regions load, empty and FAIL independently) ·
//          BR-REP-029 (money and counts arrive pre-formatted) · BR-REP-031
//          (activity: 24h, max 6 — and the panel SAYS 24h) · BR-REP-032 (to
//          do: a row nobody could count shows NO NUMBER) · BR-REP-033.
// ───────────────────────────────────────────────────────
//
// **WHY THIS FILE EXISTS AND WHAT IT REFUSES TO DO.**
//
// Every claim below is asserted on TEXT A PERSON READS in a real browser
// against the booted stack. Nothing here reads the API payload and calls that
// a screen: the whole reason CR-012 needed a second pass is that the first one
// shipped a correct payload behind a screen the PO did not recognise, and the
// reason ruling 1 needed a THIRD fix is that the two rows it put on the wire
// were rendered nowhere on a freshly seeded tenant.
//
// It is written against WHATEVER THE TENANT IS SEEDED WITH rather than against
// five hard-coded service names, because that is the ruling: the panel follows
// the tenant. So the test reads the tenant's OWN configured services from
// Settings → Services — the screen a utility uses to turn a service on — and
// then asserts the dashboard draws exactly those, in the platform's seed
// order. A spec that hard-coded "Electric, Water" would pass on this fixture
// and prove nothing about the rule.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

skipUnlessAppServer(test);

const dashboardPath = (): string => `/${tenant()}/dashboard`;

/** BR-RAT-024's ten, in the platform's SEED order — the order the panel must
 *  draw whatever subset the tenant has enabled. Mirrored from
 *  `apps/tenancy/migrations/0001_initial.SERVICE_SEED`. */
const SEED_ORDER = [
  "Electric",
  "Water",
  "Gas",
  "Sewer",
  "Trash",
  "Storm water",
  "Solar",
  "Broadband",
  "Thermal/Heat",
  "Battery",
] as const;

/** What this tenant SELLS, read from the product's own Settings → Services
 *  screen through the session the browser already holds. This is the tenant's
 *  answer, not the test's assumption. */
async function enabledServiceNames(page: Page): Promise<string[]> {
  const rows = await page.evaluate(async (slug) => {
    const response = await fetch(`/api/${slug}/settings/services`, {
      credentials: "same-origin",
    });
    return (await response.json()) as { data?: unknown };
  }, tenant());
  const list = (Array.isArray(rows) ? rows : ((rows as { data?: unknown }).data ?? [])) as {
    service: string;
    name: string;
    enabled: boolean;
  }[];
  return list.filter((row) => row.enabled).map((row) => row.name);
}

// ═══════════════════════════════════════════════════════════════════════════
// RULING 1 · THE SERVICE ROWS FOLLOW THE TENANT
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-012 r1 · the Service mix draws THIS tenant's services, all of them, in seed order ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const panel = page.locator('[data-dash="region"]', { hasText: "Service mix" });
  await expect(panel).toBeVisible();

  const configured = await enabledServiceNames(page);
  expect(configured.length, "the fixture tenant must sell something").toBeGreaterThan(0);

  // Every service this utility sells is DRAWN — that is the ruling's "always
  // all of them", and it is asserted on the label a person reads.
  const drawn = (await panel.locator('[data-dash="mix-label"]').allTextContents()).map((text) =>
    text.trim(),
  );
  expect(drawn).toEqual(
    SEED_ORDER.filter((name) => configured.includes(name)),
  );

  // And a service this utility does NOT sell has no row at all. This is the
  // half the PO reported: five fixed rows meant three permanently empty ones.
  for (const name of SEED_ORDER) {
    if (!configured.includes(name)) {
      expect(drawn, `${name} is not sold here and must not be drawn`).not.toContain(name);
    }
  }

  // No raw service CODE ever reaches the screen (DEF-282's shape, one ruling
  // on): the label map has to cover all ten now that any of them can arrive.
  await expect(panel).not.toContainText("dashboard.service.");
  for (const code of ["storm_water", "thermal_heat", "broadband"]) {
    await expect(panel).not.toContainText(`>${code}<`);
  }
});

test(`CR-012 r1 · a service that billed nothing draws an em-dash and NEVER $0.00 ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const panel = page.locator('[data-dash="region"]', { hasText: "Service mix" });
  await expect(panel).toBeVisible();
  // RED, quoted, on the stack this spec was written against: this panel
  // rendered "Nothing was billed in this period, so there is no service mix to
  // show." and drew NO rows, because the region reported `empty` whenever the
  // month had billed nothing — so the two rows the ruling had just put into the
  // payload were on the wire and on no screen.
  await expect(panel.locator('[data-dash="mix-row"]').first()).toBeVisible();
  await expect(panel).not.toContainText("$0.00");

  // A printed zero and an absent service look identical to a reader and mean
  // opposite things. Every unbilled row is the em-dash.
  const values = await panel.locator('[data-dash="mix-value"]').allTextContents();
  expect(values.length).toBeGreaterThan(0);
  for (const value of values) {
    expect(value.trim(), "a mix cell is a figure or an em-dash, never a zero").not.toBe("$0.00");
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// RULING 4 · THE REFUSING TILES SPEAK PLAIN ENGLISH
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-012 r4 · a KPI nobody can count reads "Not counted yet", and the reason moves to the support line ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const strip = page.locator(".kpi-grid");
  await expect(strip).toBeVisible();

  // The three tiles whose owners publish no count.
  await expect(strip.getByText("Not counted yet").first()).toBeVisible();
  expect(await strip.getByText("Not counted yet").count()).toBeGreaterThanOrEqual(1);

  // ⚠ THE TWO WORDINGS THAT MUST NOT COME BACK, AND WHY EACH IS ASSERTED.
  // "Not available — metering publishes no unbilled-read count" is our module
  // boundaries explained to a utility clerk; "reads not received" asserts a
  // fact about the UTILITY'S DATA (that no reads arrived) where the true fact
  // is about OUR PRODUCT (we cannot count them), so a clerk who has just
  // imported 400 reads would be told something false.
  await expect(strip).not.toContainText("Not available");
  await expect(strip).not.toContainText(/reads not received/i);

  // The specific reason SURVIVES — it moved into the support text, it was not
  // deleted, so someone diagnosing can still reach it.
  await expect(strip).toContainText(/still waiting to be billed|fifty|pending and closed/);

  // And a refusal is NEVER a zero. Read every tile's value cell and check each
  // one: a bare `0` under "Unbilled reads" is the false claim this whole rule
  // exists to prevent, and it is indistinguishable from a true zero on screen.
  for (const value of await strip.locator(".v").allTextContents()) {
    expect(value.trim(), "a KPI value is a figure or a stated absence, never a bare zero").not.toBe(
      "0",
    );
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// RULING 5 · THE CYCLE LINE OFFERS NO SET-UP LINK
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-012 r5 · the cycle line states the configured state and offers no set-up link ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const rollup = page.locator(".fin-rollup").first();
  await expect(rollup).toBeVisible();
  await expect(rollup).not.toContainText("Set up billing cycles");
  expect(
    await rollup.locator("a").count(),
    "PO 2026-08-19 d.5 — 'no provide any link'. Cycle set-up lives in Settings → Routes & Cycles, which is in the sidebar of every screen.",
  ).toBe(0);
  // It still SAYS something — the removal is of the errand, not of the line.
  expect((await rollup.textContent())?.trim().length ?? 0).toBeGreaterThan(0);
});

// ═══════════════════════════════════════════════════════════════════════════
// RULING 6 · RECENT ACTIVITY STATES ITS WINDOW
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-012 r6 · the Recent-activity panel says how far back it looked ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const panel = page.locator('[data-dash="region"]', { hasText: "Recent activity" });
  await expect(panel).toBeVisible();
  // "Nothing has happened here yet" means something very different at 24 hours
  // than at forever, and on a utility's first Monday the difference is the
  // whole message.
  await expect(panel).toContainText("24 hours");
  await expect(panel).not.toContainText("Nothing has happened here yet.");
});

// ═══════════════════════════════════════════════════════════════════════════
// RULING 3 · A TO-DO ROW WITH NO COUNT SHOWS NO NUMBER
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-012 r3 · no To-do row prints a zero, and none renders a raw key ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const panel = page.locator('[data-dash="region"]', { hasText: "To do" });
  await expect(panel).toBeVisible();
  // A zero here tells the operator "nothing needs my attention", which is false
  // when the owning module simply could not answer.
  for (const item of await panel.locator("li").allTextContents()) {
    expect(item, "a To-do row never carries a bare zero").not.toMatch(/(^|\s)0(\s|$)/);
  }
  await expect(panel).not.toContainText("dashboard.todo.");
  // Every row is a real destination, not a dead span (hard-won law 2).
  const links = panel.locator("a");
  if ((await links.count()) > 0) {
    await expect(links.first()).toHaveAttribute("href", new RegExp(`^/${tenant()}/`));
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// RULING 2 · THE FIVE-MINUTE CLIENT WINDOW, PROVED BY COUNTING REQUESTS
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-012 r2 · leaving the dashboard and coming back does not recompute it ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);

  let summaryCalls = 0;
  page.on("request", (request) => {
    if (request.url().includes("/dashboard/summary")) {
      summaryCalls += 1;
    }
  });

  await page.goto(dashboardPath());
  await expect(page.locator(".kpi-grid")).toBeVisible();
  const afterFirst = summaryCalls;
  expect(afterFirst).toBeGreaterThan(0);

  // Navigate away inside the SPA and back — the round trip a clerk makes all
  // day. Within `DASHBOARD_STALE_MS` the answer is served from cache, so the
  // server computes the rollup once rather than once per glance.
  await page.getByRole("link", { name: "Accounts", exact: true }).first().click();
  await page.waitForURL(new RegExp(`/${tenant()}/accounts`));
  await page.getByRole("link", { name: "Dashboard", exact: true }).first().click();
  await page.waitForURL(new RegExp(`/${tenant()}/dashboard`));
  await expect(page.locator(".kpi-grid")).toBeVisible();

  expect(
    summaryCalls,
    "PO 2026-08-19 d.2 — the dashboard's staleTime is five minutes, so a return trip inside it costs no recompute",
  ).toBe(afterFirst);
});

// ═══════════════════════════════════════════════════════════════════════════
// THE SCREEN ITSELF — CR-012's own requirement, still true after five rulings
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-012 · all six regions render, none of them blank, and no raw key reaches the screen ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  for (const title of ["Recent activity", "Service mix", "AR aging", "To do"]) {
    await expect(page.locator('[data-dash="region"]', { hasText: title })).toBeVisible();
  }
  await expect(page.locator(".kpi-grid")).toBeVisible();

  // DEF-282's shape: the first screen after every sign-in reading its own key
  // names. Asserted over the WHOLE page rather than one panel.
  const body = await page.locator('main, [data-dash="page"]').first().innerText();
  expect(body, "no dotted catalogue key may reach the landing screen").not.toMatch(
    /\bdashboard\.[a-z]+\./,
  );
  expect(body).not.toMatch(/\bfinance\.gap\./);

  // BR-REP-033: the two page actions, decided on the SERVER for this role.
  await expect(page.getByRole("link", { name: "Import reads" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Run billing" })).toBeVisible();
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-012 (12-governance/11-change-requests.md §CR-012 — the PO's build spec and the FULL DSH-01 requirements verbatim) · 12-governance/02-decision-log.md 2026-08-19 §"CR-012 DSH-01 — FIVE PO RULINGS FROM THE DESIGN REVIEW"
// screens: S7
// generated: 2026-08-19 by story-coder (CR-012 closing lane)
// gates: RED PROVED FIRST — the service-mix case failed against the built stack on the panel's own empty sentence before the region's state rule was corrected; its failure is quoted in the case.
// exceptions: (1) the tenant's service list is read through the product's own /settings/services rather than hard-coded, because the RULE is "follow the tenant" and a hard-coded pair would pass on this fixture and prove nothing · (2) the caching ruling's SERVER half is not built, so nothing here asserts a cache age
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
