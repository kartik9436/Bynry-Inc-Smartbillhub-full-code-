// ── Trace ──────────────────────────────────────────────
// Change:  **B14 rule 43** — the drawn `Attaching one` form, extracted out of
//          `ServiceRequestCapturePage.tsx` step 4. See `documentCapture.ts`.
// Rules:   B14 rule 21 (Tailwind only) · rule 33 (LABEL ≤ 3 words · FACT ≤ 6 ·
//          RATIONALE zero words on screen) · rule 38 (a FORM is built by our
//          UI rules, whatever the drawing does) · rule 39 (label → input →
//          helper, 20px between fields) · `BR-SHL-031`
// Screens: `REQ-03.4`, Accounts blueprint p078 (BOTTOM)
// ───────────────────────────────────────────────────────
import { useState } from "react";

import { Button } from "@/components/Button";
import { FileDropField } from "@/components/FileDropField";
import { CheckboxField, SelectField, TextField } from "@/components/FormModal";

import { DOCUMENT_ACCEPT, refusedFileExtension } from "./documentCapture";
import type { DocumentCaptureValue, DocumentTranslator } from "./documentCapture";

/** One option in the type picker — the host's own closed vocabulary. */
export interface DocumentTypeOption {
  value: string;
  label: string;
}

/**
 * **`Attaching one` — THE DRAWN FORM AND ITS TWO BUTTONS.**
 *
 * ⚠ **THE TWO BUTTONS ARE THE SAME ACT WITH AND WITHOUT BYTES.** p078 draws
 * `Attach a file` and `Add another document` side by side, and the table above
 * has rows of BOTH kinds — one carries a file, one shows `—` and `Nothing
 * attached`. A row of the second kind can only be made by the no-file path,
 * which is what `Add another document` is: *the applicant is expected to bring
 * this*. The host is handed a boolean and decides which of its own two routes
 * that means; this component knows neither route.
 *
 * ⚠ **`File *` CARRIES ITS ASTERISK BECAUSE IT IS REQUIRED FOR `Attach a
 * file`, AND `Add another document` IGNORES IT.** Neither button is disabled:
 * a disabled control whose reason a clerk has to infer is the shape this
 * product keeps having to remove, so a press with no file is REFUSED BY NAME,
 * under the form where the eye already is.
 *
 * ⚠ **NEITHER DRAWN HELP LINE IS BUILT, AND BOTH ARE DRAWN.** p078 puts
 * *"Eight designed types, plus Anything else…"* (14 words) under the type and
 * *"Name and size are recorded, with who attached it and when"* (11 words)
 * under the file. Both are RATIONALE — they describe what the control already
 * shows and what the table beside them already prints — and B14 rule 33 puts
 * rationale at zero words on screen. Recorded as a divergence rather than
 * shortened, because six words of the same argument is still the argument.
 */
