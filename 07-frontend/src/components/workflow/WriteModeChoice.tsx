// ── Trace ──────────────────────────────────────────────
// Change:   CR-042 — "in all imports - we need 2 option on step 1 insert,
//           insert & update; replace option is not required; currently many
//           places this option is at step 4 of import- can you check all
//           imports and make the corrections" (PO, 2026-08-27).
// Rules:    BR-MET-210 (two modes, that order, those words, step 1, ONE
//           control) · CR-036 (g) (the mode is a PREMISE, chosen at step 1) ·
//           DEF-770 (step 4 STATES it and never offers a second control) ·
//           B14 rule 9/10 (one control vocabulary) · B14 rule 21 (Tailwind
//           utilities, no stylesheet class — this file is on Route B) ·
//           hard-won law 3 (the safe option is the one you get for free)
// Impacts:  features/metering/ImportWorkflowPage.tsx (premises · units · the
//           three assets targets · accounts) · features/metering/
//           readsImportRail.tsx → UploadReadsWizard.tsx (meter reads) ·
//           components/workflow/DryRunPanel.tsx (the step-4 statement)
// ───────────────────────────────────────────────────────
//
// THE WRITE MODE, AS ONE CONTROL, FOR EVERY IMPORT IN THE PRODUCT.
//
// ⚠ **WHY THIS FILE EXISTS: THE SAME DECISION WAS DRAWN TWO DIFFERENT WAYS,
// AND IN EIGHT OF ELEVEN LANGUAGES IT ALSO READ DIFFERENTLY.** Before CR-042
// the shared ETL runner drew a three-across `SegmentedField` captioned
// **"Write mode"**, and the reads rail drew radio cards captioned **"What does
// this file mean?"** with a consequence sentence under the choice. Two shapes,
// two captions — and two SEPARATE catalogue key sets, which had drifted:
//
//     de   Nur neue einfügen   ·  Nur Neue einfügen
//     es   Solo insertar nuevas ·  Solo insertar nuevos
//     ja   新規のみ登録         ·  新規のみ追加
//     ko   신규만 추가          ·  새 항목만 추가
//     it   Inserisci solo le nuove · Inserisci solo i nuovi
//
// Same option, same product, different words — invisible to every gate,
// because each catalogue was internally complete and G15 only checks PARITY.
// One control with one key set is the only fix that stays fixed.
//
// ⚠ **A KIND SUPPLIES ITS CONSEQUENCE SENTENCE AND NOTHING ELSE.** The LABELS,
// the caption, the help line, the layout and the step-4 statement are the
// same everywhere by construction — that is the PO's ask. What legitimately
// differs is what "already on file" MEANS on that rail: for reads it is a
// reading at a meter/date/register with BR-MET-127's billed refusal attached;
// for the ETL runner it is a record under the same reference. Flattening that
// into one sentence would make the control lie on one of the two rails, which
// is the BR-MET-099 mistake in a different costume.
//
// ⚠ **THERE ARE TWO MODES AND THE ORDER IS THE PO's.** `insert` is FIRST and
// is the default because it is the only mode that cannot alter a record
// already on file: a clerk who never touches this control gets the safe one
// (hard-won law 3 — the unsafe option must be the one you type). `replace` was
// withdrawn on 2026-08-27; see `write_modes.py` and `import_runs.py` for what
// happened to the behaviour behind it, which is NOT the same answer on the two
// rails.
import { Button } from "@/components/Button";

/** The two modes, as the SERVER spells them on both rails. */
export const WRITE_MODES = ["insert", "upsert"] as const;
export type WriteModeId = (typeof WRITE_MODES)[number];

/** hard-won law 3 — the safe option is the one you get without typing. */
export const DEFAULT_WRITE_MODE: WriteModeId = "insert";

/** A translator, structurally identical to `useTranslation`'s `t`. */
type Translator = (key: string, params?: Record<string, unknown>) => string;

export interface WriteModeOption {
  id: WriteModeId;
  label: string;
  /** What this mode does to a record already on file, in one sentence. */
  consequence: string | null;
  /**
   * ⛔ **`P1.18` — WHY THIS TARGET CANNOT USE THIS MODE.** `null`/absent = it
   * can, which is every caller that existed before 2026-09-22, so no importer
   * already shipped moves by a pixel.
   *
   * ⚠ **A REFUSED MODE IS DRAWN, DISABLED, WITH THIS SENTENCE — NEVER DROPPED
   * FROM THE LIST.** Blueprint p068 ③ on the payments target: *"it is drawn
   * present and refused, with its reason, rather than silently absent: a clerk
   * who has used the premises importer will look for it."* That is `BR-SHL-025`
   * exactly — the user learns the rule instead of hunting for a control
   * somebody removed — and it is why this is a field on the option rather than
   * the caller simply passing a shorter array.
   */
  refused?: string | null;
}

/**
 * The two options, with the labels resolved from the ONE key set and the
 * consequence sentences supplied by the calling rail.
 *
 * A FUNCTION rather than a module constant because `t()` cannot be called at
 * module scope — the i18n instance is not ready at import time and a string
 * frozen there never changes language. `kinds.ts` states the same rule for the
 * same reason.
 */
export function writeModeOptions(
  t: Translator,
  consequences?: { insert?: string | null; upsert?: string | null },
  /** `P1.18` — per-target refusals, from `kinds.writeModeRefusals(kind, t)`.
   *  Omitted means neither mode is refused, which is every caller before
   *  2026-09-22. */
  refusals?: { insert?: string | null; upsert?: string | null },
): WriteModeOption[] {
  return [
    {
      id: "insert",
      label: t("workflow.writeMode.insert"),
      consequence: consequences?.insert ?? null,
      refused: refusals?.insert ?? null,
    },
    {
      id: "upsert",
      label: t("workflow.writeMode.upsert"),
      consequence: consequences?.upsert ?? null,
      refused: refusals?.upsert ?? null,
    },
  ];
}

