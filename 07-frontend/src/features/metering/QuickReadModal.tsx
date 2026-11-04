// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 · ADDITION 2026-08-26 — **W5 task 6, the quick single-
//           reading entry (S28's counter case).** PO verbatim: *"we will need
//           modpage to load single reading, if it is simple then modal"*.
//           REDRAWN 2026-09-14 to the Meter Reads blueprint's **entry 12**,
//           built from the drawing AS AN IMAGE (B14 rule 42, PO 2026-09-13).
//           Two commitments land here — **MR-25**, the modal grows one value
//           box per REGISTER instead of handing a two-number meter to a
//           five-stage file wizard, and **MR-31**, the register reads as a
//           WORD and never as the served code.
//           Screens: S25 (the "Add reading" action lives here) · S28 (the path
//           this hands off to when the registers are UNKNOWN)
// Story:    US-MET-012 (S25) · US-MET-007 (S28 steps 1–2, the pipeline reused)
// Rules:    BR-MET-049 (the plan-driven expected register set — what makes a
//           meter "simple") · BR-MET-131 (no read DRAWER — and why a CAPTURE
//           modal is not one; see below) · BR-MET-129 (a warned reading POSTS) ·
//           BR-MET-122 (an off-cycle meter is a WARNING with a reason, never a
//           refusal) · BR-MET-140 (a meter on NO cycle: ACCEPTED and
//           WARNED — the neighbouring case, PO 2026-08-27) · BR-MET-012 (nothing posts before commit) · BR-MET-017
//           (the compliance stamp, certification included) · IS-1 (modal vs
//           guided page) · IS-10 (Esc/✕/backdrop close, focus trap, aria) ·
//           B14 rule 21 (Tailwind utilities; this file adds NO stylesheet class)
//           CLAUDE.md hard rule 3 (a quantity NEVER travels without its unit)
// Questions: OQ-422 **CLOSED 2026-08-27** — PO: *"(b) Accept and warn"*. The
//           reading POSTS and the absence is a WARNING with a reason a clerk
//           can act on (BR-MET-140). No `data-tracks` remains: a stated
//           absence that cites a CLOSED question is the note G38 exists to
//           stop outliving its reason.
// Tests:    07-frontend/src/features/metering/QuickReadModal.test.tsx
// Impacts:  ReadsListPage.tsx mounts it from the S25 header
// ───────────────────────────────────────────────────────
//
// ────────────────────────────────────────────────────────────────────────────
// A DIFFERENT SURFACE. NOT A DIFFERENT PIPELINE. THAT IS THE WHOLE FEATURE.
// ────────────────────────────────────────────────────────────────────────────
// A clerk with ONE reading at the counter should not walk a five-stage import
// wizard. What this must never become is a second way for a reading to reach
// `meter_reads` — a second write path would be a second place for the sixteen
// VEE rules to be wrong, and those rules are what the whole product bills off.
//
// So `submitQuickRead` below calls, in order and with no shortcut:
//
//     stageReadBatch({ rows: [ONE ROW] })   POST /read-batches
//     validateReadBatch(batchId)            POST /read-batches/{id}/validate
//     postReadBatch(batchId, {certified})   POST /read-batches/{id}/post
//
// the SAME three wrappers `UploadReadsWizard` drives for a 1,247-row CSV. The
// counter read is therefore exactly as validated, as audited (BR-MET-017's
// stamp, batch number and all), as idempotent and as correctable as a file row
// — and `test_task6_tc13` on the backend asserts it lands with an
// `import_batch_id` for exactly that reason.
//
// ────────────────────────────────────────────────────────────────────────────
// WHY THIS IS NOT THE DRAWER BR-MET-131 BANNED — written where it is doubted
// ────────────────────────────────────────────────────────────────────────────
// BR-MET-131 (PO 2026-08-26): *"no read drawer required"* — S29 is a PAGE and
// the drawer retires with this very wave. A reader meeting a modal in the reads
// surface is right to check, so:
//
//   · BR-MET-131 retired a DETAIL VIEW in a side panel — S29, which DISPLAYS an
//     existing read with its supersession chain, compliance stamp and
//     corrections. A record with that much behind it needs a page and a URL.
//   · This CAPTURES a record that does not exist yet. Four fields, no history,
//     no URL worth sharing, one outcome. The PO asked for it by name — *"if it
//     is simple then modal"* — in the SAME session that retired the drawer.
//
// A modal that captures and a drawer that displays are different objects. Both
// statements are live law and neither is an exception to the other.
//
// ────────────────────────────────────────────────────────────────────────────
// ⚠ THE WRONG-REGISTER TRAP — WHY THIS FILE IS THE ONE THE PO PUT FIRST
// ────────────────────────────────────────────────────────────────────────────
// PO ruling 2026-09-14, verbatim: *"Put this first. DEF-797 already cost 412 kW
// billed as 14 kWh — $154 against $4,532. Money path, so I'm not classifying
// it"*.
//
// A reading filed against the WRONG REGISTER is PERMANENT. `supersede_read`
// takes a value and a reason and nothing else, and migration `0007`'s trigger
// FREEZES the channel — so a correction cannot move it. On a demand plan the
// two registers do not even share a unit, which is how DEF-797 happened.
//
// So this screen's whole job on the way in is to make the register impossible
// to mistake, and it does exactly three things about it, none of which decides
// anything:
//
//   1. **THE REGISTER IS NAMED, IN WORDS.** `channelWord` below resolves
//      `tou_on` to *On-peak* through `metering.reads.channel.*` — the SAME
//      catalogue the reads list reads it through, so one register cannot read
//      two ways on two screens. Before this, the modal printed the served CODE
//      where the list printed the word.
//   2. **THE UNIT IS IN EVERY LABEL** — `On-peak · kWh`, never a bare number
//      box (CLAUDE.md hard rule 3). The unit is the meter's own
//      (`context.meter.unit`); where the server serves none the label shows a
//      DASH, because a dash is the honest answer and an assumed unit is the
//      defect.
//   3. **ONE BOX PER REGISTER, ALL OF THEM, ALWAYS TOGETHER.** A form with one
//      box on a four-register meter is how three registers go missing.
//
// ⚠ **AND IT DECIDES NOTHING.** B4/B5 are ❄️ FROZEN and move only by a finance
// re-sign. Nothing here rounds, converts a unit, estimates, or picks a register
// on the clerk's behalf: when the server cannot say what the registers ARE
// (`channels === null`) the modal REFUSES rather than guessing `total` — the
// same refusal `quick_read._registers` already makes on the server and for the
// same reason, that a wrong default files one register's dial as a whole
// month's usage.
//
// ────────────────────────────────────────────────────────────────────────────
// MR-25 — THE MODAL GROWS THE ROWS IT HAS ALREADY FETCHED
// ────────────────────────────────────────────────────────────────────────────
// As built, a meter with more than one register rendered NO value fields at
// all and sent the clerk to the five-stage upload wizard. The wizard's manual
// grid does take them — one row per register — so the path existed; it was
// five stages for two numbers.
//
// The modal has ALREADY fetched `channels`, by name, before the clerk types
// anything. Rendering three labelled number boxes instead of one is the same
// form, the same endpoint and the same pipeline, and it deletes the detour.
// **The hand-off stays for `channels === null`** — the one case where the
// modal genuinely does not know what to ask for.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { CustomFieldsInput } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import {
  isDeferredPost,
  postReadBatch,
  receiptAfterPostJob,
  stageReadBatch,
  validateReadBatch,
} from "@/api/endpoints";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { formatMonthYear } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";

