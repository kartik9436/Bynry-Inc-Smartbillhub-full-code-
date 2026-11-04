// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 W7 — ONE IMPORT RAIL. Tasks 1/2 (reads join the shared
//           five-stage runner), 3 (the write modes at stage 1), 4
//           (BR-MET-130's shortfall on the post step), 5 (the co-sign).
// Rules:    CR-038 R1 (PO 2026-08-26: "We need to follow tailwind wizard that
//           we are using - i believe we are using same code for various") ·
//           CR-038 R2 + CR-036 (g) (the write mode is a PREMISE, at stage 1) ·
//           BR-MET-127 (a billed reading is refused BY NAME) · BR-MET-130
//           (PO: "allow it" — post an incomplete cycle once the shortfall is
//           SHOWN) · BR-SHL-020 (a stated absence, never a silent zero) ·
//           BR-SHL-025 (a control you may not use is disabled WITH its reason)
//           · B14 rule 21 (Tailwind utilities, no new stylesheet class)
// Defect:   DEF-770 (the write mode had two controls and nothing said which
//           one won) · DEF-659 (a batch that says `posted` over nothing)
// ───────────────────────────────────────────────────────
// **WHAT NO OTHER CHECK IN THIS REPO CAN ANSWER, AND WHY THESE EXIST.**
//
// `tsc` proves the props line up. `eslint` proves the syntax is house style.
// G31 and `routeBUtilities.test.ts` prove every class token resolves. Not one
// of them can answer *does the operator SEE the sentence the rule requires* —
// which is the whole content of BR-MET-127 ("refused with the read NAMED"),
// BR-MET-130 ("what is mandatory is the SHOWING") and BR-SHL-020. Hard-won law
// 6 says the same thing about the rendered app: no gate looks at output.
//
// So these render the components and read the markup.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import {
  CosignPanel,
  CycleShortfall,
  DEFAULT_READ_WRITE_MODE,
  READ_WRITE_MODES,
  RefusedBilledRows,
  SupersededSummary,
  WriteModeField,
  WriteModeStated,
  readWriteModeChoices,
} from "./readsImportRail";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/**
 * A catalogue sentence as it appears IN THE MARKUP.
 *
 * ⚠ `renderToStaticMarkup` escapes `&`, `<`, `>`, `"` and `'`, so a raw
 * `t()` comparison fails on the two labels that matter most here — *"Insert &
 * update"* becomes `Insert &amp; update` and *"everybody's bill"* becomes
 * `everybody&#x27;s bill`. Without this the assertion would be quietly weakened
 * to a substring that avoids punctuation, which is how a copy test stops
 * checking the copy.
 */
const rendered = (key: string, params?: Record<string, unknown>): string =>
  renderToStaticMarkup(<>{t(key, params)}</>);

