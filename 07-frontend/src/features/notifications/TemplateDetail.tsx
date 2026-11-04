// ── Trace ──────────────────────────────────────────────
// Story:    CR-007 (SET-10 the template detail — variant switcher, live
//           preview, merge-fields panel, editing, variant management and
//           version history with restore)   Screens: SET-10
// Rules:    BR-NOT-001 · BR-NOT-006 · BR-NOT-014 · BR-NOT-015 · BR-BIL-026
//           (an edit is a NEW version) · BR-BIL-027 (System Admin publishes) ·
//           BR-SHL-020 (plain-language failure) · BR-SHL-025 (disabled WITH
//           its reason, never hidden) · CLAUDE.md rule 4 (a published body is
//           evidence of what a customer was sent)
// ───────────────────────────────────────────────────────
// SET-10 — ONE TEMPLATE: WHAT IT SAYS, WHAT IT MAY SAY, AND WHAT IT SAID.
//
// ══ CR-199-BRC10 · 2026-10-29 · THE SCREEN IS `TemplateWorkspace` NOW ═════
// The redesign (`05-prototype/templates-redesign-2026-10-29/images/`) redrew
// SET-10 end to end, and B14 rule 43 says each piece is a component: the
// pickers, the action bar, the wording pane, the placeholder picker, the live
// preview, the variant form and the history are each their own file, and
// `TemplateWorkspace.tsx` composes them. **This file now holds the PARTS the
// redesign kept** — the head's meta line, the three-word control note, the
// contract offer and *Create from our default*, the variant's lifecycle
// controls, the surface tabs, the change record — and the pure helpers.
// The reading view, the designer, the composer, the merge-field rail, the old
// preview pane and the history PAGE are DELETED rather than left unreferenced
// (hard-won law 1); `CR-199-BRC10` §6 says where each of their actions went.
//
// ── EVERY REFUSAL ON THIS SCREEN IS THE SERVER'S OWN SENTENCE ─────────────
// Not one of them is composed here. The save refusal, the three disabled
// controls, the "no body yet" notice and the fallback explanation all arrive as
// strings on the payload, because a screen that worded them itself would drift
// from the ruling the moment either changed — hard-won law 1, and the reason
// the backend serves prose rather than flags.
//
// ── THE EDITOR AND THE PREVIEW SHARE ONE VALIDATOR, ON PURPOSE ────────────
// `POST …/preview` and `POST …/draft` both run `rendering.validate_body`, so a
// body the pane renders is a body the save accepts and a body the save refuses
// never renders. An editor whose preview is more permissive than its save
// teaches somebody to write a letter that cannot be published.
//
// ── WHY "SAVE" NEVER OVERWRITES ───────────────────────────────────────────
// BR-BIL-026: every edit is a new append-only version, and the one that is LIVE
// keeps rendering until a System Admin publishes. So the editor's button says
// *Save as new version* rather than *Save*, and publishing is a second,
// deliberate act — because publishing is the moment a customer's next letter
// changes.
//
// ── RESTORE PUTS AN OLD BODY IN A NEW DRAFT, NEVER BACK IN ITS OLD ROW ────
// A published version is evidence of what a customer was sent (rule 4) and the
// database refuses to rewrite one. So restoring v2 produces v4 holding v2's
// body, v2 is untouched, and every message pinned to v2 still renders v2.
//
// ── THE FOUR THINGS THIS SCREEN LEARNED ON 2026-08-18 (DEF-209 · DEF-212) ──
//  1. **THE WAY BACK IS TWO STEPS AND THE SCREEN NOW SAYS SO.** There is no
//     unarchive in `template_service` and no route for one, so a one-click
//     Reactivate would be a button onto nothing. What EXISTS is
//     `POST …/restore` → `POST …/publish`: the archived version's wording comes
//     back as a NEW draft, which a System Admin then publishes. The control
//     renders DISABLED WITH THAT PATH AS ITS REASON (BR-SHL-025) rather than
//     being hidden, because a person who has just deactivated a variant looks
//     for exactly that control and used to find nothing (DEF-209 remainder).
//  2. **A SAVED DRAFT IS REACHABLE.** The editor used to seed itself from the
//     PUBLISHED version always, so an edit saved and not published could not be
//     opened again — which made `save_draft` pointless to a human (DEF-212 (1)).
//     It now opens the newest DRAFT when there is one, says WHICH version it
//     holds, and every history row carries an ✎ that loads that version.
//  3. **"INACTIVE" WAS TWO STATES WEARING ONE WORD** (DEF-212 (3)): a variant
//     nobody has published yet and a variant somebody deactivated. Only one of
//     them can be deactivated, and pressing the control on the other was
//     REFUSED by the server after the click. The badge now separates them and
//     the control renders disabled with its reason BEFORE the click.
//     ⚠ THE BADGE NEVER SAYS "Deactivated" WITHOUT PROOF: it is drawn from an
//     `archived_at` on a version this screen actually holds. Where the payload
//     cannot prove which of the two it is (a tab that is not the selected one
//     carries a count and no versions), it says the weaker true thing.
//  4. **THE EDITOR IS REMOUNTED PER VARIANT** (`key`). Its body is React state
//     seeded once from the payload; re-selecting an already-cached variant kept
//     the previous variant's text in the textarea, and Save posts the TEXTAREA
//     to the SELECTED variant — so the wrong wording could be saved against the
//     wrong audience without anybody typing a character.
//
// ══════════════════════════════════════════════════════════════════════════
//  THE RULE THIS SCREEN KEEPS BREAKING — READ IT BEFORE ADDING ANY TEXT
//  (CR-048 wave I, 2026-08-30)
// ══════════════════════════════════════════════════════════════════════════
//
// **A CONTROL HOLDS A LABEL. A TABLE CELL HOLDS A VALUE. THE SENTENCE THAT
// EXPLAINS EITHER BELONGS IN A TOOLTIP, IN AN OPENED DETAIL, OR IN HELP — AND
// IS NEVER RENDERED INLINE.**
//
// The Product Owner walked the deployed v2.83.0 screen by screen and found that
// one mistake **TEN TIMES IN A SINGLE SITTING**, most of them on THIS page.
// Their words, repeatedly: *"again too much text content breking the UI"* and
// *"just use 3 or 4 wrods and fix the UI"*. It is not a copy preference. Prose
// rendered where a value belongs sets the height of the thing containing it, so
// a 249-character note in a version-history cell drew a **645px-tall row** in a
// 344px-wide panel, and a merge-field badge under every token doubled the height
// of every row of the table.
//
// ── HOW TO FIX ONE, AND IT IS NOT "DELETE THE SENTENCE" ───────────────────
// The PO ratified the shape the same morning, for a different note, verbatim:
// *"keep the fact, kill the paragraph — a small greyed marker on the row, and
// the full sentence only when you open that event. Same protection, no
// wreckage."*
//
// So: **three or four words on screen, the whole sentence one hover away.**
// Several of the sentences on this page are the honest answer to *"why is this
// control dead"* (BR-SHL-025), and **a control that refuses silently is a worse
// defect than a long sentence** — deleting them would trade a layout bug for a
// usability one. Every `*_label` on the payload is the on-screen half and every
// `*_reason` is the tooltip half; they are served as a PAIR and neither is
// optional.
//
// ── AND THE ID RULE RIDES WITH IT (DEF-335, DEF-2478, DEF-2479) ───────────
// Rule ids, open-question ids, module paths and column names NEVER appear in a
// sentence a clerk reads. They travel on `data-br-ref`, from a `*_br_ref` field,
// where support reaches them off the DOM and a water utility never does. G28
// enforces this for API modules; it did NOT catch `download_pdf_reason` (which
// had been entered in the gate's own baseline file) or the preview's absence
// notes (which live in service modules the gate does not sweep).
//
// ⚠ **NOTHING AUTOMATED CAN SEE ANY OF THIS.** jsdom performs no layout, so
// every one of these passed `tsc`, eslint and 220 DOM cases while the screen was
// unusable. The check that finds them is
// `10-scripts/render-checks/cr048-notifications-geometry.mjs`, which measures
// HEIGHT and OVERFLOW in a real browser — extend it rather than trusting a
// `toContain`.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import {
  createTemplateFromDefault,
  deactivateTemplateVariant,
  fetchTemplateChange,
} from "@/api/endpoints";
import type { TemplateDetail, TemplateVariantRow, TemplateVersionRow } from "@/api/endpoints";
import { ContractSurface } from "./templateSurfaces";
import {
  ACTIONS,
  CHIPS,
  DESC,
  HEAD_META,
  HEAD_META_ABSENT,
  HEAD_META_SEP,
  INBOX_LINES,
  INLINE_FORM,
  MUTED,
  SUBHEAD,
} from "./notificationsKit";
import { ConfirmDialog } from "@/components/ConfirmDialog"; // DEF-209
import { DatePickerField } from "@/components/FormModal";
import { useRegional } from "@/features/metering/meteringShared";
import { Button } from "@/components/Button";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import { apiErrorText, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";

/** *"Where it's used"* — CR-007 addendum A: **ONE PLAIN SENTENCE, not a list of
 *  ids** (DEF-212, last item). Thirty-four of the thirty-six classes already
 *  answer in English (*"Nothing yet — move-in queues no notice"*); the two that
 *  are actually WIRED answered with the Python path that consumes them —
 *  `notices.generate_reminder — dunning stages 1-2 (BR-NOT-008)` — which is the
 *  one shape a System Admin cannot read.
 *
 *  So this drops a LEADING `module.function —` and nothing else. The rule id
 *  stays: every other row carries one, and stripping citations here would make
 *  two classes cite less than the thirty-four beside them. Narrow on purpose —
 *  a sentence with no code path in front of it is returned untouched, so this
 *  can never quietly reword the server. */
export function plainUsedBy(raw: string): string {
  const match = /^[a-z_]+(?:\.[a-z_]+)+\s*[—–-]\s*(.+)$/.exec(raw);
  if (match === null) {
    return raw;
  }
  const rest = match[1];
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

/** What the payload can PROVE about a variant's state (DEF-212 (3)).
 *
 *  `active` means "has a live published version" and nothing else, so its
 *  negation covers two different situations with two different answers. This
 *  returns the strongest statement the data supports and never guesses:
 *  `deactivated` requires an `archived_at` on a version in hand.
 */
export type VariantState = "live" | "unpublished" | "deactivated" | "not-live";

/**
 * THE CATALOGUE KEY FOR EACH STATE — and it exists because one of them was
 * WRONG ON SCREEN (`DEF-NOT-4444`).
 *
 * The screen built its key by interpolation — ``templates.detail.state.${state}``
 * — and `i18n/index.ts` sets `keySeparator: false`, so the catalogue key is one
 * FLAT string that has to match character for character. Three of the four did.
 * The fourth is `not-live` in this file's own vocabulary and `notLive` in all
 * eleven catalogues, so a variant that has wording nobody published rendered
 * the literal text **`templates.detail.state.not-live`** in a badge beside its
 * name — the raw key, on a clerk's screen.
 *
 * ⚠ **NOTHING COULD SEE IT AND THE REASONS ARE WORTH KNOWING.** `tsc` cannot:
 * `t()` takes a string. G15 checks the eleven catalogues hold the SAME keys as
 * each other, which they do — the key is missing from all eleven equally.
 * `TemplateDetail.test.tsx` asserts `variantStateOf` returns `"not-live"`,
 * which it does; no test renders that badge. And the state needs a variant with
 * versions and nothing published, which no fixture had.
 *
 * ⚠ **A MAP AND NOT AN INTERPOLATION, AND THAT IS THE ACTUAL FIX.** Renaming
 * either side would work once; a literal key per state is what makes the next
 * mismatch a compile error instead of a string on a screen, and it is what
 * every key-scanning check in this repo can actually read.
 */
export const VARIANT_STATE_KEY: Record<Exclude<VariantState, "live">, string> = {
  unpublished: "templates.detail.state.unpublished",
  deactivated: "templates.detail.state.deactivated",
  "not-live": "templates.detail.state.notLive",
};

export function variantStateOf(
  variant: TemplateVariantRow,
  versions: TemplateVersionRow[] | null,
): VariantState {
  if (variant.active) {
    return "live";
  }
  if (versions !== null && versions.some((version) => version.archived_at !== null)) {
    return "deactivated";
  }
  if (variant.version_count === 0) {
    return "unpublished";
  }
  // Something has been written and nothing is live: a draft nobody published,
  // or a dated publication (BR-NOT-002) this screen cannot date-resolve. Both
  // are honestly "not live"; neither is "deactivated".
  return "not-live";
}


/**
 * THE HEAD'S ONE META LINE — the surface set, where it is used, and when it was
 * last edited.
 *
 * The design draws four facts here: *"PDF + e-bill email · All bill runs · last
 * edited Jul 12 · Alex Reed"*. **This product serves three of them.**
 *
 * ⚠ **THE AUTHOR'S NAME IS NOT SERVED AND IS NAMED AS ABSENT RATHER THAN
 * FAKED (BR-SHL-020).** `TemplateVersionRow.author_label` is documented on its
 * own field as *"the id, or the platform, never a name"*, and the column behind
 * it is a `UUIDField` — identity's display names are another module's table
 * (B11 F-3, `OQ-255`). So drawing it would put a database id on screen, which
 * B14 rule 31 forbids in the Product Owner's own words (*"no Databse ID on
 * screen - that is a rule"*), and inventing a name would claim somebody
 * authorised wording they have never seen. The line says the fact is not
 * recorded, in four words, and stops.
 *
 * ⚠ **"LAST EDITED" IS THE SELECTED VARIANT'S, BECAUSE THAT IS WHAT IS IN
 * HAND.** The detail payload carries versions for the SELECTED variant only, so
 * this is the newest of those and the label says *this wording*. The catalogue
 * row's `edited` — the whole class's — is not on this payload at all.
 */
export function HeadMeta(props: { data: TemplateDetail }) {
  const { t } = useTranslation();
  // `versions` arrives newest-first (`order_by("-version")`), so the newest
  // EDIT is the first row. Not `editorSource`, which prefers a draft: that is
  // the question *"what would the editor open"*, and this is *"when did this
  // wording last move"*.
  const newest = props.data.versions[0];
  const facts: React.ReactNode[] = [
    <span key="kind" data-testid="head-kind">
      {props.data.kind}
    </span>,
    <span key="used" data-testid="head-used-by">
      {plainUsedBy(props.data.used_by)}
    </span>,
    newest === undefined ? (
      <span key="edited" className={HEAD_META_ABSENT} data-testid="head-never-edited">
        {t("templates.detail.neverEdited")}
      </span>
    ) : (
      <span key="edited" data-testid="head-edited">
        {t("templates.detail.lastEdited", { date: newest.updated_at.slice(0, 10) })}
      </span>
    ),
  ];
  // ⚠ **`DEF-NOT-4531` — THIS LINE USED TO BE UNCONDITIONAL.** It said *author
  // not recorded* on every version there is, which is TRUE of a seeded body
  // (provisioning writes no author on purpose) and FALSE the moment a System
  // Admin saves a draft — their id is stamped, so the author IS recorded and
  // what we lack is a NAME (a uuid is a database id on screen, B14 rule 31, and
  // identity publishes no display names). Asserting the wrong one of those two
  // is the same shape as the `used_by` sentence the same defect fixed: a
  // hard-coded literal standing in for a fact the server knows.
  //
  // Where an author IS recorded the fact is simply OMITTED rather than replaced
  // with a longer apology — B14 rule 32's description budget, and the meta line
  // already carries *last edited <date>*, which is what a person came for.
  // `!== true` and not `=== false`: a server that has not been redeployed
  // serves no such field, and the honest absence is what it printed before.
  if (newest === undefined || newest.author_recorded !== true) {
    facts.push(
      <span
        key="author"
        className={HEAD_META_ABSENT}
        data-testid="head-author-absent"
        title={t("templates.detail.authorUnknownWhy")}
        aria-description={t("templates.detail.authorUnknownWhy")}
      >
        {t("templates.detail.authorUnknown")}
      </span>,
    );
  }
  return (
    <p className={HEAD_META} data-testid="head-meta">
      {facts.map((fact, index) => (
        <Fragment key={index}>
          {index > 0 && (
            <span className={HEAD_META_SEP} aria-hidden="true">
              ·
            </span>
          )}
          {fact}
        </Fragment>
      ))}
    </p>
  );
}




/** A small greyed marker: THREE OR FOUR WORDS, with the whole sentence on hover.
 *
 * ⚠ **THIS COMPONENT IS THE FIX FOR TEN SEPARATE PO REPORTS**, so read the
 * screen's own rule above before changing it. It replaces the shape that was
 * everywhere on this page — a `<p className={DESC}>` holding a served paragraph
 * under a control — with the shape the PO ratified: *"keep the fact, kill the
 * paragraph — a small greyed marker on the row, and the full sentence only when
 * you open that event."*
 *
 * ⚠ **`reason` IS NOT OPTIONAL AND MUST NOT BECOME SO.** A marker reading
 * "Default is fixed" with no reachable explanation is a control that refuses
 * and will not say why — BR-SHL-025's exact prohibition, and a worse defect
 * than the paragraph this replaces. It is on `title` (so a mouse reaches it)
 * AND on `aria-description` (so a screen reader does), because a tooltip nobody
 * can focus is not an explanation.
 *
 * `brRef` is the DEF-335 machine field: support reads the rule ids off the DOM
 * and a water utility never sees them.
 */
export function ControlNote(props: {
  label: string;
  reason: string;
  testId: string;
  brRef?: string;
}) {
  return (
    /* ⚠ **NO `data-desc` — AND THAT IS A CLAIM, NOT AN OVERSIGHT.** That
       attribute marks a DESCRIPTION, and B14 rule 18 holds every description to
       the 80% measure (`max-w-measure`) so a paragraph does not run the width of
       the page. This is a three-word LABEL: it has no measure to keep, and
       tagging it as a description would either fail rule 18's check or force a
       `max-width` onto something eight characters wide. `TemplateDetail.test.tsx`
       asserts rule 18 over every `data-desc` on the screen, so this distinction
       is enforced rather than merely asserted here. */
    <span
      className={CONTROL_NOTE}
      data-control-note
      data-testid={props.testId}
      data-br-ref={props.brRef}
      title={props.reason}
      aria-description={props.reason}
    >
      {props.label}
    </span>
  );
}

/** The marker's own look: muted, small, and carrying a dotted underline that
 *  says "there is more here on hover" — the affordance a bare grey word does
 *  not have. `w-fit` because a flex column stretches its children and a
 *  full-width underline reads as a divider (the `self-start` lesson one
 *  component up, which was itself a defect). */
const CONTROL_NOTE =
  "mt-1 w-fit cursor-help text-sm underline decoration-dotted underline-offset-2 " +
  "text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]";

/**
 * CR-011 item 9 — WHAT A CLASS WITH NO VARIANT HAS TO SAY, drawn where a
 * person is looking.
 *
 * ⚠ **IT LEFT `VariantSwitcher` ON 2026-09-07 AND THE MOVE IS THE POINT
 * (`DEF-NOT-4456`).** The four contract classes carry wording the platform
 * OFFERS and deliberately does not seed: BR-NOT-002 makes a contract
 * effective-dated and that date is a human's choice, not the day provisioning
 * ran. So the body arrives on the payload and never as a version — which means
 * **this block IS the document** on those four screens, and when the variant
 * controls moved to the 320px rail it went with them. A contract's own wording
 * in a rail, under a main column reading *"Type a body to see it render"*, is
 * hard-won law 2 wearing a tidy layout.
 */
export function PlatformDefaultOffer(props: {
  data: TemplateDetail;
  code: string;
  client: ApiClient;
  readOnly: boolean;
  /** The new variant's id — the screen opens it in the editor. */
  onCreated: (variantId: string) => void;
  onRefusal: (refusal: Refusal | null) => void;
}) {
  const { t } = useTranslation();

    // CR-011 item 9 — A CLASS WITH NO VARIANT IS NOT ALWAYS A CLASS WITH
    // NOTHING TO SAY. The four contract classes carry wording the platform
    // OFFERS and deliberately does not seed: BR-NOT-002 makes a contract
    // effective-dated and that date is a human's choice, not the day
    // provisioning ran. So the body arrives on the payload and never as a
    // version, and a screen that only knew how to render versions would show
    // "no variant yet" over wording that is sitting right there — served and
    // invisible, which is hard-won law 2.
    const offer = props.data.platform_default;
    if (offer !== null) {
      return (
        <div data-testid="platform-default-offer">
          <h3 className={SUBHEAD}>{t("templates.detail.offer.heading")}</h3>
          {/* The server's OWN sentences, never composed here — the same posture
              every refusal on this screen takes, so the wording cannot drift
              from the ruling that set it. */}
          <p className={DESC} data-desc data-testid="offer-label">
            {offer.label}
          </p>
          <p className={DESC} data-desc data-testid="offer-notice">
            {offer.notice}
          </p>
          {offer.is_placeholder && (
            <RefusalStrip data-testid="offer-placeholder-warning">
              {t("templates.detail.offer.placeholderWarn")}
              {offer.placeholder_marker !== null && ` (${offer.placeholder_marker})`}
            </RefusalStrip>
          )}
          {offer.requires_from_utility.length > 0 && (
            <>
              <h4 className={SUBHEAD} data-testid="offer-requires-heading">
                {t("templates.detail.offer.requiresHeading")}
              </h4>
              <ol className={DESC} data-desc data-testid="offer-requires">
                {offer.requires_from_utility.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ol>
            </>
          )}
          {offer.requires_effective_date && (
            <p className={DESC} data-desc data-testid="offer-date-required">
              {t("templates.detail.offer.dateRequired")}
            </p>
          )}
          {/* ⚠ **THE OFFERED WORDING IS A DOCUMENT AND IS DRAWN AS ONE.** It was
              a `<pre>` carrying the raw string, which is exactly the shape
              `DEF-NOT-4465` was filed about one surface along — and it applied
              to the four documents a customer actually SIGNS, so the classes
              where the drawing matters most were the ones getting the blob.
              `ContractSurface` gives it the page's typography and puts a real
              signature block where the author's own signature line falls.
              ⚠ It still carries its `{tokens}` unresolved, and that is correct
              rather than unfinished: nobody has published this wording, so
              there is no version to render it against. The two sentences above
              (`offer-label`, `offer-notice`) are the server's own and say so. */}
          {!props.readOnly && (
            <CreateFromDefault
              code={props.code}
              client={props.client}
              onCreated={props.onCreated}
              onRefusal={props.onRefusal}
            />
          )}
          <div data-testid="offer-body">
            <ContractSurface body={offer.body} data={props.data} />
          </div>
        </div>
      );
    }
    return (
      <p className={DESC} data-desc data-testid="variant-none">
        {t("templates.detail.noVariants")}
      </p>
    );
}

/**
 * `CR-190-BRC10` — *Create from our default*, one click (PO 2026-10-22, *"keep
 * your rule (each utility publishes its own) but make it one click"*).
 *
 * The admin picks the date it takes effect — BR-NOT-002 still makes that a
 * person's choice — and the server creates the variant and a DRAFT holding the
 * platform's wording. The screen then opens that draft in the editor, where the
 * existing Publish action makes it live. Non-admins never see this
 * (`readOnly`), and the server refuses them too.
 */
function CreateFromDefault(props: {
  code: string;
  client: ApiClient;
  onCreated: (variantId: string) => void;
  onRefusal: (refusal: Refusal | null) => void;
}) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const { dateFormat } = useRegional({});
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const create = useMutation({
    mutationFn: () =>
      createTemplateFromDefault(props.code, { effective_from: effectiveFrom }, props.client),
    onSuccess: async ({ variant }) => {
      props.onRefusal(null);
      fireToast(t("templates.detail.offer.created"));
      await queryClient.invalidateQueries({ queryKey: ["template-catalog"] });
      props.onCreated(variant.id);
    },
    onError: (error: unknown) => props.onRefusal(refusalOf(error, t)),
  });
  return (
    <form
      className={INLINE_FORM}
      data-testid="create-from-default"
      onSubmit={(event) => {
        event.preventDefault();
        create.mutate();
      }}
    >
      <DatePickerField
        id="from_default_effective_from"
        label={t("templates.detail.offer.takesEffect")}
        dateFormat={dateFormat}
        value={effectiveFrom}
        onChange={setEffectiveFrom}
        required
      />
      <div className={ACTIONS}>
        <Button
          variant="primary"
          type="submit"
          disabled={create.isPending || effectiveFrom === ""}
          data-testid="create-from-default-submit"
        >
          {t("templates.detail.offer.create")}
        </Button>
      </div>
    </form>
  );
}

/**
 * WHAT MAY BE DONE TO THE OPEN VARIANT — Deactivate, and the way back.
 *
 * ⚠ **IT WAS CALLED `VariantSwitcher` AND IT NO LONGER SWITCHES ANYTHING.** The
 * TABS left for the shared page header on 2026-09-07 (B14 rule 36) and the
 * platform-default OFFER left for the main column the same day
 * (`PlatformDefaultOffer` above, `DEF-NOT-4456`), so the old name described a
 * component that had stopped doing either job — hard-won law 1's shape applied
 * to a symbol rather than to a comment. What is left is a lifecycle pair, and
 * it is drawn in the rail: reachable, in the danger tier, and not in front of
 * the thing a person opened the screen to look at.
 *
 * ⚠ **`data-testid="variant-switcher"` IS UNCHANGED ON PURPOSE.** Three suites
 * and the CR-048 render-check select this block by name; it still answers the
 * same question (*what may I do to this variant*) and renaming it would cost a
 * rename in four files to say nothing new.
 */
export function VariantLifecycle(props: {
  data: TemplateDetail;
  selected: string | null;
  readOnly: boolean;
  code: string;
  client: ApiClient;
  onRefusal: (refusal: Refusal | null) => void;
}) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState<string | null>(null);
  const deactivate = useMutation({
    mutationFn: (id: string) => deactivateTemplateVariant(props.code, id, props.client),
    onSuccess: async () => {
      props.onRefusal(null);
      /* DEF-NOT-10689 — the screen's own sentence. `consumers.detail` is the
         server's English diagnostic (it cites an internal rule) and is for
         support, not for a clerk. */
      fireToast(t("templates.detail.deactivatedToast"));
      await queryClient.invalidateQueries({ queryKey: ["template-catalog"] });
    },
    onError: (error: unknown) => props.onRefusal(refusalOf(error, t)),
  });
  // A class with no variant has no lifecycle to offer. What it DOES have to
  // say — the platform's offered wording, or "no variant yet" — is drawn in
  // the main column by `PlatformDefaultOffer`, because on the four contract
  // classes that block IS the document.
  if (props.data.variants.length === 0) {
    return null;
  }
  const selectedVariant =
    props.data.variants.find((variant) => variant.id === props.selected) ?? null;
  // Only the SELECTED variant's versions are on the payload, so only it can be
  // asked whether anything was ever archived (DEF-212 (3)).
  const selectedState =
    selectedVariant === null ? null : variantStateOf(selectedVariant, props.data.versions);
  // BR-SHL-025: this is the sentence the control carries BEFORE the click. It
  // is the screen's own — the server's refusal only exists after a POST — and
  // it deliberately says the same thing the route's refusal says, so a person
  // who clicks past it is not told something new.
  const nothingToDeactivate =
    selectedState !== null && selectedState !== "live"
      ? t("templates.detail.deactivateUnavailable")
      : null;

  return (
    /* ⚠ **THE TAB STRIP LEFT THIS COMPONENT ON 2026-09-07 AND ONLY THE
       LIFECYCLE CONTROLS REMAIN.** The variant TABS are the shared page
       header's now (B14 rule 36 — one strip, one visual decision, every
       screen), and they were never the same thing as the three controls below:
       a tab SELECTS, and Deactivate ARCHIVES A PUBLISHED VERSION. Drawing a
       destructive commit inside a tab strip is how it got the danger tier and
       a confirm dialog bolted on afterwards (DEF-209).

       ⚠ **THE `data-testid` IS UNCHANGED ON PURPOSE.** Three suites and the
       CR-048 render-check select this block by name; the block still answers
       the same question (*what may I do to this variant*) and renaming it
       would cost a rename in four files to say nothing new. */
    <div className={ACTIONS} data-testid="variant-switcher">
      {/* ⚠ **`Set as default` IS NOT HERE ANY MORE — IT IS IN THE PREVIEW
          STRIP**, where the design puts it and where it answers the question a
          person is actually asking while looking at a rendered document: *is
          this the one my letters fall back to?* It is the same control, still
          disabled, still carrying `set_default_reason` and `set_default_br_ref`
          (OQ-252, DEF-335) — see `PreviewStrip`. */}
      {props.selected !== null && (
        <Button
          variant="danger"
          // DEF-209, ruled by the PO 2026-08-17 ("Okay"): a destructive commit
          // takes the DANGER tier (B14 rule 6) and asks first (rule 11). It used
          // to fire on one click, in an unstyled default button, with no way
          // back — and on the default variant that leaves the class with nothing
          // to resolve.
          // ⚠ DEF-212 (3): it is DISABLED WITH ITS REASON when there is nothing
          // to deactivate, instead of being live, clicked, and refused by the
          // server afterwards. Being told a variant is inactive and then told
          // you may not deactivate it is the same fact arriving twice, the
          // second time as an error.
          disabled={props.readOnly || deactivate.isPending || nothingToDeactivate !== null}
          title={
            nothingToDeactivate ??
            (props.readOnly ? (props.data.cannot_edit_reason ?? "") : undefined)
          }
          onClick={() => setConfirming(props.selected as string)}
          data-testid="deactivate-variant"
        >
          {t("templates.detail.deactivate")}
        </Button>
      )}

      {/* ── DEF-209's REMAINDER · THE WAY BACK, SAID OUT LOUD ──────────────
          There is no unarchive in `template_service` and no route for one, so
          a live Reactivate button would be a control onto nothing. What EXISTS
          is two steps — `POST …/restore` brings the archived wording back as a
          NEW DRAFT (history is never rewritten, CLAUDE.md rule 4) and
          `POST …/publish` makes that draft live. The screen never mentioned
          it, which is what made "no way back" true in practice.
          BR-SHL-025: rendered, DISABLED, carrying the path as its reason. */}
      {props.selected !== null && (
        <Button
          variant="secondary"
          disabled
          title={t("templates.detail.reactivateHelper")}
          data-testid="reactivate-variant"
        >
          {t("templates.detail.reactivate")}
        </Button>
      )}
      {/* CR-048 wave I — the 303-character "there is no one-click reactivate"
          explanation was a paragraph under the button. It is the SAME string
          the disabled button already carries as its `title`, so rendering it
          inline said everything twice and set the panel's height. */}
      {selectedState === "deactivated" && (
        <ControlNote
          label={t("templates.detail.reactivateLabel")}
          reason={t("templates.detail.reactivateHelper")}
          testId="reactivate-helper"
        />
      )}

      {confirming !== null && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): deactivate a template variant.
          confirmVariant="danger"
          title={t("templates.detail.deactivateConfirmTitle", {
            name: props.data.variants.find((v) => v.id === confirming)?.name ?? "",
          })}
          // ⚠ THE CONSEQUENCE IS NOT ONE SENTENCE, because deactivating the
          // DEFAULT variant is a materially different act. BR-NOT-006 makes
          // every other variant fall back to the default; the default has
          // nothing to fall back to, so the class is left unable to produce
          // anything and generation HOLDS. A single generic warning would let a
          // System Admin walk into the worse of the two believing it was the
          // milder one.
          // ⚠ AND THE WAY BACK IS PART OF THE CONSEQUENCE (DEF-209 remainder).
          // B14 rule 11 asks what this will DO; a destructive commit whose
          // reversal costs two steps and a new version has to say so before the
          // click, not after it.
          consequence={`${
            props.data.variants.find((v) => v.id === confirming)?.is_default
              ? t("templates.detail.deactivateConfirmDefault")
              : t("templates.detail.deactivateConfirmFallback")
          } ${t("templates.detail.reactivateHelper")}`}
          confirmLabel={t("templates.detail.deactivate")}
          working={deactivate.isPending}
          onConfirm={() => {
            const id = confirming;
            setConfirming(null);
            deactivate.mutate(id);
          }}
          onCancel={() => setConfirming(null)}
        />
      )}

      {/* A variant carries a language; a message picks the one in the
          UTILITY's language and never the customer's (OQ-CUS-12619,
          2026-09-23). The words are the server's.
          CR-048 wave I: three words on screen, the sentence on hover. */}
      <ControlNote
        label={props.data.language_selection_label}
        reason={props.data.language_selection_reason}
        testId="language-note"
        brRef={props.data.language_selection_br_ref}
      />
    </div>
  );
}

