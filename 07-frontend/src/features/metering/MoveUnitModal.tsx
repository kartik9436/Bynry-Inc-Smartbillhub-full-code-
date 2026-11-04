// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-002 (S15 units) · Change: CR-024 (PO 2026-08-21) ·
//           CR-089 wave J (`PUJ-46`, `PUJ-47`, `PUJ-55`)
//           Screens: S15 / PRM-01U row action · PRM-03 header action
// Rules:    BR-MET-095 (a unit MAY move, and the move is a DATED EVENT —
//           SUPERSEDES-REFINES BR-MET-046) · BR-MET-042 (an override on a
//           protected change is allowed WITH a warning and an audit row) ·
//           BR-MET-1161 (an address is stored on `premises` and NOWHERE else —
//           every other entity walks to it) · BR-MET-1162 (a unit may carry its
//           own point) · BR-MET-082 clause 2 (grouping a premises groups every
//           unit in it, which is why the route follows the move) ·
//           BR-SHL-025 (server-authoritative RBAC) · BR-SHL-032 (a confirm
//           NAMES the action it is about to take) · BR-SHL-033 (a long picker
//           is type-ahead searchable) · B14 rule 6 (danger tier) · B14 rule 11
//           (a consequence preview before a commit) · B14 rule 21 (Tailwind, no
//           new class — and this file is NOT on `route-b-migrated.txt`, so it
//           writes no utility of its own and composes the kit instead) ·
//           B14 rule 36 (the shared component kit is how you comply)
// Defects:  DEF-MET-4694 (a date format asked for in words; a machine's plural
//           in a consequence) · DEF-511 (nothing counts bills for one unit)
// ───────────────────────────────────────────────────────
// CR-024 — MOVE A UNIT TO ANOTHER PREMISE.
//
// PO verbatim: *"please ensure move units works in Units; we have that
// functionalities - you can have a modal for that; bascially user has put a
// unit in wrong premises they want to move it to correct premises."*
//
// ⚠ **THE RULE USED TO FORBID THIS, AND THE RULE CHANGED — READ BR-MET-095
// BEFORE ASSUMING EITHER STATE.** BR-MET-046 refused the move to protect
// *"by-premises money traceability"*. That property turned out to be held by
// the LEDGER STAMP and not by the refusal: `journal_lines.premises_id` is
// written at POSTING time and the by-premises report groups on the stamp with
// no read-time join (US-LED-010 TC-5 is a structural test asserting exactly
// that). So money already posted keeps the premise it was posted under, and
// this modal says so on its face rather than leaving the user to wonder.
//
// ── WHAT CR-089 WAVE J CHANGED, AND WHY EACH ─────────────────────────────────
//
// **1 · THE CONSEQUENCE IS A LIST, NOT TWO SENTENCES (`PUJ-46`).** The screen
// asked its four questions well and then described what a move DOES in one
// note about the ledger. Two of the real consequences were readable nowhere in
// the product:
//   · **every asset tagged to the unit changes address.** An address is stored
//     on `premises` and NOWHERE else (hard rule 8 / BR-MET-1161), and an asset
//     derives its own by walking unit → premises — `assets.selectors` serves it
//     as `assigned_address`. So the meters, sub-meters, carts and fire lines on
//     this unit are all re-addressed at the moment of the press, and the old
//     screen mentioned none of it.
//   · **the route and the cycle change** — who reads the meter and when it
//     bills. A unit takes its route from its building (BR-MET-082 clause 2),
//     which `derivation._resolve_one` states in its own comment as the thing
//     that *"carries a unit that has just been MOVED to a routed premises onto
//     that premises' route with no cascade on the move path"*.
// Seven consequences, each ONE sentence (B14 rule 32's budget), each built from
// a figure the SERVER read — `GET /units/{id}/move-preview`. **Not one of them
// is computed here**, because a screen that worked out its own asset count
// would be a second answer to a question the assets module already owns.
//
// **2 · THE DANGER TIER (`PUJ-46`).** This file used to carry a note saying
// rule 6's danger tier was NOT used and was not an oversight, on the argument
// that a move *"destroys nothing — it is a correction"*. CR-089 overrides that,
// and the reason is worth keeping rather than just the ruling: a move
// re-attributes where the unit's NEXT bill lands, and **it cannot be undone by
// moving it back** — the second move is its own dated event with its own
// reason, so afterwards the record says the unit moved twice and neither date
// is wrong. That is not a correction, and it now commits through
// `FormModal`'s `submitVariant` (added for this, the same optional shape
// `ConfirmDialog.confirmVariant` took for DEF-718; absent still means primary,
// so no other form moved).
//
// **3 · A HUMAN PLURAL AND A REFUSAL THAT IS NOT A FORMAT SPEC
// (`PUJ-47` / DEF-MET-4694).** *"This unit has carried 2 account(s)"* put a
// machine's plural on the one sentence asking a person to accept an
// irreversible consequence; it is `_one`/`_other` in all eleven catalogues now.
// *"Enter the date as YYYY-MM-DD"* is what a screen says when it has no picker
// — and `DatePickerField` has always been a native date input, so the refusal
// was describing a control the screen does not use. It points at the calendar.
//
// ⚠ **THE WORKED EXAMPLES IN `PUJ-47` READ *"8 Sep 2026"* AND *"two
// accounts"*, AND THIS SCREEN PRINTS NEITHER LITERALLY — the same departure
// wave A recorded on `A3`, for the same reason.** The date is the TENANT's
// format through the one shared formatter (`DatePickerField`'s regional echo);
// a fifth date formatter here would be `DEF-MET-4689`, which is wave H's. And
// the count is the digit: spelling numerals out is a rule about English, and
// B14 rule 35 says a catalogue is written in its own language rather than
// translated from one — eleven number-word tables would be that rule broken
// eleven times to satisfy an example. The DEFECT was the `(s)`, and the `(s)`
// is gone.
//
// **4 · THE BILL COUNT IS SERVED THE DAY BILLING CAN COUNT IT (`PUJ-55`).**
// `DEF-511` is still open — nothing counts issued invoices by unit — but the
// hold is now WIRED rather than described: `seams.issued_bill_count_for_unit`
// declares the one contract billing owes and resolves it at call time, so the
// number appears with no change to this file. Until then the count is `null`,
// which is *nobody could count them* and never `0`; the screen states the
// absence in the words it always did.
//
// ⚠ **A FUTURE DATE IS REFUSED BY THE SERVER, AND ONLY BY THE SERVER.**
// `units` holds one `premises_id` and no dated move history, so a future
// effective date would be applied at once and then read as scheduled —
// `services.move_unit` refuses it with `metering.unit.move_date_future`. The
// shared `DatePickerField` takes no `max`, so this screen does NOT stop a user
// picking one first; the field's `help` line says so in words. Stated rather
// than implied, because a comment claiming a guard is not the guard
// (hard-won law 1).
//
// ⚠ **THIS FILE IS NOT ON `src/styles/route-b-migrated.txt`.** B14 rule 21's
// per-file clause: a Tailwind utility written here is emitted by nothing and
// renders as NOTHING, while `tsc` and every `toContain` assertion pass on it.
// So the consequence list is the KIT's `ConsequenceBox` — whose own file IS
// migrated, so its classes exist — and this file adds no class at all.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPremises, getUnitMovePreview, moveUnit } from "@/api/endpoints";
import type { MovePreview, MovePreviewRouteSide, PremisesRow, UnitRow } from "@/api/endpoints";
import { PlainTable } from "@/components/Surfaces";
import {
  CheckboxField,
  DatePickerField,
  FormModal,
  SearchSelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Note } from "@/components/TextBits";
