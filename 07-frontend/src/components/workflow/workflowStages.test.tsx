// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the ten stage components of the ETL kit
// Rules:    BR-MET-088 (real target columns) · BR-MET-090 (severity and action
//           are two columns) · BR-MET-091 (an unavailable rule is DECLARED with
//           its reason) · B14 rule 17 (every list has an empty state)
// Impacts:  src/components/workflow/** (no screen mounts these yet — the
//           metering lane owns PRM-01/PRM-01U/PRM-04)
// ───────────────────────────────────────────────────────
//
// TEST DATA IS DESIGN B15 §16's OWN, so the numbers a reviewer checks against
// the design are the numbers here: a 431-row premises file with 3 exact
// duplicates leaving 428 forward, 2 errors and 5 warnings at validation, 426
// created and 2 rejected at the load.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n"; // the i18next singleton with the eleven catalogues

import { DropZone } from "./DropZone";
import { DryRunPanel } from "./DryRunPanel";
import { MappingTable } from "./MappingTable";
import { Receipt } from "./Receipt";
import { ReconcileStrip } from "./ReconcileStrip";
import { RejectList } from "./RejectList";
import { RollbackNotice } from "./RollbackNotice";
import { WORKFLOW_KINDS, rollbackControlIsOffered, type WorkflowKindId } from "./kinds";
import { RowHandlingOptions } from "./RowHandlingOptions";
import { RuleResultsTable } from "./RuleResultsTable";
import { SourceCards } from "./SourceCards";
import type {
  ApprovalNote,
  DryRunFigure,
  MappingRow,
  ReceivedFile,
  ReconcileFigure,
  Receipt as ReceiptData,
  RejectedRow,
  RuleResult,
  TargetColumn,
} from "./contract";
import type { WriteModeOption } from "./WriteModeChoice";
import { WORKFLOW_SOURCES } from "./kinds";

const noop = () => undefined;

// ── §4.1 · the file r10 receives ───────────────────────────────────────────
const FILE: ReceivedFile = {
  name: "silvercreek_premises_2026.csv",
  rows: 431,
  size_label: "96 KB",
  sha256: "c19a7f6b2d4e8a01c3b5d7f9e1a3c5b7d9f1a3c5b7d9e1f3a5c7b9d1e3f5a4407",
};

// ── §4.2A · the REAL columns of `metering.Premises`, as the server serves them
const TARGETS: TargetColumn[] = [
  { id: "premise_no", label: "Premise ID", required: false },
  { id: "address_line", label: "Address line", required: true },
  { id: "city", label: "City", required: false },
  { id: "inside_city_limits", label: "Inside city limits", required: false },
  { id: "external_ref", label: "External reference", required: false },
];

const MAPPING: MappingRow[] = [
  {
    source_column: "PREMISE_ID",
    sample_value: "P-10432",
    target_column: "premise_no",
    status: "matched",
    transform_label: "Trim whitespace",
  },
  {
    source_column: "ADDR1",
    sample_value: "1408 Elm Street",
    target_column: "address_line",
    status: "matched",
    transform_label: null,
  },
  // r10 maps this one to `— ignore —`; B15 §4.2A recommends `external_ref`.
  // Either way the row's own state has to be distinguishable from "nobody
  // looked at it", which is the next row.
  {
    source_column: "LEGACY_KEY",
    sample_value: "88214",
    target_column: null,
    status: "ignored",
    transform_label: null,
  },
  {
    source_column: "NOTES",
    sample_value: "corner lot",
    target_column: null,
    status: "unmapped",
    transform_label: null,
  },
];

// ── §4.3 · the rules that ran, INCLUDING the one that cannot ───────────────
const RULES: RuleResult[] = [
  {
    code: "PRM.ADDRESS_IN_TERRITORY",
    sentence: "Address must geocode inside the service territory",
    severity: "error",
    action_label: "Reject row",
    hits: 0,
    available: false,
    unavailable_reason: "Address look-up is not switched on, so this rule was not applied.",
  },
  {
    code: "PRM.NO_DUPLICATE_ADDRESS",
    sentence: "No premise already on file at this address",
    severity: "warning",
    action_label: "Skip on load",
    hits: 3,
    available: true,
    unavailable_reason: null,
  },
  {
    code: "PRM.TYPE_IN_LOOKUP",
    sentence: "Premise type exists in the lookup table",
    severity: "warning",
    action_label: "Default to Residential",
    hits: 2,
    available: true,
    unavailable_reason: null,
  },
];