/** Which version the editor opens (DEF-212 (1)).
 *
 *  ⚠ IT USED TO BE `published ?? versions[0]`, ALWAYS, and that is the whole
 *  defect: once a variant had a published version, a draft saved and not
 *  published could not be opened again from any screen in the product. The only
 *  route back to your own unfinished wording was Restore, which makes a THIRD
 *  version holding it. A drafting workflow you cannot resume is not one.
 *
 *  Order: the row a person explicitly opened with the ✎ · else the newest DRAFT
 *  (unfinished work is what somebody left off doing) · else the live one · else
 *  whatever exists. `versions` arrives newest-first (`order_by("-version")`).
 */
export function editorSource(
  versions: TemplateVersionRow[],
  openVersionId: string | null,
): TemplateVersionRow | undefined {
  const chosen = versions.find((row) => row.id === openVersionId);
  if (chosen !== undefined) {
    return chosen;
  }
  return (
    versions.find((row) => row.status === "draft") ??
    versions.find((row) => row.status === "published") ??
    versions[0]
  );
}


/**
 * CR-048 E2 — THE FIVE KINDS, resolved ONCE for the whole screen.
 *
 * *"Five kinds, one screen: printable · email · SMS · in-app · contract."*
 *
 * ⚠ **`group` IS THE SERVED FIELD THAT ANSWERS THIS, AND IT IS NOT `category`
 * OR `kind`.** `catalogs.py` is explicit: *"`group` is the CHANNEL family
 * (printable / email / sms / contracts) and answers **what kind of artifact is
 * this**; `category` answers **what part of the business sends it**."* Its five
 * values — `printable`, `email`, `sms`, `contracts`, `in_app` — are E2's five
 * kinds exactly, which is why nothing new had to be defined for this task.
 *
 * The row's `kind` string (*"Print + email"*) is DISPLAY COPY and is not parsed
 * here: reading a drawing decision out of a human sentence is how a screen
 * starts changing behaviour when somebody edits a label.
 *
 * A `group` this screen does not know falls back to `printable` — the drawing
 * every document in this product had before E2 — rather than to a blank pane.
 */