import type { Translator } from "@/features/tenancy/settingsShared";

import { toEnvelope } from "./PremisesListPage";
import { unitFormTitle } from "./UnitEditModal";
import { premisesPickerOptions } from "./UnitsListPage";
import { useRegional } from "./meteringShared";
import type { RegionalProps } from "./meteringShared";

/** The server's own refusal code when the unit has had accounts (BR-MET-095). */
export const MOVE_NEEDS_OVERRIDE = "metering.unit.move_needs_override";

/**
 * The destination options, minus the premise the unit is already on.
 *
 * Offering the current premise would produce a "move" the server refuses as a
 * no-op — a control that can only fail is worse than no control, so the option
 * is not there to pick (`services.move_unit` refuses it as well; this is the
 * convenience half, never the guarantee).
 */
export function moveDestinationOptions(
  rows: readonly PremisesRow[] | undefined,
  currentPremisesId: string,
): { value: string; label: string }[] {
  return premisesPickerOptions(rows).filter((option) => option.value !== currentPremisesId);
}

/** *"Route RT-012 · Cycle CY-003"*, or just the route where it has no cycle. */
function routeSideText(side: MovePreviewRouteSide, t: Translator): string {
  return side.cycle_code === null
    ? t("metering.units.move.effect.routeSideNoCycle", { route: side.route_code })
    : t("metering.units.move.effect.routeSide", {
        route: side.route_code,
        cycle: side.cycle_code,
      });
}

