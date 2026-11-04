// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-007 (S28 steps 1–2) · US-MET-008 (steps 3–4) ·
//           US-MET-009 (duplicate-vs-committed) · US-MET-010 (step 5, the
//           compliance stamp and the atomic commit) · US-MET-017 (one row per
//           channel)   Screens: S28
// Rules:    BR-MET-012 · BR-MET-013 · BR-MET-014 · BR-MET-015 · BR-MET-017 ·
//           BR-MET-018 · BR-MET-032 · BR-MET-052 · BR-MET-055 · BR-MET-059 ·
//           BR-SHL-018/019/020/025
// Defect:   DEF-115 — the read-import screen did not exist, so `meter_reads`
//           held 0 rows on a fully seeded stack.
// ───────────────────────────────────────────────────────
// §4 test data is EP-MET-03's own Brazos Bend batch, rendered through the
// mocked client seam — no network, ever.
//
// The assertions worth naming, because each is a rule this screen could quietly
// break and still look finished:
//
//   · an ERROR row offered a plain "Accept" (BR-MET-015 — the server refuses it
//     and the option must not be on the screen either);
//   · a staged row printing a usage figure with no unit (CLAUDE.md rule 3 — a
//     staged row is a register reading and the unit lives on the meter);
//   · a "Missing records" tile printing 0 where the computation does not exist;
//   · a commit result that reports only its successes (the partial-success
//     defect the accounts and premises importers already carry a rule against).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  MyPermissions,
  ReadBatchCounts,
  ReadImportBatchRow,
  ReadBatchValidation,
} from "@/api/endpoints";
import { READ_CHANNELS } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  DISPOSITIONS,
  SOURCE_KINDS,
  SOURCE_KIND_AMI,
  SOURCE_KIND_CSV,
  SOURCE_KIND_MANUAL,
  UPLOAD_STEP_IDS,
  UploadReadsWizard,
  dispositionsFor,
  emptyManualRow,
  manualRowsMissingRegister,
  filledManualRows,
  reasonRequired,
  reviewRows,
  rowReasonText,
  ruleTally,
  unresolvedErrorRows,
  uploadReadMethodsKey,
  validationTiles,
} from "./UploadReadsWizard";
import { PREMISES_PERMISSION } from "./meteringShared";
import { READS_UPLOAD_ROUTE } from "./readsShared";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** Copy as it appears in the RENDERED markup — "Source & context" ships as
 *  "Source &amp; context", and an assertion that forgets it tests the escaper
 *  rather than the screen. */
const rendered = (key: string): string =>
  t(key).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/'/g, "&#x27;");

function counts(over: Partial<ReadBatchCounts> = {}): ReadBatchCounts {
  return {
    rows: 620,
    passed: 596,
    warnings: 20,
    errors: 4,
    rows_with_unevaluated: 0,
    accepted: 596,
    rejected: 0,
    field_visit: 0,
    skipped: 0,
    estimate_requested: 0,
    undispositioned: 24,
    posted: 0,
    severity_total: 620,
    reconciles: true,
    ...over,
  };
}

/** EP-MET-03 §4: M-7204's high-usage water row, and M-7823's negative usage. */
function row(over: Partial<ReadImportBatchRow> = {}): ReadImportBatchRow {
  return {
    row_no: 27,
    meter_no: "M-7204",
    asset_id: "a-7204",
    read_at: "2026-08-03",
    read_at_raw: "2026-08-03",
    channel: "total",
    value: "438240.000000",
    raw_value: "438240.000000",
    unit: "kgal",  // BR-MET-143 — the register's own unit, served per row
    service: "W",
    read_method: "walk_by",  // inherited from the batch tag (BR-MET-014)
    note: null,
    severity: "warning",
    rule_outcomes: [{ rule: "high", severity: "warning", detail: { ratio_pct: "312.0" } }],
    disposition: null,
    disposition_reason: null,
    // BR-MET-051 (CR-038 W4) — every staged row states its reset and whether
    // it is the demand register. The default fixture is an energy row.
    demand_reset_noted: false,
    is_peak: false,
    meter_read_id: null,
    ...over,
  };
}