export type DesignerKind = "printable" | "email" | "sms" | "in_app" | "contract";

export function designerKind(data: { group: string | null }): DesignerKind {
  switch (data.group) {
    case "email":
      return "email";
    case "sms":
      return "sms";
    case "in_app":
      return "in_app";
    case "contracts":
      return "contract";
    default:
      return "printable";
  }
}

/**
 * CR-076 item 1 — THE SURFACES **THIS ONE TEMPLATE** IS A FORM FOR.
 *
 * *"you are correct - dont use hard coding"* — PO, 2026-09-07, after proposing
 * a fixed list of five themselves.
 *
 * ⚠ **THE LIST IS THE SERVER'S AND THIS FUNCTION DOES NOT ADD TO IT.** The
 * detail payload carries `preview_surfaces`, derived in `catalogs.py` from
 * `CHANNELS_BY_KIND` — the only place in this repo that says what a `kind`
 * string like *"Print + email"* MEANS. A tab bar built from a constant would
 * offer an empty SMS tab on a letter and would go on offering exactly five on
 * the day a sixth surface exists: the sign-up screen's eleventh service, one
 * screen along (hard-won law 2).
 *
 * ⚠ **WHAT `isDesignerKind` BELOW IS, AND WHAT IT IS NOT.** It is the DRAWING
 * vocabulary — the five shapes `PreviewBody` knows how to render — and it is
 * not the tab list. It exists because a served string has to be narrowed before
 * it can be drawn, and a surface nothing can draw must not become a tab that
 * opens onto a blank pane.
 *
 * It is a list of five in a file that has just argued against lists of five, so
 * the drift it could cause is guarded ON THE OTHER SIDE rather than promised
 * here: `test_cr076__every_seeded_class_derives_a_surface_it_can_actually_draw`
 * asserts that the surfaces the catalog can derive are exactly these five, and
 * fails NAMING THIS FILE. Adding a channel there without a drawing here goes
 * red there — which is the direction that would otherwise fail silently, since
 * an unknown surface would simply be filtered out and no tab would appear.
 *
 * Duplicates are dropped and order is the server's, which reads print-first.
 */
