// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-135 phase 1 · `P1.18` (WriteModeField on step 1 — the payments
//           target offers ONE of the two) and `P1.19` (a Scan paper source
//           card — a fifth card on Extract)
// Screens:  4·3a Import (the runner's Extract stage), blueprint
//           `05-prototype/06 Payments Page Blueprint.pdf` p067 and p068
// Rules:    B14 rule 9 (one control vocabulary) · rule 32 (one sentence per
//           section) · rule 33 (a label ≤ 3 words, a fact ≤ 6, an instruction
//           ≤ 6 per sentence) · rule 36 · rule 43 · BR-SHL-025 (a control that
//           cannot be honoured is DISABLED WITH ITS REASON, never hidden) ·
//           BR-MET-210 / CR-042 (ONE write-mode control for every import) ·
//           CLAUDE.md hard rule 4 (financial immutability)
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ⚠ **BOTH OF THESE ARE HOLDS, AND A HOLD WITH NO TEST IS A PROMISE NOBODY IS
// KEEPING** (CLAUDE.md hard-won law 2's mirror, the failure that cost the
// customer portal six of its eight front doors on 2026-09-05). So each is
// asserted three ways: that the control EXISTS, that it is HELD, and that it
// says WHY. The day either hold expires, the case naming it goes red and names
// the thing to change — which is the whole point of writing the test in the
// same commit as the hold.
//
// ⚠ **AND THE RULES ARE ASSERTED WITHOUT MOUNTING THE WIZARD.** `kinds.ts`
// holds them as functions for exactly this reason (B14 rule 43): a rule that can
// only be checked by rendering a 4,000-line page is a rule nobody checks.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ScanInput, ScannedRows } from "./ScanInput";
import {
  DEFAULT_WRITE_MODE,
  SourceCards,
  WORKFLOW_KINDS,
  WORKFLOW_SOURCES,
  WriteModeField,
  workflowSourcesFor,
  writeModeIsRefused,
  writeModeOptions,
  writeModeRefusals,
  type WorkflowKindId,
} from "./index";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

const EVERY_KIND = Object.keys(WORKFLOW_KINDS) as WorkflowKindId[];

// ══════════════════════════════════════════════════════════════════════════
// P1.19 — THE SCAN PAPER CARD
// ══════════════════════════════════════════════════════════════════════════

