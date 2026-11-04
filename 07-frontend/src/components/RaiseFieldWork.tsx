// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-039 (EP-WRK-05) — the five flows raise their jobs.
//           Screens: Work-029 (`wireframes/Work-029.png`) · Work-020 ·
//           REQ-04 · MVO-01 step 2 · MVI-01 step 3 · TRF-01 step 2 · DSC-02
// Rules:    BR-WRK-055 (the flow does not wait for the visit and the visit does
//           not close the account; *No visit needed* is a recorded choice) ·
//           BR-WRK-016 (the offer is the utility's own PUBLISHED templates) ·
//           B14 rule 11 (a consequence preview before a commit) · rule 21
//           (Tailwind only, and only in a file on `route-b-migrated.txt`) ·
//           rule 31 (no database id is ever the visible value of a field) ·
//           rule 32 (one sentence per section) · rule 33 (a refusal is five or
//           six words) · rule 36 (the shared component kit is how you comply)
// Tests:    src/components/RaiseFieldWork.test.tsx
// Impacts:  features/customers/MoveOutWizard.tsx (step 2) · MoveInWizard.tsx
//           (step 3) · TransferWizard.tsx (step 2) · ServiceRequestDetailPage.tsx
//           (the Route action) · DisconnectWizard.tsx (the reconnect)
// ───────────────────────────────────────────────────────
//
// **ONE PANEL, FIVE HOSTS — never five copies** (`P4`, B14 rule 36). The five
// moments are different flows in different modules on different screens, and
// the QUESTION is identical every time: *does somebody have to attend, and what
// happens if I say yes?* Five copies of that question is five places for the
// consequence sentence to drift, and the consequence is the part a clerk reads.
//
// ⚠ **IT LIVES IN THE KIT AND NOT IN `features/work/`, DELIBERATELY.** Four of
// its five hosts are Customers screens. A component that four Customers screens
// import out of a Work feature folder is a module boundary drawn on a diagram
// and not in the code — and `ConsequenceBox` had exactly that shape until
// 2026-09-05, declared inside a screen file and read by four call sites.
//
// ⚠ **THIS FILE IS ON `route-b-migrated.txt`, ADDED IN THE COMMIT THAT CREATED
// IT** (B14 rule 21's per-file clause, `DEF-974`). A Tailwind utility written
// in a file that is not on that list is a class no stylesheet declares: it
// renders as NOTHING AT ALL while `tsc`, eslint and every `toContain` assertion
// pass, because the class IS in the DOM. Its two wizard hosts —
// `MoveOutWizard.tsx` and `MoveInWizard.tsx` — are NOT on the list and must add
// no class of their own; that is why every utility this panel needs is here.

/** One published template the flow could raise, as `GET /work/flows/…/proposed`
 *  serves it. `template_no` is the visible reference and the uuid is never
 *  drawn (B14 rule 31). */
export type FieldWorkTemplate = {
  template_id: string;
  template_no: string | null;
  name: string;
  service: { code: string; name: string } | null;
  scope: string;
  is_gate: boolean;
  est_duration_minutes: number | null;
};

/** What the flow could raise, and why it could not. */
export type FieldWorkOffer = {
  flow: { kind: string; id: string; ref: string | null };
  proposed: FieldWorkTemplate[];
  count: number;
  /** Judgment 8 — a request with no resolved address has no anchor to stand a
   *  job on, so the panel draws the refusal INSTEAD of the list. */
  refusal: { code: string; message_key: string } | null;
};