/**
 * The route half of the consequence, as ONE sentence per service joined.
 *
 * ⚠ **EVERY SERVICE IS NAMED, INCLUDING THE ONES THAT DO NOT MOVE.** A unit on
 * water and electric where only the water route changes is a different fact
 * from one where both do, and a list that printed only the changes would leave
 * a clerk to assume the rest. The five shapes are five different sentences
 * rather than one with blanks, because *"is on no route at either property"*
 * and *"stays on RT-020"* are not the same news.
 */
export function moveRouteSentence(preview: MovePreview, t: Translator): string {
  if (preview.routes.length === 0) {
    return t("metering.units.move.effect.routesNone");
  }
  return preview.routes
    .map((row) => {
      // ⚠ `rating.service.*` AND NOT `metering.service.*` — `DEF-763` ruled the
      // ONE service-name catalogue, and `ReadDetailPage`, `UnitDetailPage`,
      // `ServicesAvailableField` and `UploadReadsWizard` all read it. The bare
      // code is the default so a tenant-added service is VISIBLE rather than
      // blank, exactly as `serviceBadge` treats one it does not know.
      const service = t(`rating.service.${row.service_code}`, {
        defaultValue: row.service_code,
      });
      if (row.from !== null && row.to !== null) {
        return row.changes
          ? t("metering.units.move.effect.route", {
              service,
              from: routeSideText(row.from, t),
              to: routeSideText(row.to, t),
            })
          : t("metering.units.move.effect.routeSame", {
              service,
              route: routeSideText(row.from, t),
            });
      }
      if (row.from !== null) {
        return t("metering.units.move.effect.routeLost", {
          service,
          from: routeSideText(row.from, t),
        });
      }
      if (row.to !== null) {
        return t("metering.units.move.effect.routeGained", {
          service,
          to: routeSideText(row.to, t),
        });
      }
      return t("metering.units.move.effect.routeNone", { service });
    })
    .join(" ");
}

/** One row of the drawn consequence table: a bold label, one sentence. */
export interface MoveConsequence {
  /** The `data-` hook a test and a walkthrough find this row by. */
  id: string;
  label: string;
  text: string;
}