export function isDesignerKind(value: string): value is DesignerKind {
  return (
    value === "printable" ||
    value === "email" ||
    value === "sms" ||
    value === "in_app" ||
    value === "contract"
  );
}

export function previewSurfaces(
  data: { preview_surfaces?: readonly string[] },
  derived: DesignerKind,
): DesignerKind[] {
  // ⚠ **A BOUNDARY READ, GUARDED.** This value comes off the wire. An older
  // backend that does not serve it, or serves something that is not a list,
  // must cost the tab strip and NOT the whole designer — the same bargain the
  // server makes for a `kind` it cannot answer for. `[]` is the caller's signal
  // to draw the screen exactly as it was before this field existed.
  const raw = data.preview_surfaces;
  if (!Array.isArray(raw) || raw.length === 0) {
    return [];
  }
  const kept: DesignerKind[] = [];
  for (const value of raw) {
    if (isDesignerKind(value) && !kept.includes(value)) {
      kept.push(value);
    }
  }
  if (kept.length === 0) {
    return [];
  }
  // ⚠ **THE SURFACE THE CLASS'S OWN `group` NAMES IS ALWAYS IN THE LIST.** It
  // is the surface the screen OPENS on — so that nothing moves until a person
  // presses something — and an open tab that is not one of the tabs would be a
  // selection nobody can see. Both facts are the server's (`group` and
  // `preview_surfaces` are two fields of one payload), so this unions two
  // statements rather than inventing a third. No seeded class needs it; it is
  // here because the alternative, silently previewing a class as something its
  // own group does not name, is the worse failure of the two.
  return kept.includes(derived) ? kept : [derived, ...kept];
}