const REJECTS: RejectedRow[] = [
  {
    row_number: 88,
    key: "P-11902",
    problem: "The address falls outside the service area.",
    suggested_fix: "Confirm and load anyway",
  },
  {
    row_number: 214,
    key: "P-12044",
    problem: "The street name could not be found.",
    suggested_fix: "Correct the address",
  },
];

const DRY_RUN: DryRunFigure[] = [
  { id: "create", label: "Will create", value: "426", numeric: true },
  { id: "update", label: "Existing records updated", value: "2", numeric: true },
  { id: "reject", label: "Rows rejected", value: "2", numeric: true },
  { id: "scope", label: "Scope affected", value: "426 addresses", numeric: false },
  { id: "target", label: "Target", value: "Premises", numeric: false },
];

// CR-042 — TWO modes. `replace` was the third and is withdrawn; the fixture
// follows the product rather than the prototype, which still draws three.
const MODES: WriteModeOption[] = [
  { id: "insert", label: "Insert new only", consequence: null },
  { id: "upsert", label: "Insert & update", consequence: null },
];

const APPROVAL: ApprovalNote = {
  threshold_pct: 5,
  rejected: 2,
  of_rows: 428,
  always_requires: null,
};

const RECEIPT: ReceiptData = {
  run_id: "RUN-2812",
  finished_label: "Aug 6, 2026 · 09:14:22 CDT",
  duration_label: "18s",
  source_label: "silvercreek_premises_2026.csv · 96 KB",
  file_sha256: FILE.sha256,
  file_hash_verified: true,
  run_by: "Alex Reed · alex@silvercreek.example",
  session_and_ip: null, // ⚠ deliberately absent — see the receipt test
  mapping_used: "Migration v2",
  rollback_point: { id: "RB-2812", expiry_label: "available for 30 days" },
};

describe("CR-023 · Stage 1 · EXTRACT", () => {
  it("states the three sources we do not support, rather than drawing them live", () => {
    // B15 §4.1 puts three of r10's four cards out of scope and §8 Q2 leaves
    // whether they are in scope at all UNRULED. Deleting them makes the screen
    // quietly disagree with the design a utility was shown; wiring them answers
    // an open question by building it. So they are listed and they refuse.
    const html = renderToStaticMarkup(
      <SourceCards
        legend="Where is the data coming from?"
        choices={WORKFLOW_SOURCES}
        selectedId="file"
        groupName="wf-source"
        onSelect={noop}
      />,
    );
    expect(html).toContain("Upload a file");
    expect(html).toContain("Pull from a server");
    expect(html).toContain("Head-end or partner");
    expect(html).toContain("Key it in");
    // Three refusals, each with a sentence — and each unclickable, because a
    // styled box that swallows a press says nothing to a keyboard.
    expect([...html.matchAll(/Not switched on yet\./g)].length).toBe(3);
    expect([...html.matchAll(/data-available="false"/g)].length).toBe(3);
    expect([...html.matchAll(/disabled/g)].length).toBe(3);
    // …and the one that IS supported is the one selected.
    expect(html).toContain('data-workflow-source="file"');
    expect(html).toContain('data-state="selected"');
  });

  it("the drop target states what it received, hash included", () => {
    const html = renderToStaticMarkup(<DropZone file={FILE} onBrowse={noop} />);
    expect(html).toContain("silvercreek_premises_2026.csv");
    expect(html).toContain("431 rows");
    expect(html).toContain("96 KB");
    expect(html).toContain(FILE.sha256);
    expect(html).toContain('data-state="received"');
  });

  it("an empty target is a STATE, not a blank box", () => {
    const html = renderToStaticMarkup(<DropZone file={null} onBrowse={noop} />);
    expect(html).toContain("No file chosen yet.");
    expect(html).toContain('data-state="empty"');
  });
});