/**
 * `PUJ-46`'s SEVEN consequences, in the order the `U11` frame draws them.
 *
 * ⚠ **THEY ARE LABELLED PAIRS AND NOT BULLETS, AND THAT IS `DEF-MET-4763`.**
 * The frame draws a two-column table — `WHAT THIS WILL DO`, a bold label on the
 * left and one sentence on the right — and this shipped as an unlabelled bullet
 * list, because `ConsequenceBox`'s `heading`/`bullets` props are its
 * CUSTOMER-PORTAL look. Seven sentences with nothing naming what each is about
 * is a paragraph in disguise; the labels are what make it scannable, which is
 * the whole reason the frame itemises the move at all.
 *
 * ⚠ **AND THE ROW SET MOVED, WHICH IS THE PART WORTH READING SLOWLY.** Three
 * rows this screen used to draw are NOT on the frame — the new address, the map
 * pin, and *moving it back is a second move rather than an undo* — and three
 * the frame draws were not here: what happens to bills already ISSUED, what
 * happens to the NEXT one, and what is written down. The first pair used to
 * live in a note ABOVE the fields (`postedMoneyNote`) where the frame puts them
 * in the table, so nothing is lost there; the three dropped rows ARE a loss and
 * are recorded as divergences in the conformance file rather than quietly kept.
 *
 * Pure on purpose — the seven sentences are the deliverable, so they are
 * provable without a browser and without a server. Every figure in them comes
 * out of `preview` or out of the form; this function invents none.
 */
export function moveConsequences(
  preview: MovePreview,
  effectiveDate: string,
  fromPremise: string,
  t: Translator,
): MoveConsequence[] {
  return [
    {
      id: "issuedBills",
      label: t("metering.units.move.effect.label.issuedBills"),
      text: t("metering.units.move.effect.issuedBills", { premise: fromPremise }),
    },
    {
      id: "nextBill",
      label: t("metering.units.move.effect.label.nextBill"),
      // ⚠ **NO DATE IS A DIFFERENT SENTENCE, NOT A BLANK.** The table is drawn
      // as soon as a destination is picked, which is usually before the date is
      // typed; *"from ."* is the shape of a bug and reads as one.
      text:
        effectiveDate.trim() === ""
          ? t("metering.units.move.effect.nextBillNoDate")
          : t("metering.units.move.effect.nextBill", { date: effectiveDate }),
    },
    {
      id: "accounts",
      label: t("metering.units.move.effect.label.accounts"),
      text:
        preview.accounts.ever === 0
          ? t("metering.units.move.effect.accountsNone")
          : t("metering.units.move.effect.accounts", { count: preview.accounts.ever }),
    },
    {
      id: "bills",
      label: t("metering.units.move.effect.label.bills"),
      // ⛔ `null` IS NOT `0`. `DEF-511`: nothing counts issued invoices by unit,
      // so the server says *nobody could count them* and the screen prints the
      // absence it has always printed. A zero here would read as *this unit has
      // never billed*, which is the fact that makes a move harmless.
      text:
        preview.bills.count === null
          ? t("metering.units.move.billCountUnavailable")
          : t("metering.units.move.effect.bills", { count: preview.bills.count }),
    },
    {
      id: "route",
      label: t("metering.units.move.effect.label.route"),
      text: moveRouteSentence(preview, t),
    },
    {
      id: "assets",
      label: t("metering.units.move.effect.label.assets"),
      text:
        preview.assets.count === 0
          ? t("metering.units.move.effect.assetsNone")
          : t("metering.units.move.effect.assets", { count: preview.assets.count }),
    },
    {
      // B14 rule 34's ratified word for *held here*, and the frame draws it.
      id: "recorded",
      label: t("metering.units.move.effect.label.recorded"),
      text: t("metering.units.move.effect.recorded"),
    },
  ];
}

