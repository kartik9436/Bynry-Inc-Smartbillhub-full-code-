// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-018 (EP-RBS-01) — CR-075 wave D task D3.
// Screens: RBS-002.1 (`S148.1`) — the library we ship, at
//          `/{tenant}/runbooks/templates`.
// Rules:   `BR-RBS-025` (a category with no runbook is never drawn as a
//          filter) · `TC-RBS-20` · `NFR-3` (server pagination) · `NFR-5` (no
//          caps) · B14 rule 2 (page head) · rule 12 (toolbar grammar) · rule
//          21 (Tailwind only, and this folder is on route-b-migrated.txt) ·
//          rule 31 (no database id on screen) · rule 32 (one sentence per
//          section, no rule id or internal code in clerk copy) · rule 33 (a
//          refusal caps at five or six words).
// Tests:   TemplateLibrary.dom.test.tsx (TC-RBS-20 among them) ·
//          10-scripts/render-checks/rbs-d-the-library.mjs
// Defects: DEF-RBS-4309 (the four facts the wire does not carry) ·
//          DEF-RBS-4310 (the chips with no server count and no server filter).
// ───────────────────────────────────────────────────────
// THE CHIP ROW IS THE POINT OF THIS SCREEN.
//
// ══════════════════════════════════════════════════════════════════════════
// `TC-RBS-20` — BUILT FROM THE TEMPLATES PRESENT, NEVER FROM THE FIXED SIXTEEN
// ══════════════════════════════════════════════════════════════════════════
// `BR-RBS-025`: *a category with no runbook is never drawn as a filter*, and
// `RB-019`'s *done looks like* is this screen in one sentence — *"Templates
// shows eight category chips for twelve templates and none reading Assets or
// Work."* The reason is hard-won law 2: a chip that filters to nothing is dead
// UI. Sixteen categories exist; **Accounts draws a chip on the strength of one
// reserved template while Assets, Work, Customer portal and Business draw
// none.**
//
// ⚠ **SO THIS COMPONENT COUNTS NOTHING.** `categoryChips` and `kindChips` are
// the SERVER's counts, computed once in `selectors._template_category_chips`
// over the whole registry. A screen that counted `view.rows` would be counting
// A PAGE, which is right at twelve templates and wrong at the first page
// boundary — `NFR-3` in the exact shape `DEF-PAY-4221` records four times over.
// The test changes the rows and asserts every chip count stays put, because a
// page-derived count and a server count are indistinguishable on a short list.
//
// ⚠ **PROVED RED FIRST, IN THE HARNESS THAT RUNS IT** (law 7, both halves).
// The chip row was first built from a hard-coded list of the sixteen
// categories; `TemplateLibrary.dom.test.tsx` failed by name —
// `expected [ 'Platform1', …(15) ] to have a length of 8 but got 16` and
// `Assets holds no template and must draw no chip: expected 'Platform1 · …' not
// to contain 'Assets'` — through `./node_modules/.bin/vitest`, the runner
// CI uses, never `python3 <gate>.py`'s equivalent. The list was then deleted and
// the row built from the payload.
//
// ══════════════════════════════════════════════════════════════════════════
// THREE THINGS THE SHEET DRAWS THAT ARE NOT HERE, EACH STATED RATHER THAN
// SMOOTHED OVER (`08-screen-layouts.md` carries the stamps)
// ══════════════════════════════════════════════════════════════════════════
//   * **The `Not added 5` chip.** No server count and no `f.state` filter
//     (`DEF-RBS-4310`). Drawing it would mean either a number counted from the
//     current page or a chip that filters nothing, and a chip that does nothing
//     looks exactly like one that works.
//   * **The card's one sentence.** `RunbookDefinition` has no purpose field
//     (`DEF-RBS-4309`). An absent one draws NOTHING — no dash, no placeholder,
//     no invented text — which is the wave C lane's rule for `Step.why`.
//   * **The footer's services line** (*Water · Sewer* / *All services*). It is
//     a template's SCOPE, which is resolved per tenant at run start
//     (`BR-RBS-042` clause 1) and is on no template payload. Same treatment.
//
// ⚠ **AND ONE THE SHEET QUOTES AND DOES NOT WANT.** Region 2 is stamped with
// rule 12's full grammar including `[▦ Columns]`, and this screen has no Columns
// button and no pagination footer. `08-screen-layouts.md` settles it: *"this is
// a card gallery, not a list table, and rules 12/14/16 govern list tables. The
// quoted grammar is boilerplate, not a requirement here."* A pager is drawn only
// when the library outgrows one page, which is `NFR-3` honoured without
// furniture the frame does not draw.
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { Button, ButtonLink } from "@/components/Button";
import { ChipRow, ChipToggle } from "@/components/Chip";
import { createSearchDebouncer } from "@/components/DataTable";
import { ListPager } from "@/components/ListPager";
import { PageHeader } from "@/components/PageHeader";
import { EmptyList, ZeroResults } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import type { PageSize } from "@/components/tableTypes";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

