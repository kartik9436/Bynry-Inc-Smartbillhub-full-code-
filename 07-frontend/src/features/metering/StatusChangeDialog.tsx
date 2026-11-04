// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-001 (S14 property detail) · US-MET-002 (S15 unit detail)
//           Change: CR-089 wave D, tasks D1 (`PUJ-21`) and D2 (`PUJ-48`)
//           Screens: PRM-02 header · PRM-03 header
// Rules:    BR-MET-1164 (a property cannot be deactivated while any unit is
//           active, any asset is attached or any account is open; a unit is
//           blocked by an open account — and the refusal NAMES what is
//           blocking) · BR-MET-047 (the money term, unchanged) ·
//           BR-MET-035 (a status change is the System Admin's) ·
//           BR-SHL-025 (the server is authoritative; the UI gate is
//           convenience) · BR-SHL-032 (a confirm NAMES the action) ·
//           B14 rule 6 (danger tier on a destructive commit) · B14 rule 11
//           (a consequence preview before a commit that changes service
//           state) · B14 rule 21 (Tailwind utilities, no new stylesheet
//           class) · B14 rule 32 (one sentence per section) · B14 rule 33
//           (a refusal caps at five or six words and says what to do) ·
//           B14 rule 36 (the shared component kit is how you comply)
// Tests:    src/features/metering/StatusChangeDialog.dom.test.tsx
// ───────────────────────────────────────────────────────
// TAKING A PLACE OUT OF SERVICE — AND PUTTING IT BACK.
//
// PO 2026-09-08, verbatim: *"Allow user to cahnge Unit and Premsies status"*,
// and *"if you ahve units - active, assets or active accounts, you cannot shut
// down building pr premises."*
//
// ⚠ **UNTIL THIS FILE LANDED THERE WAS NO WAY TO DO THIS AT ALL FROM EITHER
// PAGE.** Both showed a status pill and neither offered a control, and the unit
// page went further and ADVISED the clerk to *"deactivate it and create it
// under the other premise"* — advice for a button that did not exist. That is
// hard-won law 2's mirror: a refusal pointing at a door nobody had built.
//
// ⚠ **THE COUNTS COME FROM THE SERVER WHEN THE DIALOG OPENS, AND ARE NEVER
// COMPUTED HERE.** BR-MET-1164 refuses on LIVE dependencies; a count this
// screen worked out from rows it happened to have would go stale the moment a
// colleague closed an account, and the commit would be refused for a reason the
// screen had already said was clear. The server re-reads them on the press, so
// what is drawn here is a forecast and the refusal is the guarantee.
//
// ⚠ **EVERY COUNT IS A LINK, BECAUSE A NUMBER A CLERK CANNOT ACT ON IS A
// WALL** (CR-089 §6 D1). The server names the LIST that clears each one as a
// route NAME and its parameters; this file turns that into a path. A URL built
// on the server would be a second copy of the SPA's route table.
//
// ⚠ **THE REACTIVATION HALF IS NOT A BONUS.** CR-089 §8 names it as the one
// thing this wave's rollback must keep: revert without it and everything
// already deactivated has no screen that can bring it back.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  changePremisesStatus,
  changeUnitStatus,
  getPremisesStatusChange,
  getUnitStatusChange,
} from "@/api/endpoints";
import type { StatusChangeBody, StatusChangeView, StatusDependency } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DatePickerField, ModalShell, SelectField, TextField } from "@/components/FormModal";
import { LoadingSkeleton, WorkingButton } from "@/components/StateFrame";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { premisesDetailPath, unitDetailPath, useRegional } from "./meteringShared";
import type { RegionalProps } from "./meteringShared";

/** Which of the two things this dialog is standing on. */
export type StatusSubject = "premises" | "unit";

/**
 * The order the counts are DRAWN in, which is not the order they are ENFORCED
 * in and deliberately so.
 *
 * The PO was shown *"4 active units · 9 attached assets · 3 open accounts"* and
 * that is what this list is. The server holds the commit on the FIRST count in
 * the order the work is actually done — an account is closed before its unit
 * can go — so the two orders answer different questions and neither is derived
 * from the other. `unpaid_balances` is last because it appears only when it has
 * something to say.
 */
