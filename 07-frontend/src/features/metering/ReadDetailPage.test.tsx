// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-013 (S29 read detail — override & dispute) · US-MET-016
//           (the J6 correction linkage the page renders)
//           Change: CR-038 W5 — S29 is a FULL PAGE (PO 2026-08-26)
//           Screens: S29
// Rules:    BR-MET-017 (the compliance stamp) · BR-MET-022 (stored self-describing
//           outcomes) · BR-MET-024 (Override APPENDS; the original stays immutable) ·
//           BR-MET-028 (an estimate carries no register value) · BR-MET-029 (an estimate
//           is a lawful bill input that travels flagged) · BR-MET-053 (BILLED is locked;
//           the fix routes through the billing correction path) · BR-MET-056 (full chain,
//           math shown, flag reason WITH thresholds, channel) · BR-SHL-025
// ───────────────────────────────────────────────────────
// The retired ReadDetailDrawer's suite, ported to the page and extended for
// the three sections that stopped stating absences (tags, linkage, history)
// and the one that never rendered anywhere (corrections). The contract is
// unchanged and is still WHERE the numbers come from: every figure on screen
// is one the server stored, and the screen computes none of them.
//
// RED-FIRST (CR-038 W5): the route test below was run before App.tsx carried
// `reads/:readId` — the deep link rendered NotBuiltYetPage's copy where the
// page's H1 should be.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