function errorRow(): ReadImportBatchRow {
  return row({
    row_no: 84,
    meter_no: "M-7823",
    value: "88102.000000",
    severity: "error",
    rule_outcomes: [{ rule: "negative_usage", severity: "error", detail: {} }],
  });
}

function parseErrorRow(): ReadImportBatchRow {
  return row({
    row_no: 112,
    meter_no: null,
    read_at: null,
    read_at_raw: "13/45/2026",
    value: null,
    severity: "error",
    rule_outcomes: [
      { rule: "parse", severity: "error", detail: { code: "read_date_unparseable" } },
    ],
  });
}

function validation(over: Partial<ReadBatchValidation> = {}): ReadBatchValidation {
  return {
    id: "b-2608-04",
    batch_no: "B-2608-04",
    status: "validated",
    source_kind: "csv",
    source_detail: "walk_by",
    read_method: "walk_by",
    period_month: "2026-08-01",
    cycle_id: "c-08a",
    route_id: null,
    service: null,
    compliance: {
      file_name: "brazosbend_reads_08A.csv",
      file_hash: "a3f4c19e8291",
      // ⚠ A REALISTIC UUID, DELIBERATELY (DEF-899). `u-marcus` is short and
      // reads like a handle, so the receipt LOOKED fine here while the live
      // panel printed a primary key at a clerk.
      uploaded_by: "01a01d99-d617-7aa9-9f07-e2c08cc4fdc9",
      uploaded_by_name: "Marcus Johnson",
      uploaded_at: "2026-08-06T14:14:22Z",
      session_ref: "sess_9f27",
      ip: "98.200.114.7",
      certified: false,
      cosigned_by: null,
      cosigned_by_name: null,
    },
    counts: counts(),
    posted_at: null,
    unevaluated_rules: [{ rule: "high", reason: "validation_config_missing" }],
    validation_config_present: false,
    ...over,
  };
}

/** The staged rows. They come back from `GET /read-batches/{id}` — the
 *  validate answer carries none, which is why they are their own fixture. */
function stagedRows(): ReadImportBatchRow[] {
  return [row(), errorRow(), parseErrorRow()];
}

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access }],
  };
}

/**
 * The tenant's SEEDED `read_methods` list — the PO's five words of 2026-08-26
 * (BR-MET-123) plus BR-MET-142's three of 2026-08-27. Seeded into the query
 * cache rather than fetched, because these tests render to static markup and
 * never run an effect.
 *
 * ⚠ THIS IS A FIXTURE, NOT THE VOCABULARY. The product reads the list from the
 * tenant (`GET /reads/read-methods` → `assets.read_methods`); a tenant that
 * adds a ninth gets it, and this array does not. The test two blocks down
 * proves exactly that by rendering a tenant whose only method is `drone`.
 */
const READ_METHOD_FIXTURE = [
  { code: "ami", name: "AMI" },
  { code: "amr", name: "AMR" },
  { code: "walk_by", name: "walk-by" },
  { code: "manual", name: "Manual" },
  { code: "mobile", name: "Mobile" },
  // ⚠ BR-MET-142 (PO ruling 2026-08-27, closing OQ-392) — the vocabulary went
  // from five to eight. Appended, in the server's own seed order, because the
  // picker is ordered seeded-first: the five above stay where a clerk expects
  // them. This array is still a FIXTURE and still not the source (the comment
  // above says so); it is updated so a test that walks it exercises the eight
  // labels the product actually renders.
  { code: "drive_by", name: "Drive-by" },
  { code: "self_read", name: "Self-read" },
  { code: "field_visit", name: "Field visit" },
];