/**
 * Client validation is UX only — the SERVER is authoritative (B8 forms), and
 * every one of these three is refused there too, by name. The screen validating
 * them as well is what keeps a user from posting an obviously empty form and
 * reading a server refusal for it.
 *
 * ⚠ **THE KEYS ARE THE SERVER'S FIELD NAMES, AND THAT IS LOAD-BEARING —
 * `DEF-MET-4721`.** `collectFormErrors` files an error under the zod PATH,
 * `envelopeErrors` files the server's under its `field` name, and
 * `useFieldError` looks both up by the input's `id`. One string has to be all
 * three. It was three different strings here — `premisesId` in the schema,
 * `move-premises` on the input, `premises_id` from the server — so **pressing
 * the commit button on an empty form did nothing at all**: three errors filed
 * under names no field could look up, no summary line (it prints above three
 * and there are exactly three), and `scrollToFirstError` focusing nothing.
 * Every sibling modal in this feature already named its inputs this way
 * (`QuickReadModal`'s `meter_no`/`read_date`, `EstimateReadModal`'s `read_at`);
 * this one did not, and no check compares an id with a schema key.
 */
export function moveUnitSchema(t: Translator) {
  return z.object({
    premises_id: z.string().trim().min(1, t("metering.unit.premises_required")),
    effective_date: z.string().trim().min(1, t("metering.unit.move_date_required")),
    reason: z.string().trim().min(1, t("metering.unit.move_reason_required")),
  });
}

export interface MoveUnitModalProps extends RegionalProps {
  client?: ApiClient;
  unit: UnitRow;
  onClose: () => void;
  /** `premise` is the destination's own label, for the toast. */
  onMoved: (premise: string) => void;
}