import { categoryLabel } from "./libraryLabels";
import type { CategoryChip, KindChip, TemplateRow } from "./libraryTypes";

/** Everything `RBS-002.1` draws. One object, and no runbook named in it. */
export interface TemplateLibraryView {
  rows: readonly TemplateRow[];
  /** The server's total, so *"1–12 of 12"* is a true sentence. */
  total: number;
  categoryChips: readonly CategoryChip[];
  kindChips: readonly KindChip[];
}

export interface TemplateLibraryProps {
  view: TemplateLibraryView;
  /** The request this page was drawn for — the screen holds no filter state of
   *  its own, because two copies of *which chip is on* is how a chip and a list
   *  end up disagreeing. */
  request: { q: string; kind: string; category: string; page: number; per: PageSize };
  onSearch: (q: string) => void;
  onKind: (kind: string) => void;
  onCategory: (category: string) => void;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
  /** Drop the search and both chips at once — the way out of a list narrowed
   *  to nothing (`ZeroResults`). */
  onClearFilters: () => void;
  /**
   * **+ Add** — `POST /runbooks` is task `E1` and is not built.
   *
   * ⚠ **REQUIRED, NOT OPTIONAL, AND THAT IS THE ANSWER TO LAW 2 / `G13`.** An
   * optional prop nothing passes is dead UI: it renders, every test passes, and
   * the feature does not exist. A required prop cannot have that shape — a
   * caller that forgets it does not compile.
   */
  onAdd: (template: TemplateRow) => void;
}

/** The kind chip order the sheet draws: **All · Checks · Actions**. */
const KIND_ORDER = ["all", "check", "action"] as const;