// Static, so the (heavy) route-table import is paid in the collect phase, not
// inside a test's own 5s budget — APP_ROUTES is exported unwrapped for exactly
// this kind of reader (App.tsx's own note).
import { APP_ROUTES } from "@/App";
import type {
  AssetReadRow,
  MyPermissions,
  ReadChainEntry,
  ReadDetail,
  ReadImportBatchDetail,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { assetReadsQueryKey } from "@/features/assets/AssetDetailPage";
import { ToastProvider } from "@/components/Toast";

import {
  LIFECYCLE_BILLED,
  ReadDetailPage,
  billedCorrectionSchema,
  clearDisputeBlockedReason,
  correctionIsBilled,
  disputeBlockedReason,
  disputeSchema,
  overrideBlockedReason,
  overrideSchema,
  readBatchQueryKey,
  readDetailQueryKey,
  stringList,
  versionLine,
} from "./ReadDetailPage";
import { PREMISES_PERMISSION } from "./meteringShared";
import { readDetailPath } from "./readsShared";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** US-MET-013 §4: M-7001's August read, batch B-2608-04. */
function detail(over: Partial<ReadDetail> = {}): ReadDetail {
  const base: ReadDetail = {
    id: "r-7001-aug",
    meter: "M-7001",
    asset_id: "a-7001",
    // DEF-045 closed: the linkage, served — the page's tags and premise block.
    cycle: "08-A",
    cycle_id: "c-08a",
    route: "R-1",
    route_id: "rt-1",
    service: "electric",
    premise: "1408 Elm Street",
    premise_no: "P-00101",
    premises_id: "p-1408",
    // `B30` (PO 2026-09-14) — the account the reading was taken FOR, served
    // from `meter_reads.account_id` through the customers seam. The fixture
    // carries one so the default case is the LIVE link; the absence cases pass
    // `account: null` with their own reason.
    account: {
      id: "acc-10432",
      account_no: "ACC-2042",
      customer_name: "Dana Whitfield",
      status: "active",
    },
    account_absent_reason: null,
    unit_label: "Unit A",
    unit_id: "u-1408a",
    channel: "total",
    read_at: "2026-08-03",
    period_start: "2026-07-03",
    period_end: "2026-08-03",
    prior_value: "42180.000000",
    current_value: "42864.000000",
    prior_value_display: "42180 kWh",
    current_value_display: "42864 kWh",
    multiplier: "1.000000",
    consumption: "684.000000",
    unit: "kWh",
    usage_display: "684 kWh",
    days_since_prior: 31,
    source: "import",
    source_detail: "walk_by",
    // CR-038 W3 — a pre-change read: nothing recorded the method, so the
    // server DERIVES it from `source_detail` and says so.
    // `read_dict` serves `read_type` too (export vs consumption) — DEF-816.
    read_type: "consumption",
    read_method: "walk_by",
    read_method_origin: "derived",
    status: "ok",
    lifecycle: "committed",
    rule_outcomes: [
      { rule: "high", severity: "ok", detail: { ratio_pct: "104.5", threshold_pct: "200" } },
    ],
    import_batch_id: "b-2608-04",
    import_batch_no: "RB-2608-0044",
    disposition: null,
    disposition_reason: null,
    estimation_method: null,
    consecutive_estimate_no: null,
    trues_up_read_ids: [],
    superseded_by_id: null,
    superseded_at: null,
    supersede_reason: null,
    disputed_at: null,
    dispute_reason: null,
    disputed: false,
    disputed_by: null,
    dispute_cleared_at: null,
    dispute_cleared_by: null,
    demand_reset_noted: false,
    is_peak: false,
    // US-MET-016: no correction linkage on an ordinary read.
    corrections: [],
    // US-AST-011/012: served on every read. A FLAT meter's answer is
    // `is_net_meter: false` with the reason — never an empty pair, and never a
    // zero export (BR-AST-010).
    net_pair: {
      is_net_meter: false,
      read_at: "2026-08-03",
      consumption: null,
      export: null,
      absent_reason: "asset_is_not_net_metering",
    },
    chain: [],
    ...over,
  };
  if (base.chain.length === 0) {
    base.chain = [{ ...base, version: 1 } as unknown as ReadChainEntry];
  }
  return base;
}

/** US-MET-013 TC-8: M-7204's high-usage read, with the thresholds the engine used. */
function flaggedDetail(): ReadDetail {
  return detail({
    id: "r-7204-aug",
    meter: "M-7204",
    unit: "kgal",
    usage_display: "26.24 kgal",
    consumption: "26.240000",
    prior_value: "412000.000000",
    current_value: "438240.000000",
    prior_value_display: "412000 kgal",
    current_value_display: "438240 kgal",
    status: "high",
    rule_outcomes: [
      {
        rule: "high",
        severity: "warning",
        // ⚠ **THE BAG IS THE ENGINE'S, KEY FOR KEY** (`validation._high_low_outcomes`
        // → `base` + the high branch). It used to be a five-key subset with no
        // `unit`, and a fixture that is not the payload cannot test the rule
        // CLAUDE.md hard rule 3 puts on this panel: a figure with no unit on
        // the bag is DROPPED rather than printed bare, so the subset silently
        // exercised the absence path instead of the drawn sentence.
        detail: {
          consumption: "26.240000",
          unit: "kgal",
          ratio_pct: "312.0000000000",
          threshold_pct: "200",
          absolute_floor: "1",
          absolute_floor_unit: "kgal",
          delta_over_average: "17.840000",
          trailing_average: "8.400000",
          trailing_reads: 3,
        },
      },
      {
        rule: "factor_flag",
        severity: "not_evaluated",
        // The engine puts `rule_ref: "BR-MET-020"` on every unratified verdict
        // (`validation._unratified_outcomes`) — carried here so the rule-31
        // guard below is pointed at the real payload and not at a tidied one.
        detail: { reason: "threshold_not_ratified", rule_ref: "BR-MET-020" },
      },
    ],
  });
}

/** US-MET-019 §4's own disputed fixture — M-7333, DEF-046's impossible read. */
function disputedDetail(over: Partial<ReadDetail> = {}): ReadDetail {
  return detail({
    meter: "M-7333",
    disputed: true,
    disputed_at: "2026-08-04T10:12:00Z",
    dispute_reason: "customer reports vacant since July",
    disputed_by: "u-marcus",
    ...over,
  });
}

function batch(): ReadImportBatchDetail {
  return {
    id: "b-2608-04",
    batch_no: "B-2608-04",
    status: "posted",
    source_kind: "csv",
    source_detail: "walk_by",
    read_method: "walk_by",
    period_month: "2026-08-01",
    cycle_id: "c-08a",
    route_id: "rt-1",
    service: "electric",
    compliance: {
      file_name: "reads_08A.csv",
      file_hash: "a3f4c19e8291",
      // ⚠ THE ID IS A REALISTIC UUID ON PURPOSE (DEF-899). The fixture used
      // to read `u-marcus`, which is short, readable and looks like a handle —
      // so the shipped panel LOOKED fine in this test while the live app
      // printed `01a01d99-d617-7aa9-9f07-e2c08cc4fdc9` at a clerk. A fixture
      // that cannot embarrass the screen cannot catch this class of defect.
      uploaded_by: "01a01d99-d617-7aa9-9f07-e2c08cc4fdc9",
      uploaded_by_name: "Marcus Johnson",
      uploaded_at: "2026-08-06T14:14:22Z",
      session_ref: "sess_9f27",
      ip: "98.200.114.7",
      certified: true,
      cosigned_by: null,
      cosigned_by_name: null,
    },
    counts: {
      rows: 941,
      passed: 906,
      warnings: 32,
      errors: 3,
      rows_with_unevaluated: 0,
      accepted: 938,
      rejected: 3,
      field_visit: 0,
      skipped: 0,
      estimate_requested: 0,
      undispositioned: 0,
      posted: 941,
      severity_total: 941,
      reconciles: true,
    },
    posted_at: "2026-08-06T14:15:00Z",
    rows: [],
  };
}

/** RDS-04's history table — the meter's last cycles, off the assets seam. */
function history(): AssetReadRow[] {
  return [
    {
      read_id: "r-7001-aug",
      date: "2026-08-03",
      channel: "total",
      read_type: "consumption",
      reading: "42864.000000",
      consumption: "684.000000",
      unit: "kWh",
      export: null,
      export_unit: null,
      export_read_id: null,
      source: "import",
      status: "ok",
    },
    {
      read_id: "r-7001-jul",
      date: "2026-07-03",
      channel: "total",
      read_type: "consumption",
      reading: "42180.000000",
      consumption: "612.000000",
      unit: "kWh",
      export: null,
      export_unit: null,
      export_read_id: null,
      source: "import",
      status: "ok",
    },
  ];
}

function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function renderPage(
  read: ReadDetail,
  seed: { batch?: ReadImportBatchDetail; access?: string; history?: AssetReadRow[] } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(readDetailQueryKey(read.id), read);
  if (seed.batch !== undefined) {
    queryClient.setQueryData(readBatchQueryKey(seed.batch.id), seed.batch);
  }
  // ⚠ `{rows, total}` SINCE `AST-B-19`, and this seed is the reason to say why:
  // `GET /assets/{id}/reads` went onto the house envelope server-side in
  // `2.237.8` while its wrapper still described a bare array, and every test
  // that seeds React Query directly — this one included — kept passing over a
  // screen that threw. A fixture seeds what the WRAPPER returns, never what the
  // selector holds.
  queryClient.setQueryData(assetReadsQueryKey(read.asset_id), {
    rows: seed.history ?? [],
    total: (seed.history ?? []).length,
  });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access ?? "Full"));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* The page reads its subject off the ROUTE (`/reads/:readId`), so the
            harness mounts the same pattern App.tsx declares. */}
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${readDetailPath(read.id)}`]}>
          <Routes>
            <Route path="/:tenant/reads/:readId" element={<ReadDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("S29 — the read detail PAGE (US-MET-013 · CR-038 W5)", () => {
  it("CR-038 W5: `reads/:readId` is a ROUTED page — the deep link renders it, not the catch-all", () => {
    // RED first: before App.tsx carried the route, this resolved to
    // NotBuiltYetPage. Asserted on the ROUTE TABLE (the same contract the
    // routing tests use) so a lane deleting the line goes red here.
    const tenant = APP_ROUTES.find((route) => route.path === "/:tenant");
    const shell = tenant?.children?.find((child) => child.path === undefined);
    const paths = (shell?.children ?? []).map((child) => child.path);
    expect(paths).toContain("reads/:readId");
    // …and the page itself renders at that address with the header line-up.
    const html = renderPage(detail(), { batch: batch() });
    expect(html).toContain(t("metering.read.title"));
    expect(html).toContain(t("metering.reads.title")); // the back link's label
  });

  it("US-MET-013 TC-1: the math line shows the stored operands and the SERVER's usage, unit included", () => {
    const html = renderPage(detail(), { batch: batch() });
    // ⚠ **THIS READ `toContain("42864.000000")` UNTIL `Q9`** — PO ruling
    // 2026-09-14, the blueprint's `B35`: *a reading displays as drawn —
    // `45910`, not `45910.000000`*. The operands go through `formatQuantity`
    // now, so the CALCULATION panel and the history table spell one quantity
    // one way (the blueprint's `D6`).
    expect(html).toContain("42,864");
    // DEF-1086 — the REGISTER column was `42180.000000`; it carries its unit now.
    expect(html).toContain("42180 kWh");
    expect(html).toContain("684 kWh"); // DEF-1120 — was "684.000000 kWh"
    expect(html).toContain(t("metering.read.days", { days: 31 }));
    // BR-MET-056: the page shows what is STORED. `684` never appears without
    // its unit, and nothing here evaluates 42864 − 42180.
    expect(html).not.toContain(">684<");
  });

  // ── Q9 · B35 — the storage column stops reaching a clerk ─────────────────

  it("Q9: no six-decimal storage figure reaches the screen, and the 'Register:' prefix is gone", () => {
    const html = renderPage(detail(), { batch: batch(), history: history() });
    // The whole page, not just the line: this composer was the last place
    // BR-MET-019's `NUMERIC(18,6)` column reached a clerk on this screen.
    expect(html).not.toContain("42864.000000");
    expect(html).not.toContain("42180.000000");
    expect(html).not.toContain("1.000000");
    // ⚠ **DISPLAY ONLY, AND THIS IS THE ASSERTION THAT SAYS SO.** The SERVED
    // value is untouched — the fixture still carries the stored string and the
    // correction form still prefills from it — which is what keeps `Q9` a
    // rendering change and nowhere near a ❄️ FROZEN B4/B5 figure.
    expect(detail().current_value).toBe("42864.000000");
  });

  it("US-MET-013 TC-1: the channel and the compliance stamp render from storage (BR-MET-017)", () => {
    const html = renderPage(detail(), { batch: batch() });
    expect(html).toContain(t("metering.reads.channel.total"));
    expect(html).toContain("B-2608-04");
    expect(html).toContain("reads_08A.csv");
    expect(html).toContain("a3f4c19e8291");
    expect(html).toContain("sess_9f27");
    expect(html).toContain("98.200.114.7");
  });

  // ── DEF-899 · BR-MET-163 — people are rendered as people ─────────────────

  it("DEF-899: 'Uploaded by' shows a NAME, and the primary key is not the visible value", () => {
    // PO 2026-08-27, on the live app: "on reading detail page - decimal places
    // databse keys". The panel printed
    // `Uploaded by  01a01d99-d617-7aa9-9f07-e2c08cc4fdc9` while the row
    // directly beneath it formatted its timestamp for a human — half
    // translated, and it LOOKED considered, which is why review missed it.
    const html = renderPage(detail(), { batch: batch() });
    expect(html).toContain("Marcus Johnson");
    // The id is EVIDENCE and stays reachable — on `title`, never as the value.
    expect(html).toContain('title="01a01d99-d617-7aa9-9f07-e2c08cc4fdc9"');
    expect(html).not.toContain(">01a01d99-d617-7aa9-9f07-e2c08cc4fdc9<");
    // The sentence that explained the key away goes with the key.
    expect(html).not.toContain("their name is not served with it");
  });

  it("DEF-899: an actor that cannot be resolved says so IN WORDS, never as the key", () => {
    // BR-AUD-003's posture: the stamp outlives any user row, so a null name is
    // a real state and not an error. What it must never do is fall back to
    // printing the id, which is the defect wearing a different hat.
    const orphaned = batch();
    const html = renderPage(detail(), {
      batch: {
        ...orphaned,
        compliance: { ...orphaned.compliance, uploaded_by_name: null },
      },
    });
    expect(html).toContain(t("metering.read.compliance.actorUnresolved"));
    expect(html).not.toContain(">01a01d99-d617-7aa9-9f07-e2c08cc4fdc9<");
    expect(html).toContain('title="01a01d99-d617-7aa9-9f07-e2c08cc4fdc9"');
  });

  it("DEF-951: the CO-SIGNER is a person too — the same defect one row down", () => {
    // Nothing had ever written a co-signature, so nobody had seen this. The
    // moment CR-038 W7's writer produced one, "Approvals" would have printed a
    // SECOND raw primary key.
    const signed = batch();
    const html = renderPage(detail(), {
      batch: {
        ...signed,
        compliance: {
          ...signed.compliance,
          cosigned_by: "01a0aa11-bbbb-7cc0-8ddd-eeeeffff0000",
          cosigned_by_name: "Diana Chen",
        },
      },
    });
    expect(html).toContain("Diana Chen");
    expect(html).not.toContain(">01a0aa11-bbbb-7cc0-8ddd-eeeeffff0000<");
    // And an UNSIGNED batch still says "None required" rather than an em dash.
    expect(renderPage(detail(), { batch: batch() })).toContain(
      t("metering.read.compliance.noCosigner"),
    );
  });

  it("US-MET-013 TC-1 (CR-038 W5): the TAGS are real — service, cycle and route from the served payload", () => {
    const html = renderPage(detail(), { batch: batch() });
    expect(html).toContain(t("rating.service.electric"));
    expect(html).toContain(t("metering.read.tag.cycle", { cycle: "08-A" }));
    expect(html).toContain(t("metering.read.tag.route", { route: "R-1" }));
    // The old stated absence is gone WITH ITS KEY — a re-added hint would
    // render the raw key and fail the parity suite, not sneak back silently.
    expect(html).not.toContain("metering.read.tagsUnavailable");
  });

  it("B30 (PO 2026-09-14): the linkage block links the premise AND the account, by number", () => {
    // ⚠ **THIS ASSERTED THE ABSENCE UNTIL 2026-09-14** — *"ACCOUNT is still not
    // served — the honest absence stays"* — over `meter_reads.account_id`, a
    // reviewed cross-module FK stamped at collection since `DEF-658`. PO:
    // *"if you ahve account or meter in read details screen - please ensure you
    // ahve link it back to account and mter to imporve interaction design"*.
    const html = renderPage(detail(), { batch: batch() });
    expect(html).toContain("1408 Elm Street");
    expect(html).toContain(`href="/${TEST_TENANT}/premises/p-1408"`);
    expect(html).toContain("Unit A");
    // B14 rule 31 — the NUMBER is the visible value and the uuid rides on
    // `title` as evidence. Read as markup on purpose: the rule's own sentence
    // puts the id on an attribute, so a check over `textContent` alone would
    // go green on a screen that showed the uuid in the attribute's place.
    expect(html).toContain("ACC-2042");
    expect(html).toContain(`href="/${TEST_TENANT}/accounts/acc-10432"`);
    expect(html).toContain('title="acc-10432"');
    expect(html).not.toContain(">acc-10432<");
    expect(html).not.toContain(t("metering.read.linkage.accountUnserved"));
  });

  it("B30: the two absences are different facts and the screen says which", () => {
    // ⚠ **A READING WITH NO ACCOUNT AND AN ACCOUNT WE COULD NOT READ ARE NOT
    // THE SAME SENTENCE** (the DEF-075 posture). One is a vacancy read or a
    // unit nobody has taken service at; the other is the customers seam
    // unable to answer, and a screen that printed "no account" over the second
    // would tell a clerk something false about a reading that has one.
    const unstamped = renderPage(
      detail({ account: null, account_absent_reason: "not_stamped" }),
      { batch: batch() },
    );
    expect(unstamped).toContain(t("metering.read.linkage.accountUnserved"));
    expect(unstamped).not.toContain(t("metering.read.linkage.accountUnavailable"));
    const unresolved = renderPage(
      detail({ account: null, account_absent_reason: "unresolved" }),
      { batch: batch() },
    );
    expect(unresolved).toContain(t("metering.read.linkage.accountUnavailable"));
    expect(unresolved).not.toContain(t("metering.read.linkage.accountUnserved"));
    // And neither draws a link that goes nowhere (hard-won law 2's mirror).
    expect(unstamped).not.toContain(`/${TEST_TENANT}/accounts/`);
    expect(unresolved).not.toContain(`/${TEST_TENANT}/accounts/`);
  });

  it("DEF-899 / BR-MET-161: a unit called 'Unit 1' renders ONCE, not 'Unit Unit 1'", () => {
    // The template was `Unit {{unit}}` and the tenant's own labels already
    // begin with the word — as the seeded estate's do, and as most utilities'
    // do. A label is TENANT DATA, so no template can know whether the noun is
    // already inside it.
    // ⚠ The fixture's default label is "Unit A", which the old template
    // rendered as the perfectly innocent "Unit Unit A" — and this suite passed
    // on it, because it asserted the template's own output. The label here is
    // the PO's: `Unit 1`.
    const html = renderPage(detail({ unit_label: "Unit 1" }), { batch: batch() });
    expect(html).toContain("Unit 1");
    expect(html).not.toContain("Unit Unit");
    // The section heading is where the meaning comes from now.
    expect(html).toContain(t("metering.read.panel.location"));
  });

  it("US-MET-013 TC-1 (CR-038 W5): the read HISTORY renders the assets seam's rows — with units (rule 3)", () => {
    const html = renderPage(detail(), { batch: batch(), history: history() });
    expect(html).toContain(t("metering.read.panel.history"));
    expect(html).toContain("684 kWh"); // DEF-1120 — was "684.000000 kWh"
    // ⚠ **AMENDED 2026-08-27 (DEF-1120).** The expected string was the SERVED
    // decimal, `612.000000 kWh`. This cell reaches the client's one implementation of
    // BR-MET-144 now (*at most two decimals, trailing zeros trimmed*, PO
    // 2026-08-27), so it reads `612 kWh`. What this case guards is unchanged.
    expect(html).toContain("612 kWh");
    // DEF-1086 — the REGISTER column was `42180.000000`; it carries its unit now.
    expect(html).toContain("42180 kWh");
    // The empty state is a claim the server can now make about ONE meter.
    const empty = renderPage(detail(), { batch: batch(), history: [] });
    expect(empty).toContain(t("metering.read.history.empty"));
  });

  it("US-MET-016 (CR-038 W5): a J6 correction linkage RENDERS — invoice, status, reason; and no money figure", () => {
    const corrected = detail({
      corrections: [
        {
          id: "rc-1",
          superseded_read_id: "r-7204-jul",
          superseding_read_id: "r-7204-jul-v2",
          invoice_id: "inv-018201",
          invoice_no: "BL-2607-018201",
          asset_id: "a-7204",
          channel: "total",
          reason: "collector re-read — keying error",
          status: "open",
          opened_at: "2026-08-06T00:00:00Z",
        },
      ],
    });
    const html = renderPage(corrected, { batch: batch() });
    // ⚠ **`B27` — the linkage lives inside HISTORY now and has no heading of
    // its own.** It asserted `metering.read.correctionsTitle`, which is retired
    // with the two other headings that merged into this one panel. The line
    // names its own invoice, so it was always self-labelling.
    expect(html).toContain(t("metering.read.panel.history"));
    expect(html).toContain("BL-2607-018201");
    expect(html).toContain("collector re-read — keying error");
    // …and an ordinary read draws NO correction line at all (the Remarks
    // posture: an empty list invites the question of what belongs in it).
    expect(renderPage(detail(), { batch: batch() })).not.toContain("BL-2607-018201");
    // The retired key, named so it cannot come back: a re-added heading would
    // render the RAW KEY here (nothing resolves it in any catalogue now) and
    // this assertion goes red rather than the change landing silently.
    expect(html).not.toContain("metering.read.correctionsTitle");
  });

  it("B33 / US-MET-013 TC-8: FLAGS is the rule's name and ONE prose line, built from stored figures", () => {
    // ⚠ **THIS TEST ASSERTED THE DEFECT (`DEF-MET-5204` · `B33`).** It read
    // `toContain("312.0000000000")` and `toContain(detail.threshold_pct)` —
    // the raw `NUMERIC(18,6)` string and the `<dl>` LABEL — because that is
    // what the panel drew: the whole stored bag with the RAW KEY as each
    // label. The drawing draws one sentence and no badge.
    const html = renderPage(flaggedDetail(), { batch: batch() });
    expect(html).toContain(t("metering.reads.status.high"));
    // The drawn shape: "312% of a 8.4 kgal average · threshold 200% · 3
    // readings in the average". Nothing is compared again — every figure is
    // read off the stored bag (BR-MET-056), rounded for DISPLAY only.
    expect(html).toContain(t("metering.read.flag.ratio", { ratio: "312", average: "8.4 kgal" }));
    expect(html).toContain(t("metering.read.flag.threshold", { threshold: "200" }));
    expect(html).toContain(t("metering.read.flag.trailing", { reads: "3" }));
    // ⚠ **AND THE `NUMERIC(18,6)` STRING IS NOT ON THE SCREEN.** `312.0000000000`
    // is what the wire carries and `312` is what a person reads (`D6`).
    expect(html).not.toContain("312.0000000000");
    expect(html).not.toContain("8.400000");
    // The severity badge is gone: `Warning` beside `High usage` is the row
    // repeating what its own name offers (B14 rule 32 clause 3).
    expect(html).not.toContain(t("metering.read.severity.warning"));
  });

  it("B34 / US-MET-013 TC-8: a rule that could NOT run is NAMED, and its reason is not on screen", () => {
    // ⚠ **THE REASON WENT, AND THAT IS B14 RULE 33 RATHER THAN A CUT (`D5`).**
    // *Why* a rule did not fire is RATIONALE, which rule 33 puts at ZERO words
    // on screen — removed, never shortened. It was also the widest leak here:
    // `reasonText` falls back to the stored CODE, and only eight of the
    // twenty-nine reasons the engine can store have a catalogue entry, so a
    // clerk read `maximum_register_not_priced_by_schedule_uom` verbatim.
    // The FACT — this rule did not run — stays.
    const html = renderPage(flaggedDetail(), { batch: batch() });
    expect(html).toContain(t("metering.read.couldNotRun"));
    expect(html).toContain(t("metering.reads.status.factor_flag"));
    expect(html).not.toContain(t("metering.read.reason.threshold_not_ratified"));
    expect(html).not.toContain("threshold_not_ratified");
    // "0 errors" is only true of the rules that ran: the tally counts one.
    expect(html).toContain(t("metering.read.outcomeSummary", { passed: 0, total: 1 }));
  });

  it("DEF-MET-5204 / B14 rule 31: NOTHING from a stored bag reaches the clerk unless it was named", () => {
    // ⚠ **THE DEFECT, REPRODUCED FROM THE ENGINE'S OWN PAYLOAD.**
    // `validation._vacant_outcome` stores
    // `{"occupied": False, "basis": "no active account on the unit (BR-MET-036)"}`
    // and the panel printed the bag verbatim with the raw key as its label, so
    // **2 of 2 readings opened in a browser showed a repository rule id.**
    // Four more stored `basis` strings carry `OQ-009`, `CR-054`, `BR-MET-122`
    // and `BR-MET-049`, and `plan_registers` carries `plan_id`, a raw uuid.
    //
    // RED PROOF (hard-won law 7), with `OutcomeCard` restored to its `<dl>`:
    //   × expected '…<dt>basis</dt><dd>no active account on the unit
    //     (BR-MET-036)</dd>…' not to contain 'BR-MET-036'
    const leaky = detail({
      status: "flagged",
      rule_outcomes: [
        {
          rule: "vacant_unit",
          severity: "warning",
          detail: { occupied: false, basis: "no active account on the unit (BR-MET-036)" },
        },
        {
          rule: "unit_mismatch",
          severity: "error",
          detail: {
            read_uom: "kWh",
            pricing_uom: "therm",
            plan_id: "01a09bc5-a577-7d9b-99bc-6cea00393b46",
            basis: "BR-MET-049 — the unit's plan determines the required read set",
            resolutions: ["fix_schedule_uom", "set_asset_uom", "reject"],
          },
        },
      ],
    });
    const html = renderPage(leaky, { batch: batch() });
    // The rule's own words, in the clerk's language, on both.
    expect(html).toContain(t("metering.read.flag.vacant"));
    expect(html).toContain(t("metering.read.flag.unitMismatch", { read: "kWh", priced: "therm" }));
    // And not one internal reference, in any family, anywhere on the page.
    expect(html).not.toMatch(/\b(?:BR|US|EP|OQ|DEF|GT|IS|ADR)-[A-Z]{0,3}-?\d{3,5}\b/);
    expect(html).not.toContain("01a09bc5-a577-7d9b-99bc-6cea00393b46");
    // The raw payload KEYS were the other half of `D4` — they were the labels.
    expect(html).not.toContain(">basis<");
    expect(html).not.toContain(">occupied<");
    expect(html).not.toContain(">plan_id<");
    expect(html).not.toContain("fix_schedule_uom");
  });

  it("US-MET-013 TC-4: an estimated read says so, with its method and its consecutive number", () => {
    const html = renderPage(
      detail({
        id: "r-7108-aug",
        meter: "M-7108",
        prior_value: null,
        current_value: null,
        prior_value_display: null,
        current_value_display: null,
        usage_display: "612 kWh",
        status: "estimated",
        source: "estimated",
        source_detail: null,
        estimation_method: "trailing_3_cycle_daily_average",
        consecutive_estimate_no: 1,
        rule_outcomes: [],
        import_batch_id: null,
        import_batch_no: null,
      }),
    );
    expect(html).toContain(t("metering.reads.status.estimated"));
    expect(html).toContain("trailing_3_cycle_daily_average");
    // ⚠ **AMENDED 2026-08-27 (DEF-1120).** The expected string was the SERVED
    // decimal, `612.000000 kWh`. This cell reaches the client's one implementation of
    // BR-MET-144 now (*at most two decimals, trailing zeros trimmed*, PO
    // 2026-08-27), so it reads `612 kWh`. What this case guards is unchanged.
    expect(html).toContain("612 kWh");
    // BR-MET-028: no register value, so no math line is invented for it.
    expect(html).not.toContain(t("metering.read.mathUnavailable"));
    // ⚠ **THIS ASSERTED `metering.read.action.alreadyEstimated` UNTIL THE
    // ESTIMATE BUTTON WAS REMOVED** — PO ruling 2026-09-12, the blueprint's
    // change 2.3, and `Q6`'s shape: a control is removed only when its refusal
    // is PERMANENT. See the case below, which owns the removal.
    expect(html).not.toContain("metering.read.action.alreadyEstimated");
  });

  // ── Q6 — the Estimate button is REMOVED, not disabled ────────────────────

  it("Q6: the Estimate control is GONE from the reading, in every state, with no reason left behind", () => {
    // PO ruling 2026-09-12: estimation fills a MISSING (meter, channel, date)
    // record and this reading EXISTS, so the refusal is permanent rather than a
    // state — and a control that can never become live is not a disabled
    // control, it is a word in the wrong place. Estimating stays reachable from
    // the Reads header and from a cycle's shortfall.
    //
    // ⚠ **AND NO SENTENCE REPLACES IT.** B14 rule 33 puts rationale at zero
    // words on screen: *why a control is absent* belongs in the code and the
    // register, which is where this paragraph is.
    for (const read of [detail(), detail({ status: "estimated" }), flaggedDetail()]) {
      const html = renderPage(read, { batch: batch() });
      // The three retired keys, by NAME. They resolve in no catalogue now, so a
      // re-added button renders the raw key and this goes red rather than the
      // control creeping back with a fresh string.
      expect(html).not.toContain("metering.read.action.estimate");
      expect(html).not.toContain("metering.read.action.estimateUnavailable");
      expect(html).not.toContain("metering.read.action.alreadyEstimated");
      // The two actions the drawing DOES keep are still there.
      expect(html).toContain(t("metering.read.action.dispute"));
    }
  });

  it("US-MET-013 TC-2: the FULL chain renders, oldest first, and the head is named", () => {
    const v1 = detail({
      id: "v1",
      current_value: "42864.000000",
      usage_display: "684 kWh",
      superseded_by_id: "v2",
      superseded_at: "2026-08-06T00:00:00Z",
      supersede_reason: "collector re-read — keying error",
    });
    const v2 = detail({
      id: "v2",
      current_value: "42876.000000",
      usage_display: "696 kWh",
      chain: [],
    });
    v2.chain = [
      { ...v1, version: 1 } as unknown as ReadChainEntry,
      { ...v2, version: 2, chain: undefined } as unknown as ReadChainEntry,
    ];
    const html = renderPage(v2, { batch: batch() });
    expect(html).toContain(t("metering.read.chainVersion", { version: 1 }));
    expect(html).toContain(t("metering.read.chainVersion", { version: 2 }));
    expect(html).toContain("collector re-read — keying error");
    // Both usages carry their unit — rule 3 holds inside the chain too.
    expect(html).toContain("684 kWh"); // DEF-1120 — was "684.000000 kWh"
    expect(html).toContain("696 kWh");
    expect(versionLine(v2, t)).toBe(t("metering.read.versionHead", { version: 2 }));
  });

  it("US-MET-013 TC-1: a single-version read reads 'immutable' (BR-MET-024)", () => {
    expect(versionLine(detail(), t)).toBe(t("metering.read.versionImmutable", { version: 1 }));
  });

  it("MR-15: a BILLED read's primary is LIVE and takes the J6 door — the refusal it replaces was FALSE", () => {
    // ⚠ **THIS CASE ASSERTED THE DEFECT UNTIL TODAY.** It read
    // `expect(overrideBlockedReason(billed, null, t)).toBe(billedLocked)` and
    // `expect(html).toContain(billedLocked)` — pinning
    // *"This reading is already billed. Its correction has to travel with the
    // money fix, **and that path is not built**."*
    //
    // **THE PATH WAS BUILT.** `POST /reads/{id}/billed-correction` is mounted
    // at `api.py:1479` and routed at `:3067`; the bill detail screen is live at
    // `/billing/bills/:invoiceId`; and the server's own
    // `metering.read.cascade_billed_recommendation` tells clerks to
    // *"correct it through the billed-correction door"*. Nothing in `.ts` or
    // `.tsx` had ever called it — hard-won law 2's mirror, a live screen
    // behind a dead control, and a test that asserted the hold rather than
    // asking whether the hold was still true.
    const billed = detail({ lifecycle: LIFECYCLE_BILLED });
    expect(overrideBlockedReason(billed, null, t)).toBeNull();
    expect(correctionIsBilled(billed)).toBe(true);
    expect(correctionIsBilled(detail())).toBe(false);
    const html = renderPage(billed, { batch: batch() });
    expect(html).toContain(t("metering.read.action.correctBilled"));
    expect(html).toContain(t("metering.read.billedTag"));
    // The retired refusal, named so it cannot come back: the key resolves in no
    // catalogue now, so a re-added hold renders it raw and this goes red.
    expect(html).not.toContain("metering.read.action.billedLocked");
    expect(html).not.toContain("that path is not built");
    // ⚠ **AND THE CONTROL IS NOT MERELY PRESENT — IT IS NOT DISABLED.**
    // `GuardedButton` renders `<Button disabled title={reason}>` when refused,
    // so asserting the LABEL alone would pass over the dead control this case
    // exists to remove (DEF-182's shape: a check whose output cannot
    // distinguish pass from fail).
    //
    // ⚠ **THE FIRST VERSION OF THIS ASSERTION WAS DEF-182's OWN SHAPE AND IT
    // COULD NOT PASS ON CORRECT CODE.** It read `toMatch(/<button(?![^>]*
    // disabled)[^>]*>Correct billed read/)` — and every button in this kit
    // carries `disabled:opacity-45 disabled:cursor-not-allowed` in its CLASS
    // string, so the lookahead matched the Tailwind VARIANT and the check was
    // red whether the control was live or dead. The ATTRIBUTE is what decides,
    // so that is what is read: `<Button disabled>` serialises as `disabled=""`.
    const label = t("metering.read.action.correctBilled");
    expect(html).toContain(`>${label}</button>`);
    expect(html).not.toMatch(new RegExp(`disabled=""[^>]*>${label}</button>`));
    // …and the SAME assertion fires on a read that IS refused, which is the
    // half that proves it can tell a live control from a dead one at all.
    const refused = renderPage(detail({ lifecycle: LIFECYCLE_BILLED, superseded_by_id: "v2" }), {
      batch: batch(),
    });
    expect(refused).toMatch(new RegExp(`disabled=""[^>]*>${label}</button>`));
  });

  it("MR-15: the billed door is still refused for the two states the SERVER refuses", () => {
    // BR-MET-053 refuses a superseded head, and BR-SHL-025 leaves the role
    // check to the endpoint. Removing the billed hold removed ONE reason, not
    // the guard — which is what separates this from deleting the refusal.
    const superseded = detail({
      lifecycle: LIFECYCLE_BILLED,
      superseded_by_id: "v2",
      superseded_at: "2026-08-06T00:00:00Z",
    });
    expect(overrideBlockedReason(superseded, null, t)).toBe(t("metering.read.action.notHead"));
    expect(
      overrideBlockedReason(
        detail({ lifecycle: LIFECYCLE_BILLED }),
        t("metering.read.action.readOnly"),
        t,
      ),
    ).toBe(t("metering.read.action.readOnly"));
  });

  it("MR-15: the billed correction's schema demands the INVOICE the plain path does not", () => {
    // BR-MET-053: "read fix and money fix travel together". The invoice is the
    // whole difference between the two doors, and the server refuses without it
    // by name (`metering.read.invoice_required`).
    const schema = billedCorrectionSchema(t);
    expect(schema.safeParse({ value: "42876", reason: "re-read", invoice_id: "" }).success).toBe(
      false,
    );
    expect(schema.safeParse({ value: "42876", reason: "", invoice_id: "inv-1" }).success).toBe(
      false,
    );
    expect(schema.safeParse({ value: "-1", reason: "re-read", invoice_id: "inv-1" }).success).toBe(
      false,
    );
    expect(
      schema.safeParse({ value: "42876", reason: "re-read", invoice_id: "inv-1" }).success,
    ).toBe(true);
    // …and the plain path still takes two fields and no invoice, so a clerk
    // correcting an unbilled reading is never asked for a bill that does not
    // exist.
    expect(overrideSchema(t).safeParse({ value: "42876", reason: "re-read" }).success).toBe(true);
  });

  it("US-MET-013 TC-2: a read that is no longer the lineage head cannot be overridden", () => {
    const superseded = detail({ superseded_by_id: "v2", superseded_at: "2026-08-06T00:00:00Z" });
    expect(overrideBlockedReason(superseded, null, t)).toBe(t("metering.read.action.notHead"));
    expect(versionLine(superseded, t)).toBe(
      t("metering.read.versionSuperseded", { version: 1 }),
    );
  });

  it("US-MET-013 TC-8 (RBAC): a role without write access sees Override disabled with the reason", () => {
    expect(overrideBlockedReason(detail(), t("metering.read.action.readOnly"), t)).toBe(
      t("metering.read.action.readOnly"),
    );
    const html = renderPage(detail(), { batch: batch(), access: "View" });
    expect(html).toContain(t("metering.read.action.readOnly"));
  });

  it("US-MET-013 TC-5: an override with no reason, or a negative value, is refused before it is sent", () => {
    const schema = overrideSchema(t);
    expect(schema.safeParse({ value: "42876", reason: "" }).success).toBe(false);
    expect(schema.safeParse({ value: "-5", reason: "typo" }).success).toBe(false);
    expect(schema.safeParse({ value: "", reason: "typo" }).success).toBe(false);
    expect(schema.safeParse({ value: "42876", reason: "collector re-read" }).success).toBe(true);
  });

  it("US-MET-013 TC-3: Dispute is a LIVE control, not a disabled one with a reason", () => {
    const html = renderPage(detail(), { batch: batch() });
    expect(html).toContain(t("metering.read.action.dispute"));
    expect(html).not.toContain('disabled="" title="' + t("metering.read.action.dispute"));
    expect(disputeBlockedReason(detail(), null, t)).toBeNull();
  });

  it("US-MET-013 TC-3: a disputed reading shows the reason, WHO raised it, and that the account is held", () => {
    const html = renderPage(disputedDetail(), { batch: batch() });
    expect(html).toContain(t("metering.read.dispute.title"));
    expect(html).toContain("customer reports vacant since July");
    // OQ-043's whole v1 consequence, in the clerk's own words.
    expect(html).toContain(t("metering.read.dispute.holdsRun"));
    // …and the header now offers the CLEAR action instead of a second dispute.
    expect(html).toContain(t("metering.read.action.clearDispute"));
    expect(html).not.toContain(t("metering.read.action.dispute") + "</button>");
  });

  it("US-MET-013 TC-3: only a System Admin is offered Clear (the OQ-043 closure names the role)", () => {
    expect(clearDisputeBlockedReason(disputedDetail(), "system_admin", t)).toBeNull();
    expect(clearDisputeBlockedReason(disputedDetail(), "billing_clerk", t)).toBe(
      t("metering.read.action.clearNeedsAdmin"),
    );
    // A null role means /me/permissions has not answered; BR-SHL-025 says the
    // SERVER is the boundary, so the control is offered rather than guessed at.
    expect(clearDisputeBlockedReason(disputedDetail(), null, t)).toBeNull();
  });

  it("US-MET-013 TC-3: a BILLED reading is disputable, and the screen states BR-MET-133 rather than implying the bill moved", () => {
    const billed = disputedDetail({ lifecycle: LIFECYCLE_BILLED });
    expect(disputeBlockedReason(detail({ lifecycle: LIFECYCLE_BILLED }), null, t)).toBeNull();
    const html = renderPage(billed, { batch: batch() });
    expect(html).toContain(t("metering.read.dispute.billedBillStands"));
    // An UNBILLED dispute must not carry that sentence — it would be a warning
    // about a bill that does not exist.
    expect(renderPage(disputedDetail(), { batch: batch() })).not.toContain(
      t("metering.read.dispute.billedBillStands"),
    );
  });

  // RED PROOF, MEASURED (hard-won law 7). The two English strings were put
  // back to their shipped wording — "That bill is untouched: it stays issued,
  // stays due, and its late fees keep running. What a dispute should do to a
  // bill already sent has not been decided." and "Clearing records no verdict."
  // `npx vitest run src/features/metering/ReadDetailPage.test.tsx` measured
  // `1 failed | 22 passed | 2 todo (25)`:
  //   × BR-MET-133: the billed-bill sentence says what the RULE says…
  //     → expected 'A bill has already used this reading.…' to contain 'stands'
  // Restored: `23 passed`. The test ABOVE stayed green through the revert —
  // it compares the render to the catalogue and so passes over any copy at
  // all, which is exactly why this one exists.
  it("BR-MET-133: the billed-bill sentence says what the RULE says, not that nobody has decided", () => {
    // ⚠ The test above passes over ANY copy, because it compares the render to
    // the catalogue. This one pins the CONTENT — which is the half that was
    // wrong for the whole of OQ-245's life and would have gone on being wrong
    // silently after it closed (hard-won law 1).
    //
    // BR-MET-133, PO verbatim 2026-08-26: *"Bill stands, resolution through the
    // billed-correction door, and the disputed amount doesn't age into late
    // fees while open"*, plus *"the undisputed remainder of the bill ages
    // normally"*. All four facts are what a clerk repeats to a customer on the
    // phone, so all four are on the screen.
    const sentence = t("metering.read.dispute.billedBillStands");
    expect(sentence).toContain("stands");
    expect(sentence).toContain("disputed amount does not age");
    expect(sentence).toContain("no late fees");
    expect(sentence).toContain("rest of the bill ages as usual");
    expect(sentence).toContain("billed correction");
    // The retired wording, named so it cannot come back: the screen used to say
    // the late-fee clock kept running and that nobody had decided.
    expect(sentence).not.toContain("has not been decided");
    expect(sentence).not.toContain("late fees keep running");

    // Clearing is the "the reading stands" outcome (clause 3), and it says so.
    const clearing = t("metering.read.dispute.clearOutcome");
    expect(clearing).toContain("the bill was always correct");
    expect(clearing).toContain("billed correction");
    expect(clearing).not.toContain("records no verdict");
  });

  it("US-MET-013 TC-3: a dispute with no reason is refused before it is sent", () => {
    const schema = disputeSchema(t);
    expect(schema.safeParse({ reason: "" }).success).toBe(false);
    expect(schema.safeParse({ reason: "   " }).success).toBe(false);
    expect(schema.safeParse({ reason: "customer reports vacant since July" }).success).toBe(true);
  });

  it("US-MET-013 TC-3: a superseded version cannot be disputed — the head is (BR-MET-016)", () => {
    expect(disputeBlockedReason(detail({ superseded_by_id: "r-v2" }), null, t)).toBe(
      t("metering.read.action.notHead"),
    );
    expect(disputeBlockedReason(disputedDetail(), null, t)).toBe(
      t("metering.read.action.alreadyDisputed"),
    );
  });

  // ── The redraw · entry 03 (blueprint p12–p15, read as IMAGES — B14 r42) ──

  it("R4 · MR-32: the five information groups are PANELS, and the top-rule SECTION is gone", () => {
    // PO ruling 2026-09-12, verbatim: *"use Panel — a box, 1px border on all
    // four sides, surface fill, 16px padding, heading inside … in detail
    // section use Panel to information groups"*. `ReadDetailPage` drew
    // `border-t border-divider pt-3.5` — a rule across the top, no box — which
    // the drawings render nowhere.
    //
    // Asserted on the kit's own `data-panel` handle rather than on a class
    // string, for the reason `Panel.tsx` gives it: a check that selects by a
    // class name is checking something Route B is in the business of deleting.
    const html = renderPage(detail(), { batch: batch(), history: history() });
    const panels = html.match(/data-panel=""/g) ?? [];
    // Calculation · Flags · History · Location · Evidence. FIVE, which is what
    // the drawing draws and what the ruling's own sentence counts.
    expect(panels).toHaveLength(5);
    for (const title of ["calculation", "flags", "history", "location", "evidence"]) {
      expect(html).toContain(t(`metering.read.panel.${title}`));
    }
    // The shape it replaces, named so a lane cannot reinstate it quietly.
    expect(html).not.toContain("border-t border-divider pt-3.5");
    // ⚠ **AND THE DISPUTE BANNER IS DELIBERATELY NOT ONE.** The ruling names
    // *information groups*; the banner and the net-meter pair are NOTICES that
    // appear only when they apply, and the drawing keeps both unchanged. A
    // disputed read still renders exactly five panels.
    const disputed = renderPage(disputedDetail(), { batch: batch(), history: history() });
    expect(disputed.match(/data-panel=""/g) ?? []).toHaveLength(5);
    expect(disputed).toContain(t("metering.read.dispute.title"));
  });

  it("B23: the body is TWO columns — judge the number on the left, prove it on the right", () => {
    // The drawing's own note: *"everything a clerk reads to judge the number on
    // the left, everything they read to prove where it came from on the right.
    // At narrow widths the right column drops beneath the left."* The page was
    // one 720px column before.
    const html = renderPage(detail(), { batch: batch(), history: history() });
    expect(html).toContain("lg:grid-cols-3");
    expect(html).toContain("lg:col-span-2");
    // The retired measure, named: a lane re-adding it would put the two
    // columns back into one and nothing else would notice.
    expect(html).not.toContain("max-w-[720px]");
  });

  it("B22: the four figures are the KPIStrip BAND, not a 2 × 2 grid of cards", () => {
    const html = renderPage(detail(), { batch: batch() });
    // `.kpi-grid` is the band — 2px rules top and bottom, four across — and it
    // is the kit's, so this row looks like the same row on every other screen
    // (B14 rule 36).
    expect(html).toContain('class="kpi-grid"');
    expect(html).toContain(t("metering.read.previous"));
    expect(html).toContain(t("metering.read.current"));
    expect(html).toContain(t("metering.read.usage"));
    expect(html).toContain(t("metering.read.statusLabel"));
    expect(html).toContain(t("metering.read.outcomeSummary", { passed: 1, total: 1 }));
  });

  // ── R5 / MR-47 / Q7 — service and register sit with the identity ─────────

  it("R5 · Q7: the SERVICE and the REGISTER are chips in the header, beside the status", () => {
    // PO ruling 2026-09-12: *"on this screen can you show utility services chip
    // in header"*, and the register with it — *"They belong with the identity
    // because they decide how the number is read"*. Both were served already:
    // the service sat inside the LOCATION group four sections down and the
    // register only inside the kicker's run-on line.
    //
    // ⚠ **Q7 IS WHY THE REGISTER HALF MATTERS.** A reading against the wrong
    // register is permanent — `supersede_read` takes a value and a reason, and
    // migration `0007` freezes the channel — and DEF-797 cost 412 kW billed as
    // 14 kWh. This puts the register where a clerk cannot miss it.
    const html = renderPage(detail(), { batch: batch() });
    const header = html.slice(0, html.indexOf("kpi-grid"));
    expect(header).toContain(t("rating.service.electric"));
    expect(header).toContain(t("metering.reads.channel.total"));
    // The status pill keeps its place beside them (B14 rule 2 / DEF-966: state
    // renders with the IDENTITY, never in the action row).
    expect(header).toContain(t("metering.reads.status.ok"));
    // …and the letter square is the product's ONE badge component, not a
    // second vocabulary invented here (CR-023 §9.7 / DEF-439).
    expect(header).toContain('role="img"');
  });

  it("N4: the service leaves LOCATION rather than appearing twice on one screen", () => {
    // The drawing's own reasoning: *"the Location group keeps the cycle, route,
    // source and method; the service leaves it rather than appearing twice"*. A
    // fact drawn twice on one screen is a fact that can disagree with itself.
    const html = renderPage(detail(), { batch: batch() });
    const body = html.slice(html.indexOf("kpi-grid"));
    expect(body).not.toContain(t("rating.service.electric"));
    // The five that stay are all still there.
    expect(body).toContain(t("metering.read.tag.cycle", { cycle: "08-A" }));
    expect(body).toContain(t("metering.read.tag.route", { route: "R-1" }));
    expect(body).toContain(t("metering.reads.channel.total"));
    expect(body).toContain(t("metering.reads.source.import"));
    expect(body).toContain(t("metering.reads.readMethod.walk_by"));
  });

  // ── B31 · MR-45 · ⑬ — the register set the plan expects ──────────────────

  it("B31: the plan's expected register set renders, ticked off, with the SHORTFALL named", () => {
    // The data has been stored on every read since CR-038 W1 and reached only
    // the upload wizard. `plan_registers` is `ok` on a complete meter and
    // `flaggedOutcomes` drops `ok` — so a clerk looking at one time-of-use
    // window could not see that a sibling register never arrived.
    const tou = detail({
      channel: "tou_on",
      rule_outcomes: [
        {
          rule: "plan_registers",
          severity: "warning",
          detail: {
            expected: ["tou_on", "tou_mid", "tou_off", "total"],
            received: ["tou_on", "tou_off", "total"],
            missing: ["tou_mid"],
            unexpected: [],
            plan_model: "time_of_use",
            // ⚠ THE BAG CARRIES THESE TWO AND THE SCREEN MUST NOT PRINT EITHER
            // — see the case below. They are in the fixture on purpose.
            plan_id: "01a09bc5-a577-7d9b-99bc-6cea00393b46",
            basis: "BR-MET-049 — the unit's plan determines the required read set per meter",
          },
        },
      ],
    });
    const html = renderPage(tou, { batch: batch() });
    expect(html).toContain(t("metering.read.planRegisters.title"));
    expect(html).toContain(t("rating.model.time_of_use"));
    expect(html).toContain(t("metering.reads.channel.tou_on"));
    expect(html).toContain(t("metering.reads.channel.tou_mid"));
    expect(html).toContain(t("metering.read.planRegisters.missing"));
    expect(html).toContain(t("metering.read.planRegisters.count", { present: 3, expected: 4 }));
    // …and the meter is one click away, which is the drawing's own affordance.
    expect(html).toContain(`href="/${TEST_TENANT}/assets/a-7001"`);
    // A read whose plan set could not be resolved says nothing here — the
    // FLAGS group already carries that stated absence, and one sentence twice
    // is B14 rule 32's own complaint.
    expect(renderPage(detail(), { batch: batch() })).not.toContain(
      t("metering.read.planRegisters.title"),
    );
  });

  it("D4 · B14 rule 31: the plan-register line prints NO uuid and NO rule number", () => {
    // ⚠ **`OutcomeCard` RENDERS A DETAIL BAG VERBATIM WITH THE RAW KEY AS ITS
    // LABEL**, so routing this outcome through it would put a primary key and a
    // rule id on a clerk's screen the day the rule fires. The panel reads four
    // keys BY NAME instead, which is why `plan_id` and `basis` are in the
    // fixture above.
    const tou = detail({
      rule_outcomes: [
        {
          rule: "plan_registers",
          severity: "warning",
          detail: {
            expected: ["total", "demand"],
            received: ["total"],
            missing: ["demand"],
            plan_model: "demand",
            plan_id: "01a09bc5-a577-7d9b-99bc-6cea00393b46",
            basis: "BR-MET-049 — the unit's plan determines the required read set per meter",
          },
        },
      ],
    });
    const html = renderPage(tou, { batch: batch() });
    expect(html).toContain(t("metering.read.planRegisters.title"));
    expect(html).not.toContain("01a09bc5-a577-7d9b-99bc-6cea00393b46");
    expect(html).not.toContain("BR-MET-049");
    expect(html).not.toContain("plan_id");
    expect(html).not.toContain("basis");
  });

  it("a detail bag that is not shaped as expected renders NOTHING, never `[object Object]`", () => {
    // `detail` is `Record<string, unknown>` on purpose — it is self-describing
    // storage (BR-MET-022) — so the reader narrows rather than casting.
    expect(stringList(["a", "b"])).toEqual(["a", "b"]);
    expect(stringList(["a", 7, null])).toEqual(["a"]);
    expect(stringList("total")).toEqual([]);
    expect(stringList(undefined)).toEqual([]);
    const malformed = detail({
      rule_outcomes: [
        { rule: "plan_registers", severity: "ok", detail: { expected: { total: true } } },
      ],
    });
    const html = renderPage(malformed, { batch: batch() });
    expect(html).not.toContain("[object Object]");
    expect(html).not.toContain(t("metering.read.planRegisters.title"));
  });

  // ── B32 · ⑭ · DEF-797 — a demand register is a MAXIMUM ───────────────────

  it("B32: a demand reading says what the billable figure IS, and no other reading does", () => {
    // BR-MET-051. DEF-797 cost 412 kW billed as 14 kWh — $154.00 against
    // $4,532.00 — and this page never said what the billable figure was on a
    // demand register at all.
    //
    // ⚠ **NOTHING HERE CHOOSES A ROUNDING, A UNIT OR AN ESTIMATE.** B4/B5 are
    // ❄️ FROZEN; the arithmetic above the line is untouched. This states a fact
    // the engine already implements.
    const peak = detail({ channel: "demand", is_peak: true, unit: "kW", usage_display: "412 kW" });
    const html = renderPage(peak, { batch: batch() });
    expect(html).toContain(t("metering.read.peakIsMaximum"));
    expect(html).toContain(t("metering.read.peakIsMaximumBasis"));
    expect(html).toContain(t("metering.read.peak"));
    // ⚠ **AND IT RENDERS ON A DEMAND REGISTER AND NOWHERE ELSE.** On any other
    // reading it would be rationale about a case that does not apply, which
    // B14 rule 33 puts at zero words on screen.
    expect(renderPage(detail(), { batch: batch() })).not.toContain(
      t("metering.read.peakIsMaximum"),
    );
  });

  // ── B27 · MR-48 · ⑨ — the history pager (B14 rule 16) ────────────────────

  it("MR-48: the history table carries a pager, and the count is the ENVELOPE's own", () => {
    // `getAssetReads` has taken a window and answered `total` since `AST-B-19`;
    // this screen asked for page one and drew the rows with no footer, so a
    // meter with years of history showed a truncated table **with nothing
    // saying so**. Nothing is counted here — `total` is served.
    const html = renderPage(detail(), { batch: batch(), history: history() });
    expect(html).toContain("table-pager");
    expect(html).toContain(t("table.pager.range", { from: 1, to: 2, total: 2 }));
    expect(html).toContain(t("table.pager.pageOf", { page: 1, pages: 1 }));
    // An empty meter draws its empty state and no table, so no footer either
    // (rule 16's subject is a list TABLE).
    expect(renderPage(detail(), { batch: batch(), history: [] })).not.toContain("table-pager");
  });

  // ── B29 · N3 — EVIDENCE is eight rows with the drawn short labels ────────

  it("B29: EVIDENCE draws the drawn eight rows, and the two duplicated ones are gone", () => {
    const html = renderPage(detail(), { batch: batch() });
    for (const label of [
      "batch",
      "file",
      "hash",
      "uploadedBy",
      "uploadedAt",
      "session",
      "certified",
      "approvals",
    ]) {
      expect(html).toContain(t(`metering.read.compliance.${label}`));
    }
    // The labels are the DRAWN short ones, not the sentences they replaced.
    expect(t("metering.read.compliance.hash")).toBe("Hash");
    expect(t("metering.read.compliance.uploadedBy")).toBe("By");
    expect(t("metering.read.compliance.certified")).toBe("Certified");
    // ⚠ **`Rule outcomes` AND `Version` LEAVE (`N3`).** Neither was ever
    // evidence: the first is the band's STATUS tile and the second is the head
    // of HISTORY, so each was a fact stated twice on one screen — and two
    // copies of a fact can disagree.
    expect(html).not.toContain("metering.read.compliance.outcomes");
    expect(html).not.toContain("metering.read.compliance.version");
    // …and both facts are still ON the page, in their one place each.
    expect(html).toContain(t("metering.read.outcomeSummary", { passed: 1, total: 1 }));
    expect(html).toContain(t("metering.read.versionImmutable", { version: 1 }));
  });

  // ── B18 — the title the drawing gives it ─────────────────────────────────

  it("B18: the page is called `Reading`, and the kicker still carries meter and register", () => {
    expect(t("metering.read.title")).toBe("Reading");
    const html = renderPage(detail(), { batch: batch() });
    // The three segments and their separators, unchanged — `B19`'s shape. The
    // meter is an `<a>` now, so the sentence is asserted in pieces rather than
    // as one literal; the pieces are what the drawing draws.
    expect(html).toContain("Reading · ");
    expect(html).toContain("M-7001");
    expect(html).toContain(` · ${t("metering.reads.channel.total")}`);
  });

  it("PO 2026-09-14: the kicker's METER NUMBER is the door back to the meter", () => {
    // PO, verbatim: *"if you ahve account or meter in read details screen -
    // please ensure you ahve link it back to account and mter to imporve
    // interaction design"*. The kicker already NAMED the meter; the one
    // identifier a clerk reads first was the one thing they could not follow.
    //
    // RED PROOF (hard-won law 7), before the kicker took a `ReactNode`:
    //   × expected '…<span data-kicker="">Reading · M-7001 · Total register…'
    //     to contain 'href="/brazosbend/assets/a-7001"'
    const html = renderPage(detail(), { batch: batch() });
    expect(html).toContain(`href="/${TEST_TENANT}/assets/a-7001"`);
    expect(html).toContain(`title="${t("metering.read.meterLink")}"`);
    // ⚠ **AND THE LINK IS THE METER NUMBER ITSELF, INSIDE THE KICKER** — not a
    // second control beside it. The anchor opens after "Reading · " and the
    // register follows it, which is the drawn order with nothing added.
    const kicker = html.slice(html.indexOf('data-kicker=""'));
    const anchor = kicker.indexOf(`href="/${TEST_TENANT}/assets/a-7001"`);
    expect(anchor).toBeGreaterThan(kicker.indexOf("Reading · "));
    expect(anchor).toBeLessThan(kicker.indexOf(t("metering.reads.channel.total")));
    // A reading with no meter number links to nothing rather than wrapping a
    // dash in an anchor (hard-won law 2's mirror: a control that goes nowhere).
    const nameless = renderPage(detail({ meter: null }), { batch: batch() });
    expect(nameless).not.toContain(`href="/${TEST_TENANT}/assets/a-7001"`);
  });

  it.todo(
    "US-MET-013 TC-2 (browser): submitting the override and watching the PAGE navigate to v2 needs a live browser — the pure halves (the schema, the blocked reasons, the version line) are asserted above",
  );
  it.todo(
    "US-MET-013 TC-6/TC-7 (server): the compliance stamp's immutability and the cross-tenant 404 are the backend suite's and the G5 isolation suite's",
  );
});

