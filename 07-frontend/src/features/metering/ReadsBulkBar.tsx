// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 · ADDITION 2026-08-26 — **W5 task 7, bulk operations on the
//           reads list.** PO verbatim: *"We will need bulk operation; also note
//           read are for perticualr period and they need to be part of read
//           cycle or bill cycle - how we are going to keep the sanity"*.
//           REDRAWN 2026-09-14 to the Meter Reads blueprint's **entry 13**,
//           built from pages 37–38 AS IMAGES (B14 rule 42, PO 2026-09-13).
//           Screens: S25
// Story:    US-MET-012 (S25 — its §5 fix actions get their first UI here)
// Rules:    BR-MET-129 (a warned reading POSTS; flags are worked AFTER commit) ·
//           BR-MET-023 (the per-flag fix vocabulary — and why only ACCEPT is
//           bulk) · BR-MET-016 (consumers work the lineage HEAD) ·
//           BR-SHL-025 (a control a row cannot offer renders DISABLED with its
//           reason) · B14 rule 21 (Tailwind utilities; NO stylesheet class) ·
//           B14 (one table type — the checkbox is a CELL in the S25 config,
//           exactly as `AssetRegistryPage` does it)
// Defects:  DEF-046 finding 2 — *"fix_disposition/fix_reason/fixed_by exist
//           with no writer and no route"* (open since 2026-08-11)
// Tests:    07-frontend/src/features/metering/ReadsBulkBar.test.tsx
// Impacts:  ReadsListPage.tsx renders the bar and owns the selection state
// ───────────────────────────────────────────────────────
//
// ────────────────────────────────────────────────────────────────────────────
// SPEED FROM THE BUTTON. ACCOUNTABILITY FROM EVERY ROW. THE PO SAID BOTH.
// ────────────────────────────────────────────────────────────────────────────
// PO, 2026-08-26, verbatim: *"keep the rule — speed comes from the bulk
// button… an auditor asking 'who chose to estimate M-4412?' gets a name"*.
//
// So this screen never sends an anonymous instruction. The reason box is
// REQUIRED and the server records that reason, the acting user and an
// `audit_log` row on EVERY row the click touches. The clerk saves forty clicks;
// the record loses nothing.
//
// **AND ONLY ACCEPT IS BULK.** BR-MET-023 lists more fix verbs per flag —
// override, investigate, check, field-visit, prorate, change-multiplier — and
// none of them belongs here: an override is a SUPERSEDE that needs a new value
// and its own reason for each individual read, and one reason typed once about
// forty different readings would be untrue of thirty-nine of them. Accept is
// the one verb whose meaning survives being said about a set: *"I have looked
// at these flags and they are fine."*
//
// ⚠ **THE OUTCOME IS PER ROW AND IS SHOWN AS SUCH.** The server answers with
// what it applied AND what it refused, each refusal named. A clerk who selected
// forty rows of which two were superseded gets the thirty-eight done and the
// two explained — never a bare "done" that hid them, and never a 4xx that lost
// all forty.
//
// ────────────────────────────────────────────────────────────────────────────
// THE REASON IS THE FEATURE, AND BR-MET-061 IS WHY IT CANNOT BE DROPPED
// ────────────────────────────────────────────────────────────────────────────
// BR-MET-061 (CONFIRMED, PO `OQ-066`): the TOU sum-sanity check — Σ windows
// against the total, ±1% — is severity **WARNING**, and such a reading is
// *"postable only via explicit accept + reason … never a silent pass"*.
// BR-MET-129 then moved WHEN that happens: the reading posts with its flag and
// the accept happens AFTER the commit, from this bar. **What did not move is
// the reason.** A bulk accept that took no reason, or took one and dropped it,
// would turn BR-MET-061's explicit accept into exactly the silent pass it
// forbids — for every row in the selection at once.
//
// So the reason box is REQUIRED here (`bulkReasonSchema`), the server requires
// it again (`_bulk_reason` refuses an empty one), and it is stored PER ROW in
// `fix_reason` beside `fix_disposition` and `fixed_by`, with one `audit_log`
// row each. Forty clicks saved; nothing lost from the record.
//
// ⚠ **NFR-5 — AND THE SERVER REFUSES RATHER THAN CAPPING.** `BULK_MAX_ROWS`
// is 500 and `_bulk_ids` RAISES past it with `metering.reads.bulk.too_many`,
// naming both the selection and the maximum. That is a refusal a clerk can see
// and act on, not a silent truncation of what they picked — and nothing on this
// screen caps a selection of its own accord.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { SelectionToolbar } from "@/components/SelectionToolbar";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import type { ReadRow } from "@/api/endpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/** The server's own status word for a reading with nothing to work. */
export const READ_STATUS_CLEAN = "ok";

/**
 * Can this row be bulk-accepted? — the SAME predicate the server enforces,
 * mirrored so the screen disables rather than lets a clerk select forty rows
 * that will all come back refused.
 *
 * ⚠ It is a MIRROR, not the authority. `services.bulk_fix_reads` refuses on its
 * own terms (not a head, already dispositioned, not flagged) and the response
 * is rendered; this only stops the obviously-pointless selection.
 */