export function DocumentCaptureForm(props: {
  value: DocumentCaptureValue;
  onChange: (next: DocumentCaptureValue) => void;
  /** `true` means *with the chosen file*; `false` means *record that it is
   *  expected*. The host owns both routes and this owns neither. */
  onSubmit: (withFile: boolean) => void;
  docTypes: readonly DocumentTypeOption[];
  t: DocumentTranslator;
  busy?: boolean;
  /** A refusal already resolved to a sentence — this component never guesses
   *  a message key for a server it cannot see. */
  error?: string | null;
  /** The browser's picker filter. `BR-SHL-031`'s allowlist by default; a host
   *  whose door takes a narrower set passes its own. */
  accept?: string;
  /**
   * Bumped by the host after every successful add, and used as the file
   * input's `key`.
   *
   * ⚠ **A FILE INPUT'S VALUE CANNOT BE DRIVEN FROM REACT STATE — the browser
   * owns it** — so after a successful attach the picker goes on naming a file
   * that has already been sent, and a clerk pressing Attach again would be
   * looking at a stale label. Remounting the element is the one way to clear
   * it without reaching past React into the DOM.
   */
  resetNonce?: number;
  /** Prefixes every control id, so two of these on one screen stay distinct. */
  idPrefix?: string;
  /**
   * ⛔ **THE SECOND BUTTON — PO 2026-09-29, `DEF-CUS-7851`**, verbatim: *"add
   * another document button is not required attach document button"*.
   *
   * ⚠ **IT IS THE BUTTON THAT GOES AND NOT THE ROUTE.** `Add another
   * document` was *the applicant is expected to bring this* — the ONLY way to
   * make a table row that reads `—` and `Nothing attached`. With this
   * `false`, one `Attach a file` does both: a file in the box attaches it, an
   * empty box records the document as expected. **Removing the capability is
   * not what was asked for.**
   *
   * ⚠ **IT DEFAULTS TO `true`, SO NOTHING EXISTING MOVES.** The ruling was
   * made looking at `REQ-03`; `TransferWizard` draws the same component and
   * was not in front of the PO, and quietly restyling a screen nobody ruled
   * on is how one screen's authority changes the product (B14 rule 38's own
   * reasoning).
   */
  expectedDocumentButton?: boolean;
  /**
   * ⛔ **`false` DROPS THE `Attaching one` HEADING — the approved `REQ-03`
   * drawing of 2026-09-29 does not draw it.** The section already has a
   * `Documents` heading and a sub-line above the table; a second heading over
   * the form beneath is the same fault B14 rule 32 calls *"too much content"*
   * and the one step 1 and step 6 each had once, in `h3` form.
   *
   * ⚠ **IT DEFAULTS TO `true`, SO NOTHING EXISTING MOVES.** `TransferWizard`
   * draws this form inside a step that has no heading of its own and was not
   * in front of the PO.
   */
  formHeading?: boolean;
}) {
  const { t, value } = props;
  const id = props.idPrefix ?? "doc-capture";
  const accept = props.accept ?? DOCUMENT_ACCEPT;
  // ══════════════════════════════════════════════════════════════════════
  // `DEF-CUS-6113` — THE TYPE IS REFUSED WHERE THE FILE IS CHOSEN
  // ══════════════════════════════════════════════════════════════════════
  // ⚠ **A `.txt` WAS ACCEPTED HERE, CARRIED THROUGH SEVEN MORE WIZARD STEPS,
  // REFUSED 415 AFTER THE BUILD WAS COMMITTED, AND LOST.** The done panel read
  // *"1 document was not filed."* — one sentence, on a screen the clerk was
  // about to leave, with no retry and no way back in. The allowlist is right
  // (`BR-SHL-031`) and the MOMENT was wrong.
  //
  // ⚠ **IT IS LOCAL STATE AND NOT THE HOST'S `error` PROP**, because the host
  // resolves refusals it has SEEN — a server's answer — and this one is
  // answered here, before anything is sent. Both draw in the same place, and
  // the local one wins while it stands: it is about the file in the box.
  const [refusedType, setRefusedType] = useState<string | null>(null);
  // **`File *` IS ONLY REQUIRED WHILE THERE ARE TWO BUTTONS.** With one, an
  // empty box is a lawful answer that means *expected, not yet brought*, so a
  // mark saying otherwise would be a refusal the button does not make.
  const twoButtons = props.expectedDocumentButton !== false;
  const set = (patch: Partial<DocumentCaptureValue>): void => {
    props.onChange({ ...value, ...patch });
  };
  return (
    <>
      {/* ⚠ **NO `mt-4` — THE SECTION OWNS THE RHYTHM NOW (item 8).**
          `DocumentCapture` wraps table + form in one `flex flex-col gap-5`, so
          a margin here would add to that gap and put this heading at a
          different distance from the table than every other pair in the
          block. One number, in one place. */}
      {props.formHeading !== false && (
        <h4 className="text-sm font-semibold text-text">
          {t("customers.serviceRequest.capture.attachingOne")}
        </h4>
      )}
      {/* Rule 39's rhythm, and the same grid `FieldGrid` emits — 24px between
          side-by-side blocks, 20px between one field and the next. It is
          written here rather than imported because `FieldGrid` lives under
          `features/customers/` and a kit component reaching into a feature is
          the coupling rule 43 is trying to remove, not a smaller one. */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 max-lg:grid-cols-1">
        <SelectField
          id={`${id}-type`}
          label={t("customers.serviceRequest.capture.documentType")}
          required
          value={value.docType}
          onChange={(next) => set({ docType: next })}
          options={[...props.docTypes]}
        />
        {/* ══════════════════════════════════════════════════════════════
            **A DROP TARGET, NOT A BARE FILE INPUT — PO 2026-09-22, item 7**:
            *"a proper drop-file control"* — drag a file in, or browse.

            ⚠ **IT IS A KIT COMPONENT AND NOT A BLOCK WRITTEN HERE — B14 rule
            43**, which was ratified on precisely this shape. `FileDropField`
            sits beside `FileField` in `components/`, so the two screens that
            take a document off a person get one drop control rather than two.

            ⚠ **NOTHING ABOUT WHAT IS REFUSED MOVED.** The same
            `refusedFileExtension` runs on the same `accept`, and it now runs
            on a DROPPED file too — a drop never goes through the picker, so
            `accept` cannot even hint at it and this check is the only thing
            standing between a `.txt` and `DEF-CUS-6113`'s seven-step journey
            to a 415.
            ══════════════════════════════════════════════════════════════ */}
        <FileDropField
          id={`${id}-file`}
          label={t("customers.serviceRequest.capture.col.file")}
          hint={t("customers.serviceRequest.capture.dropAFile")}
          browseLabel={t("customers.serviceRequest.capture.chooseAFile")}
          required={twoButtons}
          accept={accept}
          fileName={value.file?.name ?? null}
          onChange={(file) => {
            // ⚠ **THE FILE IS NOT HELD.** A refused file left on the value
            // would be one the Attach button could still send, which is the
            // defect with an extra step in it. The box is cleared and the
            // reason is drawn under it.
            const refused = refusedFileExtension(file, accept);
            setRefusedType(refused);
            set({ file: refused === null ? file : null });
          }}
          key={`${id}-file-${props.resetNonce ?? 0}`}
        />
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 max-lg:grid-cols-1">
        <TextField
          id={`${id}-proves`}
          label={t("customers.serviceRequest.documents.col.whatItProves")}
          value={value.whatItProves}
          onChange={(next) => set({ whatItProves: next })}
        />
        {/* ⚠ **THE BOX THAT WAS MISSING — PO ruling 2026-09-22, `DEF-CUS-6179`.**
            This form asked ONE free-text question and the reviewer's column
            beside it carried the same three words, so a clerk holding a driving
            licence had nowhere to put `865554556` and typed it into the words
            box, where it printed in full on a list screen.

            ⚠ **THE HELP LINE IS A FACT AND NOT A REASSURANCE.** Rule 33 caps a
            fact at six words and gives RATIONALE zero words on screen, so it
            says what the clerk will SEE — only the last four — and does not
            explain the rule behind it. */}
        <TextField
          id={`${id}-number`}
          label={t("customers.serviceRequest.documents.col.documentNumber")}
          value={value.documentNumber}
          onChange={(next) => set({ documentNumber: next })}
          help={t("customers.serviceRequest.capture.documentNumberHelp")}
        />
      </div>
      <CheckboxField
        id={`${id}-required`}
        label={t("customers.serviceRequest.capture.requiredOnThisRequest")}
        checked={value.required}
        onChange={(next) => set({ required: next })}
      />
      {refusedType !== null ? (
        /* B14 rule 33 — an INSTRUCTION is six words a sentence, and two
           sentences of six beat one of twelve. It names the extension the
           clerk chose and the four the door takes; it does not explain WHY,
           which is rationale and is zero words on screen. */
        <p className="field-error" role="alert" data-doc-type-refused={refusedType}>
          {t("customers.serviceRequest.capture.fileTypeRefused", {
            defaultValue: "{{ext}} files are not accepted. Choose PDF, PNG, JPG or CSV.",
            ext: refusedType.toUpperCase(),
          })}
        </p>
      ) : (
        (props.error ?? null) !== null && (
          <p className="field-error" role="alert" data-doc-error="">
            {props.error}
          </p>
        )
      )}
      <div className="flex flex-wrap gap-2">
        {/* ⚠ **WITH ONE BUTTON THE BOX DECIDES THE ROUTE, NOT THE CLERK.** A
            file in it means attach; an empty one means *expected, not yet
            brought*. Both rows the table can hold are still reachable, which
            is the whole of `DEF-CUS-7851`: the PO removed a control, not a
            capability. */}
        <Button
          variant="primary"
          data-doc-attach=""
          disabled={props.busy === true}
          onClick={() => props.onSubmit(twoButtons ? true : (value.file ?? null) !== null)}
        >
          {t("customers.serviceRequest.capture.attachAFile")}
        </Button>
        {twoButtons && (
          <Button
            variant="secondary"
            data-doc-add=""
            disabled={props.busy === true}
            onClick={() => props.onSubmit(false)}
          >
            {t("customers.serviceRequest.capture.addAnotherDocument")}
          </Button>
        )}
      </div>
    </>
  );
}