describe("CR-038 W7 task 3 — the write mode, at stage 1 (CR-036 (g))", () => {
  it("offers exactly the two modes the PO named, in the server's order", () => {
    // PO 2026-08-27, verbatim: *"in all imports - we need 2 option on step 1
    // insert, insert & update; replace option is not required"*. SUPERSEDES the
    // 2026-08-26 sentence this test used to quote — *"we need insert, insert
    // update, repalce option in step 1 of wirzard"* — same person, six days
    // apart. Asserted against the SERVER's tuple order so the control and
    // `write_modes.READ_WRITE_MODES` cannot drift apart.
    expect(READ_WRITE_MODES).toEqual(["insert", "upsert"]);
    const html = renderToStaticMarkup(
      <WriteModeField value="insert" onChange={() => undefined} t={t} />,
    );
    for (const choice of readWriteModeChoices(t)) {
      expect(html).toContain(renderToStaticMarkup(<>{choice.label}</>));
    }
    // ⚠ **THE HOOK IS `write-mode` AND NOT `reads-write-mode` — CR-042.** The
    // control is shared with every other import in the product now, so the
    // marker is the control's, not the rail's. A per-rail marker is what a
    // per-rail control leaves behind.
    expect(html).toContain('data-workflow="write-mode"');
  });

  it("defaults to the one mode that cannot write over a reading on file", () => {
    // hard-won law 3 — the unsafe option must be the one you type.
    expect(DEFAULT_READ_WRITE_MODE).toBe("insert");
  });

  it("shows the CONSEQUENCE of the mode chosen, and only that one", () => {
    // RED with the `chosen` lookup removed: the panel renders three labels and
    // no sentence, which is a control that never explains what it does.
    const choices = readWriteModeChoices(t);
    const html = renderToStaticMarkup(
      <WriteModeField value="upsert" onChange={() => undefined} t={t} />,
    );
    expect(html).toContain('data-workflow="write-mode-consequence"');
    expect(html).toContain(renderToStaticMarkup(<>{choices[1].consequence}</>));
    // Not the other one — a sentence about the mode the operator did NOT pick
    // is noise, and the ETL runner draws the same shape from the same file.
    expect(html).not.toContain(renderToStaticMarkup(<>{choices[0].consequence}</>));
  });

  it("`upsert` states that a BILLED reading is refused, before anything is read", () => {
    // ⚖️ BR-MET-127 is a refusal a clerk meets AFTER the commit. The mode that
    // triggers it is chosen at stage 1, so the sentence belongs there too —
    // otherwise the first a clerk hears of it is a receipt naming rows they
    // cannot now change from this screen.
    const [, upsert] = readWriteModeChoices(t);
    expect(upsert.consequence).toContain("billed");
  });

  it("⛔ CR-042 — there are TWO modes and `replace` is not one of them", () => {
    // PO 2026-08-27, verbatim: *"in all imports - we need 2 option on step 1
    // insert, insert & update; replace option is not required"*.
    //
    // ⚠ **THIS TEST REPLACES ONE THAT ASSERTED THE OPPOSITE**, and the old one
    // is worth remembering: it pinned that `replace` carried a CAUTION saying
    // the mode did exactly what `insert & update` did and that what it SHOULD
    // do was a question with the Product Owner (OQ-418). That caution was the
    // honest thing to draw at the time, and it is what produced the ruling —
    // the PO read it and removed the mode. A control that has to explain that
    // it does nothing distinctive is a control that should not exist.
    const choices = readWriteModeChoices(t);
    expect(choices.map((choice) => choice.id)).toEqual(["insert", "upsert"]);
    // The ORDER is the PO's and it is not incidental: `insert` is first because
    // it is the only mode that cannot alter a reading already on file, so the
    // clerk who never touches the control gets the safe one (hard-won law 3).
    expect(choices[0].id).toBe("insert");
    const html = renderToStaticMarkup(
      <WriteModeField value="insert" onChange={() => undefined} t={t} />,
    );
    expect(html).not.toContain("Replace");
    expect(html).not.toContain("replace");
  });

  it("⛔ DEF-770 — stage 4 STATES the mode and offers no second control", () => {
    // PO on the deployed v2.51.0: *"Write mode from this screen may not
    // required . it is already added on step 1"*. The defect's own diagnosis
    // is what this pins: the duplicate solved a problem the navigation had
    // already solved. So stage 4 gets a SENTENCE and a way back — never a
    // second radiogroup that could disagree with stage 1's.
    const html = renderToStaticMarkup(
      <WriteModeStated value="upsert" onChangeRequested={() => undefined} t={t} />,
    );
    expect(html).toContain('data-workflow="write-mode-stated"');
    expect(html).toContain(t("workflow.writeMode.change"));
    expect(html).not.toContain('role="radiogroup"');
    expect(html).not.toContain('data-workflow="reads-write-mode"');
  });
});