export function bulkSelectable(row: ReadRow): { ok: boolean; reason: string | null } {
  if (!row.id) {
    // A DERIVED pending entry (`f.status=pending`) carries `id: null` — it is
    // not a stored read at all, so there is nothing to disposition. Estimating
    // it is the action that applies, and that is a different button.
    return { ok: false, reason: "derived" };
  }
  if (row.status === READ_STATUS_CLEAN) {
    // An accept is a statement about a FLAG. On an unflagged reading it files
    // a judgment about nothing.
    return { ok: false, reason: "notFlagged" };
  }
  return { ok: true, reason: null };
}

// ── the endpoint, typed exactly as `services.bulk_fix_reads` answers ────────
export interface BulkFixRefusal {
  read_id: string;
  meter?: string | null;
  reason: string;
  fixed_by?: string | null;
}

export interface BulkFixResult {
  disposition: string;
  reason: string;
  acted_by: string | null;
  selected: number;
  applied: { read_id: string; meter: string | null; channel: string; status: string }[];
  applied_count: number;
  refused: BulkFixRefusal[];
  refused_count: number;
  rule_ref: string;
}

export async function bulkFixReads(
  payload: { read_ids: string[]; reason: string; disposition?: string },
  client: ApiClient = api,
): Promise<BulkFixResult> {
  const response = await client.post<BulkFixResult>("/reads/bulk-fix", payload);
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export const bulkReasonSchema = (t: Translator) =>
  z.object({
    reason: z.string().trim().min(1, t("metering.reads.bulk.error.reasonRequired")),
  });

/**
 * The selection bar. Rendered ONLY when something is selected — a permanent
 * empty toolbar above every list is chrome nobody reads.
 */
export function ReadsBulkBar(props: {
  selected: string[];
  rows: ReadRow[];
  onClear: () => void;
  client?: ApiClient;
  t: Translator;
}) {
  const { t } = props;
  const [accepting, setAccepting] = useState(false);
  const [result, setResult] = useState<BulkFixResult | null>(null);

  if (props.selected.length === 0 && result === null) {
    return null;
  }

  return (
    <>
      {/* ⚠ DRAWN AT ENTRY 13, AND THREE THINGS MOVED TO MATCH IT (B14 rule 41,
          read as an IMAGE per rule 42):

            · **a plain 1px border, not an accent rail.** The rail is this
              module's device for a WARNING about one meter; a selection bar is
              not a warning about anything, and spending the accent on it is
              what B14 rule 36 calls one visual decision taken in a screen file.
            · **the count is BOLD** — it is the one fact in the row that changes
              as the clerk ticks, and everything else in the bar is constant.
            · **the *Accept only* sentence sits at the FAR RIGHT and is not
              italic.** It is not a control, so it does not belong in the run of
              controls (B14 rule 32's own clause: a row of controls holds only
              things a person can press). */}
      {props.selected.length > 0 && (
        <SelectionToolbar
          // ⚠ **`P0.10` (payments blueprint, 2026-09-22) — THE ROW IS THE KIT'S
          // NOW AND NOT ONE PIXEL OF IT MOVES.** The three decisions the note
          // above records — a plain 1px border rather than an accent rail, a
          // BOLD count, and a sentence that is not a control pushed to the far
          // right — are exactly what `components/SelectionToolbar.tsx` was
          // built from, because this bar was the best of the three the product
          // had. `role="status"` is passed rather than folded into the kit's
          // default: what a screen-reader user hears on a shipped screen is not
          // a side effect of a refactor.
          label={t("metering.reads.bulk.selected", { count: props.selected.length })}
          role="status"
          data-testid="reads-bulk-bar"
          count={t("metering.reads.bulk.selected", { count: props.selected.length })}
          note={t("metering.reads.bulk.acceptOnly")}
        >
          <Button variant="secondary" onClick={() => setAccepting(true)}>
            {t("metering.reads.bulk.accept")}
          </Button>
          <Button variant="ghost" onClick={props.onClear}>
            {t("metering.reads.bulk.clear")}
          </Button>
          {/* ⚠ BR-MET-023's other verbs are NOT here and the clerk is told why,
              rather than left hunting for Override — which is the blueprint's
              own reason for keeping this sentence.

              ⚠ **AND IT IS THE ONE THING ON THIS SCREEN THAT A SIGNED RULE AND
              THE DRAWING DISAGREE ABOUT.** B14 rule 33 caps an instruction at
              six words per sentence and puts RATIONALE — *why a control is
              absent* — at ZERO words on screen. This is eleven words and it is
              that kind. It is LEFT AS IT IS rather than shortened by lane fiat:
              it is a pre-existing string the blueprint's as-built drawing
              preserves deliberately, rule 33's own amendment binds *"every NEW
              or CHANGED string"* rather than sweeping the old ones, and B14
              rule 41 sends a drawing that contradicts a signed rule to the PO
              instead of to a judgement call. REPORTED.

              ⚠ **IT IS THE KIT'S `note` SLOT NOW (`P0.10`).** The sentence, its
              muted weight and its far-right placement are unchanged; what moved
              is that the RULE — *a row of controls holds only things a person
              can press* — is now held by one component for every list instead of
              by an `ml-auto` written out on each of them. */}
        </SelectionToolbar>
      )}

      {result !== null && (
        <BulkOutcome result={result} onDismiss={() => setResult(null)} t={t} />
      )}

      {accepting && (
        <BulkAcceptModal
          readIds={props.selected}
          client={props.client}
          t={t}
          onClose={() => setAccepting(false)}
          onDone={(outcome) => {
            setResult(outcome);
            setAccepting(false);
            props.onClear();
          }}
        />
      )}
    </>
  );
}

function BulkAcceptModal(props: {
  readIds: string[];
  client?: ApiClient;
  t: Translator;
  onClose: () => void;
  onDone: (result: BulkFixResult) => void;
}) {
  const { t } = props;
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");

  const run = useMutation({
    mutationFn: () =>
      bulkFixReads({ read_ids: props.readIds, reason, disposition: "accept" }, client),
    onSuccess: (outcome) => {
      void queryClient.invalidateQueries({ queryKey: ["reads"] });
      props.onDone(outcome);
    },
  });

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await run.mutateAsync();
      return { ok: true };
    } catch (error) {
      // B12 §3: the server's envelope renders itself, field errors included.
      return { ok: false, error: error as never };
    }
  }

  return (
    <FormModal
      title={t("metering.reads.bulk.acceptTitle", { count: props.readIds.length })}
      kicker={t("metering.reads.bulk.acceptKicker")}
      schema={bulkReasonSchema(t)}
      values={{ reason }}
      onSubmit={handleSubmit}
      onClose={props.onClose}
      submitLabel={t("metering.reads.bulk.acceptSubmit", { count: props.readIds.length })}
    >
      <TextField
        id="reason"
        label={t("metering.reads.bulk.reasonLabel")}
        value={reason}
        onChange={setReason}
        required
        multiline
        help={t("metering.reads.bulk.reasonHelp")}
      />
      {/* BR-MET-129, on screen. A clerk must not think this button is what
          lets the readings through — they are already through. This records a
          judgment about flags on readings that already posted. */}
      <p className={`m-0 text-sm ${MUTED}`}>{t("metering.reads.bulk.warningsPost")}</p>
      {/* The PO's own sentence, said to the person it is about. */}
      <p className={`m-0 text-sm ${MUTED}`}>{t("metering.reads.bulk.namedNote")}</p>
    </FormModal>
  );
}