describe("CR-023 · Stage 2 · TRANSFORM", () => {
  it("BR-MET-088 · MAPS TO offers the REAL target columns and nothing else", () => {
    // "at the transform screen - you can choose actual column you have from
    // table" — so a column that exists can always be mapped and a column that
    // does not can never be offered. A hand-written label list drifts from the
    // schema and the operator's value is silently dropped.
    const html = renderToStaticMarkup(
      <MappingTable rows={MAPPING} targets={TARGETS} idPrefix="wf" onTargetChange={noop} />,
    );
    for (const target of TARGETS) {
      expect(html).toContain(`value="${target.id}"`);
      expect(html).toContain(target.label);
    }
    // Nothing invented: exactly the served columns plus the ignore sentinel.
    const optionValues = [...html.matchAll(/<option value="([^"]*)"/g)].map((m) => m[1]);
    expect(new Set(optionValues)).toEqual(
      new Set([...TARGETS.map((t) => t.id), "__ignore__"]),
    );
  });

  it("`— ignore —` is a CHOICE and is distinguishable from nobody mapping it", () => {
    // B15 §4.2A: discarding the customer's own key costs reconciliation, a
    // re-import that duplicates rows, and the answer to "what happened to
    // property 88214" — none of it visible on the day of the migration. The
    // difference the screen has to carry is between a decision and an omission.
    const html = renderToStaticMarkup(
      <MappingTable rows={MAPPING} targets={TARGETS} idPrefix="wf" onTargetChange={noop} />,
    );
    expect(html).toContain("— ignore —");
    expect(html).toContain('data-workflow-map-status="ignored"');
    expect(html).toContain('data-workflow-map-status="unmapped"');
    expect(html).toContain("Ignored");
    expect(html).toContain("Not mapped");
  });

  it("row handling is the three checkboxes, from the SHARED control", () => {
    const html = renderToStaticMarkup(
      <RowHandlingOptions
        value={{
          drop_exact_duplicates: true,
          // ⚠ The WIRE name (`DEF-522`). The kit declared this option as
          // `keep_latest_on_duplicate_key` and the server has always called it
          // `keep_latest_on_key`; the server read an unknown key as `false`,
          // so the mis-spelling kept the FIRST row instead of the latest.
          keep_latest_on_key: true,
          skip_rows_missing_required: false,
        }}
        idPrefix="wf"
        onChange={noop}
      />,
    );
    expect(html).toContain("Drop exact duplicate rows");
    expect(html).toContain("Keep the latest row when a key appears twice");
    expect(html).toContain("Skip rows with empty required fields rather than rejecting them");
    // The shared `CheckboxField`, not a fourth checkbox drawn by hand. It was
    // the `.radio`/`.dot` kit until DEF-569 — three MULTI-selects wearing the
    // radio's circle — and the shared mark it draws now is a square with a
    // tick, counted here by its handle.
    expect([...html.matchAll(/data-checkbox-mark/g)].length).toBe(3);
    expect([...html.matchAll(/class="radio"/g)].length).toBe(0);
    expect([...html.matchAll(/checked=""/g)].length).toBe(2);
  });
});

