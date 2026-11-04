// ── Trace ──────────────────────────────────────────────
// Story:    CR-168-BRC10 round 3, lane ASSIGN — P4.12 (advice beside every
//           name, *Best fit* first) · P4.13 (bulk assign) — images 02, 12, 13
// Rules:    ruling 2 (the match ADVISES and never blocks; a lapsed
//           certificate only WARNS) · NFR-3 / NFR-5 (paged in SQL, searched on
//           the server, no maximum) · IS-3 (search debounced 300 ms, from two
//           characters) · B14 rule 8 (5+ options are searchable) · rule 21
//           (Tailwind; on route-b-migrated.txt) · rule 31 (no id on screen) ·
//           rule 33 (each fact ≤ 6 words) · rule 43 (a COMPONENT, so the
//           raise's crew step can take the same picker)
// Tests:    src/features/work/cr168Assign.dom.test.tsx
// Impacts:  OrderEditPage.tsx (images 12, 13) · dispatchModals.tsx (image 02)
// ───────────────────────────────────────────────────────
//
// ONE picker for every place a dispatcher chooses who is going.
//
// ⚠ **IT NEVER GREYS A NAME.** Image 12 draws five names and every one is
// choosable; the words at the right edge are the reason a name fits or does
// not. A disabled option would be the refusal ruling 2 retired, moved from the
// server to the screen where nobody could override it.
//
// ⚠ **PAGED, NOT CAPPED.** The first page arrives with nothing typed — best fit
// first — and a search of two letters or more asks the SERVER, so the 51st
// technician of a 40,000-account utility is one word away rather than absent.
// `per` is a page size, never a ceiling (NFR-5).
//
// ⚠ **TYPING DOES NOT UNASSIGN.** The kit clears its value on every keystroke
// (its own money rule: a stale id behind a changed box). Here a cleared value
// means *the dispatcher is searching*, never *Nobody yet* — that is its own
// option — so the job's holder in the form moves only on a real pick, and a
// search abandoned by tabbing away puts the box back on the holder.
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { formatDate } from "@/components/DateCell";
import { useFieldError } from "@/components/FormModal";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import type { RemoteOption } from "@/components/RemoteSearchSelectField";
import { useRegional } from "@/features/metering/meteringShared";

import { adviceText, availabilityAlert, bestFitFirst, kindWord, mergeAcross } from "./candidateAdvice";
import { listCandidatesPage } from "./workEndpoints";
import type { Candidate, CandidatePage } from "./workEndpoints";

/** A page, not a ceiling (NFR-5): the search reaches everyone past it. */
export const CANDIDATE_PAGE_SIZE = 50;

/** IS-3: the server is asked from two characters, 300 ms after the last key. */
const MIN_TERM = 2;
const DEBOUNCE_MS = 300;

const NOBODY = "__nobody__";

export interface CandidatesState {
  term: string;
  setTerm: (term: string) => void;
  /** Best fit first; for several orders, merged across all of them. */
  candidates: Candidate[];
  /** True when every page has been seen — the only time *all* may be said. */
  complete: boolean;
  searching: boolean;
  failed: boolean;
  loaded: boolean;
}

/** The candidates for one order or several, paged and searched (§7.3). */
export function useCandidates(orderIds: string[], client: ApiClient): CandidatesState {
  const [term, setTerm] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const trimmed = term.trim();
    const next = trimmed.length >= MIN_TERM ? trimmed : "";
    const timer = setTimeout(() => setQ(next), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [term]);

  const fetchAll = (search: string): Promise<CandidatePage[]> =>
    Promise.all(
      orderIds.map((id) => listCandidatesPage(id, { q: search, page: 1, per: CANDIDATE_PAGE_SIZE }, client)),
    );
  const base = useQuery({
    queryKey: ["work", "candidates", ...orderIds, ""],
    queryFn: () => fetchAll(""),
    enabled: orderIds.length > 0,
  });
  const search = useQuery({
    queryKey: ["work", "candidates", ...orderIds, q],
    queryFn: () => fetchAll(q),
    enabled: orderIds.length > 0 && q !== "",
  });
  const active = q === "" ? base : search;

  const candidates = useMemo(() => {
    const pages = active.data ?? [];
    if (pages.length === 0) return [];
    return pages.length === 1 ? bestFitFirst(pages[0].results) : mergeAcross(pages);
  }, [active.data]);

  return {
    term,
    setTerm,
    candidates,
    complete: (active.data ?? []).every((page) => page.next === null),
    searching: active.isFetching,
    failed: active.isError,
    loaded: active.isSuccess,
  };
}

export interface CandidatePickerProps {
  id: string;
  label: string;
  state: CandidatesState;
  /** The chosen holder's id; `""` is *Nobody yet* (or nothing chosen). */
  value: string;
  onPick: (candidate: Candidate | null) => void;
  /** Offer *Nobody yet* — the edit page's way to take a job off everybody. */
  allowNobody?: boolean;
  /** The job's holder, so the box names them even when they are past page 1. */
  current?: { id: string; kind: string; name: string } | null;
  placeholder?: string;
  /** The line under the field, and its test hook. */
  help?: string | null;
  helpKey?: string;
}

/** The words beside one name — for the edit page's *Was …* line as well. */
export function useAdviceWords(): (candidate: Candidate, options?: { availabilityShownApart?: boolean }) => string {
  const { t } = useTranslation();
  const { timeZone, dateFormat } = useRegional({});
  return (candidate, options) =>
    adviceText(candidate, (key, params) => t(key, params), (iso) => formatDate(iso, timeZone, dateFormat), options);
}