import { MeterReadingEntry } from "./MeterReadingEntry";
import { useRegional } from "./meteringShared";

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/** What a fact reads as when the server did not serve it. Hard rule 3's own
 *  sentence: *a bare number is refused; a dash is the honest answer*. */
const DASH = "—";

// ── what `GET /reads/quick-context` answers (typed exactly as served) ───────
// Local, following `AccountUsageTab`'s precedent: `api/endpoints.ts` is shared
// and a wrapper there plus a type here would be two contracts (hard-won law 5).
export interface QuickReadRegisters {
  simple: boolean;
  channels: string[] | null;
  channel_count: number | null;
  default_channel: string | null;
  absent_reason: string | null;
  hand_off_to: string | null;
}

export interface QuickReadCycle {
  cycle: { id: string; code: string; name: string } | null;
  // BR-MET-140 (PO 2026-08-27, *"(b) Accept and warn"*). `accepted` is served
  // beside the reason because the first thing a clerk needs to know is that
  // their reading is NOT being refused; `action` is what makes the warning
  // something to act on rather than a statement of fact.
  cycle_absent: {
    reason: string;
    severity: string;
    accepted: boolean;
    action: string;
    rule_ref: string;
  } | null;
  route: { id: string; code: string } | null;
  period_month: string;
  read_window: { from: string; to: string } | null;
  in_window: boolean | null;
}