describe("CR-023 · the figure strip is ONE component and THREE uses", () => {
  const TRANSFORM: ReconcileFigure[] = [
    { id: "in", label: "Rows in", value: 431, flagged: false },
    { id: "dropped", label: "Duplicates dropped", value: 3, flagged: false },
    { id: "forward", label: "Rows forward to validation", value: 428, flagged: false },
  ];
  const VALIDATE: ReconcileFigure[] = [
    { id: "checked", label: "Rows checked", value: 428, flagged: false },
    { id: "clean", label: "Passed clean", value: 421, flagged: false },
    { id: "errors", label: "Errors", value: 2, flagged: true },
    { id: "warnings", label: "Warnings", value: 5, flagged: false },
  ];
  const RESULT: ReconcileFigure[] = [
    { id: "loaded", label: "Loaded", value: 426, flagged: false },
    { id: "rejected", label: "Rejected", value: 2, flagged: true },
    { id: "flagged", label: "Flagged for review", value: 5, flagged: false },
  ];

  it("use 1 · the transform reconcile, and its three figures add up", () => {
    const html = renderToStaticMarkup(
      <ReconcileStrip caption="After transform" figures={TRANSFORM} layout="rows" />,
    );
    expect(html).toContain("After transform");
    expect(html).toContain("431");
    expect(html).toContain("428");
    expect(html).toContain('data-layout="rows"');
    // B15 §16 TC-3: in − dropped = forward. The screen does not compute it, so
    // this asserts the FIXTURE is the design's, which is what makes the
    // rendered figures reviewable against §4.2.
    // `ReconcileFigure.value` widened to `number | string` with CR-036 (f) —
    // an absent count is drawn as an em-dash, never as a zero — so the three
    // figures are read back as numbers before the arithmetic. The fixture is
    // the design's and all three ARE counts.
    expect(Number(TRANSFORM[0].value) - Number(TRANSFORM[1].value)).toBe(
      Number(TRANSFORM[2].value),
    );
  });

  it("use 2 · the Validate KPI strip, with the ERRORS tile flagged", () => {
    const html = renderToStaticMarkup(
      <ReconcileStrip caption={null} figures={VALIDATE} layout="tiles" />,
    );
    expect(html).toContain('data-layout="tiles"');
    expect(html).toContain("Rows checked");
    expect([...html.matchAll(/data-flagged="true"/g)].length).toBe(1);
    const errors = html.slice(html.indexOf('data-workflow-figure="errors"'));
    expect(errors.slice(0, 400)).toContain("tabular-nums");
  });

  it("use 3 · the Result KPI strip, from the SAME component", () => {
    const html = renderToStaticMarkup(
      <ReconcileStrip caption={null} figures={RESULT} layout="tiles" />,
    );
    expect(html).toContain("Loaded");
    expect(html).toContain("426");
    expect([...html.matchAll(/data-flagged="true"/g)].length).toBe(1);
    expect(html).toContain('data-workflow="reconcile"');
  });
});

describe("CR-023 · Stage 3 · VALIDATE", () => {
  it("BR-MET-091 · a rule that CANNOT RUN is listed WITH ITS REASON", () => {
    // r10's only ERROR-severity rule on a premises import needs a geocoder and
    // a service territory, and this product has neither. Omitting the row would
    // leave "errors block the load" as a promise with no error rule behind it,
    // and a screen listing three rules where four were expected tells the
    // operator nothing at all.
    const html = renderToStaticMarkup(
      <RuleResultsTable
        caption="Rules that ran"
        rules={RULES}
        emptyMessage="No rules ran on this file."
      />,
    );
    expect(html).toContain("Address must geocode inside the service territory");
    expect(html).toContain("Address look-up is not switched on, so this rule was not applied.");
    expect(html).toContain('data-available="false"');
    expect(html).toContain("Cannot run");
    // Not `0` hits: zero means the rule ran and found nothing, which is the
    // opposite of what happened.
    const row = html.slice(html.indexOf('data-workflow-rule="PRM.ADDRESS_IN_TERRITORY"'));
    expect(row.slice(0, 700)).toContain("—");
  });

  it("BR-MET-090 · severity and action are two columns, and the pair is visible", () => {
    // "Premise type exists in the lookup table · Warning · 2 · Default to
    // Residential" is a WARNING that performs a WRITE nobody asked for. Two
    // premises silently become Residential and price as Residential; showing
    // the pair is what makes that visible BEFORE the load.
    const html = renderToStaticMarkup(
      <RuleResultsTable
        caption="Rules that ran"
        rules={RULES}
        emptyMessage="No rules ran on this file."
      />,
    );
    expect(html).toContain("Severity");
    expect(html).toContain("Action");
    expect(html).toContain("Warning");
    expect(html).toContain("Default to Residential");
  });

  it("B14 rule 17 · an empty rule list says so", () => {
    const html = renderToStaticMarkup(
      <RuleResultsTable caption="Rules that ran" rules={[]} emptyMessage="No rules ran on this file." />,
    );
    expect(html).toContain("No rules ran on this file.");
  });

  it("a reject carries the problem AND the suggested fix", () => {
    // A reject list that says only what is wrong sends an operator back to a
    // 431-row spreadsheet with no instruction.
    const html = renderToStaticMarkup(
      <RejectList
        caption="Fix the rejects here — no need to re-upload"
        rejects={REJECTS}
        emptyMessage="Nothing was rejected."
      />,
    );
    expect(html).toContain("88");
    expect(html).toContain("P-11902");
    expect(html).toContain("The address falls outside the service area.");
    expect(html).toContain("Confirm and load anyway");
    expect(html).toContain("Correct the address");
  });

  it("an empty reject list is good news and says it", () => {
    const html = renderToStaticMarkup(
      <RejectList caption="Rejects" rejects={[]} emptyMessage="Nothing was rejected." />,
    );
    expect(html).toContain("Nothing was rejected.");
  });
});