const DEPENDENCY_ORDER: Record<StatusSubject, string[]> = {
  premises: ["active_units", "attached_assets", "open_accounts", "unpaid_balances"],
  // ⚠ **THE UNIT'S ORDER IS NOT THE PROPERTY'S, AND THE FRAME DRAWS IT
  // (`DEF-MET-4763`, found in a browser).** `U12` puts *Account … is still
  // open* on row 1 and the meters on row 2 — which is also the order the work
  // is done in, since the account is the only thing that HOLDS the commit. One
  // shared list rendered them assets-first on the unit, and no test could see
  // it: every case asserted the rows were present, none their sequence.
  unit: ["open_accounts", "attached_assets", "unpaid_balances"],
};

/**
 * The hold sentence for each blocking count, WRITTEN OUT rather than built from
 * the kind.
 *
 * ⚠ A key assembled as `` `…hold.${kind}` `` is a string no grep finds and no
 * gate resolves — G32's own blind spot, where a refusal that reaches a clerk as
 * SILENCE is indistinguishable from one that resolves. Every key below is a
 * literal, in this file and in all eleven catalogues, and it is the same set the
 * SERVER refuses with so the two cannot say different things.
 */
const HOLD_KEYS: Record<StatusSubject, Record<string, string>> = {
  premises: {
    open_accounts: "metering.premises.status.holdAccounts",
    unpaid_balances: "metering.premises.status.holdBalances",
    attached_assets: "metering.premises.status.holdAssets",
    active_units: "metering.premises.status.holdUnits",
  },
  unit: {
    open_accounts: "metering.units.status.holdAccount",
    unpaid_balances: "metering.units.status.holdBalance",
  },
};

/**
 * The dialog's OWN copy, written out per subject.
 *
 * ⚠ **NOT `` `metering.${subject}.status.…` `` — for the same reason the hold
 * keys are literals.** It also would not work: this feature's screen copy lives
 * under `metering.units.*` (plural) while the SERVER's refusals live under
 * `metering.unit.*` (singular), a convention that predates this file by a
 * month. A template literal would have quietly produced the wrong half.
 */
const COPY_KEYS: Record<StatusSubject, Record<string, string>> = {
  premises: {
    deactivateTitle: "metering.premises.status.deactivateTitle",
    reactivateTitle: "metering.premises.status.reactivateTitle",
    deactivateAction: "metering.premises.status.deactivateAction",
    reactivateAction: "metering.premises.status.reactivateAction",
    deactivateConsequence: "metering.premises.status.deactivateConsequence",
    reactivateConsequence: "metering.premises.status.reactivateConsequence",
    // `P11`'s drawn panel heading — PLURAL, because a building is held by
    // three different kinds of thing at once and a unit by one.
    refusalHeading: "metering.premises.status.refusalHeading",
    // The SERVER's own field refusals, so the screen's validation and the
    // server's say ONE sentence rather than two that nearly agree.
    dateRequired: "metering.premises.status_date_required",
    reasonRequired: "metering.premises.status_reason_required",
  },
  unit: {
    deactivateTitle: "metering.units.status.deactivateTitle",
    reactivateTitle: "metering.units.status.reactivateTitle",
    deactivateAction: "metering.units.status.deactivateAction",
    reactivateAction: "metering.units.status.reactivateAction",
    deactivateConsequence: "metering.units.status.deactivateConsequence",
    reactivateConsequence: "metering.units.status.reactivateConsequence",
    refusalHeading: "metering.units.status.refusalHeading",
    dateRequired: "metering.unit.status_date_required",
    reasonRequired: "metering.unit.status_reason_required",
  },
};

