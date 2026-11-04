// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-031 (the work-order edit screen — assign, reschedule,
//           re-prioritise, re-area, cancel, behind a Change effects box)
//           Screens: Work-021 (`wireframes/Work-021.png`, r10 `WRK-03`)
// Rules:    BR-WRK-031 (a moved date or window tells the customer, on the
//           `appointment` kind; EVERY field change is audited with who and
//           when) · BR-WRK-032 (Cancel work order is danger tier; Save follows
//           a Change effects box) · BR-WRK-018 (a Complete order refuses a
//           priority change) · BR-WRK-023 (dispatch state is the third axis) ·
//           BR-SHL-025 (a control that cannot be honoured is disabled WITH ITS
//           REASON) · B14 rule 2 (one page header) · rule 6 (danger tier on a
//           destructive commit) · rule 11 (the consequence preview) · rule 21
//           (Tailwind; on route-b-migrated.txt) · rule 31 (no database id is a
//           visible value) · rule 32 (one sentence per section) · rule 33 (a
//           refusal is five or six words)
// Tests:    src/features/work/OrderEditPage.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · src/App.tsx (one route) ·
//           src/routing/screenIds.ts (WRK-03) · src/features/work/OrdersPage
//           .tsx (the row action that opens this)
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **THE BOX IS THE POINT OF THIS SCREEN, AND A BOX SAYING "THIS WILL CHANGE
// THE ORDER" WOULD BE WORTHLESS.**
//
// Every other screen in CR-070 CREATES something. This one changes something
// that already exists and that somebody may be driving to right now. B14 rule
// 11 asks for a consequence preview before an irreversible commit, and this is
// the wave that rule was written for — so the box names WHAT changes, FOR WHOM,
// and what cannot be undone:
//
//   * **Customer notification** — Sarah Miller is TOLD. That is the line that
//     cannot be taken back: a message queued is a message a person will read.
//   * **Technician phone** — D. Ortiz's copy changes under him while he is in
//     the van. He is not asked.
//   * **Audit** — every field, with a name and a time, permanently.
//
// ⚠ **THE FIRST LINE READ *"not yet sent; being decided"* IN SIX DOCUMENTS ON
// THE DAY THIS WAS BUILT.** `OQ-WRK-1495` closed on 2026-09-04 (option (a), a
// new `appointment` message kind) and the plan, the epic, the rule table, the
// story index, the overview and journey `J62` all still described the stub.
// `DEF-WRK-4028`. The box tells the truth about what Save does TODAY, which is
// the only thing a consequence box is for.
//
// ⚠ **WHAT HAPPENS TO WORK ALREADY DONE: NOTHING.** Moving this order from D.
// Ortiz to R. Patel writes an `unassign` row and an `assign` row and leaves D.
// Ortiz's row where it is — the history is append-only at the database. A
// safety row a crew ticked at 09:40 stays ticked at 09:40. The order carries a
// NEW PROMISE; it does not acquire a new past. That is why this screen has no
// "reset the checklist" control and must never grow one.
//
// ⚠ **ONLY WHAT MOVED IS SENT.** A browser posts the whole form. Sending it all
// would audit seven fields for a dispatcher who changed one and — far worse —
// would fire the customer notification on a Save that touched only the notes,
// telling somebody their visit moved to the time it already was.
// ⚠ **CR-168 ROUND 2 (lane ORDERS-LIST) — IMAGES 12 AND 13, AND TWO CRITICAL
// FAULTS THIS PAGE CARRIED.** (1) `DEF-WRK-9563`: *Assigned to* listed people,
// crews and a contractor in one select and posted EVERY choice as
// `technician_id`, so a crew's id reached the server as a person's, the server
// answered 404 — correctly — and the page discarded the answer: no `onError`
// on either mutation. A dispatcher believed the job was assigned. The holder's
// KIND now decides the key (`technician_id` for a person, `crew_id` for a crew
// or a contractor, both of which are `crews` rows), and every refusal renders
// in a `role="alert"` line through the catalogue (P1.1). (2) ruling 18: the
// office never completes a job, so *Complete* is not offered as a status.
// The actions moved into the page header (ruling 16, P1.30); the commit reads
// *Assign ✓* on a job nobody holds and *Reassign ✓* on one somebody does
// (P1.27); and the effects box says what THIS save will do (P1.26) — the
// customer is promised a message only when the day or the window moves.
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { CustomFieldsInput, customDataChanges, customFieldErrors } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { DatePickerField, FieldErrorsScope } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { getLookupEntries } from "@/api/endpoints";