export function CandidatePicker(props: CandidatePickerProps) {
  const { t } = useTranslation();
  const words = useAdviceWords();
  const [typing, setTyping] = useState(false);
  const state = props.state;

  const current = props.current;
  const listed = useMemo(() => {
    const rows = state.candidates;
    if (current && current.id !== "" && !rows.some((row) => row.id === current.id) && state.term.trim() === "") {
      return [
        ...rows,
        {
          kind: current.kind,
          id: current.id,
          name: current.name,
          best_fit: false,
          advice: {
            skill: null,
            has_skill: true,
            area_match: false,
            off_that_day: false,
            jobs_that_day: null,
            certifications_lapsed: [],
          },
        },
      ];
    }
    return rows;
  }, [state.candidates, state.term, current]);

  const options: RemoteOption[] = [
    ...(props.allowNobody ? [{ value: NOBODY, label: t("work.edit.option.unassigned") }] : []),
    ...listed.map((candidate) => {
      // FB-033 D1/D2 — Off duty in red, On break as a warning; still choosable.
      const alert = availabilityAlert(candidate, (key, params) => t(key, params));
      return {
        value: candidate.id,
        label: candidate.name,
        kind: kindWord(candidate.kind, (key) => t(key)),
        badge: candidate.best_fit ? t("work.assign.bestFit") : undefined,
        ...(alert === null ? {} : { alert: alert.text, alertTone: alert.tone }),
        aside: words(candidate, { availabilityShownApart: true }),
      };
    }),
  ];

  const shown = typing ? "" : props.value === "" ? (props.allowNobody ? NOBODY : "") : props.value;

  return (
    <div
      className="flex flex-col"
      data-candidate-picker={props.id}
      onBlur={(event) => {
        if (event.currentTarget.contains(event.relatedTarget as Node | null)) return;
        setTyping(false);
        state.setTerm("");
      }}
    >
      <RemoteSearchSelectField
        id={props.id}
        label={props.label}
        term={state.term}
        onTermChange={state.setTerm}
        status={{
          idle: !state.loaded && !state.searching && !state.failed,
          searching: state.searching,
          searched: state.loaded,
          failed: state.failed,
        }}
        options={options}
        value={shown}
        startClosed
        placeholder={props.placeholder}
        onChange={(value) => {
          if (value === "") {
            setTyping(true);
            return;
          }
          setTyping(false);
          state.setTerm("");
          if (value === NOBODY) {
            props.onPick(null);
            return;
          }
          props.onPick(listed.find((candidate) => candidate.id === value) ?? null);
        }}
        words={{
          tooShort: t("work.assign.search.tooShort"),
          searching: t("work.assign.search.searching"),
          failed: t("work.assign.search.failed"),
          noMatch: t("work.assign.search.noMatch"),
        }}
      />
      {props.help ? (
        <p className="m-0 mt-1.5 text-sm text-neutral-600" data-field-help={props.helpKey ?? props.id}>
          {props.help}
        </p>
      ) : null}
    </div>
  );
}

/** Image 13's *Why it moves* — the five drawn reasons, in the drawn order. The
 *  server keeps the reason as the dispatcher's own words (§7.3: `reason` is
 *  text), so these are catalogue words, never stored codes. */
export const MOVE_REASONS = ["workload", "offSick", "skill", "customer", "closer"] as const;

/** The reason as the history will read it: *Workload — D. Ortiz has four jobs
 *  that day.* — the chosen word, then the note when there is one. */
export function moveReasonText(reason: string, note: string, t: (key: string) => string): string {
  const word = reason === "" ? "" : t(`work.assign.why.reasons.${reason}`);
  const said = note.trim();
  if (word === "") return said;
  return said === "" ? word : `${word} — ${said}`;
}

const CONTROL = "border border-divider px-2 py-1.5 text-base";

/**
 * P4.4 — image 13's *Why it moves*: a reason (required) and a note. ONE
 * component for the edit page and the bulk dialog, because the server asks the
 * same question at both doors (SRV-2: a move off somebody without a reason is
 * refused `work.dispatch.reason_required`, one order at a time in bulk).
 */
export function MoveReasonField(props: {
  reason: string;
  note: string;
  onReason: (reason: string) => void;
  onNote: (note: string) => void;
  /** The commit was pressed with no reason chosen. */
  missing: boolean;
}) {
  const { t } = useTranslation();
  // Inside a FormModal the schema's own refusal arrives by field id, so the
  // bulk dialog and the edit page mark the same control the same way.
  const formError = useFieldError("reason");
  const missing = props.missing || formError !== undefined;
  return (
    <fieldset className="m-0 flex flex-col gap-1 border-0 p-0" data-field="reason">
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">
          {t("work.assign.why.label")}
          <span aria-hidden="true"> *</span>
        </span>
        <select
          className={CONTROL}
          value={props.reason}
          aria-invalid={missing ? true : undefined}
          onChange={(event) => props.onReason(event.target.value)}
        >
          <option value="">{t("work.assign.why.choose")}</option>
          {MOVE_REASONS.map((reason) => (
            <option key={reason} value={reason}>
              {t(`work.assign.why.reasons.${reason}`)}
            </option>
          ))}
        </select>
      </label>
      <textarea
        className={CONTROL}
        rows={2}
        aria-label={t("work.assign.why.note")}
        value={props.note}
        onChange={(event) => props.onNote(event.target.value)}
      />
      {missing ? (
        <span className="text-sm text-danger-700" role="alert">
          {t("work.assign.why.required")}
        </span>
      ) : null}
    </fieldset>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §8 row R3 ASSIGN · §7.3 `GET /work-orders/{id}/candidates` · images 02, 12, 13
// generated: 2026-10-04 by lane ASSIGN
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · eslint · vitest cr168Assign.dom.test.tsx · routeBUtilities (on route-b-migrated.txt)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