/** One count's own words — plural through i18next, never `2 account(s)`
 *  (`DEF-MET-4694` is that machine plural on the move screen).
 *
 * ⚠ **THE UNIT'S THREE ARE SENTENCES AND THE PREMISES' FOUR ARE STILL NOUN
 * PHRASES, AND THAT IS A SCOPE LINE RATHER THAN AN INCONSISTENCY LEFT LYING.**
 * The `U12` frame draws each blocked row as a sentence — *2 meters are still on
 * this unit* — beside a link of its own, and `DEF-MET-4763` is that re-cut.
 * `P11`'s four rows are drawn the same way and are `CR-089-p041`'s to re-word;
 * this lane changes the STRUCTURE both subjects render in and only the unit's
 * WORDS, so the property lane's copy is not moved under it while it is running.
 */
const COUNT_KEYS: Record<StatusSubject, Record<string, string>> = {
  premises: {
    active_units: "metering.premises.status.count.activeUnits",
    attached_assets: "metering.premises.status.count.attachedAssets",
    open_accounts: "metering.premises.status.count.openAccounts",
    unpaid_balances: "metering.premises.status.count.unpaidBalances",
  },
  unit: {
    attached_assets: "metering.units.status.blocker.assets",
    open_accounts: "metering.units.status.blocker.account",
    unpaid_balances: "metering.units.status.blocker.balance",
  },
};

/**
 * Which link word each blocked row carries, drawn per KIND.
 *
 * The `U12` frame gives the account row `Open it →` and the meters row
 * `Show them →`, and the difference is not decoration: one destination is a
 * single record and the other is a list. `P11` draws `Show them →` on all
 * three of its rows, which falls out of the same rule rather than needing a
 * second one — none of a building's blockers is a single record.
 */
const SINGLE_RECORD_ROUTES = new Set(["unit_account"]);

/**
 * The SPA path a count links to. The server names a route and its parameters;
 * the paths live here, once, beside every other path this feature knows.
 */
export function dependencyHref(
  link: StatusDependency["link"],
  tenantPath: (path: string) => string,
): string | null {
  const premisesId = link.premises_id ?? "";
  const unitId = link.unit_id ?? "";
  switch (link.route) {
    case "premises_units":
      return premisesId === "" ? null : tenantPath(`${premisesDetailPath(premisesId)}?tab=units`);
    case "premises_assets":
      return premisesId === "" ? null : tenantPath(`${premisesDetailPath(premisesId)}?tab=assets`);
    case "unit_account":
      return unitId === "" ? null : tenantPath(`${unitDetailPath(unitId)}?tab=account`);
    case "unit_assets":
      return unitId === "" ? null : tenantPath(`${unitDetailPath(unitId)}?tab=assets`);
    default:
      // An unknown route is drawn as PLAIN TEXT rather than as a dead link. A
      // link that goes nowhere is worse than a number, because it costs a click
      // to learn that (hard-won law 2's mirror).
      return null;
  }
}

/**
 * Which rows the refusal panel draws, in the PO's order.
 *
 * ⚠ **EVERY ROW WITH SOMETHING IN IT, AND NO ZERO ROWS — WHICH REVERSES THE
 * DEF-127 POSTURE THIS FUNCTION SHIPPED WITH, DELIBERATELY (`DEF-MET-4763`).**
 * It used to draw a zero for every count the rule names, so that *"no open
 * accounts"* could not be mistaken for *"nobody looked"*. The `U12` and `P11`
 * frames draw the panel as `NOT WHILE THIS IS LIVE` — **one row per blocker** —
 * and draw the panel ONLY in the blocked state, where a zero row is a line
 * saying nothing is wrong inside a panel whose heading says something is.
 *
 * The posture is not lost, it moves: in the CLEAR state the frame replaces the
 * whole panel with the consequence, which states in words what will happen to
 * the meters and the billing. That is the same reassurance in a sentence
 * instead of in a row of noughts.
 */
export function visibleDependencies(
  view: StatusChangeView,
  subject: StatusSubject = "premises",
): StatusDependency[] {
  const order = DEPENDENCY_ORDER[subject];
  const rows = view.dependencies.filter((row) => row.count > 0);
  return [...rows].sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
}