import { WORK_ORDERS_ROUTE } from "./WorkShell";
import { windowMoments, todayDay } from "./visitWindow";
import type { WindowChoice } from "./visitWindow";
import { CandidatePicker, MoveReasonField, moveReasonText, useAdviceWords, useCandidates } from "./CandidatePicker";
import { getOrderEditForm, listWorkAreas, saveOrderEdit } from "./workEndpoints";
import type { Candidate, OrderEditForm, OrderEditPatch } from "./workEndpoints";


/** `BR-WRK-023`'s seven, in the order the run happens. */
const DISPATCH_STATES = [
  "queued",
  "scheduled",
  "en_route",
  "on_site",
  "complete",
  "on_hold",
  "cancelled",
] as const;

/** What the OFFICE may set — the seven less *Complete* (ruling 18, PO
 *  2026-09-24: *"back office cannot complete the job it can only accept it"*).
 *  A job the field already closed still shows its own word, as the current
 *  value, so the select never opens blank over a real state. */
export function officeDispatchStates(current: string): string[] {
  const offered: string[] = DISPATCH_STATES.filter((state) => state !== "complete");
  return current === "complete" ? ["complete", ...offered] : offered;
}

function timeOf(iso: string | null): string {
  if (!iso) return "";
  const at = new Date(iso);
  return Number.isNaN(at.valueOf())
    ? ""
    : `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
}

function dateOf(iso: string | null): string {
  if (!iso) return "";
  const at = new Date(iso);
  return Number.isNaN(at.valueOf()) ? "" : at.toISOString().slice(0, 10);
}

/** The booked clock times — the server's own reading in the UTILITY's zone
 *  when it sends one (`DEF-WRK-9688`), else the stored instants read here. */
function clockOf(form: OrderEditForm): { start: string; end: string } {
  if (form.appointment) {
    return { start: form.appointment.start ?? "", end: form.appointment.end ?? "" };
  }
  return { start: timeOf(form.window_start), end: timeOf(form.window_end) };
}

/** Which of the four the loaded order is on. Read from the two stored ends. */
function windowChoiceOf(form: OrderEditForm): WindowChoice {
  if (!form.window_start) return "any";
  const { start, end } = clockOf(form);
  if (start === "08:00" && end === "12:00") return "morning";
  if (start === "12:00" && end === "17:00") return "afternoon";
  return "exact";
}

interface Draft {
  dispatch_state: string;
  priority_id: string;
  area_id: string;
  technician_notes: string;
  /** The holder's id — a technician's, a crew's or a contractor's. */
  technician_id: string;
  /** The holder's KIND: `person` posts `technician_id`, anything else (`crew`,
   *  `contractor`) posts `crew_id`. Absent reads as a person — the only kind
   *  the field ever held before CR-168. */
  holder_kind?: string;
  date: string;
  window: WindowChoice;
  exact: string;
  /** P4.4 — why the job moves off its holder (image 13); `""` until chosen. */
  reason?: string;
  reasonNote?: string;
}

/** The holder the form opens on. `technician_id` (P1.25) when the server
 *  serves it, else the holder's own `id`. */
function holderIdOf(form: OrderEditForm): string {
  return form.technician_id ?? form.technician?.id ?? "";
}

function draftOf(form: OrderEditForm): Draft {
  return {
    dispatch_state: form.dispatch_state,
    priority_id: form.priority_id ?? "",
    area_id: form.area_id ?? "",
    technician_notes: form.technician_notes ?? "",
    technician_id: holderIdOf(form),
    holder_kind: form.technician?.kind,
    date: form.appointment?.date ?? dateOf(form.due_at ?? form.window_start),
    window: windowChoiceOf(form),
    exact: windowChoiceOf(form) === "exact" ? clockOf(form).start : "",
    reason: "",
    reasonNote: "",
  };
}

/** The job moves OFF somebody — onto somebody else or onto *Nobody yet*. Both
 *  need a reason: SRV-2's `edit.py` refuses any move away from a holder
 *  without one (`work.dispatch.reason_required`, its judgment (6)).
 *  ⚠ `DEF-WRK-9607`: this read *onto somebody else* only, so taking a held job
 *  to *Nobody yet* met the server's refusal with no field to answer it. */
export function isReassign(form: OrderEditForm, draft: Draft): boolean {
  const was = holderIdOf(form);
  return was !== "" && draft.technician_id !== was;
}

/** The reason as the history will read it: *Workload — D. Ortiz has four jobs
 *  that day.* — the chosen word, then the note when there is one. */
export function reasonText(draft: Draft, t: (key: string) => string): string {
  return moveReasonText(draft.reason ?? "", draft.reasonNote ?? "", t);
}

/** The whole of `US-WRK-031` TC-6, and the reason this function exists rather
 *  than the form posting itself: only what MOVED is sent. */
export function patchOf(form: OrderEditForm, draft: Draft): OrderEditPatch {
  const patch: OrderEditPatch = {};
  const original = draftOf(form);
  if (draft.dispatch_state !== original.dispatch_state) {
    patch.dispatch_state = draft.dispatch_state;
  }
  if (draft.priority_id !== original.priority_id) {
    patch.priority_id = draft.priority_id || null;
  }
  if (draft.area_id !== original.area_id) patch.area_id = draft.area_id || null;
  if (draft.technician_notes !== original.technician_notes) {
    patch.technician_notes = draft.technician_notes || null;
  }
  if (draft.technician_id !== original.technician_id) {
    // ⚠ `DEF-WRK-9563` — THE KIND DECIDES THE KEY. A crew's or a contractor's
    // id sent as `technician_id` is a 404 from the server, correctly.
    if (draft.technician_id === "") {
      patch.technician_id = null;
      patch.crew_id = null;
    } else if ((draft.holder_kind ?? "person") === "person") {
      patch.technician_id = draft.technician_id;
    } else {
      patch.crew_id = draft.technician_id;
    }
  }
  const dateMoved = draft.date !== original.date;
  const windowMoved = draft.window !== original.window || draft.exact !== original.exact;
  if (dateMoved || windowMoved) {
    const day = draft.date || original.date;
    if (!day) return patch;
    patch.due_at = `${day}T00:00:00`;
    Object.assign(patch, windowMoments(day, draft.window, draft.exact));
  }
  return patch;
}

type Translate = (key: string, params?: Record<string, unknown>) => string;

/**
 * **P1.26 — WHAT THIS SAVE WILL DO, AND NOTHING IT WILL NOT.** The box read
 * the same three lines whatever changed, so a priority change promised the
 * customer a message (measured on `2.490.6`). Each line now follows the patch:
 * the new holder is told, the old holder is told it is taken off them, the
 * technician's phone updates when anything else moves, and the customer is
 * told ONLY when the day or the window moves (`BR-WRK-031`).
 */
export function changeEffects(
  patch: OrderEditPatch,
  names: { was: string | null; now: string | null },
  t: Translate,
): { key: string; text: string }[] {
  const lines: { key: string; text: string }[] = [];
  const moved = "technician_id" in patch || "crew_id" in patch;
  if (moved && names.was !== null) {
    lines.push({ key: "was", text: t("work.edit.effects.offThem", { name: names.was }) });
  }
  if (moved && names.now !== null) {
    lines.push({ key: "now", text: t("work.edit.effects.toldNow", { name: names.now }) });
  }
  if (!moved && Object.keys(patch).length > 0 && names.was !== null) {
    lines.push({ key: "technician", text: t("work.edit.effects.technician") });
  }
  const visitMoved = "due_at" in patch || "window_start" in patch;
  lines.push({
    key: "customer",
    text: visitMoved ? t("work.edit.effects.customerMoved") : t("work.edit.effects.customerNotTold"),
  });
  lines.push({
    key: "audit",
    text: moved && names.was !== null ? t("work.edit.effects.auditBoth") : t("work.edit.effects.audit"),
  });
  return lines;
}

const CONTROL = "border border-divider px-2 py-1.5 text-base";

export interface OrderEditPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function OrderEditPage(props: OrderEditPageProps = {}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const { dateFormat } = useRegional({});
  const { orderId = "" } = useParams<{ orderId: string }>();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [customData, setCustomData] = useState<CustomFieldValues | null>(null);

  const form = useQuery({
    queryKey: queryKeys.workOrderEdit(orderId),
    queryFn: () => getOrderEditForm(orderId, client),
    enabled: Boolean(orderId),
  });
  const areas = useQuery({ queryKey: queryKeys.workAreas(), queryFn: () => listWorkAreas(client) });
  // P4.12 — paged and searched (NFR-3 / NFR-5), best fit first, every name
  // choosable (ruling 2).
  const pool = useCandidates(orderId === "" ? [] : [orderId], client);
  const adviceWords = useAdviceWords();
  const [picked, setPicked] = useState<Candidate | null>(null);
  const [reasonMissing, setReasonMissing] = useState(false);
  const priorities = useQuery({
    queryKey: queryKeys.workLookup("work_priorities"),
    queryFn: () => getLookupEntries("work_priorities", { per: 200 }, client),
  });

  // ⚠ RESOLVED ONCE, from the first page with nothing typed: a later search
  // changes the list, and a holder resolved against a filtered list would read
  // as moved the moment the dispatcher typed.
  const [resolvedHolder, setResolvedHolder] = useState<string | null>(null);

  // ⚠ **THE FORM THE PATCH IS MEASURED AGAINST, WITH ITS HOLDER RESOLVED.**
  // Until the server serves the holder's id (`DEF-WRK-9530`, P1.25) the form
  // carries only a kind and a name, and a select whose value matches no option
  // opens on *Nobody yet* over a job somebody holds. Resolving the holder by
  // kind and name against the candidates closes that gap; once the id is
  // served this is a no-op. The SAME resolved form is the patch's base, so
  // opening the page can never itself read as a change.
  useEffect(() => {
    if (resolvedHolder !== null || !form.data) return;
    if (holderIdOf(form.data) !== "" || form.data.technician === null) {
      setResolvedHolder("");
      return;
    }
    if (pool.term.trim() !== "" || !pool.loaded) return;
    const held = form.data.technician;
    // A crew's candidate name carries its head-count (*Field crew A (2)*) where
    // the holder's does not, so the name matches whole or as that prefix.
    const match = pool.candidates.find(
      (c) => c.kind === held.kind && (c.name === held.name || c.name.startsWith(`${held.name} (`)),
    );
    setResolvedHolder(match ? match.id : "");
  }, [form.data, resolvedHolder, pool.candidates, pool.loaded, pool.term]);

  const baseForm: OrderEditForm | undefined = useMemo(() => {
    if (!form.data || resolvedHolder === null) return undefined;
    return resolvedHolder === "" ? form.data : { ...form.data, technician_id: resolvedHolder };
  }, [form.data, resolvedHolder]);

  useEffect(() => {
    if (!baseForm) return;
    if (draft === null) setDraft(draftOf(baseForm));
    if (customData === null) setCustomData(baseForm.custom_data ?? {});
  }, [baseForm, draft, customData]);

  const patch = useMemo(() => {
    if (!baseForm || !draft) return {};
    const base: OrderEditPatch = patchOf(baseForm, draft);
    if (isReassign(baseForm, draft)) {
      const why = reasonText(draft, (key) => t(key));
      if (why !== "") base.reason = why;
    }
    const changed = customDataChanges(baseForm.custom_data ?? {}, customData ?? {});
    return Object.keys(changed).length > 0 ? { ...base, custom_data: changed } : base;
  }, [baseForm, draft, customData, t]);
  const changedCount = Object.keys(patch).filter((key) => key !== "reason").length;

  const save = useMutation({
    mutationFn: () => saveOrderEdit(orderId, patch, client),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["work"] });
      navigate(tenantPath(WORK_ORDERS_ROUTE));
    },
  });

  const cancelOrder = useMutation({
    mutationFn: () => client.post(`/work-orders/${orderId}/cancel`, {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["work"] });
      navigate(tenantPath(WORK_ORDERS_ROUTE));
    },
  });

  if (!baseForm || !draft) {
    return (
      <PageHeader
        kicker={t("work.edit.kicker")}
        title={t("work.edit.loading")}
        rollup={t("work.edit.description")}
      />
    );
  }
  const order = baseForm;
  const set = (patchDraft: Partial<Draft>) => setDraft({ ...draft, ...patchDraft });
  const held = holderIdOf(order) !== "";
  const nameOf = (id: string): string | null => {
    if (id === "") return null;
    if (picked !== null && picked.id === id) return picked.name;
    if (id === holderIdOf(order)) return order.technician?.name ?? null;
    return pool.candidates.find((c) => c.id === id)?.name ?? null;
  };
  const reassigning = isReassign(order, draft);
  // Image 13's line under the field: who had it, and the new name's advice.
  const pickedNow = picked !== null && picked.id === draft.technician_id ? picked : null;
  const pickerHelp =
    reassigning && pickedNow !== null
      ? [
          t("work.assign.help.wasPrefix", { name: order.technician?.name ?? "" }),
          [pickedNow.name, adviceWords(pickedNow)].filter((part) => part !== "").join(" · ") + ".",
        ].join(" ")
      : t("work.assign.help.adviceOnly");
  const commit = () => {
    if (reassigning && (draft.reason ?? "") === "") {
      setReasonMissing(true);
      return;
    }
    setReasonMissing(false);
    save.mutate();
  };
  const effects = changeEffects(
    patch,
    {
      was: held ? (order.technician?.name ?? nameOf(holderIdOf(order))) : null,
      now: nameOf(draft.technician_id),
    },
    (key, params) => t(key, params),
  );
  // P1.1 — the newest refusal of either commit, in the catalogue's words.
  const refusal = cancelOrder.isError ? cancelOrder.error : save.isError ? save.error : null;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        kicker={t("work.edit.kicker")}
        title={t("work.edit.title", { order: order.order_no ?? "", type: order.type ?? "" })}
        rollup={t("work.edit.description")}
        // ⚠ **RULING 16 / P1.30 — THE THREE ACTS SIT TOP RIGHT, IN THE DRAWN
        // ORDER** (images 12, 13): *Cancel · Cancel work order · Assign ✓*. They
        // were a row at the bottom-left under the effects box until CR-168.
        secondaryActions={
          <>
            <Button variant="secondary" onClick={() => navigate(tenantPath(WORK_ORDERS_ROUTE))}>
              {t("confirm.cancel")}
            </Button>
            {/* B14 rule 6 — destructive commit, danger tier, and it asks first. */}
            <Button variant="danger" onClick={() => setConfirming(true)} data-action="cancel-order">
              {t("work.edit.action.cancelOrder")}
            </Button>
            <Button
              variant="primary"
              disabled={changedCount === 0 || save.isPending}
              onClick={commit}
              data-action="save"
            >
              {held ? t("work.edit.action.reassign") : t("work.edit.action.assign")}
            </Button>
          </>
        }
      />

      {refusal !== null ? (
        <p role="alert" className="m-0 text-danger-700" data-refusal="">
          {refusalText((key, params) => t(key, params), refusal)}
        </p>
      ) : null}

      {/* ── THE BOX — B14 rule 11; image 12 draws it under the title ────── */}
      <ConsequenceBox
        tone="check"
        tag={t("work.edit.effects.tag")}
        title={t("work.edit.effects.title")}
        data-consequence="change-effects"
        body={
          <ul className="flex flex-col gap-1">
            {effects.map((line) => (
              <li key={line.key} data-effect={line.key}>
                {line.text}
              </li>
            ))}
          </ul>
        }
      />

      {/* ── STATUS, PRIORITY AND PROMISE ──────────────────────────────── */}
      <section className="flex flex-col gap-3" data-section="status">
        <h2 className="text-sm font-bold uppercase tracking-wide">
          {t("work.edit.section.status")}
        </h2>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">{t("work.edit.field.status")}</span>
          <select
            className={CONTROL}
            value={draft.dispatch_state}
            onChange={(event) => set({ dispatch_state: event.target.value })}
            data-field="dispatch_state"
          >
            {officeDispatchStates(order.dispatch_state).map((state) => (
              <option key={state} value={state} disabled={state === "complete"}>
                {t(`work.orders.dispatch.${state}`)}
              </option>
            ))}
          </select>
          <span className="text-sm text-neutral-600">{t("work.edit.help.status")}</span>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">{t("work.edit.field.priority")}</span>
          <select
            className={CONTROL}
            value={draft.priority_id}
            disabled={order.priority_locked}
            onChange={(event) => set({ priority_id: event.target.value })}
            data-field="priority_id"
          >
            <option value="">{t("work.edit.option.noPriority")}</option>
            {(priorities.data?.results ?? []).map((priority) => (
              <option key={priority.id} value={priority.id}>
                {priority.name}
              </option>
            ))}
          </select>
          {order.priority_locked ? (
            <span className="text-sm text-neutral-600" data-reason="priority_locked">
              {t("work.edit.refusal.priorityLocked")}
            </span>
          ) : null}
        </label>
      </section>

      {/* ── WHO AND WHEN ──────────────────────────────────────────────── */}
      <section className="flex flex-col gap-3" data-section="who">
        <h2 className="text-sm font-bold uppercase tracking-wide">
          {t("work.edit.section.who")}
        </h2>
        {/* P1.3 + P4.12 — people, crews and contractors, each named with its
            kind and the ADVICE beside it (image 12); Best fit first; every
            name choosable (ruling 2). */}
        <CandidatePicker
          id="assigned-to"
          label={t("work.edit.field.assignedTo")}
          state={pool}
          value={draft.technician_id}
          allowNobody
          current={
            holderIdOf(order) !== "" && order.technician !== null
              ? { id: holderIdOf(order), kind: order.technician.kind, name: order.technician.name }
              : null
          }
          onPick={(candidate) => {
            setPicked(candidate);
            set({ technician_id: candidate?.id ?? "", holder_kind: candidate?.kind });
          }}
          help={pickerHelp}
          helpKey="assigned-to"
        />

        {/* P4.4 — image 13's *Why it moves*: a reason, required, whenever the
            job moves off somebody (DEF-WRK-9607). */}
        {reassigning ? (
          <MoveReasonField
            reason={draft.reason ?? ""}
            note={draft.reasonNote ?? ""}
            onReason={(reason) => set({ reason })}
            onNote={(reasonNote) => set({ reasonNote })}
            missing={reasonMissing && (draft.reason ?? "") === ""}
          />
        ) : null}

        <DatePickerField
          id="due_at"
          label={t("work.edit.field.date")}
          value={draft.date}
          onChange={(value) => set({ date: value })}
          dateFormat={dateFormat}
          todayValue={todayDay()}
        />

        <fieldset className="flex flex-col gap-1" data-field="window">
          <legend className="text-sm font-medium">{t("work.edit.field.window")}</legend>
          <select
            className={CONTROL}
            aria-label={t("work.edit.field.window")}
            value={draft.window}
            onChange={(event) => set({ window: event.target.value as WindowChoice })}
          >
            <option value="any">{t("work.edit.window.any")}</option>
            <option value="morning">{t("work.edit.window.morning")}</option>
            <option value="afternoon">{t("work.edit.window.afternoon")}</option>
            <option value="exact">{t("work.edit.window.exact")}</option>
          </select>
          {draft.window === "exact" ? (
            <input
              type="time"
              className={CONTROL}
              aria-label={t("work.edit.window.exact")}
              value={draft.exact}
              onChange={(event) => set({ exact: event.target.value })}
              data-field="window_exact"
            />
          ) : null}
          <span className="text-sm text-neutral-600">{t("work.edit.help.window")}</span>
        </fieldset>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">{t("work.edit.field.area")}</span>
          <select
            className={CONTROL}
            value={draft.area_id}
            onChange={(event) => set({ area_id: event.target.value })}
            data-field="area_id"
          >
            <option value="">{t("work.edit.option.noArea")}</option>
            {(areas.data ?? []).map((area) => (
              <option key={area.id} value={area.id}>
                {area.name}
              </option>
            ))}
          </select>
          <span className="text-sm text-neutral-600">{t("work.edit.help.area")}</span>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">{t("work.edit.field.notes")}</span>
          <textarea
            className={CONTROL}
            rows={3}
            value={draft.technician_notes}
            onChange={(event) => set({ technician_notes: event.target.value })}
            data-field="technician_notes"
          />
          <span className="text-sm text-neutral-600">{t("work.edit.help.notes")}</span>
        </label>
        {/* CR-161-BRC10 W4 — the utility's OWN work-order fields (`WORK_EDIT`).
            Nothing at all when none is placed here; a refusal is marked on its
            own control. */}
        <FieldErrorsScope
          errors={
            isApiError(save.error) ? customFieldErrors(save.error.fieldErrors, (key, params) => t(key, params)) : {}
          }
        >
          <CustomFieldsInput
            entity="work_orders"
            screen="WORK_EDIT"
            values={customData ?? {}}
            onChange={setCustomData}
          />
        </FieldErrorsScope>
      </section>

      {confirming ? (
        <ConfirmDialog
          title={t("work.edit.confirm.title", { order: order.order_no ?? "" })}
          consequence={t("work.edit.confirm.body")}
          confirmLabel={t("work.edit.confirm.confirm")}
          working={cancelOrder.isPending}
          confirmVariant="danger"
          onConfirm={() => {
            setConfirming(false);
            cancelOrder.mutate();
          }}
          onCancel={() => setConfirming(false)}
        />
      ) : null}
    </div>
  );
}
