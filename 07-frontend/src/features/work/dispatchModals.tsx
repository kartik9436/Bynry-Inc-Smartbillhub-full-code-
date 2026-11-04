// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-027 (bulk Assign · Reschedule · Change priority) ·
//           US-WRK-025 (the act that gets appended) · US-WRK-011 (the Area
//           filter's options)  Screens: Work-007's ActionRow
// Rules:    BR-WRK-027 (one row PER ORDER, never one for the batch) ·
//           BR-WRK-029 (only a matching skill is offered) · BR-WRK-018 (a
//           priority carries a promise) · B14 rule 32 (one sentence per
//           section) · rule 33 (a fact ≤ 6 words) · rule 21 (Tailwind only,
//           and this file is on route-b-migrated.txt in the commit that
//           creates it)
// Tests:    src/features/work/OrdersPage.test.tsx
// Impacts:  src/features/work/OrdersPage.tsx · workEndpoints.ts
// ───────────────────────────────────────────────────────
//
// The three modals the selection is driven with, kept out of `OrdersPage.tsx`
// so the screen file stays the screen and these stay the forms.
//
// ⚠ **THE ASSIGN PICKER OFFERS THE UNION, WITH ADVICE — CR-168 round 3, lane
// ASSIGN (P4.13, image 02).** Until then it offered the INTERSECTION of the
// eligible lists, because `BR-WRK-029` refused a mismatch at the write. The PO
// ruled on 2026-09-23 that the match ADVISES and never blocks (ruling 2), and
// on 2026-10-04 that a lapsed certificate only warns, so an intersection would
// have been the retired refusal moved to the screen. Every name for ANY ticked
// order is offered (`mergeAcross`), the advice beside it holds across ALL of
// them, and one line under the field says who lacks a skill and who is off.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { DatePickerField, FormModal, SelectField } from "@/components/FormModal";
import { useRegional } from "@/features/metering/meteringShared";
import { bulkAdviceLine } from "./candidateAdvice";
import { CandidatePicker, MoveReasonField, moveReasonText, useAdviceWords, useCandidates } from "./CandidatePicker";
import type { BulkAct, BulkRequest, Candidate } from "./workEndpoints";
import { isDay, windowMoments } from "./visitWindow";
import type { WindowChoice } from "./visitWindow";
import type { FormSubmitOutcome } from "@/components/FormModal";

export interface BulkModalProps {
  act: BulkAct;
  ids: string[];
  priorities: { value: string; label: string }[];
  client: ApiClient;
  /** How many of the ticked orders somebody already holds. SRV-2 refuses a
   *  move off a holder without a reason, ONE ORDER AT A TIME in bulk, so the
   *  dialog asks *Why it moves* when this is above zero (lane ASSIGN). */
  held?: number;
  onSubmit: (body: Omit<BulkRequest, "act" | "ids">) => Promise<FormSubmitOutcome>;
  onClose: () => void;
}