/**
 * The ONE legal destination, drawn as the frame's `New status` field.
 *
 * ⚠ **ONE OPTION, AND THAT IS THE PRODUCT'S TRUTH RATHER THAN A HALF-BUILT
 * PICKER.** A live place can only go inactive and an inactive one can only come
 * back; the server computes which in `status_change_dict.target_status` and
 * refuses the other by name (`metering.unit.status_unchanged`). Offering both
 * would be a control whose second choice can only fail, which is worse than no
 * control at all — the reasoning `moveDestinationOptions` already carries one
 * screen over.
 *
 * What the field earns its place with is the SENTENCE: *Inactive — no longer
 * takes service* is the one place on this dialog that says, in words a clerk
 * reads rather than infers from a button, what state the record ends in.
 */
export function statusOptions(
  target: "active" | "inactive",
  t: Translator,
): { value: string; label: string }[] {
  return [
    {
      value: target,
      label: t(target === "inactive" ? "metering.status.option.inactive" : "metering.status.option.active"),
    },
  ];
}

/** B14 rule 33: five or six words, and it says what to DO. */
export function holdSentence(
  subject: StatusSubject,
  view: StatusChangeView,
  t: Translator,
): string | null {
  if (!view.blocked || view.held_by === null) {
    return null;
  }
  const key = HOLD_KEYS[subject][view.held_by];
  return key === undefined ? t("metering.status.holdGeneric") : t(key);
}

export interface StatusChangeDialogProps extends RegionalProps {
  client?: ApiClient;
  subject: StatusSubject;
  /** The record this dialog is standing on. */
  id: string;
  /** What the clerk calls it — the address, or `U-01145 · Flat 2B`. */
  name: string;
  onClose: () => void;
  /** `status` is what it became, for the caller's own toast. */
  onChanged: (status: "active" | "inactive") => void;
}