describe("MQ-033 task 13 — the page WIRES the read-format answers (hard-won law 2)", () => {
  // RED first: the server has served `read_format_answers` since task 10 and
  // this page read nothing from it. The panel's own suite is
  // `ReadFormatAnswersPanel.dom.test.tsx`; this asserts the PAGE passes it.
  it("a reading that carried a format shows the panel; one that did not shows none", () => {
    const answered = renderPage(
      detail({
        read_format_answers: {
          read_format: { id: "f-1", name: "Water monthly walk", version_id: "v-1", version_no: 1 },
          needs_review: false,
          answers: [
            {
              question_key: "meter_condition",
              label: "Meter condition",
              data_type: "select",
              value: "Damaged",
              photo_id: null,
              issue: null,
              work_order: { id: "wo-uuid", order_no: "WO-4870" },
            },
          ],
        },
      }),
      { batch: batch() },
    );
    expect(answered).toContain(t("metering.read.panel.readFormat"));
    expect(answered).toContain("Water monthly walk · v1");
    expect(answered).toContain("Meter condition");
    expect(answered).toContain(`href="/${TEST_TENANT}/work/orders/WO-4870"`);
    const plain = renderPage(detail({ read_format_answers: null }), { batch: batch() });
    expect(plain).not.toContain(t("metering.read.panel.readFormat"));
  });
});