describe("CR-038 W7 task 4 — BR-MET-130's shortfall, where the button is", () => {
  it("names expected · received · missing and says the post is ALLOWED", () => {
    // The rule's own worked case, at the rule's own figures: CY-001 holds
    // 1,240 meters, the file carries 1,180, **60 unread** — and the PO's
    // ruling on it was one word, *"allow it"*.
    //
    // ⛔ **THE FIXTURE BELOW USED TO READ `{ expected, received, missing }`,
    // AND THOSE ARE FIELD NAMES THE SERVER HAS NEVER SENT — DEF-2440.** So
    // this test rendered a shape nothing produces, asserted three numbers that
    // only ever appear in this file, and passed for four days over a live
    // screen printing *"This cycle expects  readings."* with three blanks in
    // it. A fixture is not the server, and a test built from a TYPE is only as
    // true as the type: `ReadCycleCoverage` carried an index signature, so
    // three wrong names typechecked exactly as three right ones would.
    //
    // The figures are unchanged and still the rule's own: 1,180 in this batch
    // plus 60 already committed = 1,240 expected, 60 still unread.
    const html = renderToStaticMarkup(
      <CycleShortfall
        coverage={{
          expected_meters: 1240,
          received_in_batch: 1120,
          committed_before_batch: 60,
          missing_after_batch: 60,
        }}
        absentReason={null}
        t={t}
      />,
    );
    expect(html).toContain("1240");
    expect(html).toContain("1180");
    expect(html).toContain("60");
    expect(html).toContain(rendered("metering.upload.coverage.allowed"));
  });

  it("a COMPLETE cycle draws no 'you can post anyway' nag", () => {
    // The rule makes the SHOWING mandatory, not the warning. A cycle with
    // nothing missing has nothing to be reassured about.
    const html = renderToStaticMarkup(
      <CycleShortfall
        coverage={{
          expected_meters: 1240,
          received_in_batch: 1240,
          committed_before_batch: 0,
          missing_after_batch: 0,
        }}
        absentReason={null}
        t={t}
      />,
    );
    expect(html).not.toContain(rendered("metering.upload.coverage.allowed"));
  });

  it("no cycle → the REASON, never a zero (BR-SHL-020, hard-won law 1)", () => {
    // A `0` beside "not read" would read as *nothing is missing*, which is a
    // different claim about this utility's data entirely.
    const html = renderToStaticMarkup(
      <CycleShortfall coverage={null} absentReason="batch_not_tagged_with_cycle" t={t} />,
    );
    expect(html).toContain('data-workflow="reads-coverage-absent"');
    expect(html).toContain(rendered("metering.upload.coverage.absent"));
    expect(html).not.toContain(">0<");
  });
});

describe("CR-038 W7 — the receipt tells the truth about what it did", () => {
  it("⚖️ BR-MET-127 — a refused billed reading is NAMED on the receipt", () => {
    // The rule: *"refused with the read named and the reason"*. This is
    // DEF-659's lesson one row wide — a batch that posts 1,179 of 1,180 and
    // prints only the 1,179 lets the clerk walk away from a correction that
    // was never made.
    const html = renderToStaticMarkup(
      <RefusedBilledRows
        rows={[
          {
            row_no: 7,
            existing_read: "M-4021 · 2026-07-31 · total",
            reason: "billed_read_refused",
          },
        ]}
        total={1}
        t={t}
      />,
    );
    expect(html).toContain('data-workflow="reads-refused-billed"');
    expect(html).toContain("M-4021 · 2026-07-31 · total");
    expect(html).toContain("7");
    expect(html).toContain(rendered("metering.upload.refusedBilled.why"));
  });

  it("rows skipped for OTHER reasons are not dressed up as billed refusals", () => {
    // A clerk who REJECTED a row and a rule that refused a money correction are
    // different events; a panel that merged them would send someone to the
    // billed-correction door for a row they themselves rejected.
    const html = renderToStaticMarkup(
      <RefusedBilledRows
        rows={[{ row_no: 3, existing_read: null, reason: "not_dispositioned_for_posting" }]}
        total={0}
        t={t}
      />,
    );
    expect(html).toBe("");
  });

  it("`superseded_reads` is drawn — 41 ADDED and 41 CORRECTED are not the same event", () => {
    const html = renderToStaticMarkup(<SupersededSummary count={41} mode="upsert" t={t} />);
    expect(html).toContain('data-workflow="reads-superseded"');
    expect(html).toContain("41");
    // A run that corrected nothing says nothing — a "0 corrected" line on every
    // ordinary upload is noise that trains a reader to skip the panel.
    expect(renderToStaticMarkup(<SupersededSummary count={0} mode="insert" t={t} />)).toBe("");
  });
});