export function StatusChangeDialog(props: StatusChangeDialogProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const tenantPath = useTenantPath();
  const { dateFormat } = useRegional(props);

  // BR-TEN-043 — the date the OPERATOR states. Nothing is pre-filled: a
  // pre-filled "today" on a record somebody will be asked about in a year is
  // the wrong answer more often than the right one, which is the reasoning
  // `MoveUnitModal` already carries one screen over.
  const [effectiveDate, setEffectiveDate] = useState("");
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const view = useQuery({
    queryKey: statusChangeQueryKey(props.subject, props.id),
    queryFn: () =>
      props.subject === "premises"
        ? getPremisesStatusChange(props.id, client)
        : getUnitStatusChange(props.id, client),
    // The counts are the point, so they are read fresh every time the dialog
    // opens rather than served from whatever this session read earlier.
    staleTime: 0,
    retry: false,
  });

  // The two endpoints answer with two different row shapes and this screen reads
  // neither — it invalidates and lets the page re-read. Typed as `unknown` so
  // the union is not silently widened into one of the two.
  const commit = useMutation<unknown, unknown, StatusChangeBody>({
    mutationFn: async (body: StatusChangeBody) =>
      props.subject === "premises"
        ? await changePremisesStatus(props.id, body, client)
        : await changeUnitStatus(props.id, body, client),
  });

  const data = view.data;
  const target = data?.target_status ?? "inactive";
  const deactivating = target === "inactive";
  const hold = data === undefined ? null : holdSentence(props.subject, data, translate);
  const copy = COPY_KEYS[props.subject];
  const dateError = touched && effectiveDate.trim() === "" ? t(copy.dateRequired) : undefined;
  const reasonError = touched && reason.trim() === "" ? t(copy.reasonRequired) : undefined;
  const complete = effectiveDate.trim() !== "" && reason.trim() !== "";

  async function submit(): Promise<void> {
    setTouched(true);
    if (!complete || data === undefined) {
      return;
    }
    setRefusal(null);
    try {
      await commit.mutateAsync({
        status: target,
        effective_date: effectiveDate.trim(),
        reason: reason.trim(),
      });
      void queryClient.invalidateQueries({ queryKey: ["premises"] });
      void queryClient.invalidateQueries({ queryKey: ["units"] });
      void queryClient.invalidateQueries({
        queryKey: statusChangeQueryKey(props.subject, props.id),
      });
      props.onChanged(target);
    } catch (error) {
      // The SERVER's own words, rendered verbatim. It re-reads the counts on the
      // press, so a dependency that appeared while this dialog was open is
      // refused here even though the list above said the commit was free.
      setRefusal(apiErrorText(error, translate));
    }
  }

  const titleKey = deactivating ? copy.deactivateTitle : copy.reactivateTitle;

  return (
    <ModalShell
      title={t(titleKey, { name: props.name })}
      kicker={t("metering.kicker")}
      role="alertdialog"
      onClose={props.onClose}
    >
      <div className="modal-body" data-status-dialog={props.subject}>
        {view.isPending && <LoadingSkeleton variant="card" rows={2} />}
        {!view.isPending && data === undefined && (
          <RefusalStrip>{apiErrorText(view.error, translate)}</RefusalStrip>
        )}

        {data !== undefined && (
          <>
            {/* ── THE THREE DRAWN INPUTS COME FIRST (`DEF-MET-4763`) ────────
                The frame draws `New status`, `From` and `Why`, then the panel
                that says whether the commit can be made. This screen drew them
                the other way round — counts, hold, consequence, then the two
                questions — so a clerk read the verdict before they had said
                what they were doing. B14 rule 38: what the form CONTAINS is the
                drawing's; how the form is BUILT is ours, which is why these are
                three stacked kit fields and not the frame's two-up row. */}
            <SelectField
              id="status-new"
              label={t("metering.status.newStatus")}
              value={target}
              options={statusOptions(target, translate)}
              required
              onChange={() => undefined}
            />
            <DatePickerField
              id="status-effective-date"
              label={t("metering.status.effectiveDate")}
              value={effectiveDate}
              onChange={setEffectiveDate}
              required
              dateFormat={dateFormat}
              error={dateError}
            />
            {/* Both required, both ways, and both land in the audit log — the
                only place they are held. A status change on a place is a thing
                somebody will be asked about a year later. */}
            <TextField
              id="status-reason"
              label={t("metering.status.reason")}
              value={reason}
              onChange={setReason}
              required
              multiline
              error={reasonError}
            />

            {/* ── THE REFUSAL AND THE CONSEQUENCE ARE ALTERNATIVES ──────────
                The frames say it in one sentence — *the refusal panel is
                REPLACED BY the consequence* — and this screen drew both at
                once, so a blocked place showed a panel saying it cannot be
                done above a box describing what would happen when it was. */}
            {deactivating && data.blocked ? (
              <section data-status-refusal-panel="">
                <h4>{t(copy.refusalHeading)}</h4>
                {/* B14 rule 20's small table, from the kit — the frame names
                    `PlainTable` and the kit has it. Each blocked thing is a
                    ROW with a link of its own, so *why not* is also the route
                    to do it first. */}
                <PlainTable data-status-dependencies="">
                  <tbody>
                    {visibleDependencies(data, props.subject).map((row) => {
                      const href = dependencyHref(row.link, tenantPath);
                      return (
                        <tr key={row.kind} data-dependency={row.kind}>
                          <td>{countLabel(props.subject, row, translate)}</td>
                          <td className="text-right!">
                            {href === null ? null : (
                              <Link className="underline" to={href}>
                                {t(
                                  SINGLE_RECORD_ROUTES.has(row.link.route)
                                    ? "metering.status.link.open"
                                    : "metering.status.link.show",
                                )}
                              </Link>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </PlainTable>
                {/* B14 rule 33 — five or six words, and it says what to do
                    next rather than everything that is wrong. This is the
                    frame's held line; it sits here rather than under the
                    footer because a slot below `ModalShell`'s footer is a
                    change to every dialog in the product (B14 rule 38). */}
                {hold !== null && <RefusalStrip data-status-hold="">{hold}</RefusalStrip>}
              </section>
            ) : (
              /* B14 rule 11 — the consequence, before the commit, in ONE
                 sentence (rule 32): what stops billing, what happens to the
                 meters, and what the record will read afterwards. */
              <ConsequenceBox
                tone="check"
                tag={t("metering.status.consequenceTag")}
                title={t("metering.status.consequenceTitle")}
                body={t(deactivating ? copy.deactivateConsequence : copy.reactivateConsequence)}
                data-consequence="status-change"
              />
            )}

            {refusal !== null && <RefusalStrip data-status-refusal="">{refusal}</RefusalStrip>}
          </>
        )}
      </div>

      <div className="modal-foot">
        <Button variant="ghost" disabled={commit.isPending} onClick={props.onClose}>
          {t("forms.cancel")}
        </Button>
        {/* B14 rule 6: taking a place out of service is the danger tier;
            putting it back is not, so the tier is COMPUTED from the action
            rather than pinned — the polymorphic call site ConfirmDialog's own
            `confirmVariant` note describes. */}
        <WorkingButton
          working={commit.isPending}
          variant={deactivating ? "danger" : "primary"}
          disabled={data === undefined || (data.blocked && deactivating)}
          onClick={() => void submit()}
        >
          {t(deactivating ? copy.deactivateAction : copy.reactivateAction)}
        </WorkingButton>
      </div>
    </ModalShell>
  );
}

export function statusChangeQueryKey(subject: StatusSubject, id: string) {
  return [subject === "premises" ? "premises" : "units", id, "status-change"] as const;
}

/**
 * One blocked row's own words. A kind this build has no sentence for renders the
 * bare number rather than a catalogue key — a raw `metering.…` string on screen
 * is what B14 rule 32 forbids and what a missing translation looks like.
 *
 * ⚠ **A NAME BEATS A COUNT WHERE THE SERVER GAVE ONE (`DEF-MET-4763`).** The
 * `U12` frame draws *Account A-10517 is still open* rather than *1 open
 * account*, and `unit_status_dependencies` now sends the number because a unit
 * is blocked by at most one account. `reference` is absent everywhere there is
 * no single thing to name — every premises row, every asset count, every
 * balance — and the count sentence answers there, unchanged.
 */
export function countLabel(
  subject: StatusSubject,
  row: StatusDependency,
  t: Translator,
): string {
  if (subject === "unit" && row.kind === "open_accounts" && row.reference) {
    return t("metering.units.status.blocker.accountNamed", { account: row.reference });
  }
  const key = COUNT_KEYS[subject][row.kind];
  return key === undefined ? String(row.count) : t(key, { count: row.count });
}

export default StatusChangeDialog;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-089 §6 wave D (D1 `PUJ-21`, D2 `PUJ-48`) · BR-MET-1164 (PO
//         2026-09-08, verbatim in 04-docs/05-modules/04-metering/
//         02-business-rules.md) · BR-MET-047 (the money term, unchanged) ·
//         B14 rules 6, 11, 21, 32, 33, 36
// generated: 2026-09-08 by the CR-089 wave D lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc · vitest StatusChangeDialog.dom.test.tsx · G31 (this file is on
//        src/styles/route-b-migrated.txt, so its utilities are emitted)
// exceptions: E3 the effective date and the reason are recorded in `audit_log`
//         and in NO column — neither can be queried back, exactly as
//         `move_unit`'s pair cannot; stated rather than implied · E3 the unit's
//         attached assets are COUNTED and do not block, because BR-MET-1164
//         names one term for a unit and a meter blocking would refuse nearly
//         every unit this product has · E3 CR-089 §6 D2's own sentence says
//         *"2 attached meters"*; the PO ruled the same day that on a unit
//         *"Meter = assets"*, and the count links to the unit's ASSETS tab, so
//         the word here is Assets — recorded in the decision log
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