export interface QuickReadContext {
  meter: {
    id: string;
    asset_no: string;
    unit: string;
    multiplier: string | null;
    service: string | null;
  };
  read_at: string;
  registers: QuickReadRegisters;
  cycle: QuickReadCycle;
  pipeline: Record<string, string>;
  rule_refs: string[];
}

export function quickReadContextKey(meterNo: string, readAt: string) {
  return ["reads", "quick-context", meterNo, readAt] as const;
}

export async function getQuickReadContext(
  meterNo: string,
  readAt: string,
  client: ApiClient = api,
): Promise<QuickReadContext> {
  const response = await client.get<QuickReadContext>("/reads/quick-context", {
    query: { meter_no: meterNo, read_at: readAt },
  });
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * ⚠ **MR-31 — THE REGISTER'S DISPLAY WORD, AND NEVER THE SERVED CODE.**
 *
 * The blueprint's own finding on this screen: *"this screen renders the
 * register as the served code — `tou_on`, not On-peak — because no signed
 * vocabulary maps a channel to a display word on this surface. The reads list
 * DOES translate it (`metering.reads.channel.*`), so the same register reads
 * two ways on two screens."* There IS a vocabulary; this surface simply never
 * called it. It does now, and it is the SAME catalogue prefix the list uses, so
 * the two cannot drift.
 *
 * ⚠ **THE FALLBACK IS THE CODE AND NOT THE KEY.** `READ_CHANNELS` is seven and
 * fixed today and all seven have words, so this branch is unreachable for the
 * served set — but a tenant channel outside it would otherwise render
 * `metering.reads.channel.solar_export` at a clerk, and B14 rule 31 forbids a
 * path on screen by name. Rule 31's other option — *"the field says so in
 * words"* — is wrong HERE specifically: two registers both reading *not named*
 * are indistinguishable, which is the permanent mistake this screen exists to
 * prevent. The code is ugly and it is at least the truth.
 */
export function channelWord(t: Translator, channel: string): string {
  const key = `metering.reads.channel.${channel}`;
  const word = t(key);
  return word === key || word.trim() === "" ? channel : word;
}

/**
 * The DOM id of a register's value box — and therefore the name a zod issue and
 * a server field error land under.
 *
 * A one-register meter keeps the plain `reading`, which is the server's own
 * field name (B8: an error lands under the field it names with no translation
 * table in between) and is what the drawing labels *Reading · kWh*. Past one,
 * every register gets its own box and its own id.
 */
export function readingFieldId(channel: string, single: boolean): string {
  return single ? "reading" : `reading_${channel}`;
}

/**
 * ⚠ **THE VALUE READS AS IT WAS DRAWN — `×1`, not `×1.000000`** (Q9, PO
 * 2026-09-14, *"as drawn"*). Display only: the multiplier the batch is rated
 * against is the server's, untouched, and nothing here rounds anything (B4 is
 * ❄️ FROZEN).
 */
export function displayMultiplier(raw: string | null): string {
  if (raw === null || raw.trim() === "") {
    return DASH;
  }
  const trimmed = raw.trim();
  return trimmed.includes(".") ? trimmed.replace(/0+$/, "").replace(/\.$/, "") : trimmed;
}

/**
 * The form, as the server's own field names — so a server field error lands
 * under the field it names without a translation table in between (B8).
 *
 * `channels` is the meter's expected register set as the server resolved it.
 * Absent or single → one `reading`. Past one → one required box per register,
 * because **all of them post together**: a form that accepted three of four
 * would file a permanent hole in a month nobody can correct (entry 04 — the
 * register of a filed reading can never be changed).
 */
export const quickReadSchema = (t: Translator, channels?: string[] | null) => {
  const value = z.string().trim().min(1, t("metering.quickRead.error.readingRequired"));
  const base = {
    meter_no: z.string().trim().min(1, t("metering.quickRead.error.meterRequired")),
    read_date: z.string().trim().min(1, t("metering.quickRead.error.dateRequired")),
  };
  if (channels === undefined || channels === null || channels.length <= 1) {
    return z.object({ ...base, reading: value });
  }
  const perRegister: Record<string, typeof value> = {};
  for (const channel of channels) {
    perRegister[readingFieldId(channel, false)] = value;
  }
  return z.object({ ...base, ...perRegister });
};

/**
 * ⚠ **THE BATCH, BUILT IN A PURE FUNCTION SO IT CAN BE ASSERTED.**
 *
 * `source_kind: "manual"` is the TRANSPORT (BR-MET-123 clause 2) — the clerk
 * typed it rather than uploading it. `period_month` is the READ DATE's month,
 * DERIVED and never typed, per CR-038's period/cycle sanity statement clause 1:
 * *"The read date is the truth… Period membership is DERIVED from `read_at`
 * against the cycle's calendar — never typed, never guessed."*
 *
 * `cycle_id` rides along when the context resolved one, so the batch carries
 * the same tag a file would (BR-MET-014). When it did not, the field is
 * ABSENT rather than blank — an empty cycle tag would be a claim, and OQ-422
 * is the unruled question about a counter read on no cycle.
 */
export function quickReadBatchRequest(values: {
  meter_no: string;
  read_date: string;
  notes: string;
  cycleId: string | null;
  /** In the server's own order, which is the order they are drawn in.
   *
   *  ⚠ **MR-25: ONE ROW PER REGISTER, AND IT IS STILL ONE BATCH.** A
   *  four-register meter stages four rows the way a CSV would —
   *  `read_import.parse_manual_rows` is the same parser the S28 manual grid
   *  feeds, one row per register — so the four validate together, post
   *  together and carry ONE `import_batch_id`. They are one visit to one meter
   *  and they are recorded as one. */
  registers: { channel: string; reading: string }[];
  /** CR-161-BRC10 W4 — the utility's own reading fields, ONE set of answers
   *  for the visit, carried on every register row. Absent for a caller that
   *  draws no fields; the modal always passes it (`{}` included). */
  customData?: CustomFieldValues;
}) {
  return {
    source_kind: "manual",
    period_month: `${values.read_date.slice(0, 7)}-01`,
    ...(values.cycleId === null ? {} : { cycle_id: values.cycleId }),
    rows: values.registers.map((register) => ({
      meter_id: values.meter_no,
      read_date: values.read_date,
      reading: register.reading,
      channel: register.channel,
      ...(values.notes.trim() === "" ? {} : { notes: values.notes }),
      ...(values.customData === undefined ? {} : { custom_data: values.customData }),
    })),
  };
}

/** What the modal shows after the commit — the VERDICT, in the modal, per
 *  CR-038 task 6: *"the verdict is shown in the modal"*. */
export interface QuickReadOutcome {
  posted: number;
  skipped: number;
  batchNo: string | null;
  /** BR-MET-129: a WARNED reading posts. `flagged` is not a failure — it is a
   *  reading on file with a loud flag, which is the entire point of that rule
   *  (*"the reading exists, the flag is loud, and a person investigates"*). */
  flagged: boolean;
}

export function QuickReadModal(props: {
  onClose: () => void;
  onPosted: (outcome: QuickReadOutcome) => void;
  client?: ApiClient;
  t: Translator;
  // IS-8: the tenant's own date format, threaded from the page. A modal that
  // picked its own would print a different date shape from the list behind it.
  dateFormat: RegionalDateFormat;
  /** The tenant's zone — the *Read on* line under Fetch (DEF-MET-10183). */
  timeZone?: string;
  // ⚠ THERE IS DELIBERATELY NO `initialMeterNo` PROP, AND G13 IS WHY.
  // The first draft carried one — "pre-set when the modal is opened from a
  // meter's own context" — and nothing opens it from a meter's page, so the
  // whole pre-filled branch was dead UI: it rendered nothing and every test
  // passed over it (hard-won law 2, four defects in one day).
  // `check_unwired_props` named it exactly: *"renders behind
  // `props.initialMeterNo` but no caller passes it"*. It comes back in the
  // commit that adds the caller, and not one commit earlier.
}) {
  const { t } = props;
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);

  const [meterNo, setMeterNo] = useState("");
  const [readDate, setReadDate] = useState(today);
  /** DEF-MET-10183 — the box holds the head-end's reading (and its date). */
  const [fetched, setFetched] = useState(false);
  const { timeZone } = useRegional({ timeZone: props.timeZone, dateFormat: props.dateFormat });
  /** Keyed by CHANNEL CODE, never by field id — the code is what the batch
   *  carries and the id is only how the box is addressed on screen. */
  const [readings, setReadings] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  // CR-161-BRC10 W4 — the utility's own reading fields for this visit.
  const [customData, setCustomData] = useState<CustomFieldValues>({});
  const [lookedUp, setLookedUp] = useState<string>("");

  // ⚠ ON BLUR, NEVER PER KEYSTROKE. A per-character request asks the server
  // about "M", "M-", "M-4" and every one of those is a miss the clerk reads as
  // an error — which is why the helper under the box is *"We look it up."* and
  // there is no button to press.
  const contextQuery = useQuery({
    queryKey: quickReadContextKey(lookedUp, readDate),
    queryFn: () => getQuickReadContext(lookedUp, readDate, client),
    retry: false,
    enabled: lookedUp.trim() !== "",
  });

  const context = contextQuery.data;
  const registers = context?.registers;
  /** ⚠ THE ONE FACT THIS SCREEN BRANCHES ON, AND IT IS THE SERVER'S.
   *  `null` means the server could not resolve the meter's plan — NOT that the
   *  meter has one register. Guessing `total` there is `DEF-797`'s shape. */
  const channels = registers?.channels ?? null;
  const single = channels !== null && channels.length === 1;
  const handOff = context !== undefined && channels === null;
  /** Hard rule 3 — and a DASH when the server served no unit, never a guess. */
  const unit = context?.meter.unit ?? null;
  const unitWord = unit === null || unit.trim() === "" ? DASH : unit;

  const commit = useMutation({
    mutationFn: async (): Promise<QuickReadOutcome> => {
      // ⚠ THE PIPELINE. Three calls, in order, the same three a CSV walks.
      const batch = await stageReadBatch(
        quickReadBatchRequest({
          meter_no: meterNo,
          read_date: readDate,
          notes,
          cycleId: context?.cycle.cycle?.id ?? null,
          // ⚠ THE CHANNEL IS THE SERVER'S OWN, NEVER A HARDCODED `total`. A
          // one-register meter whose plan names a different register gets THAT
          // one, and a multi-register meter posts every one of them together.
          registers: (channels ?? []).map((channel) => ({
            channel,
            reading: readings[channel] ?? "",
          })),
          customData,
        }),
        client,
      );
      await validateReadBatch(batch.id, client);
      // BR-MET-017: the commit carries the certification the compliance stamp
      // records. The clerk pressing the commit button IS the certification for
      // a reading they took themselves — the same statement the wizard's step 5
      // checkbox makes, made by the act rather than by a second click on a
      // four-field form.
      const answer = await postReadBatch(batch.id, { certified: true }, client);
      // DEF-MET-8106 — a post over the server's bar answers with a job. One
      // quick reading never is, but the receipt is read the same way if so.
      const posted = isDeferredPost(answer)
        ? await receiptAfterPostJob(answer, client)
        : answer;
      return {
        posted: posted.posted_reads,
        skipped: (posted as { skipped_reads?: number }).skipped_reads ?? 0,
        batchNo: posted.batch_no,
        flagged: (posted.counts?.warnings ?? 0) > 0,
      };
    },
    onSuccess: (outcome) => {
      // The list behind the modal is now stale in two ways — the row itself and
      // the Needs-attention counts a flagged read moves.
      void queryClient.invalidateQueries({ queryKey: ["reads"] });
      props.onPosted(outcome);
    },
  });

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await commit.mutateAsync();
      return { ok: true };
    } catch (error) {
      // B12 §3: the server's envelope is authoritative and renders itself.
      return { ok: false, error: error as never };
    }
  }

  const values: Record<string, string> = { meter_no: meterNo, read_date: readDate };
  for (const channel of channels ?? []) {
    values[readingFieldId(channel, single)] = readings[channel] ?? "";
  }
  if (channels === null) {
    values.reading = "";
  }

  return (
    <FormModal
      title={t("metering.quickRead.title")}
      kicker={t("metering.quickRead.kicker")}
      schema={quickReadSchema(t, channels)}
      values={values}
      onSubmit={handleSubmit}
      onClose={props.onClose}
      submitLabel={t("metering.quickRead.submit")}
      // ⚠ Q6's shape (PO 2026-09-14): a refusal that is a STATE is DISABLED
      // with its reason, never removed — removal is for a refusal that is
      // PERMANENT. A meter whose registers the server could not resolve is a
      // state: fix the plan and the same meter posts.
      commitBlocked={handOff ? t("metering.quickRead.registersUnknownAction") : undefined}
    >
      {/* ⚠ THE BLUR HANDLER IS ON THE WRAPPER, AND IT IS A DELIBERATE SECOND
          CHOICE. B14 rule 36 says a piece the kit lacks is ADDED TO THE KIT,
          and `TextField` lacks `onBlur`; the right home for this is
          `components/FormModal.tsx`. That file was held UNCOMMITTED by another
          lane at the moment of writing, and a pathspec commit takes a file's
          whole working-tree content — so committing it would publish their
          in-flight work with mine, which is hard-won law 11's mechanism five
          (`DEF-168`) and is invisible to every check in that law. React's focus
          events bubble, so a handler on the container is the same behaviour
          with none of that risk. REPORTED so the kit prop lands in one commit
          when the file is free; this is not a pattern to copy. */}
      <div onBlur={() => setLookedUp(meterNo.trim())}>
        <TextField
          id="meter_no"
          label={t("metering.quickRead.meterLabel")}
          value={meterNo}
          onChange={(value) => setMeterNo(value)}
          required
          autoComplete="off"
          help={t("metering.quickRead.meterHelp")}
        />
      </div>

      {contextQuery.isPending && lookedUp.trim() !== "" && (
        <p className={`m-0 text-sm ${MUTED}`}>{t("metering.quickRead.looking")}</p>
      )}
      {contextQuery.isError && (
        <p className="m-0 text-sm text-danger-700" role="status">
          {apiErrorText(contextQuery.error, t)}
        </p>
      )}

      {context !== undefined && (
        <>
          {/* ⚠ **THE CONTEXT PANEL — *is this the right meter?*, ANSWERED BEFORE
              THE VALUE IS TYPED.** It is a `Panel` and not three loose lines,
              per the PO's ruling of 2026-09-12 (*"in detail section use Panel
              to information groups"*) and the way entry 12 draws it.

              Its first line is the Q7 line: the meter, **its register in
              words**, and the multiplier the reading will be rated by. Every
              part of it is SERVED — nothing here is composed from a guess.

              ⚠ The blueprint also draws the premises address and the unit label
              in this line. `quick_read.quick_entry_context` serves NEITHER
              today, and composing them on the client would breach hard rule 8
              (an address is DERIVED by walking to `premises`, never held
              elsewhere) — so they are ABSENT and reported, never faked. */}
          <Panel className="text-base" data-testid="quick-read-meter">
            <p className="m-0">
              <strong>{context.meter.asset_no}</strong>
              {single && channels !== null ? ` · ${channelWord(t, channels[0])}` : ""}
              {` · \u00d7${displayMultiplier(context.meter.multiplier)}`}
            </p>
            {context.cycle.cycle !== null && (
              <p className={`m-0 mt-1 text-sm ${MUTED}`} data-testid="quick-read-cycle">
                {t("metering.quickRead.cycleLine", {
                  cycle: context.cycle.cycle.code,
                  // Q9 — a value displays as drawn: a MONTH, never `2026-08-01`,
                  // whose day-of-month means nothing to anybody.
                  // `formatMonthYear` is the kit's one month-year shape.
                  period: formatMonthYear(context.cycle.period_month, "UTC"),
                })}
              </p>
            )}
          </Panel>

          {/* ⚠ **BR-MET-140 — THIS WAS A MUTED LINE UNTIL 2026-08-27.** The PO
              ruled *"(b) Accept and warn"*: the reading posts, and the absence
              stops being a quiet blank and becomes something a clerk can act on,
              **so somebody fixes the route**.

              ⚠ **AMBER, NOT RED, AND THE TIER IS THE RULING.** Nothing is wrong
              with the reading; the configuration fault is ours. The commit
              button is never disabled by this.

              ⚠ **A RAIL, NOT A BOX** — the blueprint draws one amber rule down
              the left edge and no border around it, which is r10's own device
              for emphasis and is how entry 12 draws this exact note. */}
          {context.cycle.cycle === null && (
            <div
              className="border-l-[3px] border-l-warning-500 py-1 pl-3 text-base"
              role="status"
              data-testid="quick-read-cycle-absent"
              data-reason={context.cycle.cycle_absent?.reason ?? undefined}
            >
              <p className="m-0 text-warning-700">
                {t(
                  context.cycle.cycle_absent?.reason === "route_has_no_cycle"
                    ? "metering.quickRead.cycleAbsentNoCycle"
                    : "metering.quickRead.cycleAbsentNoRoute",
                )}{" "}
                {t("metering.quickRead.cycleAbsentAccepted", {
                  period: formatMonthYear(context.cycle.period_month, "UTC"),
                })}
              </p>
              {/* BR-MET-140 clause 3: each reason is *"followed by the action
                  that fixes it"*, and the action is PER REASON — a clerk told
                  the wrong one looks in the wrong place. */}
              <p className={`m-0 mt-1 text-sm ${MUTED}`}>
                {t(
                  context.cycle.cycle_absent?.reason === "route_has_no_cycle"
                    ? "metering.quickRead.cycleAbsentActionNoCycle"
                    : "metering.quickRead.cycleAbsentActionNoRoute",
                )}
              </p>
            </div>
          )}

          {/* BR-MET-122: an off-window read WARNS with a reason and is never
              refused. Shown here, one step BEFORE the commit, rather than as a
              flag discovered on the list afterwards — same information, earlier,
              which is the whole value of a counter surface. */}
          {context.cycle.in_window === false && (
            <p className="m-0 text-sm text-warning-700" role="status">
              {t("metering.quickRead.outOfWindow")}
            </p>
          )}
        </>
      )}

      {/* ⚠ THE HAND-OFF, AND MR-25 LEAVES EXACTLY ONE. It fires for
          `channels === null` — the server could not resolve this meter's plan —
          and for nothing else. It does not guess a register: filing a dial
          against the wrong one is permanent, because `supersede_read` takes only
          a value and a reason and `0007`'s trigger freezes the channel. */}
      {handOff && (
        <div
          className="border-l-[3px] border-l-warning-500 py-1 pl-3 text-base"
          role="status"
          data-testid="quick-read-registers-unknown"
        >
          <p className="m-0 text-warning-700">{t("metering.quickRead.registersUnknown")}</p>
          <p className={`m-0 mt-1 text-sm ${MUTED}`}>
            {t("metering.quickRead.registersUnknownAction")}
          </p>
        </div>
      )}

      {channels !== null && (
        <>
          {/* ⚠ **ONE BOX PER REGISTER, EACH NAMED AND EACH CARRYING ITS UNIT.**
              A one-register meter is drawn as *Reading · kWh* — there is only
              one register and the panel above has already named it. Past one,
              every box takes the register's own word: *On-peak · kWh*. The list
              comes from the SERVER and is never typed out here (hard-won law 12
              — a hand-typed list is how an eighth register never appears).

              ⚠ **THE SHARED READING PIECE — `DEF-MET-10183` (PO 2026-10-17,
              *"use same code components"* … *"for meter reading, date and
              fetch"*).** Each box is `MeterReadingEntry`, the component every
              reading screen mounts. ONE date serves the visit, so it is drawn
              on the first register only (`showReadDate`) and keeps its server
              field name `read_date`; each value box keeps `readingFieldId`, so
              the schema's and the server's field errors still land on it.

              ⚠ **FETCH ON A ONE-REGISTER METER ONLY.** The head-end answers ONE
              figure per meter. On a multi-register meter that figure cannot be
              assigned to *On-peak* or *Off-peak* without guessing — and a
              reading filed against the wrong register is permanent (MR-25). So
              a multi-register meter is typed, as before. A fetch fills the
              value AND the head-end's own read date. */}
          {channels.map((channel, index) => (
            <MeterReadingEntry
              key={channel}
              meterNo={context?.meter.asset_no ?? meterNo}
              assetId={`${context?.meter.id ?? meterNo}-${channel}`}
              unit={unit}
              value={readings[channel] ?? ""}
              readDate={readDate}
              fetched={single && fetched}
              defaultReadDate={today}
              asOf={readDate}
              showFetch={single}
              showReadDate={index === 0}
              required
              readingLabel={
                single
                  ? t("metering.quickRead.valueLabel", { unit: unitWord })
                  : t("metering.quickRead.registerLabel", {
                      register: channelWord(t, channel),
                      unit: unitWord,
                    })
              }
              dateLabel={t("metering.quickRead.dateLabel")}
              help={single ? t("metering.quickRead.valueHelp") : undefined}
              valueId={readingFieldId(channel, single)}
              dateId="read_date"
              onChange={(next) => {
                setReadings((prior) => ({ ...prior, [channel]: next.value }));
                setReadDate(next.readDate);
                setFetched(next.fetched);
              }}
              client={client}
              t={t}
              timeZone={timeZone}
              dateFormat={props.dateFormat}
            />
          ))}

          {/* What the plan expects, and that they go together — so a clerk who
              has three of four numbers knows BEFORE typing that this is not the
              form for a partial visit. Two short sentences beat one long one
              (B14 rule 33). */}
          {!single && (
            <p className="m-0 text-base" data-testid="quick-read-expects">
              {t("metering.quickRead.multiExpects", { count: channels.length })}
            </p>
          )}

          <TextField
            id="notes"
            label={t("metering.quickRead.noteLabel")}
            value={notes}
            onChange={(value) => setNotes(value)}
          />
          {/* CR-161-BRC10 W4 — the utility's OWN reading fields (`READ_ENTRY`).
              Nothing at all when none is placed here. They never reach the
              bill calculation (Part 2 row 11). */}
          <CustomFieldsInput
            entity="meter_reads"
            screen="READ_ENTRY"
            values={customData}
            onChange={setCustomData}
            client={client}
          />
        </>
      )}
    </FormModal>
  );
}