describe("CR-023 · Stage 4 · LOAD", () => {
  function dryRun(modeId: string): string {
    return renderToStaticMarkup(
      <DryRunPanel
        figures={DRY_RUN}
        modes={MODES}
        selectedModeId={modeId}
        onChangeModeRequested={noop}
        approval={APPROVAL}
        options={{ create_rollback_point: true, notify_on_finish: true }}
        onOptionsChange={noop}
        idPrefix="wf"
      />,
    );
  }

  it("the dry run says what will be written, in the server's own figures", () => {
    const html = dryRun("insert");
    expect(html).toContain("Dry run · what will be written");
    expect(html).toContain("426");
    expect(html).toContain("426 addresses");
    expect(html).toContain("Premises");
  });

  it("BR-MET-085 · the `Will create` line has ONE clause, not two", () => {
    // r10 prints "426 premises · 181 single-unit premises auto-create their
    // unit" here and again on the receipt. The PO withdrew the auto-create with
    // the sentence: a premises load creates premises and nothing else.
    const html = dryRun("insert");
    expect(html).not.toContain("auto-create");
    expect(html).not.toContain("181");
  });

  it("stage 4 STATES the write mode and offers no second control for it", () => {
    // ⚠ **AMENDED 2026-08-26 (DEF-770), and the amendment REVERSES what this
    // case asserted.** It required three `seg-opt` options here — a full
    // duplicate of step 1's control — and it passed while the deployed screen
    // carried the same setting twice. PO, looking at it: *"Write mode from this
    // screen may not required . it is already added on step 1"*. Two controls
    // for one setting invite the question of which one wins, and there is no
    // good answer to give.
    //
    // What must NOT be lost, and is asserted instead: the dry run REHEARSES
    // against this mode, so an operator reading "will create 0 · will update
    // 9,881" has to know which premise produced those figures. The mode stays
    // VISIBLE as a fact, with a way back to the step that owns it.
    const html = dryRun("insert");
    expect(html).toContain("Insert new only");
    expect(html).toContain("the choice you made at step 1");
    expect(html).toContain("Change it");
    expect([...html.matchAll(/class="seg-opt"/g)].length).toBe(0);
  });

  it("⛔ CR-042 — there is no destructive mode left to caution about", () => {
    // ⚠ **THIS TEST REPLACES ONE THAT ASSERTED THE OPPOSITE, AND THE OLD ONE
    // IS THE REASON THIS ONE EXISTS.** It pinned that `Replace the batch`
    // carried a caution saying what it did to rows in the database and not in
    // the file was *"not decided yet"* (B15 §8 Q6 / OQ-326). The PO decided —
    // twice. On 2026-08-21 they gave it a behaviour (BR-MET-099), and on
    // 2026-08-27 they withdrew the option: *"replace option is not required"*.
    //
    // So the panel now has two modes, neither of which is destructive, and the
    // caution field is gone from the option type with the mode that needed it.
    // What stays is the STATEMENT of the premise (DEF-770) and the way back.
    const html = dryRun("insert");
    expect(html).not.toContain('data-workflow="write-mode-caution"');
    expect(html).not.toContain("Replace");
    expect(html).not.toContain("not decided yet");
    // A run committed BEFORE the withdrawal still carries the old value, and
    // the panel prints something true rather than a gap where the premise
    // should be — a historical receipt is not a place to render silence.
    expect(dryRun("replace")).toContain("replace");
  });

  it("the approval threshold is the SERVER's number, printed with this run's own", () => {
    // DEF-435's lesson: a screen constant no server enforces is a promise the
    // product cannot keep. The 5% is r10 copy, not a signed rule, so it arrives
    // as data and the kit prints what it is given.
    const html = dryRun("insert");
    expect(html).toContain("exceed 5% of the batch");
    expect(html).toContain("2 rejected of 428");
  });

  it("B14 rule 11 · the two checkboxes sit with the consequence preview", () => {
    const html = dryRun("insert");
    expect(html).toContain("Create a rollback point before writing");
    expect(html).toContain("Notify me when the load finishes");
  });
});