export function MoveUnitModal(props: MoveUnitModalProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const { dateFormat } = useRegional(props);

  const [premisesId, setPremisesId] = useState("");
  // BR-TEN-043: the date the OPERATOR states — this screen reads no clock for
  // them and pre-fills nothing, because a pre-filled "today" on a CORRECTION
  // is the wrong answer more often than the right one. The server is what
  // refuses a future one; see the header note.
  const [effectiveDate, setEffectiveDate] = useState("");
  const [reason, setReason] = useState("");
  const [acknowledge, setAcknowledge] = useState(false);
  const [accountsRefused, setAccountsRefused] = useState<number | null>(null);

  const premisesQuery = useQuery({
    queryKey: ["premises", "move-picker"],
    queryFn: () => getPremises({ per: 500 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const options = moveDestinationOptions(premisesQuery.data?.results, props.unit.premises_id);

  // `PUJ-46` — asked with no destination the moment the modal opens (so the
  // accounts warning is honest BEFORE a refusal rather than after one), and
  // asked again with the destination once one is picked.
  const previewQuery = useQuery({
    queryKey: ["unit-move-preview", props.unit.id, premisesId],
    queryFn: () => getUnitMovePreview(props.unit.id, premisesId, client),
    retry: false,
  });
  const preview = previewQuery.data;
  // ⚠ THE COUNT IS THE SERVER'S, WHICHEVER DOOR IT CAME THROUGH. The preview
  // answers it up front; the refusal answers it if the preview could not be
  // read. This screen never works it out — `UnitRow` carries the CURRENT
  // occupant only, and "has ever had an account" is a different question.
  const accountsSeen = accountsRefused ?? preview?.accounts.ever ?? null;

  const move = useMutation({
    mutationFn: () =>
      moveUnit(
        props.unit.id,
        {
          premises_id: premisesId,
          effective_date: effectiveDate,
          reason,
          ...(acknowledge ? { acknowledge_accounts: true } : {}),
        },
        client,
      ),
  });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await move.mutateAsync();
      void queryClient.invalidateQueries({ queryKey: ["units"] });
      void queryClient.invalidateQueries({ queryKey: ["premises"] });
      const chosen = options.find((option) => option.value === premisesId);
      props.onMoved(chosen?.label ?? premisesId);
      return { ok: true };
    } catch (error) {
      // The override prompt is the SERVER's, and stays the server's even though
      // the preview usually shows the count first: a preview that failed to
      // load and a server that refuses on 2 accounts must end in the same
      // panel, and the refusal is the one that decides.
      // ⚠ **THE ENVELOPE IS RETURNED AND NOT ALSO RENDERED HERE —
      // `DEF-MET-4722`.** `FormModal` renders `message_key` as its own
      // form-message for every consumer, so a modal that ALSO kept the sentence
      // in its own state printed it twice, one line apart: *"A move cannot be
      // dated in the future."*, then again. Both renderings were correct, which
      // is why nothing caught it and why `toContain` could not have.
      const envelope = toEnvelope(error);
      if (envelope.message_key === MOVE_NEEDS_OVERRIDE) {
        const count = Number(envelope.params?.accounts ?? 0);
        setAccountsRefused(Number.isFinite(count) ? count : 0);
      }
      return { ok: false, error: envelope };
    }
  }

  return (
    <FormModal
      // ⚠ **THE LABEL, NOT THE SERIES NUMBER (`DEF-MET-4763`).** The frame
      // draws `Move Unit 1 to another property` — the thing written on the
      // door. `unitLabel` puts `unit_no` first, which is right for a TOAST (it
      // is the reference a clerk quotes) and wrong for a title a person reads
      // to check they have the right flat. One helper, shared with the edit
      // form, so the two dialogs cannot start naming the same unit differently.
      title={t("metering.units.move.title", { unit: unitFormTitle(props.unit, translate) })}
      kicker={t("metering.kicker")}
      schema={moveUnitSchema(translate)}
      values={{ premises_id: premisesId, effective_date: effectiveDate, reason }}
      submitLabel={t("metering.units.move.submit")}
      // B14 rule 6, ruled by CR-089 `PUJ-46` — see the header note for why a
      // move is destructive and not a correction.
      submitVariant="danger"
      onSubmit={submit}
      onClose={props.onClose}
    >
      <TextField
        id="move-from"
        label={t("metering.units.move.from")}
        // ⚠ **ADDRESS FIRST, NUMBER SECOND (`DEF-MET-4763`).** The frame draws
        // `101 Silver Creek Rd, Ottumwa, IA · P-00041`; this joined the other
        // way round, so the field a clerk reads to check they have the right
        // building opened with a code nobody navigates by.
        value={
          [props.unit.premise_address, props.unit.premise_no].filter((part) => part).join(" · ") ||
          t("metering.premises.noNumber")
        }
        readOnly
        help={t("metering.units.move.fromHelp")}
        onChange={() => undefined}
      />

      {/* BR-SHL-033: the premises list is long, so it is type-ahead searchable.
          ⚠ **`required` AND `help` WERE BOTH ABSENT AND `SearchSelectField`
          TAKES BOTH.** The frame draws the asterisk and the sentence; the
          schema has always refused an empty destination, so the field was
          required in every sense except the one a person can see. */}
      <SearchSelectField
        id="premises_id"
        label={t("metering.units.move.to")}
        value={premisesId}
        options={options}
        required
        placeholder={t("metering.units.filter.premisePlaceholder")}
        help={t("metering.units.move.toHelp")}
        onChange={setPremisesId}
      />

      <DatePickerField
        id="effective_date"
        label={t("metering.units.move.effectiveDate")}
        value={effectiveDate}
        onChange={setEffectiveDate}
        required
        dateFormat={dateFormat}
        help={t("metering.units.move.effectiveDateHelp")}
      />

      <TextField
        id="reason"
        label={t("metering.units.move.reason")}
        required
        value={reason}
        onChange={setReason}
        help={t("metering.units.move.reasonHelp")}
      />

      {/* ── `PUJ-46` — WHAT THIS WILL DO, as the two-column table the frame
          draws ────────────────────────────────────────────────────────────
          Drawn only with a destination chosen: before that the rows would have
          to end *"stays on —"*, which is a blank where a fact should be.
          ⚠ **`PlainTable` FROM THE KIT, AND THIS FILE ADDS NO CLASS.** It is
          not on `src/styles/route-b-migrated.txt`, so a utility written here
          would be a class no stylesheet declares — it renders as NOTHING while
          `tsc` and every `toContain` assertion pass over it (B14 rule 21's
          per-file clause). `PlainTable`'s own utilities are emitted from
          `components/Surfaces.tsx`, which costs this file nothing. */}
      {preview !== undefined && preview.to !== null && (
        <section data-move-consequence="">
          <h4>{t("metering.units.move.effect.heading")}</h4>
          <PlainTable>
            <tbody>
              {moveConsequences(
                preview,
                effectiveDate,
                [props.unit.premise_address, props.unit.premise_no]
                  .filter((part) => part)
                  .join(" · "),
                translate,
              ).map((row) => (
                <tr key={row.id} data-effect={row.id}>
                  <td>
                    <b>{row.label}</b>
                  </td>
                  <td>{row.text}</td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </section>
      )}

      {/* The override panel. BR-MET-042's shape: the count is stated and the
          person says they mean it. It appears as soon as the SERVER has told us
          there are accounts — from the preview, or from a refusal.
          ⚠ **THE WARNING GOT ITS INSTRUCTION BACK (`DEF-MET-4763`).** It read
          *"…Reports that read a unit's current property will show its history
          under the new one"* — which is TRUE, is now row 3 of the table above,
          and left the sentence asking a person to agree with no sentence
          telling them how. The frame's own words are *Tick to move it anyway*. */}
      {accountsSeen !== null && accountsSeen > 0 && (
        <>
          <Note>{t("metering.units.move.accountsWarning", { count: accountsSeen })}</Note>
          <CheckboxField
            id="move-acknowledge"
            label={t("metering.units.move.acknowledge")}
            checked={acknowledge}
            onChange={setAcknowledge}
          />
          {/* The frame draws this in a dashed box beneath the tick. B14 rule 38
              — the BOX is form construction and ours to decide, the SENTENCE is
              the drawing's and it is here. */}
          <Note>{t("metering.units.move.acknowledgeHint")}</Note>
        </>
      )}
    </FormModal>
  );
}

export default MoveUnitModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-024 (PO 2026-08-21, verbatim in BR-MET-095) · CR-089 wave J
//         (`PUJ-46`, `PUJ-47`, `PUJ-55`) · BR-MET-095 · BR-MET-1161 ·
//         BR-MET-1162 · BR-MET-042's override precedent · DEF-MET-4694 ·
//         DEF-511 (the bill count that is not served)
// generated: 2026-08-21 by the CR-023 P0-P2 lane, taking CR-024 as an addition
//         · AMENDED 2026-09-09 by the CR-089 wave J lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest MoveUnitModal.test.tsx (the seven consequences, pure) +
//         UnitsPage.test.tsx (the move cases, beside the screens that open it)
//         · g31 (this file writes NO class — it is not on route-b-migrated.txt
//         and the consequence list is the kit's `ConsequenceBox`) · g37 (the ⇄
//         row action is `SwapIcon` from components/icons.tsx)
// exceptions: E3 **THE BILL COUNT IS STILL AN ABSENCE ON THE SCREEN — DEF-511**,
//         because `apps/billing/selectors.issued_bill_count_for_unit` does not
//         exist and `apps/billing/` is another lane's this session. The seam is
//         DECLARED and resolves at call time, so the number appears the day
//         that one function lands with no change to this file · E3 the
//         effective date and the reason are recorded in `audit_log` and in NO
//         column, so neither can be queried back today: `units` has one
//         `premises_id` and no dated move history, which is also why a FUTURE
//         date is refused rather than held · E2 `PUJ-47`'s worked example reads
//         *"two accounts"* and this screen prints *"2 accounts"* — the defect
//         was the `(s)`, and spelling numerals is a rule about English that
//         B14 rule 35 forbids exporting to ten other catalogues
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