describe("CR-038 W7 task 5 — the co-sign, which could not exist until now", () => {
  it("⛔ hard-won law 2 — an unsigned batch OFFERS the control to a qualifying role", () => {
    // S28's own docstring, before this lane: *"drawing the checkbox would offer
    // a control that changes nothing"*. `cosigned_by` shipped 2026-08-10 and
    // nothing ever wrote it. Now something does.
    const html = renderToStaticMarkup(
      <CosignPanel
        cosignedBy={null}
        cosignedAt={null}
        blocksPost={false}
        mayCosign
        busy={false}
        onCosign={() => undefined}
        formatWhen={(iso) => iso}
        t={t}
      />,
    );
    expect(html).toContain(t("metering.upload.cosign.action"));
    // ⚠ the ATTRIBUTE, not the word: Tailwind's `disabled:opacity-45` variant
    // puts "disabled" in every button's class list, so a bare substring check
    // here would pass on a button that IS disabled.
    expect(html).not.toContain('disabled=""');
  });

  it("BR-SHL-025 — a role that may not co-sign gets the control DISABLED with its reason", () => {
    // OQ-042's closure names the roles (*"supervisor = SysAdmin/Executive"*).
    // A Billing Clerk meets a disabled button and a sentence, never a 403.
    const html = renderToStaticMarkup(
      <CosignPanel
        cosignedBy={null}
        cosignedAt={null}
        blocksPost={false}
        mayCosign={false}
        busy={false}
        onCosign={() => undefined}
        formatWhen={(iso) => iso}
        t={t}
      />,
    );
    expect(html).toContain('disabled=""');
    expect(html).toContain('data-workflow="reads-cosign-denied"');
    expect(html).toContain(rendered("metering.upload.cosign.denied"));
  });

  it("a signed batch shows the signature as a FACT, with no control", () => {
    const html = renderToStaticMarkup(
      <CosignPanel
        cosignedBy="u-1"
        cosignedAt="2026-08-26T10:00:00Z"
        blocksPost={false}
        mayCosign
        busy={false}
        onCosign={() => undefined}
        formatWhen={(iso) => iso}
        t={t}
      />,
    );
    expect(html).toContain('data-workflow="reads-cosign-given"');
    expect(html).toContain("2026-08-26T10:00:00Z");
    expect(html).not.toContain(t("metering.upload.cosign.action"));
  });

  it("⚠ it says it does NOT hold the post, because that is the truth (DEF-815)", () => {
    // OQ-042's closure has two halves and only the DOOR is built. The toggle
    // that makes posting BLOCK lives in the S64 settings document another lane
    // owns. A panel that implied a block that does not happen would be a worse
    // lie than the missing control was, so the copy follows the server's own
    // `cosign_blocks_post` and this pins BOTH sentences.
    const optional = renderToStaticMarkup(
      <CosignPanel
        cosignedBy={null}
        cosignedAt={null}
        blocksPost={false}
        mayCosign
        busy={false}
        onCosign={() => undefined}
        formatWhen={(iso) => iso}
        t={t}
      />,
    );
    expect(optional).toContain(rendered("metering.upload.cosign.optional"));
    expect(optional).not.toContain(rendered("metering.upload.cosign.required"));

    // ...and the day DEF-815's toggle lands, the server flips the flag and the
    // sentence flips with it. Asserted now so the wiring cannot be forgotten.
    const required = renderToStaticMarkup(
      <CosignPanel
        cosignedBy={null}
        cosignedAt={null}
        blocksPost
        mayCosign
        busy={false}
        onCosign={() => undefined}
        formatWhen={(iso) => iso}
        t={t}
      />,
    );
    expect(required).toContain(rendered("metering.upload.cosign.required"));
  });
});

describe("CR-038 W7 — every string resolves (G27 / DEF-662)", () => {
  it("no component in this file renders a dotted key name to a user", () => {
    // DEF-662's failure mode: a `t()` whose key no catalogue defines prints
    // `metering.upload.writeMode.label` to a human. Every key here was written
    // into all eleven catalogues by this lane, and this is what proves it for
    // the rendered output rather than for the file list.
    const panels = [
      renderToStaticMarkup(<WriteModeField value="upsert" onChange={() => undefined} t={t} />),
      renderToStaticMarkup(
        <WriteModeStated value="insert" onChangeRequested={() => undefined} t={t} />,
      ),
      renderToStaticMarkup(
        <CycleShortfall
          coverage={{
            expected_meters: 3,
            received_in_batch: 2,
            committed_before_batch: 0,
            missing_after_batch: 1,
          }}
          absentReason={null}
          t={t}
        />,
      ),
      renderToStaticMarkup(<SupersededSummary count={2} mode="upsert" t={t} />),
      renderToStaticMarkup(
        <CosignPanel
          cosignedBy={null}
          cosignedAt={null}
          blocksPost={false}
          mayCosign={false}
          busy={false}
          onCosign={() => undefined}
          formatWhen={(iso) => iso}
          t={t}
        />,
      ),
    ];
    for (const html of panels) {
      expect(html).not.toMatch(/metering\.upload\./);
    }
  });
});