describe("CR-023 · Stage 5 · RESULT", () => {
  it("the receipt carries all six fields — and NO raw id is one of them", () => {
    // ⚠ **AMENDED 2026-08-26 (DEF-767), NOT WEAKENED.** This asserted
    // `RB-2812 · available for 30 days` and the bare `FILE.sha256`, and it
    // passed while the deployed screen printed
    // `01a03d62-3811-765d-a214-79352d02c075` to a clerk. PO, on that screen:
    // *"We get database keys on this screen"*. The test was checking that six
    // FIELDS were present and could not see that one of them was unreadable —
    // so the amendment ADDS the missing question rather than dropping the old
    // one: every field is still here, and now none of them is a raw id.
    const html = renderToStaticMarkup(<Receipt receipt={RECEIPT} />);
    expect(html).toContain("silvercreek_premises_2026.csv · 96 KB");
    expect(html).toContain("Alex Reed · alex@silvercreek.example");
    expect(html).toContain("Migration v2");
    expect(html).toContain("available for 30 days");

    // The fingerprint is EVIDENCE and is kept — on the hover, where evidence
    // belongs — while the clerk reads only the part they can act on.
    expect(html).toContain(`title="${FILE.sha256}"`);
    expect(html).toContain("Matched the file you uploaded.");

    // ⚠ The point of the whole amendment: the rollback POINT's id must not be
    // visible text. Asserted on the text with tags stripped, because a `title`
    // attribute is not something a clerk reads.
    const visible = html.replace(/<[^>]*>/g, " ");
    expect(visible).not.toContain("RB-2812");
    expect(visible).not.toContain(FILE.sha256);
  });

  it("an absent receipt field says NOT RECORDED rather than going blank", () => {
    // A receipt with an empty session line reads like a receipt with nothing to
    // hide. The fixture leaves `session_and_ip` null on purpose.
    const html = renderToStaticMarkup(<Receipt receipt={RECEIPT} />);
    const session = html.slice(html.indexOf('data-workflow="receipt-session"'));
    expect(session.slice(0, 300)).toContain("Not recorded");
  });

  it("the hash's verdict is a FLAG, not a word glued onto the hash string", () => {
    // ⚠ **AMENDED 2026-08-26 (DEF-767).** The property this case exists to pin
    // is unchanged and is the right one: the verdict comes from
    // `file_hash_verified`, never from parsing the hash string. Only the
    // SENTENCE moved — "not verified" was itself half the defect, a word a
    // clerk cannot act on sitting beside sixty-four hex characters.
    const verified = renderToStaticMarkup(<Receipt receipt={RECEIPT} />);
    expect(verified).toContain("Matched the file you uploaded.");

    const unverified = renderToStaticMarkup(
      <Receipt receipt={{ ...RECEIPT, file_hash_verified: false }} />,
    );
    expect(unverified).toContain("Could not be checked against the file you uploaded.");
    expect(unverified).not.toContain("Matched the file you uploaded.");
  });

  it("the rollback callout names BOTH consequences before the button", () => {
    // The second sentence is the reason this is a component: a rollback that
    // quietly keeps rows is one the operator believes was complete, and the
    // rows it keeps are exactly the ones something else is attached to.
    //
    // ⚠ AMENDED 2026-08-24 (DEF-623). This case asserted the ONE unconditional
    // sentence — *"Rolling back reverses every premise and unit the run
    // created. Units with an active account on them are skipped."* — and it is
    // exactly why the defect survived: the component rendered that string for
    // all six kinds and the test rendered the component with no kind at all, so
    // it agreed. It now asserts the PREMISES kind's own sentence, and the case
    // below asserts that no other kind repeats it.
    const html = renderToStaticMarkup(
      <RollbackNotice
        body={WORKFLOW_KINDS.premises.rollbackBody}
        action={<button type="button">Roll back this run</button>}
      />,
    );
    expect(html).toContain("Rolling back deactivates every premise this run created.");
    expect(html).toContain("active account");
    expect(html).toContain("Roll back this run");
  });

  // ── DEF-623 ────────────────────────────────────────────────────────────
  // *"in a kit parameterised by target, an UNparameterised string is a claim
  // about one target that every other target will repeat."*
  const KIND_IDS = Object.keys(WORKFLOW_KINDS) as WorkflowKindId[];

  it.each(KIND_IDS)(
    "DEF-623 · %s renders ITS OWN rollback sentence, never another target's",
    (id) => {
      const html = renderToStaticMarkup(
        <RollbackNotice
          body={WORKFLOW_KINDS[id].rollbackBody}
          action={<button type="button">Roll back this run</button>}
        />,
      );
      expect(html).toContain(WORKFLOW_KINDS[id].rollbackBody.en);
      // …and no OTHER kind's sentence rode in with it. This is the assertion
      // the pre-fix component fails on five of the six kinds.
      for (const other of KIND_IDS) {
        if (other === id) continue;
        expect(
          html,
          `${id} is printing ${other}'s rollback sentence`,
        ).not.toContain(WORKFLOW_KINDS[other].rollbackBody.en);
      }
    },
  );

  it("DEF-623 · every kind declares a DISTINCT rollback key and a non-empty sentence", () => {
    // The structural half. `rollbackBody` is a REQUIRED field, so tsc already
    // refuses a seventh kind with no sentence; this refuses a seventh kind that
    // borrows the sixth's — which is the defect one copy-paste away.
    const keys = KIND_IDS.map((id) => WORKFLOW_KINDS[id].rollbackBody.key);
    const sentences = KIND_IDS.map((id) => WORKFLOW_KINDS[id].rollbackBody.en);
    expect(new Set(keys).size).toBe(KIND_IDS.length);
    expect(new Set(sentences).size).toBe(KIND_IDS.length);
    for (const sentence of sentences) expect(sentence.length).toBeGreaterThan(40);
  });

  it("DEF-623 · the accounts sentence states BR-CUS-047's billed refusal, which is the one an operator hits", () => {
    // The row's own words: *"BR-CUS-047's rollback refuses when any account in
    // the run has been billed, which is the sentence an operator needed and did
    // not get."* Asserted on the accounts kind specifically because it is the
    // target the defect was found on.
    const html = renderToStaticMarkup(
      <RollbackNotice
        body={WORKFLOW_KINDS.accounts.rollbackBody}
        action={<button type="button">Roll back this run</button>}
      />,
    );
    expect(html).toContain("already been billed");
    expect(html).toContain("an issued bill cannot be unmade");
    // And OQ-352's whole-run refusal, which is invisible on this screen until
    // it fires (`_refuse_accounts_rollback_with_opening_books`).
    expect(html).toContain("opening balances cannot be rolled back at all");
    // The premises claim is GONE from an accounts receipt. This is the defect.
    expect(html).not.toContain("premise");
    expect(html).not.toContain("unit");
  });
});