export function TemplateLibrary(props: TemplateLibraryProps) {
  const { t } = useTranslation();
  const { view, request } = props;
  const tenant = useTenant();

  // The input is local while typing and the REQUEST is what the list is drawn
  // from; one settled keystroke burst is one server request (IS-3).
  const [typed, setTyped] = useState(request.q);
  const searchRef = useRef(createSearchDebouncer(props.onSearch, request.q));
  useEffect(() => {
    searchRef.current = createSearchDebouncer(props.onSearch, request.q);
    // `props.onSearch` is stable per page instance; re-creating the debouncer
    // when it changes keeps the closure honest rather than firing into a stale
    // handler, which is how a filter silently stops working after a remount.
  }, [props.onSearch, request.q]);

  /** Has the person narrowed the list themselves? Decides which empty state
   *  the screen is honest to draw. */
  const narrowed = request.q !== "" || request.kind !== "" || request.category !== "";

  const kindCount = useMemo(() => {
    const byKind = new Map<string, number>();
    for (const chip of view.kindChips) {
      byKind.set(chip.kind, chip.count);
    }
    return byKind;
  }, [view.kindChips]);

  return (
    // `data-screen` is the convention every screen in this product follows and
    // the handle the browser walkthrough holds on to. It is an ATTRIBUTE, never
    // visible copy, so B14 rule 32's ban on an internal code in clerk-facing
    // text is untouched.
    <main data-screen="RBS-002">
      <PageHeader
        // ⚠ `backTo` AND NOT `kicker`. The sheet writes *"kicker: ← Runbooks"*
        // and rule 1 in the same cell — *"a ← kicker names where the page EXITS
        // to"*. A kicker is TEXT, so building it that way ships an exit sign
        // that is not a door; `backTo` renders `← label` as a real `<Link>` in
        // the same slot.
        backTo={{ to: tenantPathFrom(tenant, "runbooks"), label: t("runbooks.library.back") }}
        title={t("runbooks.library.title")}
        rollup={t("runbooks.library.subtitle")}
      />

      {/* ── Region 2 · the toolbar's first row ─────────────────────────────
          rule 12's set: the search, then the chips. No `+ Filter ▾` and no
          `▦ Columns`: both are list-table furniture and this is a gallery. */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {/* The same box `DataTable` draws, class for class, so the gallery's
            search and every list's search are one control rather than two that
            drifted. `input` is a class the stylesheet DECLARES — reusing a
            declared class adds none, which is what B14 rule 21 is actually
            after (`DEF-974`). The accessible name is the same sentence as the
            placeholder, which is rule 19's own requirement. */}
        <div className="relative flex min-w-[15rem] max-w-[32rem] flex-[1_1_20rem] items-center">
          <input
            type="search"
            className="input"
            placeholder={t("runbooks.library.search")}
            aria-label={t("runbooks.library.search")}
            value={typed}
            onChange={(event) => {
              setTyped(event.target.value);
              searchRef.current.type(event.target.value);
            }}
          />
        </div>
        <ChipRow aria-label={t("runbooks.library.kindChipsLabel")} data-chips="kind">
          {KIND_ORDER.map((kind) => (
            <ChipToggle
              key={kind}
              selected={kind === "all" ? request.kind === "" : request.kind === kind}
              // Pressing the SELECTED chip clears it, exactly as the category
              // row below already did. A filter a person can switch on and not
              // off is the same defect as one that does nothing.
              onClick={() =>
                props.onKind(kind === "all" || request.kind === kind ? "" : kind)
              }
              data-kind={kind}
            >
              {t(`runbooks.library.chip.${kind}`)}
              {/* The count is the SERVER's. A chip with no count is a chip we
                  could not count, and there is no such chip on this row. */}
              <span className="ms-1 text-neutral-600">{kindCount.get(kind) ?? 0}</span>
            </ChipToggle>
          ))}
        </ChipRow>
      </div>

      {/* ── Region 3 · the declared SECOND row of dimension controls ────────
          Both toolbar regions are stamped *"one row of pressable controls only
          (rule 32)"*, which reads as though the category chips belonged on row
          one. `08-screen-layouts.md` settles it: rule 32 as ratified puts rule
          12's set on the first row and a screen's dimension controls on a
          DECLARED second row, which is what the frame draws. The stamp is the
          generator repeating one rule string on every toolbar region. */}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="text-sm font-extrabold tracking-wider text-neutral-600 uppercase">
          {t("runbooks.library.chip.categoryLabel")}
        </span>
        <ChipRow aria-label={t("runbooks.library.categoryChipsLabel")} data-chips="category">
          {view.categoryChips.map((chip) => (
            <ChipToggle
              key={chip.category}
              selected={request.category === chip.category}
              onClick={() =>
                props.onCategory(request.category === chip.category ? "" : chip.category)
              }
              data-category={chip.category}
            >
              {categoryLabel(t, chip.category)}
              <span className="ms-1 text-neutral-600">{chip.count}</span>
            </ChipToggle>
          ))}
        </ChipRow>
      </div>

      {/* ── Regions 4–9 · the cards ────────────────────────────────────────
          `[grid-template-columns:repeat(auto-fit,minmax(228px,1fr))]` is the
          same wrap point every other runbooks layout uses, so a card gallery and
          a two-column detail break at one width rather than two. */}
      {view.rows.length === 0 && narrowed ? (
        // A list narrowed to nothing is not an empty library, and telling a
        // person *"no templates"* when they have typed three letters is a
        // screen blaming the product for the filter. `ZeroResults` is the kit's
        // own answer and it carries the way out.
        <ZeroResults
          query={request.q}
          onClearFilters={() => {
            setTyped("");
            props.onClearFilters();
          }}
        />
      ) : view.rows.length === 0 ? (
        <EmptyList
          title={t("runbooks.library.empty.title")}
          helper={t("runbooks.library.empty.helper")}
          ctaLabel={t("runbooks.library.empty.cta")}
          // ⚠ **THE CTA IS DISABLED WITH ITS REASON RATHER THAN LIVE ONTO
          // NOTHING** (`BR-SHL-025`; `DEF-SHL-4043` is why the reason is
          // RENDERED and not a `title`). A library with no templates in it means
          // the registry is empty, and no screen can fix that.
          ctaReason={t("runbooks.library.empty.reason")}
          onCta={() => undefined}
        />
      ) : (
        <ul className="mt-4 grid list-none gap-3.5 p-0 [grid-template-columns:repeat(auto-fit,minmax(228px,1fr))]">
          {view.rows.map((row) => (
            <TemplateCard
              key={row.template_key}
              row={row}
              to={tenantPathFrom(tenant, `runbooks/templates/${row.template_key}`)}
              openTo={tenantPathFrom(tenant, `runbooks/${row.template_key}`)}
              onAdd={() => props.onAdd(row)}
            />
          ))}
        </ul>
      )}

      {/* ⚠ **A PAGER ONLY WHEN THERE IS A SECOND PAGE.** The request is paged
          server-side whatever this draws (`NFR-3`); the footer is the sheet's
          own omission and it stays omitted while the library fits one page. The
          day we ship more templates than a page holds, a person can still reach
          them — which is the half of `NFR-3` a missing footer would break. */}
      {view.total > request.per && (
        <ListPager
          total={view.total}
          page={request.page}
          per={request.per}
          onPage={props.onPage}
          onPer={props.onPer}
        />
      )}
    </main>
  );
}

/** The state pill's tone. `Added` is the reassuring one, so it is the success
 *  tone; the other two are neutral, exactly as the frame draws them. */
const STATE_TONE: Record<TemplateRow["state"], StatusTone> = {
  added: "success",
  not_added: "neutral",
  unavailable: "neutral",
};

/**
 * One template card — regions 4 to 9.
 *
 * The frame's anatomy, top to bottom: **kind pill · category · state pill** on
 * one row, then the **title**, then the one sentence, then a footer whose right
 * side carries the card's single button.
 *
 * ⚠ **AN `Added` CARD OPENS THE RUNBOOK, A `Not added` CARD ADDS IT.** *Open →*
 * goes to `RBS-004` at `/{tenant}/runbooks/{key}` — the address wave C already
 * ships — because once a template is added, the thing a clerk wants is its
 * setup screen. The card's TITLE always goes to the template detail
 * (`RBS-002.2`), so *what would this be allowed to touch* is reachable whether
 * or not it has been added, which is the question that screen exists to answer.
 */
function TemplateCard(props: {
  row: TemplateRow;
  /** `RBS-002.2`, this template's detail. */
  to: string;
  /** `RBS-004`, this runbook's setup — only meaningful once added. */
  openTo: string;
  onAdd: () => void;
}) {
  const { t } = useTranslation();
  const { row } = props;
  const unavailable = row.state === "unavailable";

  return (
    <li className="flex flex-col gap-2 border border-divider bg-[white] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={row.kind === "check" ? "info" : "danger"}>
          {t(`runbooks.library.kind.${row.kind}`)}
        </StatusPill>
        <span className="text-base text-neutral-600">{categoryLabel(t, row.category)}</span>
        <span className="ms-auto">
          <StatusPill tone={STATE_TONE[row.state]}>
            {t(`runbooks.library.state.${row.state}`)}
          </StatusPill>
        </span>
      </div>

      <h3 className="m-0 text-md font-bold">
        {/* The title is the door to the detail. A card whose only door is its
            button leaves *What it can touch* unreachable for anything already
            added, and that table is the reason the detail screen exists.
            ⚠ **NOT `<ButtonLink variant="link">`.** That tier is 12px and
            carries the heading family at semibold, and `Surfaces.tsx` says so
            in its own words; the card title is 14px body bold. Folding them
            together would move pixels on 23 other screens. */}
        <Link
          to={props.to}
          className="text-neutral-900 no-underline hover:underline"
          data-card-title={row.template_key}
        >
          {row.name}
        </Link>
      </h3>

      {/* ⚠ **THE ONE SENTENCE, WHEN THERE IS ONE.** `DEF-RBS-4309`: no field
          carries it today, so this draws nothing at all rather than a dash or a
          sentence this screen invented. The day the wire serves it the card
          fills in with no change here. */}
      {row.description !== undefined && row.description !== null && row.description !== "" && (
        <p className="m-0 text-base text-neutral-700">{row.description}</p>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
        {/* ⚠ **A DISABLED BUTTON CARRIES ITS REASON**, which is the sheet's own
            stamp and `BR-SHL-025`'s pattern: the reason travels ON the control,
            so it is read where the mistake would be made. It is drawn as text
            beside the button as well as on `title`, because a `title` alone is
            invisible to a person who never hovers. */}
        {unavailable && row.unavailable_reason !== null && (
          <span className="text-base text-neutral-600">{row.unavailable_reason}</span>
        )}
        <span className="ms-auto">
          {row.state === "added" ? (
            <ButtonLink to={props.openTo} data-card-open={row.template_key}>
              {t("runbooks.library.open")}
            </ButtonLink>
          ) : (
            <Button
              variant="primary"
              disabled={unavailable}
              title={unavailable ? (row.unavailable_reason ?? undefined) : undefined}
              onClick={props.onAdd}
              data-card-add={row.template_key}
            >
              {t("runbooks.library.add")}
            </Button>
          )}
        </span>
      </div>
    </li>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-018 (EP-RBS-01; CR-075 wave D task D3) · BR-RBS-025 · TC-RBS-20 · wireframes/RBS-002.1 (sheet + frame) · 08-screen-layouts.md §RBS-002
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no 🔒 path)
// gates: RED PROVED FIRST — the chip row built from a hard-coded sixteen failed TemplateLibrary.dom.test.tsx by name through ./node_modules/.bin/vitest · tsc --noEmit (the LOCAL compiler, never npx) · vitest · G31/routeBUtilities (every utility here compiles against the real theme; features/runbooks/ is on route-b-migrated.txt)
// exceptions: three regions the sheet draws are ABSENT rather than invented — the Not added chip (DEF-RBS-4310), the card sentence and the footer services line (DEF-RBS-4309) — each stamped in 08-screen-layouts.md
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