/** The S25 header control that opens it. Separated so the page mounts a BUTTON
 *  and the modal only exists while it is open — a modal rendered permanently
 *  with `hidden` is a focus trap waiting to happen (IS-10). */
export function QuickReadButton(props: { onOpen: () => void; t: Translator }) {
  return (
    <Button variant="secondary" onClick={props.onOpen}>
      {props.t("metering.quickRead.open")}
    </Button>
  );
}

export default QuickReadModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-038 ADDITION 2026-08-26 (W5 task 6) + BR-MET-049/122/129/131 + the S28 pipeline; REDRAWN 2026-09-14 to the Meter Reads blueprint entry 12 (MR-25 · MR-31), built from the drawing as an IMAGE per B14 rule 42
// generated: 2026-08-26 by the CR-038 W5 tasks 6/7/8 lane · redrawn 2026-09-14 by the Meter Reads step-2 reads lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint✔ · vitest (QuickReadModal.dom.test.tsx · ReadsBulkBar.test.tsx) · g31 (utilities only — NO new stylesheet class; this file is on route-b-migrated.txt) · g13 (`client` is optional and the mount passes it) · g40 (mounted from ReadsListPage's header)
// exceptions: E3 the commit certifies IMPLICITLY — a clerk pressing "Post reading" on a form they filled from the meter in front of them IS the BR-MET-017 statement, and a second certification checkbox on a modal this small is friction with no reader. The stamp is recorded identically either way; REPORTED rather than assumed silently · E3 the context is fetched on BLUR, not per keystroke: a per-character request asks the server about "M", "M-", "M-4" and every one is a miss · E3 a meter on no cycle posts with NO `cycle_id` tag rather than a blank one — an empty tag would be a claim; OQ-422 is CLOSED (PO 2026-08-27 *"(b) Accept and warn"*) and the absence is an amber WARNING naming the reason and the fix (BR-MET-140), never a red error, because nothing is wrong with the reading · E1 **the blur handler sits on a wrapper `<div>` and not on the kit's `TextField`** — B14 rule 36 says add the piece to the kit, and `components/FormModal.tsx` was held uncommitted by another lane at the moment of writing, where a pathspec commit publishes their in-flight work (law 11 mechanism five, DEF-168). REPORTED so the prop lands in one commit when the file is free · E1 **the blueprint draws the premises address and the unit label in the context panel and `quick_read.quick_entry_context` serves neither** — they are ABSENT rather than composed on the client, because an address is derived by walking to `premises` (hard rule 8) and that walk is a server change with its own test · E1 **the drawing draws the off-cycle sentence in plain ink and carries no action line; BR-MET-140 clauses 3 and 4 say amber and *"each followed by the action that fixes it"*** — the CONFIRMED rule is kept and the divergence REPORTED, which is B14 rule 41's own carve-out · E3 `channelWord`'s fallback renders the raw channel CODE for a channel no catalogue names; rule 31's *"says so in words"* alternative would make two unnamed registers indistinguishable, which is the permanent error this screen prevents. Unreachable for the seven served channels, all of which have words
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