// ── DEF-PAY-10758 (L3-03) — payments can never roll back, so neither the tick
// nor the receipt's "Rollback point: Not recorded" line is drawn for them.
describe("DEF-PAY-10758 · no rollback promise on a target that cannot roll back", () => {
  const panel = (offer: boolean | undefined) =>
    renderToStaticMarkup(
      <DryRunPanel
        figures={DRY_RUN}
        modes={MODES}
        selectedModeId="insert"
        onChangeModeRequested={noop}
        approval={APPROVAL}
        options={{ create_rollback_point: true, notify_on_finish: true }}
        onOptionsChange={noop}
        idPrefix="wf"
        {...(offer === undefined ? {} : { offerRollbackPoint: offer })}
      />,
    );

  it("the tick is drawn by default and not when the target refuses rollback", () => {
    expect(panel(undefined)).toContain("wf-rollback-point");
    expect(panel(false)).not.toContain("wf-rollback-point");
    expect(panel(false)).toContain("wf-notify");
  });

  it("the payments kind is one the runner offers no rollback for", () => {
    expect(rollbackControlIsOffered(WORKFLOW_KINDS.payments)).toBe(false);
  });

  it("the receipt's rollback line goes with it", () => {
    expect(renderToStaticMarkup(<Receipt receipt={RECEIPT} />)).toContain("receipt-rollback");
    expect(renderToStaticMarkup(<Receipt receipt={RECEIPT} showRollback={false} />)).not.toContain(
      "receipt-rollback",
    );
  });
});