/**
 * CR-076 item 1 — the tab strip above the rendered document.
 *
 * ⚠ **IT IS NOT `SurfaceSwitcher` AND THE TWO MUST NOT BE MERGED.** That one
 * lives in the page header and NAVIGATES: its surfaces are sibling template
 * CLASSES (`sms_bill_ready` beside `email_bill_ready`), two codes with two
 * bodies and two version lists. This one REDRAWS: its surfaces are the forms of
 * one class, which has one body. Drawing them as one strip would offer a person
 * "SMS" — meaning *go to another document* — beside "Email" — meaning *look at
 * this one differently* — as though they were the same act.
 *
 * ⚠ **AND IT IS NOT DRAWN AT ALL BELOW TWO TABS.** BR-SHL-010, and the same
 * rule `SurfaceSwitcher` keeps: one tab is a control that cannot do anything.
 * 32 of the 38 seeded classes are in that position, so this is the common case
 * rather than the edge, and on all of them the screen is exactly what it was.
 */
export function SurfaceTabs(props: {
  surfaces: readonly DesignerKind[];
  current: DesignerKind;
  onSelect: (surface: DesignerKind) => void;
}) {
  const { t } = useTranslation();
  if (props.surfaces.length < 2) {
    return null;
  }
  return (
    <div
      className={CHIPS}
      role="tablist"
      aria-label={t("templates.detail.previewAs")}
      data-testid="wireframe-surface-tabs"
    >
      {props.surfaces.map((surface) => {
        const open = surface === props.current;
        return (
          <Button
            key={surface}
            // DEF-343's lesson, a fourth time: selection is expressed in the
            // button kit's own variant vocabulary, never as a bare
            // `className="active"` no stylesheet declares.
            variant={open ? "primary" : "secondary"}
            size="sm"
            role="tab"
            aria-selected={open}
            onClick={() => props.onSelect(surface)}
            data-testid={`wireframe-surface-${surface}`}
            /* The selected tab IS the answer to *previewing as what*, so it
               carries the marker the strip's `<strong>` carries on a
               single-surface class. One fact, one element, never both —
               `Previewing as [Printed page][Email] · Printed page` is the
               repetition the Product Owner circled (`DEF-NOT-4456`). */
            data-preview-kind={open ? "" : undefined}
          >
            {t(`templates.detail.previewSurface.${surface}`)}
          </Button>
        );
      })}
    </div>
  );
}