/**
 * What actually happened, per row.
 *
 * ⚠ A REFUSED ROW IS NAMED, NEVER FOLDED INTO A COUNT. "38 of 40 accepted" is
 * a number a clerk cannot act on; "M-4412 — already worked by someone else" is
 * one they can.
 */
export function BulkOutcome(props: {
  result: BulkFixResult;
  onDismiss: () => void;
  t: Translator;
}) {
  const { result, t } = props;
  return (
    <div
      className="mb-3 border border-l-[3px] border-divider border-l-accent-500 bg-surface px-3 py-2 text-base"
      role="status"
    >
      <div className="flex flex-wrap items-center gap-3">
        <span>
          {t("metering.reads.bulk.result", {
            applied: result.applied_count,
            selected: result.selected,
          })}
        </span>
        <Button variant="ghost" onClick={props.onDismiss}>
          {t("metering.reads.bulk.dismiss")}
        </Button>
      </div>
      {result.refused_count > 0 && (
        <ul className="m-0 mt-2 list-none p-0">
          {result.refused.map((row) => (
            <li key={row.read_id} className={`text-sm ${MUTED}`} data-reason={row.reason}>
              {t(`metering.reads.bulk.refused.${row.reason}`, {
                meter: row.meter ?? row.read_id,
              })}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default ReadsBulkBar;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-038 ADDITION 2026-08-26 (W5 task 7) + BR-MET-129/023 + DEF-046 finding 2
// generated: 2026-08-26 by the CR-038 W5 tasks 6/7/8 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint✔ · vitest (ReadsBulkBar.test.tsx) · g31 (utilities only — NO new stylesheet class) · g13 (`client` is optional and the mount passes it) · g40 (mounted from ReadsListPage)
// exceptions: E3 only ACCEPT is offered in bulk — BR-MET-023's other verbs each need a per-row value or a per-row reason, and the screen SAYS so rather than leaving a clerk hunting for Override · E3 bulk ESTIMATE is served by the backend (`POST /reads/bulk-estimate`) and has NO control on this screen yet: the missing set it operates on is the DERIVED `f.status=pending` list, whose rows carry `id: null` and are a different selection model from the stored rows this bar owns. Building one selection that means two different things is how a clerk estimates the wrong meter — REPORTED and left to W1's completeness surface, which owns that list · E3 a row that cannot be accepted renders a DISABLED checkbox with its reason (BR-SHL-025) rather than no checkbox, so a clerk learns why instead of wondering where it went
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