export type FieldWorkTemplateListProps = {
  offer: FieldWorkOffer | null | undefined;
  selected: readonly string[];
  onChange: (next: string[]) => void;
  t: (key: string, fallback: string, params?: Record<string, unknown>) => string;
  loading?: boolean;
  /**
   * What an offer of NO templates says, or `null` to say nothing at all.
   *
   * ⚠ **`null` IS FOR A HOST WHERE THE SENTENCE IS NOT THE CLERK'S BUSINESS.**
   * *"This utility has published no field-work templates for this moment yet"*
   * explains OUR data model to somebody selling a house; B14 rule 33 puts
   * rationale at zero words on screen. Default is the sentence every existing
   * host already shows, so nothing moves unless a host asks.
   */
  emptyLabel?: string | null;
  /**
   * The trailing *No visit needed* row, or `null` to omit it.
   *
   * ⚠ **IT IS A PROP BECAUSE IT IS ONLY TRUE OF SOME HOSTS, NOT BECAUSE IT IS
   * DECORATION.** In a wizard the question *does somebody have to attend?* is
   * asked in passing while a clerk finishes a move-out, so NOT ticking is
   * ambiguous and `Work-029` is explicit that *"No visit needed is a recorded
   * choice, not an unticked box"*. In a dialog a person opened BY PRESSING
   * *Send someone out*, that same row offers to cancel the thing they just
   * asked for, twice, beside a Cancel button. Omitting it there is that rule
   * being obeyed rather than skipped.
   */
  noVisitLabel?: string | null;
};

/**
 * **THE OFFER ITSELF — the four states a list of proposed jobs has, in ONE
 * place** (B14 rule 36: where the kit lacks a piece, add it to the kit).
 *
 * Split out of `RaiseFieldWork` on 2026-09-14 when the Reads→Work door became
 * its SIXTH host and needed the list without the wizard furniture around it.
 * ⚠ **THE MARKUP IS UNCHANGED, DELIBERATELY.** Same elements, same utilities,
 * same `data-` attributes — the five existing hosts render byte-for-byte what
 * they rendered before, which is what makes this an extraction rather than a
 * redesign nobody scoped.
 */
export function FieldWorkTemplateList({
  offer,
  selected,
  onChange,
  t,
  loading = false,
  noVisitLabel = null,
  emptyLabel,
}: FieldWorkTemplateListProps) {
  const picked = new Set(selected);
  const proposed = offer?.proposed ?? [];
  const refusal = offer?.refusal ?? null;

  const toggle = (templateId: string) => {
    const next = new Set(picked);
    if (next.has(templateId)) next.delete(templateId);
    else next.add(templateId);
    onChange([...next]);
  };

  return (
    <>
        {refusal !== null ? (
          // B14 rule 33 — five or six words, and its own catalogue key so all
          // eleven languages carry it (G15, G32).
          <p className="text-body font-bold text-danger-700" data-field-work-refusal={refusal.code}>
            {t(refusal.message_key, "Resolve the address first.")}
          </p>
        ) : loading ? (
          <p className="text-body text-neutral-600">
            {t("work.fieldVisit.loading", "Looking up the jobs…")}
          </p>
        ) : proposed.length === 0 ? (
          emptyLabel === null ? null : (
            <p className="text-body text-neutral-600" data-field-work-empty="">
              {emptyLabel ??
                t(
                  "work.fieldVisit.none",
                  "This utility has published no field-work templates for this moment yet.",
                )}
            </p>
          )
        ) : (
          <ul className="flex flex-col gap-2">
            {proposed.map((template) => (
              <li key={template.template_id}>
                <label className="flex cursor-pointer items-start gap-3 border border-neutral-200 p-3">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={picked.has(template.template_id)}
                    onChange={() => toggle(template.template_id)}
                    data-field-work-template={template.template_no ?? template.name}
                  />
                  <span className="text-body text-neutral-900">
                    <span className="font-bold">
                      {t("work.fieldVisit.raise", "Raise a work order for {{name}}", {
                        name: template.name,
                      })}
                    </span>
                    <span className="block text-neutral-600">
                      {[
                        template.service?.name ?? null,
                        template.name,
                        template.est_duration_minutes === null
                          ? null
                          : t("work.fieldVisit.minutes", "{{count}} min", {
                              count: template.est_duration_minutes,
                            }),
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </span>
                </label>
              </li>
            ))}
            {noVisitLabel !== null && (
              <li>
                <label className="flex cursor-pointer items-start gap-3 border border-neutral-200 p-3">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={picked.size === 0}
                    onChange={() => onChange([])}
                    data-field-work-none=""
                  />
                  <span className="text-body font-bold text-neutral-900">{noVisitLabel}</span>
                </label>
              </li>
            )}
          </ul>
        )}
    </>
  );
}