/**
 * The unsampled tokens, gathered under each DISTINCT reason (DEF-2478).
 *
 * ⚠ **IT RELIES ON THE BACKEND SHARING ONE STRING OBJECT ACROSS THE IDENTITY
 * TOKENS, AND THAT IS DELIBERATE ON BOTH SIDES.** `template_preview.py` names
 * the shared sentence `SETTINGS_STAMPED` and its comment says to keep the
 * entries identical *because this grouping is what makes them one line*. Two
 * sentences that merely MEAN the same thing would group as two, which is the
 * defect. Exported for the DOM test, which pins the collapse rather than the
 * wording.
 *
 * Insertion order is preserved — the server already sorts the tokens — so the
 * list does not reshuffle between renders.
 */
export function groupByReason(
  entries: readonly { token: string; reason: string }[],
): { reason: string; tokens: string[] }[] {
  const order: string[] = [];
  const byReason = new Map<string, string[]>();
  for (const entry of entries) {
    const seen = byReason.get(entry.reason);
    if (seen === undefined) {
      order.push(entry.reason);
      byReason.set(entry.reason, [entry.token]);
    } else {
      seen.push(entry.token);
    }
  }
  return order.map((reason) => ({ reason, tokens: byReason.get(reason) as string[] }));
}


/** ONE CELL: which wording fields moved, as a VALUE (CR-049 task 8).
 *
 *  Three states, and telling them apart is the whole of this component:
 *
 *    * the FIRST version — the wording arriving. Not "nothing changed".
 *    * an edit that moved wording — the field names, and a control, because
 *      *"which of my customers is holding the old one?"* is the next question
 *      and it now has an answer.
 *    * an edit that moved NO wording — a draft saved unchanged, or a lifecycle
 *      move. Said plainly rather than left blank.
 *
 *  ⚠ **A SERVER THAT HAS NOT SHIPPED THIS FIELD YET IS NOT "NOTHING CHANGED".**
 *  `changed_fields` is optional on the wire, and `undefined` means *this build
 *  of the backend does not answer* — which must draw the same muted, honest
 *  absence the rest of this screen draws, never a confident empty value. */