export interface WriteModeFieldProps {
  value: string;
  onChange: (next: WriteModeId) => void;
  options: readonly WriteModeOption[];
  disabled?: boolean;
  /** Unique per runner instance — two importers can be mounted at once. */
  idPrefix: string;
  t: Translator;
}

/**
 * ⚠ **STEP 1 — THE PREMISE, ASKED BEFORE ANYTHING IS READ (CR-036 (g)).**
 *
 * The PO's reason is the whole design: the mode *"decides what the file MEANS"*
 * and the checks at the next two steps report against it. Their own screenshot
 * of the premises importer showed step 3 saying *"the write mode decides what
 * happens to it"* on a screen that still refused to show the write mode.
 *
 * Drawn as a radiogroup of cards rather than a segmented control because each
 * mode owes a CONSEQUENCE sentence and a segmented control has nowhere to put
 * one. B14 rule 9/10's "one control vocabulary" is satisfied by the semantics:
 * a `role="radiogroup"` of native radios is exactly what `SegmentedField` is
 * underneath.
 */
export function WriteModeField({
  value,
  onChange,
  options,
  disabled,
  idPrefix,
  t,
}: WriteModeFieldProps) {
  const chosen = options.find((option) => option.id === value);
  const labelId = `${idPrefix}-write-mode-label`;
  return (
    <div className="mt-6" data-workflow="write-mode">
      <p className="text-sm font-semibold text-text" id={labelId}>
        {t("workflow.writeMode.label")}
      </p>
      <p className="mt-1 text-sm text-neutral-700">{t("workflow.writeMode.help")}</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2" role="radiogroup" aria-labelledby={labelId}>
        {options.map((option) => {
          // `P1.18` — a mode this TARGET cannot use, and a form that is busy,
          // are two different facts and the card says which. `off` covers both
          // because either one means the radio cannot be pressed; only the
          // first one owes the clerk a sentence.
          const refused = option.refused ?? null;
          const off = disabled === true || refused !== null;
          return (
            <label
              key={option.id}
              data-write-mode={option.id}
              data-refused={refused !== null ? "true" : "false"}
              className={`flex flex-col gap-1 rounded-lg border p-3 text-sm ${
                value === option.id ? "border-accent bg-accent-100" : "border-neutral-300"
              } ${off ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
            >
              <span className="flex items-center gap-2">
                <input
                  type="radio"
                  name={`${idPrefix}-write-mode`}
                  value={option.id}
                  checked={value === option.id}
                  disabled={off}
                  onChange={() => onChange(option.id)}
                />
                <span className="font-semibold text-text">{option.label}</span>
              </span>
              {/* ⚠ THE REASON IS TEXT AND NEVER A `title` TOOLTIP — `FormModal`'s
                  `commitBlocked` makes the same choice in the same words: a
                  tooltip is unreachable by keyboard, invisible on touch and
                  unread by a clerk who is on the phone, which is the exact
                  reader B14 rule 33 writes its caps for. */}
              {refused !== null && (
                <span className="text-sm text-neutral-700" data-workflow="write-mode-refused">
                  {refused}
                </span>
              )}
            </label>
          );
        })}
      </div>
      {/* ⚠ The consequence travels with the CHOICE and not as two permanent
          paragraphs. A sentence about the mode the operator did NOT pick is
          noise; one sentence about the one they DID is the control explaining
          itself. */}
      {chosen?.consequence != null && (
        <p className="mt-3 text-sm text-neutral-700" data-workflow="write-mode-consequence">
          {chosen.consequence}
        </p>
      )}
    </div>
  );
}

export interface WriteModeStatedProps {
  value: string;
  options: readonly WriteModeOption[];
  onChangeRequested: () => void;
  t: Translator;
}

/**
 * ⛔ **THE COMMIT STEP STATES THE MODE AND DOES NOT OFFER IT AGAIN (DEF-770).**
 *
 * PO, on the deployed v2.51.0: *"Write mode from this screen may not required .
 * it is already added on step 1"*. They were right, and the reason is sharper
 * than the duplication: **two controls for one setting invite the question of
 * which one wins**, and there is no good answer to give.
 *
 * It is not simply deleted, because the commit about to happen DEPENDS on the
 * premise and an operator is entitled to read it on the screen where they press
 * the button. `Change it` walks back to the step that owns the control — a road
 * the wizard already had, now named.
 *
 * ⚠ **A WITHDRAWN MODE STILL RENDERS AS A SENTENCE.** A run committed before
 * 2026-08-27 carries `write_mode="replace"`, which is in no option list any
 * more. `options.find` misses, and the fallback prints the stored id rather
 * than an empty gap — an operator reading a historical receipt sees something
 * true rather than a blank where the premise should be.
 */
export function WriteModeStated({
  value,
  options,
  onChangeRequested,
  t,
}: WriteModeStatedProps) {
  const chosen = options.find((option) => option.id === value);
  return (
    <div
      className="mt-4 flex flex-wrap items-center gap-2 text-sm text-neutral-700"
      data-workflow="write-mode-stated"
    >
      <span>{t("workflow.writeMode.stated", { mode: chosen?.label ?? value })}</span>
      <Button variant="ghost" onClick={onChangeRequested}>
        {t("workflow.writeMode.change")}
      </Button>
    </div>
  );
}