describe("P1.19 · Scan paper is the fifth card on the payments Extract", () => {
  it("payments draws five cards and every other target still draws four", () => {
    expect(workflowSourcesFor("payments")).toHaveLength(WORKFLOW_SOURCES.length + 1);
    for (const kind of EVERY_KIND.filter((id) => id !== "payments")) {
      expect(workflowSourcesFor(kind), `${kind} grew a card it has no paper for`).toEqual(
        WORKFLOW_SOURCES,
      );
    }
  });

  it("the fifth card is LAST, so the four every clerk knows do not move", () => {
    const cards = workflowSourcesFor("payments");
    expect(cards.slice(0, WORKFLOW_SOURCES.length)).toEqual(WORKFLOW_SOURCES);
    expect(cards[cards.length - 1]?.id).toBe("scan");
  });

  it("✅ THE HOLD EXPIRED: it is drawn, LIVE, and names no reason it is not", () => {
    // ⚠ **THIS CASE WAS THE HOLD AND IT DID ITS JOB.** It read *"it is drawn,
    // refused, and says why"* and asserted `available === false`. It went red
    // on 2026-09-23, when `documents.py` started drawing the bars
    // (`DEF-BIL-6325`) after the PO said *"please enable it and also start
    // putting bar code on bills - we are still in beta and uat"*.
    //
    // ⚠ **INVERTED, NOT DELETED.** Its own comment said *rewrite this case*,
    // and the property worth keeping is the one it was really guarding: a Scan
    // paper card is honest only while our own paper can be scanned. The
    // backend half of that pairing is
    // `test_cr139_p5_12_to_p5_15.py::test_cr139_p5_15_the_scan_card_is_live_now_that_our_own_bills_carry_bars`,
    // which reads this constant and `documents.py` TOGETHER so neither can
    // move without the other.
    const scan = workflowSourcesFor("payments").find((card) => card.id === "scan");
    expect(scan, "the Scan paper card is gone").toBeDefined();
    expect(
      scan?.available,
      "the Scan paper card is refused again. Our bills carry scannable bars since " +
        "DEF-BIL-6325, so a clerk is being told to type what a scanner could read — " +
        "unless the bars came off the bill, in which case fix that instead.",
    ).toBe(true);
    expect(
      scan && scan.available === true ? "unavailable_reason_key" in scan : true,
      "a LIVE card still carries a reason it is unavailable. BR-SHL-025 puts a reason " +
        "on a control that cannot be honoured; on one that can, it is a sentence a " +
        "clerk reads and disbelieves.",
    ).toBe(false);
  });

  it("⛔ DEF-PAY-6215 / DEF-PAY-6274: the retired sentence is GONE, everywhere", () => {
    // ⚠ **TWO DEFECTS ABOUT ONE SENTENCE, AND BOTH END HERE.** `DEF-PAY-6215`:
    // the card's own key held the GENERIC refusal, byte-identical to
    // `workflow.source.notYet`, so a clerk with a sack of cheques read what
    // SFTP and API say. `DEF-PAY-6274`: the corrected sentence then named the
    // wrong absence for a day. On 2026-09-23 the absence itself went away
    // (`DEF-BIL-6325`) and the key was RETIRED from all eleven catalogues.
    //
    // ⚠ **RETIRED, NOT LEFT UNREFERENCED — which is what this case now
    // guards.** A refusal sentence still sitting in a catalogue is a sentence
    // a later lane finds, believes, and puts back on a screen; that is exactly
    // the shape of `DEF-PAY-6274` one day earlier. i18next answers a missing
    // key with the key itself, so an un-retired one is invisible to G15's
    // parity check — every catalogue would hold it equally.
    for (const language of ["en", "fr-FR", "ja-JP", "de", "hi", "es", "es-MX", "it-IT", "ko-KR", "pt-BR", "id-ID"]) {
      const resolved = i18n.getFixedT(language)("workflow.source.scan.notYet");
      expect(
        resolved,
        `${language}: the retired hold sentence is back in the catalogue. The Scan card ` +
          "is live; a sentence saying our bills print no bars is now false on screen.",
      ).toBe("workflow.source.scan.notYet");
    }
  });

  it("and it renders as a SELECTABLE radio, with no refusal sentence on it", () => {
    // BR-SHL-025 governs a control that CANNOT be honoured. This one can.
    const html = renderToStaticMarkup(
      <SourceCards
        legend={t("workflow.source.legend")}
        choices={workflowSourcesFor("payments")}
        selectedId="file"
        groupName="test-source"
        onSelect={() => undefined}
      />,
    );
    expect(html).toContain('data-workflow-source="scan"');
    expect(html).toContain(escaped(t("workflow.source.scan.title")));
    // ⚠ WAS `data-available="false"` plus the held sentence, until DEF-BIL-6325.
    // The card is now a SELECTABLE radio, and the sentence is gone from the page
    // because the fact it stated is gone from the product.
    expect(html).toContain('data-available="true"');
    expect(html).not.toContain("workflow.source.scan.notYet");
  });

  it("✅ P5.8's input is what the live card now opens onto", () => {
    // ⚠ **THIS WAS THE OTHER HALF OF THE HOLD.** `CR-139-BRC07` `P5.8` built
    // the focused input, its one door onto the grammar (`POST
    // /billing/remittance/parse`) and the Extract stage's wiring, and
    // deliberately left the CARD held because a wedge scanner reads BARS and
    // our bill printed only a line of text. `DEF-BIL-6325` drew the bars and
    // the card was released, so this component is no longer waiting — it is
    // what a clerk reaches. The case stays because it is the only one that
    // renders the field itself.
    const html = renderToStaticMarkup(
      <ScanInput rows={[]} onRowsChange={() => undefined} client={{} as never} />,
    );
    expect(html).toContain('data-workflow="scan-field"');
    expect(html).toContain(escaped(t("workflow.scan.placeholder")));
    // Empty is a STATE and not a blank box — what is missing, in one sentence.
    expect(html).toContain(escaped(t("workflow.scan.none")));
  });

  it("what has been scanned is listed by its HUMAN numbers, never an id", () => {
    // B14 rule 31: every value on this list is something the clerk can read off
    // the paper in their hand — the account number, the bill number and the
    // amount the barcode carried.
    const html = renderToStaticMarkup(
      <ScannedRows
        rows={[
          {
            account_no: "ACC-1042",
            invoice_no: "BL-2608-0117",
            amount: "142.18",
            amount_minor: 14218,
            check: "%",
          },
        ]}
        t={(key, params) => (params === undefined ? i18n.t(key) : i18n.t(key, params))}
      />,
    );
    expect(html).toContain("ACC-1042");
    expect(html).toContain("BL-2608-0117");
    expect(html).toContain("142.18");
    expect(html).toContain(escaped(i18n.t("workflow.scan.counted", { count: 1 })));
  });

  it("the scan input's own copy obeys rule 33", () => {
    const words = (key: string) => i18n.t(key).split(/\s+/).filter(Boolean).length;
    // A LABEL is at most three words and carries no sentence.
    expect(words("workflow.scan.label")).toBeLessThanOrEqual(3);
    // An INSTRUCTION: six words PER SENTENCE, and two sentences of six beat one
    // sentence of twelve.
    for (const key of ["workflow.scan.help", "workflow.scan.empty", "workflow.scan.none"]) {
      for (const sentence of i18n.t(key).split(/(?<=\.)\s+/)) {
        expect(
          sentence.split(/\s+/).filter(Boolean).length,
          `"${sentence}" is over rule 33's six words per sentence`,
        ).toBeLessThanOrEqual(6);
      }
    }
  });

  it("its copy obeys rule 33 — a 3-word label and a 6-word fact", () => {
    const words = (key: string) => i18n.t(key).split(/\s+/).filter(Boolean).length;
    expect(words("workflow.source.scan.title")).toBeLessThanOrEqual(3);
    expect(words("workflow.source.scan.sub")).toBeLessThanOrEqual(6);
    // ⚠ THE THIRD KEY WENT WITH THE HOLD. `workflow.source.scan.notYet` is
    // retired (DEF-BIL-6325), so there is no instruction left on this card —
    // a live control explains nothing, which is B14 rule 33's own posture:
    // rationale is ZERO WORDS ON SCREEN.
  });
});