/** A changed field's name. ⚠ DEF-NOT-10687: the BODY is a *Letter* only on
 *  paper; an email, a text or an in-app note calls it *Message*, the word the
 *  wording pane itself uses. */
export function changedFieldLabel(
  field: string,
  kind: DesignerKind | undefined,
  t: (key: string) => string,
): string {
  if (field === "body" && kind !== undefined && kind !== "printable" && kind !== "contract") {
    return t("templates.workspace.message");
  }
  return t(`templates.detail.field.${field}`);
}

export function ChangedCell(props: {
  version: TemplateVersionRow;
  open: boolean;
  onToggle: () => void;
  kind?: DesignerKind;
}) {
  const { t } = useTranslation();
  const fields = props.version.changed_fields;
  const testId = `version-changed-${props.version.version}`;

  if (fields === undefined) {
    return (
      <span className={MUTED} data-testid={testId}>
        {t("templates.detail.changedUnknown")}
      </span>
    );
  }
  if (props.version.changed_from_version === null || props.version.changed_from_version === undefined) {
    return (
      <span className={MUTED} data-testid={testId}>
        {t("templates.detail.changedFirst")}
      </span>
    );
  }
  if (fields.length === 0) {
    return (
      <span className={MUTED} data-testid={testId}>
        {t("templates.detail.changedNothing")}
      </span>
    );
  }
  const label = fields.map((field) => changedFieldLabel(field, props.kind, t)).join(" · ");
  return (
    <Button
      variant="ghost"
      onClick={props.onToggle}
      aria-expanded={props.open}
      title={t("templates.detail.changedTitle", {
        from: props.version.changed_from_version,
        version: props.version.version,
      })}
      data-testid={testId}
    >
      {label}
    </Button>
  );
}

/** THE OPENED DETAIL — what moved, and who is holding the wording it replaced.
 *
 *  ⚠ **BOTH HALVES OR NEITHER.** The PO asked *"any changes … noted as changed;
 *  that way it will keep the santity of the legal documents"* as one sentence,
 *  and the second half is the one a version list could never answer: a count of
 *  pins is a number, and *"which of my customers is holding it"* is a question
 *  about letters. It became answerable on 2026-08-30, when every sent document
 *  got a kept copy with an id — so a row here links to the letter itself. */