export function BulkModal(props: BulkModalProps) {
  const { t } = useTranslation();
  const { dateFormat } = useRegional({});
  const [holder, setHolder] = useState("");
  const [chosen, setChosen] = useState<Candidate | null>(null);
  const [reason, setReason] = useState("");
  const [reasonNote, setReasonNote] = useState("");
  const moving = props.act === "assign" && (props.held ?? 0) > 0;
  const [when, setWhen] = useState("");
  const [visitWindow, setVisitWindow] = useState<WindowChoice>("any");
  const [priority, setPriority] = useState("");

  // P4.13 — every name for any ticked order, paged and searched; only the
  // assign act asks.
  const pool = useCandidates(props.act === "assign" ? props.ids : [], props.client);
  const adviceWords = useAdviceWords();

  // ⚠ **A DAY IS A DATE OR NOTHING (`DEF-WRK-9570`).** The box is the kit's
  // date picker, so a browser cannot hand us `UU898`; the schema still refuses
  // a non-date, because a typed value is a claim and the server is not the
  // first place it should be checked.
  const schema = useMemo(() => {
    const day = z
      .string()
      .trim()
      .refine((value) => isDay(value), t("work.orders.bulk.whenRequired"));
    if (props.act === "assign") {
      return z.object({
        holder: z.string().trim().min(1, t("work.orders.bulk.holderRequired")),
        when: z.union([z.literal(""), day]),
        reason: moving ? z.string().min(1, t("work.assign.why.required")) : z.string(),
      });
    }
    if (props.act === "priority") {
      return z.object({
        priority: z.string().trim().min(1, t("work.orders.bulk.priorityRequired")),
      });
    }
    return z.object({ when: day });
  }, [props.act, t, moving]);

  const values =
    props.act === "assign"
      ? { holder, when, reason }
      : props.act === "priority"
        ? { priority }
        : { when };

  /** The visit the dialog writes: a day at midnight (the edit page's own
   *  convention for a promise) and the window's two moments on that day. */
  function visit(): Partial<Omit<BulkRequest, "act" | "ids">> {
    if (!isDay(when)) return {};
    const moments = windowMoments(when, visitWindow);
    return {
      scheduled_for: `${when}T00:00:00`,
      ...(moments.window_start === null ? {} : { window_start: moments.window_start }),
      ...(moments.window_end === null ? {} : { window_end: moments.window_end }),
    };
  }

  async function submit(): Promise<FormSubmitOutcome> {
    if (props.act === "assign") {
      const who = chosen?.kind === "person" ? { technician_id: holder } : { crew_id: holder };
      const why = moving ? { reason: moveReasonText(reason, reasonNote, (key) => t(key)) } : {};
      return props.onSubmit({ ...who, ...visit(), ...why });
    }
    if (props.act === "priority") {
      return props.onSubmit({ priority_id: priority });
    }
    return props.onSubmit(visit());
  }

  const windowOptions = [
    { value: "any", label: t("work.edit.window.any") },
    { value: "morning", label: t("work.edit.window.morning") },
    { value: "afternoon", label: t("work.edit.window.afternoon") },
  ];

  const dayAndWindow = (
    <>
      <DatePickerField
        id="when"
        label={t("work.orders.bulk.when")}
        value={when}
        onChange={setWhen}
        dateFormat={dateFormat}
        required={props.act === "reschedule"}
      />
      <SelectField
        id="window"
        label={t("work.orders.bulk.window")}
        value={visitWindow}
        onChange={(value) => setVisitWindow(value as WindowChoice)}
        options={windowOptions}
      />
    </>
  );

  return (
    <FormModal
      title={
        props.act === "assign"
          ? t("work.orders.bulk.title.assignCount", { count: props.ids.length })
          : t(`work.orders.bulk.title.${props.act}`)
      }
      schema={schema}
      values={values}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t(`work.orders.bulk.submit.${props.act}`)}
    >
      {props.act === "assign" && (
        <>
          {/* Image 02 — *Who is going*, nobody chosen until the dispatcher
              chooses; the advice beside each name, and one line under it. */}
          <CandidatePicker
            id="holder"
            label={t("work.orders.bulk.holder")}
            state={pool}
            value={holder}
            placeholder={t("work.assign.bulk.chooseWho")}
            onPick={(candidate) => {
              setChosen(candidate);
              setHolder(candidate?.id ?? "");
            }}
            help={
              chosen !== null
                ? `${t("work.assign.bulk.prefix")} ${[chosen.name, adviceWords(chosen)].filter((part) => part !== "").join(" · ")}.`
                : bulkAdviceLine(pool.candidates, pool.complete, (key, params) => t(key, params))
            }
            helpKey="holder"
          />
          {/* P4.4 in bulk — some ticked orders already have somebody: say why
              they move, once, for all of them. */}
          {moving ? (
            <>
              <p className="m-0 text-sm text-neutral-700" data-moving={props.held}>
                {t("work.assign.bulk.held", { count: props.held })}
              </p>
              <MoveReasonField
                reason={reason}
                note={reasonNote}
                onReason={setReason}
                onNote={setReasonNote}
                missing={false}
              />
            </>
          ) : null}
          {dayAndWindow}
          {/* Image 02's closing fact — who hears about it, in six words. */}
          <p className="m-0 text-sm text-neutral-700">{t("work.orders.bulk.toldOnPhone")}</p>
        </>
      )}
      {props.act === "reschedule" && dayAndWindow}
      {props.act === "priority" && (
        <SelectField
          id="priority"
          label={t("work.orders.bulk.priority")}
          value={priority}
          onChange={setPriority}
          options={props.priorities}
          // `DEF-SHL-10751` — starts "", so the box drew the first priority
          // while holding none and the form refused a value it showed.
          placeholder={t("customers.build.raise.pick")}
        />
      )}
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-027 · US-WRK-025 (EP-WRK-05) · 08-screen-layouts.md Work-007 · 10-execution-plan.md wave G task G3
// generated: 2026-09-05 by the CR-070 wave G build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · eslint · vitest OrdersPage.test.tsx · G31 (Tailwind only; this file is on route-b-migrated.txt in the commit that creates it)
// exceptions: the picker offers the UNION across the selection with advice (ruling 2; CR-168 round 3 lane ASSIGN replaced the intersection) — stated above, asserted by mergeAcross's cases and cr168Assign.dom.test.tsx
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