function renderWizard(access = "Full", methods = READ_METHOD_FIXTURE): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(access));
  queryClient.setQueryData(uploadReadMethodsKey, methods);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${READS_UPLOAD_ROUTE}`]}>
          <UploadReadsWizard />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("S28 — Upload reads (US-MET-007/008/009/010/017 · DEF-115)", () => {
  it("US-MET-007 TC-1 · CR-038 W7: the screen opens on the SHARED five-stage rail", () => {
    // DEF-115 in one assertion. Until 2026-08-15 this route rendered nothing
    // and `meter_reads` held 0 rows on a fully seeded stack, so no bill in the
    // product had ever come from a meter reading.
    //
    // ⚠ **AMENDED 2026-08-26 (CR-038 W7) — AND THE OLD ASSERTION WAS PINNING
    // THE DEFECT.** It asserted this screen's OWN five step labels ("Source &
    // context" …) and its own page title, which is exactly what the PO reported
    // as wrong: *"These are existing screens - We need to follow tailwind
    // wizard that we are using - i believe we are using same code for
    // various"*. Reads now mount `components/workflow/WorkflowRunner` with the
    // `reads` kind — the same runner premises, units, three assets targets and
    // accounts already share — so the rail's words are `WORKFLOW_STAGES`', and
    // a test still demanding the private labels would refuse the fix.
    //
    // `UPLOAD_STEP_IDS` is UNCHANGED and still asserted: those are the reads
    // PIPELINE's own steps, which the rail does not touch. What changed is
    // which five words a user reads on the rail.
    const html = renderWizard();
    expect(UPLOAD_STEP_IDS).toEqual(["source", "upload", "validate", "review", "post"]);
    // The shared rail, by its own stage names and its own markers.
    for (const stage of ["Extract", "Transform", "Validate", "Load", "Result"]) {
      expect(html).toContain(stage);
    }
    expect(html).toContain('data-workflow="runner"');
    expect(html).toContain('data-kind="reads"');
    // ⚠ ONE implementation, `kind` parameterised — the kind's own copy resolves
    // from the catalogue rather than rendering its dotted key name (G27/DEF-662).
    expect(html).toContain(rendered("workflow.reads.kicker"));
    expect(html).not.toContain("workflow.reads.");
  });

  it("US-MET-007 TC-1 · BR-MET-123: step 1 offers the batch tags and the READ METHOD", () => {
    // ⚠ AMENDED 2026-08-26 (CR-038 W3). This test asserted the six legacy
    // `source_detail` options. BR-MET-123 collapses three competing
    // vocabularies into ONE — the tenant's five-word `read_methods` list — and
    // the step-1 control is now that. The old six are still RENDERED on S25
    // and S29 for reads already carrying them; they are simply no longer
    // OFFERED here.
    //
    // Proved RED first by reverting the SelectField to `SOURCE_DETAILS`:
    //   AssertionError: expected '<div class="met-page rd-page">…' to contain
    //   'How were these read?'
    const html = renderWizard();
    // ⚠ `metering.upload.source.hint` was asserted here and is no longer
    // RENDERED — the blueprint draws no sub-line under "The source" (B14 rule
    // 32's description budget). The key still exists; this case is about the
    // four tags and the read-method vocabulary, which is what it now asserts.
    expect(html).toContain(t("metering.upload.field.periodMonth"));
    expect(html).toContain(t("metering.upload.field.cycle"));
    expect(html).toContain(t("metering.upload.field.route"));
    expect(html).toContain(t("metering.upload.field.readMethod"));
    for (const method of READ_METHOD_FIXTURE) {
      expect(html).toContain(t(`metering.reads.readMethod.${method.code}`));
    }
    // AMR and Mobile are the measured gap: neither could be expressed by the
    // old three-value read `source` or the old six batch details.
    expect(html).toContain(t("metering.reads.readMethod.amr"));
    expect(html).toContain(t("metering.reads.readMethod.mobile"));
  });

  it("BR-MET-123: the vocabulary is the TENANT'S list, not an array in this file", () => {
    // A tenant that adds `drone` sees `drone`. Nothing in the wizard enumerates
    // methods, so this can only pass if the options come from the server.
    //
    // Proved RED first by hardcoding the five in `SourceStep`:
    //   AssertionError: expected '…' to contain 'Drone flyover'
    const html = renderWizard("Full", [{ code: "drone", name: "Drone flyover" }]);
    expect(html).toContain("Drone flyover");
    expect(html).not.toContain(t("metering.reads.readMethod.amr"));
  });

  it("BR-MET-123: an unavailable list says so and never invents a vocabulary", () => {
    // The honest failure. `/lookups/read_methods` is System-Admin-only
    // (DEF-196) and this is the Billing Clerk's screen, which is exactly how a
    // clerk ends up looking at an empty control with no explanation.
    //
    // Proved RED first by rendering the empty SelectField anyway:
    //   AssertionError: expected '…' to contain 'The read-method list is
    //   unavailable, so this batch will be tagged with no method.'
    const html = renderWizard("Full", []);
    expect(html).toContain(t("metering.upload.field.readMethodUnavailable"));
    expect(html).not.toContain(t("metering.upload.field.readMethod"));
  });

  it("BR-MET-123: the AMI TRANSPORT card is NOT offered, and the AMI TAG is", () => {
    // ⚠ AMENDED 2026-08-26 (CR-038 W3), and this test's title used to be
    // *"the AMI card is DRAWN and DISABLED with its reason (BR-SHL-025)"*.
    //
    // BR-MET-123 clause 3 supersedes that reading for this control, verbatim:
    // *"No head-end/SFTP/API integration is built now; a transport card with
    // nothing behind it is not offered (the DEF-520 posture), but the source
    // TAGS remain complete."* The PO's own words on the rule: *"there is no
    // integration yet; but it should not stop us from tagging the soruce and
    // accepting the CSV or excel file"*.
    //
    // So the honest screen is: TWO transports, and AMI as a source TAG.
    //
    // Proved RED first by putting SOURCE_KIND_AMI back in SOURCE_KINDS:
    //   AssertionError: expected [ 'csv', 'manual', 'ami_replay' ] to
    //   have a length of 2 but got 3
    const html = renderWizard();
    expect(SOURCE_KINDS).toEqual([SOURCE_KIND_CSV, SOURCE_KIND_MANUAL]);
    expect(SOURCE_KINDS).not.toContain(SOURCE_KIND_AMI);
    expect(html).not.toContain(t("metering.reads.sourceKind.ami_replay"));
    // The capability is not hidden — it moved to where it is genuinely available: a
    // file COLLECTED by AMI, tagged AMI.
    expect(html).toContain(t("metering.upload.source.amiTagged"));
    expect(html).toContain(t("metering.reads.readMethod.ami"));
  });

  it("stage 1 carries ONE heading and the blueprint's own words (CR-096-BRC02)", () => {
    // The blueprint draws `STAGE 1 OF 5 · EXTRACT` over **The source** and then
    // the cards. The screen used to print TWO headings saying the same thing —
    // the runner's "Where is the data coming from?" and this panel's "Where are
    // these readings coming from?" — plus a sub-line the drawing does not
    // carry. B14 rule 32: one sentence of description per section, and the
    // drawing spends it on none.
    const html = renderWizard();
    expect(html).toContain("Upload reads");
    expect(html).toContain("Stage 1 of 5 · Extract");
    expect(html).toContain(t("workflow.reads.extractTitle"));
    expect(html).not.toContain(t("workflow.extract.title"));
    expect(html).not.toContain("Every reading inherits these");
    // B14 rule 33 — rationale is zero words on screen; the WRITES chip says it.
    expect(html).not.toContain(t("workflow.promise"));
  });

  it("US-MET-007 TC-3 / US-MET-017: a manual row has NO register until a person picks one (BR-MET-059 · Q7)", () => {
    // ⚠ **THIS CASE ASSERTED `"total"` AND ITS NAME SAID "EXPLICIT" — the test
    // encoded the defect, so it could never have found it.** `emptyManualRow`
    // pre-selected `total` while its comment claimed *"the channel is EXPLICIT
    // from the first keystroke"*; a value nobody touched is not explicit, and
    // hard-won law 1 is exactly this shape.
    //
    // **Q7, PO 2026-09-14, verbatim: *"Put this first."*** A reading against the
    // wrong register is permanent — `supersede_read` takes only a value and a
    // reason, and migration `0007`'s trigger freezes the channel — and on a
    // demand plan the units differ, which is how `DEF-797` billed **412 kW as
    // 14 kWh, $154 against $4,532**. An upload is the highest-volume way to get
    // it wrong, so the grid refuses to guess.
    expect(emptyManualRow().channel).toBe("");
    expect(READ_CHANNELS).not.toContain(emptyManualRow().channel);

    // Blank rows in the grid are not sent — two empty rows stage nothing, and
    // they are NOT what the refusal is about.
    expect(filledManualRows([emptyManualRow(), emptyManualRow()])).toHaveLength(0);
    expect(manualRowsMissingRegister([emptyManualRow(), emptyManualRow()])).toHaveLength(0);

    // A row a clerk has actually typed into, with no register, is refused BY
    // NAME — before the batch is staged, which is the only side of the write
    // where it can still be fixed.
    const typed = { ...emptyManualRow(), meter_id: "M-7108", reading: "89204" };
    expect(filledManualRows([typed])).toHaveLength(1);
    expect(manualRowsMissingRegister([typed])).toHaveLength(1);

    // …and the same row with a register chosen passes.
    expect(manualRowsMissingRegister([{ ...typed, channel: "demand" }])).toHaveLength(0);
  });

  it("US-MET-008 TC-1: the validation tiles are the server's counts, and Missing is '—' not 0 (BR-MET-049)", () => {
    const tiles = validationTiles(validation(), t);
    expect(tiles.map((tile) => tile.id)).toEqual([
      "rows",
      "passed",
      "warnings",
      "errors",
      "missing",
    ]);
    const valueOf = (tile: (typeof tiles)[number]): unknown =>
      "value" in tile ? tile.value : undefined;
    expect(valueOf(tiles[0])).toBe(620);
    expect(valueOf(tiles[3])).toBe(4);
    // BR-MET-049's plan-driven completeness is US-MET-018 and is not built. A
    // 0 here would say "nothing is missing", which is a different claim.
    expect(valueOf(tiles[4])).not.toBe(0);
  });

  it("US-MET-008 TC-1: the rule table TALLIES stored verdicts and never re-derives one (BR-MET-056)", () => {
    const tally = ruleTally(stagedRows());
    // Errors sort above warnings so the blocking work is at the top.
    expect(tally.map((entry) => entry.rule)).toEqual(["negative_usage", "parse", "high"]);
    expect(tally.map((entry) => entry.severity)).toEqual(["error", "error", "warning"]);
    expect(tally.every((entry) => entry.hits === 1)).toBe(true);
  });

  it("US-MET-008 TC-5: an ERROR row is never offered a plain Accept (BR-MET-015)", () => {
    // The server refuses `accept` on an error row
    // (`metering.read_row.error_needs_resolution`). The option is not on the
    // screen either — the rule is a data structure here, not care.
    expect(dispositionsFor("error")).not.toContain("accept");
    expect(dispositionsFor("error")).toEqual(["override", "reject", "field_visit", "skip"]);
    expect(dispositionsFor("warning")).toContain("accept_with_flag");
    expect(dispositionsFor("ok")).toContain("accept");
    for (const disposition of dispositionsFor("warning")) {
      expect(DISPOSITIONS).toContain(disposition);
    }
  });

  it("US-MET-008 TC-6: every disposition but a plain accept demands a reason (BR-MET-015)", () => {
    expect(reasonRequired("accept")).toBe(false);
    for (const disposition of ["accept_with_flag", "override", "reject", "skip", "field_visit"]) {
      expect(reasonRequired(disposition)).toBe(true);
    }
  });

  it("US-MET-008 TC-5: Continue is blocked while an error row has no decision", () => {
    const blocking = unresolvedErrorRows(stagedRows());
    expect(blocking.map((entry) => entry.row_no)).toEqual([84, 112]);
    // Give each one a decision and the block lifts — the count on screen is
    // this same list.
    const resolved = stagedRows().map((entry: ReadImportBatchRow) =>
      entry.severity === "error" ? { ...entry, disposition: "reject" } : entry,
    );
    expect(unresolvedErrorRows(resolved)).toHaveLength(0);
  });

  it("US-MET-008 TC-2: the review segments slice the FLAGGED rows only", () => {
    const rows = stagedRows();
    expect(reviewRows(rows, "all")).toHaveLength(3);
    expect(reviewRows(rows, "error").map((entry) => entry.row_no)).toEqual([84, 112]);
    expect(reviewRows(rows, "warning").map((entry) => entry.row_no)).toEqual([27]);
    // A clean row is not review work and is not in any segment.
    expect(reviewRows([row({ severity: "ok" })], "all")).toHaveLength(0);
  });

  it("US-MET-007 TC-7: a row that failed to PARSE says what was wrong with it, in words", () => {
    // The reason is the read_import code rendered from the catalogue — a
    // clerk sees "That is not a date we can read", never `read_date_unparseable`.
    expect(rowReasonText(parseErrorRow(), t)).toBe(
      t("metering.read_import.read_date_unparseable"),
    );
    expect(rowReasonText(errorRow(), t)).toBe(t("metering.reads.status.negative_usage"));
    // A clean row has nothing to say.
    expect(rowReasonText(row({ rule_outcomes: [] }), t)).toBe("");
  });

  it("US-MET-009 TC-3: correcting a duplicate is the override disposition, not a second write path", () => {
    // BR-MET-016/053: the commit APPENDS a superseding reading and closes the
    // old head. There is no separate "Replace existing" control, because it is
    // not a separate write — and no control anywhere edits a posted reading.
    expect(dispositionsFor("error")).toContain("override");
    expect(DISPOSITIONS).not.toContain("edit");
    expect(DISPOSITIONS).not.toContain("delete");
  });

  it("US-MET-010 §5: no staged row prints a USAGE figure — but the register reading now carries its unit (BR-MET-143)", () => {
    // A staged row is a REGISTER reading, and CONSUMPTION is still computed at
    // commit — so there is still no usage figure here and no column for one.
    const staged = row();
    expect(staged).not.toHaveProperty("consumption");
    expect(staged).not.toHaveProperty("usage_display");

    // ⚠ **AMENDED 2026-08-27 — BR-MET-143 / DEF-797. The `unit` half of this
    // assertion is INVERTED and the test is kept in place, not deleted.**
    //
    // It read `expect(staged).not.toHaveProperty("unit")`, and its reason was:
    // *"Consumption is computed at commit from the meter (`_post_row` writes
    // `unit=asset.unit`), so the staged payload carries neither quantity nor
    // unit."* Both halves of that were true and the CONSEQUENCE was DEF-797: a
    // clerk approving 1,180 rows saw `412` with nothing beside it, so a peak
    // about to commit in the wrong unit — $154.00 where the correct charge was
    // $4,532.00 — was uncheckable at the one moment a person looks at the
    // reading before it becomes an issued document.
    //
    // The row now carries the REGISTER's unit: the very string `_post_row`
    // will stamp, so what the clerk approves and what commits cannot drift.
    expect(staged).toHaveProperty("unit");
    expect(staged.unit).toBe("kgal");
  });

  it("BR-SHL-025: a View-only role meets the refusal before it fills anything in", () => {
    const html = renderWizard("View");
    expect(html).toContain(t("metering.rbac.readOnly"));
  });

  it("A18 §6: a '—' permission cell denies the whole screen", () => {
    const html = renderWizard("—");
    expect(html).toContain(t("metering.reads.denied"));
    expect(html).not.toContain(t("metering.upload.source.hint"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-007@7c9c034 (EP-MET-03 lead story, sha1 of the epic file; co-stories US-MET-008 · US-MET-009 · US-MET-010 · US-MET-017) + DEF-115
// generated: 2026-08-15 by the DEF-114/115 lane
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — test file) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report
// exceptions: E3 the browser-interaction half — staging a file, running the
//   rules, recording a disposition and posting — is a PLAYWRIGHT journey against
//   the live stack, not a jsdom render: every one of those steps is a real HTTP
//   call to a real endpoint, and a mocked version would assert this lane's own
//   fixture rather than the server's behaviour. The journey is what proved
//   DEF-115 closed, and its output is quoted in the lane report
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