describe("DEF-MET-10633 (FB-003) — the page WIRES where the reading was taken (hard-won law 2)", () => {
  // RED first: the server serves `field_capture` from this commit; the panel's
  // own suite is `FieldPositionPanel.dom.test.tsx`; this asserts the PAGE passes it.
  it("a field reading shows its position and the late one's 'added at'; any other read shows none", () => {
    const fielded = renderPage(
      detail({
        field_capture: {
          captured_at: "2026-10-26T23:32:48+00:00",
          position: { lat: "29.785300", lng: "-95.824600", accuracy_m: "10.00", at: "2026-10-26T23:35:00+00:00", added: true },
          photos: [],
        },
      }),
      { batch: batch() },
    );
    expect(fielded).toContain(t("metering.read.panel.fieldPosition"));
    expect(fielded).toContain("29.785300, -95.824600 ±10 m");
    expect(fielded).toContain("added at");
    const plain = renderPage(detail({ field_capture: null }), { batch: batch() });
    expect(plain).not.toContain(t("metering.read.panel.fieldPosition"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-013 §3 + US-MET-016 §3 · CR-038 W5 (S29 page ruling, PO 2026-08-26)
// generated: 2026-08-26 by the CR-038 W5 lane (the 2026-08-11 drawer suite, ported and extended)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report
// exceptions: E4 TC-2's SUBMIT needs a live browser; the pure halves it depends on — the zod schema, the three blocked reasons and the version line — are asserted here · E4 TC-6 (compliance immutability) and TC-7 (cross-tenant deep link) are server-side and belong to the backend + G5 suites · E4 the route assertion reads APP_ROUTES' shape the way BillRunWizard.test.tsx does — the export is deliberately unwrapped for exactly this kind of reader
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