// ══════════════════════════════════════════════════════════════════════════
// P1.18 — ONE WRITE MODE FOR PAYMENTS, AND THE OTHER IS DRAWN AND REFUSED
// ══════════════════════════════════════════════════════════════════════════

describe("P1.18 · payments offers one of the two write modes", () => {
  it("upsert is refused for payments and for no other target", () => {
    expect(writeModeIsRefused("payments", "upsert")).toBe(true);
    expect(writeModeIsRefused("payments", "insert")).toBe(false);
    for (const kind of EVERY_KIND.filter((id) => id !== "payments")) {
      expect(writeModeIsRefused(kind, "insert"), `${kind} refuses insert`).toBe(false);
      expect(writeModeIsRefused(kind, "upsert"), `${kind} refuses upsert`).toBe(false);
    }
  });

  it("⚠ BOTH MODES ARE STILL IN THE LIST — the refused one is not dropped", () => {
    // This is the case that stops the OBVIOUS implementation. `P1.18`'s task
    // row says "payments passes ONE option", which reads as a one-element
    // array — and a one-element array makes Insert & update VANISH. The
    // blueprint's own words: "it is drawn present and refused, with its reason,
    // rather than silently absent: a clerk who has used the premises importer
    // will look for it."
    const options = writeModeOptions(t, {}, writeModeRefusals("payments", t));
    expect(options.map((option) => option.id)).toEqual(["insert", "upsert"]);
    expect(options.find((option) => option.id === "upsert")?.refused).toBe(
      t("workflow.writeMode.paymentsInsertOnly"),
    );
    expect(options.find((option) => option.id === "insert")?.refused).toBeNull();
  });

  it("the refused mode renders DISABLED with its sentence as text", () => {
    const html = renderToStaticMarkup(
      <WriteModeField
        value="insert"
        onChange={() => undefined}
        options={writeModeOptions(t, {}, writeModeRefusals("payments", t))}
        idPrefix="test"
        t={t}
      />,
    );
    expect(html).toContain('data-write-mode="upsert"');
    expect(html).toContain('data-refused="true"');
    expect(html).toContain(escaped(t("workflow.writeMode.paymentsInsertOnly")));
    // The reason is TEXT, never a `title` tooltip — unreachable by keyboard,
    // invisible on touch, unread by a clerk on the phone.
    expect(html).toContain('data-workflow="write-mode-refused"');
  });

  it("every OTHER target still renders both modes live — nothing already shipped moves", () => {
    const html = renderToStaticMarkup(
      <WriteModeField
        value="insert"
        onChange={() => undefined}
        options={writeModeOptions(t, {}, writeModeRefusals("premises", t))}
        idPrefix="test"
        t={t}
      />,
    );
    expect(html).not.toContain('data-refused="true"');
    expect(html).not.toContain('data-workflow="write-mode-refused"');
  });

  it("the mode a target starts on is never one it refuses", () => {
    // A default is a choice nobody makes deliberately: a screen left on a
    // refused mode posts a value the server rejects, and the clerk never
    // touched a control.
    //
    // ⚠ THIS ASKS THE SAME FUNCTION THE PAGE ASKS, and that is the point. An
    // earlier draft added a `firstAllowedWriteMode` helper for this case alone
    // and nothing in `src/` outside this file ever called it — which is
    // `DEF-PAY-6209`'s own shape, filed by this lane an hour earlier. It was
    // removed rather than left exported, because two answers to "which mode may
    // this target start on" is one more than the product can keep true.
    for (const kind of EVERY_KIND) {
      const started = writeModeIsRefused(kind, "insert") ? "upsert" : "insert";
      expect(writeModeIsRefused(kind, started), `${kind} starts on a mode it refuses`).toBe(false);
    }
    // Today that is `insert` everywhere, INCLUDING the shared default — stated
    // so that a target which one day refuses `insert` makes this go red rather
    // than shipping quietly.
    expect(DEFAULT_WRITE_MODE).toBe("insert");
    expect(writeModeIsRefused("payments", DEFAULT_WRITE_MODE)).toBe(false);
  });

  it("the refusal sentence is a FACT under six words and names no rule", () => {
    const sentence = i18n.t("workflow.writeMode.paymentsInsertOnly");
    expect(sentence.split(/\s+/).filter(Boolean).length).toBeLessThanOrEqual(6);
    // B14 rule 32: no rule id or internal code in clerk-facing copy. The reason
    // this mode is refused — hard rule 4 — lives in `kinds.ts` and the register.
    expect(sentence).not.toMatch(/BR-|hard rule|CR-|upsert/i);
  });
});