export function ChangeRecordDetail(props: {
  code: string;
  versionId: string;
  client: ApiClient;
  onClose: () => void;
  kind?: DesignerKind;
}) {
  const { t } = useTranslation();
  const answer = useQuery({
    queryKey: ["template-change", props.code, props.versionId],
    queryFn: () => fetchTemplateChange(props.code, props.versionId, props.client),
  });

  if (answer.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (answer.error !== null || answer.data === undefined) {
    return (
      <FailedWithRetry
        title={t("templates.detail.changeRecordFailed")}
        reason={apiErrorText(answer.error, t)}
        onRetry={() => void answer.refetch()}
        onDownloadReport={() => undefined}
        onCancel={props.onClose}
      />
    );
  }

  const record = answer.data;
  const impacted = record.superseded;
  return (
    <div className="mt-3 border-t border-divider pt-3" data-testid="change-record">
      <p className={SUBHEAD}>
        {t("templates.detail.changeRecordTitle", {
          version: record.version,
          from: record.previous_version ?? record.version,
        })}
      </p>
      {/* WHAT MOVED — one short line per field. A SIZE, never a paraphrase:
        this product does not put words in an author's mouth (OQ-255(b)). */}
      <ul className={INBOX_LINES} data-testid="change-fields">
        {record.fields.map((field) => (
          <li key={field.field} data-testid={`change-field-${field.field}`}>
            {t("templates.detail.changeField", {
              field: changedFieldLabel(field.field, props.kind, t),
              added: field.lines_added,
              removed: field.lines_removed,
            })}
          </li>
        ))}
        {record.fields.length === 0 && (
          <li className={MUTED}>{t("templates.detail.changedNothing")}</li>
        )}
      </ul>
      {/* WHO IS HOLDING THE OLD WORDING — the half a version list cannot
        answer. The COUNT is the whole set; the rows are the newest page of it,
        and both come from one query so the two numbers are never about two
        different sets. */}
      <p className={SUBHEAD}>
        {t("templates.detail.stillOnOldWording", {
          count: impacted.documents,
          formatted: impacted.documents.toLocaleString(),
          version: impacted.version ?? 0,
        })}
      </p>
      {impacted.documents === 0 ? (
        <p className={MUTED} data-testid="change-impact-none">
          {t("templates.detail.stillOnOldWordingNone")}
        </p>
      ) : (
        <ul className={INBOX_LINES} data-testid="change-impact">
          {impacted.sample.map((impact) => (
            <li key={impact.message_id} data-testid={`change-impact-${impact.message_id}`}>
              {/* The channel words are the queue's own — one vocabulary for
                "Post / Email / Text message" across this product, not a second
                set invented here. `defaultValue` covers a channel this screen
                has never seen rather than printing a raw key at a clerk. */}
              {(impact.sent_at ?? "").slice(0, 10)} ·{" "}
              {t(`notifications.queue.channel.${impact.channel}`, {
                defaultValue: impact.channel,
              })}{" "}
              ·{" "}
              {impact.document_kept ? (
                /* The kept copy, by ID — the route CR-049 task 3 already
                   built. A storage key is never handed out, here or anywhere. */
                <span data-document-id={impact.document_id}>
                  {impact.display_name ?? t("templates.detail.keptCopy")}
                </span>
              ) : (
                <span className={MUTED}>{t("templates.detail.noKeptCopy")}</span>
              )}
            </li>
          ))}
          {impacted.truncated && (
            <li className={MUTED} data-testid="change-impact-truncated">
              {t("templates.detail.stillOnOldWordingMore", {
                shown: impacted.sample.length,
                count: impacted.documents,
                formatted: impacted.documents.toLocaleString(),
              })}
            </li>
          )}
        </ul>
      )}
      <div className={ACTIONS}>
        <Button variant="ghost" onClick={props.onClose} data-testid="change-record-close">
          {t("templates.detail.changeRecordClose")}
        </Button>
      </div>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-007@set0910 (12-governance/11-change-requests.md CR-007 + the three PO rulings of 2026-08-16 · 05-prototype/r10-2026-08-16/SMARTBillHub.dc.html SET-10 · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-001/006/014/015)
// generated: 2026-08-17 by story-coder (CR-007 SET-09/10 templates lane)
//   · AMENDED 2026-08-18 (DEF-209 remainder · DEF-211 · DEF-212) by the
//     templates-B14 lane.
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: ⚠ THE LINE HERE READ `vitest TemplateDetail.test.tsx` FROM 2026-08-17
//         AND THAT FILE DID NOT EXIST — hard-won law 1 in a single line, on the
//         screen that carries the editor, the publish control and the only
//         destructive commit in Settings. (The claimed unknown-token red-proof
//         belongs to the browser spec, which does cover it.) It exists now:
//         TemplateDetail.test.tsx, 21 tests + 1 todo, three guards RED-PROVED
//         by reverting the fix they cover — `editorSource` back to
//         published-only (2 red), `variantStateOf` back to one word for two
//         states (3 red), and one control stripped of its class (1 red); the
//         file was byte-identical to its pre-proof state afterwards.
//         tsc✔ · eslint --max-warnings 0✔ · vitest 1432 passed / 184 todo
//         across 95 files (1411 / 183 across 94 before this lane).
// exceptions: (1) THREE CONTROLS RENDER DISABLED WITH THE SERVER'S OWN REASON
//         and never hidden (BR-SHL-025): test send, sample PDF, set default.
//         The three sentences are DIFFERENT because the three have different
//         fixes.
//         (2) THE SUBJECT BOX IS DRAWN ONLY FOR EMAIL. A subject on an SMS or a
//         printable class is a field the renderer would refuse; drawing it
//         would offer a control whose value can never be saved.
//         (3) THE SMS COUNTER COUNTS THE RENDERED LENGTH when a render is
//         available, because tokens change it — and it never truncates or
//         blocks, since no signed rule says a 161-character SMS is invalid.
//         (4) THE DEACTIVATE CONFIRM'S CONSEQUENCE IS THIS SCREEN'S OWN WORDS,
//         which is the one place on it that does not quote the server, and the
//         reason is not laziness: the server's `resolution_after` sentence is
//         on the DEACTIVATE RESPONSE — after the click — and the GET detail
//         payload carries no such field, so a pre-click confirm cannot render
//         it without a new read. DEF-209's prevention column says it is
//         "already on the wire"; that is true only after the act it is meant to
//         warn about. Corrected in the defect note, not silently worked around.
//         (5) THE "Deactivated" BADGE IS NEVER SHOWN WITHOUT AN `archived_at`
//         in hand. An unselected variant tab carries a version COUNT and no
//         versions, so it says the weaker true thing ("Not live") rather than
//         guessing which of two states it is in.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
