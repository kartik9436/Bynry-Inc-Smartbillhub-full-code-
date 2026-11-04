// ── Trace ──────────────────────────────────────────────
// Story:    US-REP-001 (S44 Report library) · CR-142-BRC07 Phase 1 · P1.3
//           (screen 1·1) · P1.2 (the filters) · P1.4 (the broken card door) ·
//           P1.5 (no literals) · P1.8 (the enabled services).  Screens: S44
// Rules:    BR-REP-002 (every card opens a READ-MODEL) · BR-REP-003 /
//           BR-REP-005 (the ledger-owned surfaces are ROUTED to, never
//           re-implemented) · BR-REP-019 (origin is three closed values) ·
//           BR-REP-001 (a money card names its basis) · BR-SHL-025 (a control
//           this deployment cannot honour renders with its reason) ·
//           BR-SHL-044 (one page header) · B14 rules 21, 31, 32, 33, 37, 40,
//           41, 42, 43, 44 · CLAUDE.md hard-won law 2, both directions
// Tests:    src/features/reports/catalogueScreen.dom.test.tsx ·
//           routeTargetsResolve.dom.test.tsx · phaseHolds.dom.test.tsx
// ───────────────────────────────────────────────────────
// S44 — THE REPORT CATALOGUE, DRAWN FROM `05-prototype/09 Reports Build
// Brief.pdf` p19–p20 READ AS IMAGES (B14 rule 42).
//
// ════════════════════════════════════════════════════════════════════════════
// WHAT CHANGED ON 2026-09-26, AND WHAT DELIBERATELY DID NOT
// ════════════════════════════════════════════════════════════════════════════
// Until today this screen drew twenty-three cards in three groups from
// `apps/reports/catalog.py`'s frozen Python tuple, named every one of them
// through `t("reports.card.<key>.name")`, and had no search, no filter, no
// sub-tab and no pager. It now draws forty-five cards in six groups and
// nineteen sub-groups out of `report_definitions`, with all three filters read
// SERVER-SIDE.
//
// **THE NAME COMES OUT OF THE ROW.** The brief, p5: *"Until a report's name
// comes out of a row, no utility can ever author one"* — because a utility
// cannot edit our locale catalogues. So the server resolves `name_override` →
// `name_i18n[locale]` → `name`, and this screen renders what it is given.
//
// ⚠ **AND THE OLD MECHANISM IS RETIRED RATHER THAN KEPT ALONGSIDE.** The
// twenty-three names lived in `reports.card.<key>.name` in all eleven
// catalogues, and nine of those keys survive into the forty-six. Preferring
// that authored copy for a platform card was built here and deleted the same
// hour: `reports/0003` renames `ar_aging` from *"AR aging summary"* to **"AR
// Ageing"**, so the preference rendered the OLD name and ignored the row — a
// locale catalogue a utility cannot edit, quietly outranking the row that
// exists so it can. See `displayName`. The cost is that a non-English clerk
// reads English report names until `name_i18n` is written; 506 strings are not
// a lane's to author under B14 rule 35, and the gap is `DEF-REP-6817`.
//
// ════════════════════════════════════════════════════════════════════════════
// TWO THINGS THE DRAWING SHOWS THAT ARE **NOT** BUILT, BY PO RULING
// ════════════════════════════════════════════════════════════════════════════
// PO ruling 2026-09-26, verbatim: *"go as per phases - tasks"* —
// `12-governance/02-decision-log.md`, commit `76be101a3`.
//
// **THE FOUR-TAB STRIP** (Catalogue · Dashboard · Scheduled · History) is not
// drawn. p20 callout ③: *"The strip is not drawn until the second tab exists —
// a one-tab strip is furniture."* History is Phase 3; Dashboard and Scheduled
// are Phase 4.
//
// **`+ Build your own`** is not drawn. p20 callout ②: *"not drawn until Phase
// 5, when the builder lands. Until then the screen says the thing is not built
// rather than showing a button that does nothing"* — and, in terms, *"a button
// that points at nothing for four phases is the defect that left five portal
// cards dead."*
//
// ⚠⚠ **BOTH OF THOSE PARAGRAPHS ARE HISTORY NOW AND ARE KEPT FOR THE ARGUMENT
// IN THEM, NOT AS A STATEMENT ABOUT THIS SCREEN.** The strip is drawn
// (`P3.2`), and `+ Build your own` is drawn (`P5.10`, 2026-09-27) — **and it
// pointed at nothing for a day anyway, which is the exact sentence callout ②
// wrote to prevent** (`DEF-REP-7640`, PO on deployed `v2.388.0`). It is fixed
// in the page head below.
//
// ⚠ **BOTH HOLDS OWE A TEST THAT FIRES WHEN THEY EXPIRE AND BOTH HAVE ONE, IN
// THIS COMMIT.** `phaseHolds.dom.test.tsx` asserts each destination BY ADDRESS
// AND BY THE SCREEN ID IT OPENS, so the day History lands the suite goes red and
// names it. That is `DEF-CWP-3925`'s whole lesson: the customer portal's front
// page had two working doors out of eight, every screen shipped days earlier,
// 391 cases green over it, because landing a screen and releasing the control
// that pointed at it are two acts and only the first one feels like the work.
//
// ⚠⚠ **AND THE HOLD-EXPIRY TEST DID HALF OF THAT, WHICH IS THE LESSON
// `DEF-REP-7640` ADDS TO THE ONE ABOVE.** The three cases guarding this
// button asserted it was NOT DRAWN; when the hold expired they were DELETED
// and replaced with a comment naming `reportBuilder.dom.test.tsx` as their
// replacement — a file that mounts the panel and the dialog directly and
// never renders this page head at all. Grepping `buildYourOwn` across every
// test file then returned zero hits. **A hold-expiry case is AMENDED into the
// assertion the released control now owes — the destination — and never
// deleted**, because the day the hold expires is the only day anybody is
// looking at it.
//
// ════════════════════════════════════════════════════════════════════════════
// THE DESIGN DECISION THAT MATTERS: AN UNAVAILABLE CARD OPENS NOTHING
// ════════════════════════════════════════════════════════════════════════════
// **An empty table is a claim.** *"No account is 90+ days overdue"* and *"this
// product cannot tell you who is"* are different sentences and only one of them
// is true. So an unavailable card is a card and NOT a link: dashed top rule,
// dimmed, default cursor, and its reason on its face. That decision is kept —
// P1.3's own row says so.
//
// ⚠ **THE REASON IS NOW SIX WORDS AND IT USED TO BE A PARAGRAPH.** B14 rule 33
// caps a FACT at six and puts RATIONALE at ZERO words on screen. This grid used
// to render *"The trend needs twelve months of billed totals and nothing
// publishes them a month at a time. The single DSO figure is on the AR aging
// report."* on the face of a card. That is rationale, rule 33 says it is
// REMOVED rather than shortened, and the server now sends one reason code whose
// sentence — *"This report cannot be produced yet."* — is six words exactly and
// already authored in all eleven catalogues.
import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getReportLibrary } from "@/api/reportsEndpoints";
import type { ReportCard, ReportLibraryQuery } from "@/api/reportsEndpoints";
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";
import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { SubTabs } from "@/components/SubTabs";
import { Kicker } from "@/components/TextBits";
import { EmptyList, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { AUDIT_ROUTE } from "@/features/audit/AuditLogPage";
import { REPORTS_PERMISSION } from "@/features/ledger/financeShared";
import { isDenied, useAccessCell } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

// ⚠ `REPORTS_ROUTE` left this import with `DEF-REP-7640`: the page head's
// action was the only thing building an address out of it, and it now takes
// the whole address from one constant.
import { REPORT_BUILDER_NEW_ROUTE } from "./reportsShared";
import { ReportsTabs } from "./ReportsTabs";

import { CatalogueToolbar } from "./CatalogueToolbar";
import type { CatalogueQuery } from "./CatalogueToolbar";
import { unavailableSentence, viewerRouteFor } from "./reportsShared";

import "@/features/ledger/finance.css";

export const reportLibraryQueryKey = ["reports", "library"] as const;

/**
 * Where a `route` card goes. A1 screen id → the app path that owns it.
 *
 * BR-REP-003/BR-REP-005 in one object: S44 ROUTES and never re-implements, so
 * this map is the whole of the "trial balance" card's behaviour. A screen id
 * with no entry renders as a card with no link rather than a link to nowhere —
 * a dead link is the one failure a routing table can produce that looks fine.
 */
export const ROUTE_TARGETS: Readonly<Record<string, string>> = {
  S41: "/finance/taxes",
  S56: "/finance/gl",
  S59: "/reports/account-ledger",
  S60: "/reports/by-premises",
  // ⚠ **`/audit-log`, NOT `/settings/audit-log` — DEF-REP-6812, P1.4.** The
  // wrong address was not a dead link and that is why it survived six weeks:
  // `/settings/audit-log` matches `settings/:tab`, `SettingsPage` resolves an
  // unknown tab with `tabs.find(...) ?? tabs[0]`, and the card opened
  // **Settings → Company** — a real screen, with no error anywhere. It is
  // taken from `AuditLogPage`'s own exported constant rather than retyped, so
  // the two cannot drift again, and `routeTargetsResolve.dom.test.tsx` asserts
  // every value here against the router's own table.
  S61: AUDIT_ROUTE,
  S11: "/plans-rates/history",
};

export function targetFor(card: ReportCard): string | null {
  if (card.kind === "viewer" && card.available) {
    return viewerRouteFor(card.key);
  }
  if (card.kind === "route" && card.routes_to_screen !== null) {
    return ROUTE_TARGETS[card.routes_to_screen] ?? null;
  }
  return null;
}

/** The sentence a person reads when a report cannot be produced.
 *
 *  Keyed on the machine `reason_code`; falls back to naming nothing rather than
 *  printing the server's English, because a raw engineering paragraph on a card
 *  is worse than a short honest sentence. B14 rule 33: six words. */
export function reasonSentence(card: ReportCard, t: Translator): string {
  // ⚠ **DELEGATED SINCE `DEF-REP-6898`, AND THE DELEGATION IS THE FIX.** The
  // VIEWER for the same report drew the finance error panel while this card
  // drew the true sentence; one function is what stops them disagreeing again.
  return unavailableSentence(card.reason_code, t);
}

/**
 * The name a person reads. **It is the row's, and there is no second source.**
 *
 * ⚠ **A CATALOGUE PREFERENCE WAS BUILT HERE AND DELETED THE SAME HOUR, AND THE
 * REASON IS WORTH MORE THAN THE CODE.** Nine of the twenty-three old card keys
 * survive into the forty-six and `reports.card.<key>.name` holds an authored
 * translation for each of them in all eleven catalogues, so preferring that
 * copy for a platform card looked like a free way to keep ten languages. Its
 * own test found what it actually does: `reports/0003` renames `ar_aging` from
 * *"AR aging summary"* to **"AR Ageing"**, the drawing's own word, and the
 * preference rendered the OLD name and silently ignored the row. **That is
 * `P1.1` defeated** — the whole point is that a name a utility can edit comes
 * out of a row, and a locale catalogue a utility cannot edit was quietly
 * outranking it.
 *
 * So the retired mechanism is retired. `name_i18n` on the row is the slot a
 * translation lands in, the SERVER resolves `name_override` →
 * `name_i18n[locale]` → `name`, and this function renders what it is given.
 * The cost is stated rather than hidden: thirty-seven of the forty-five cards
 * never had a translation and nine of them now lose one, so a non-English
 * clerk reads English report names until somebody who speaks those languages
 * writes them into `name_i18n`. B14 rule 35 says a catalogue is written in its
 * own language and never translated from English, so the 506 strings are not a
 * lane's to author. `DEF-REP-6817`.
 */
export function displayName(card: ReportCard): string {
  return card.name;
}

/**
 * One card. Three lines, in the order p21 lists them: badge · name · basis
 * label, plus the reason sentence on an unavailable one and nothing else.
 */
export function ReportCardTile(props: {
  card: ReportCard;
  t: Translator;
  tenantPath: (p: string) => string;
}) {
  const { card, t } = props;
  const target = targetFor(card);
  const name = displayName(card);

  const body = (
    <>
      {/* The eyebrow is the SUB-GROUP's name, which is what p20 draws above
          every card — `PAYMENTS`, `ARREARS`, `RECOVERY`. The 0.08em is
          `tracking-table-header`, the SAME named value the tables use rather
          than a fourth arbitrary number. */}
      <span className="text-xs uppercase tracking-table-header text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
        {card.badge}
      </span>
      <span className="font-heading text-body font-bold">{name}</span>
      {/* BR-REP-001 — a money card says which date its figures read, on the
          card, before anyone opens it. The seed keeps the drawing's own words,
          because *As at*, *Read date* and *Effective date* are three different
          facts that all map to one basis code. A report with no money shows
          nothing here rather than an empty label. */}
      {card.basis_label === null ? null : (
        <span className="text-xs text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
          {card.basis_label}
        </span>
      )}
    </>
  );

  if (!card.available || target === null) {
    return (
      // BR-SHL-025: not a link and must not LOOK like one — dashed top rule,
      // dimmed, default cursor, and the reason on the card itself.
      <div
        className="flex cursor-default flex-col gap-1 border-t-2 border-dashed border-t-divider px-4 py-3.5 text-inherit no-underline opacity-72"
        data-report-key={card.key}
        title={card.reason_detail ?? undefined}
      >
        {body}
        <span className="text-sm leading-normal text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
          {reasonSentence(card, t)}
        </span>
      </div>
    );
  }
  return (
    <Link
      // ⚠ **NO FILL.** p20 draws a card as a TOP RULE and three lines of text
      // on the page's own ground — there is no box. The 23-card grid carried
      // `bg-surface`, which drew a grey panel behind every card and is the
      // first thing that differs when the running screen is put beside the
      // drawing (B14 rule 41, and hard-won law 6: no gate reads rendered
      // output). Removed on 2026-09-26 after looking at both.
      className="flex flex-col gap-1 border-t-2 border-t-divider px-4 py-3.5 text-inherit no-underline hover:border-t-accent focus-visible:border-t-accent"
      data-report-key={card.key}
      to={props.tenantPath(target)}
    >
      {body}
    </Link>
  );
}

export interface ReportLibraryPageProps {
  /** Which sub-tab this address opens on. `/reports/custom` passes `custom`;
   *  `/reports` passes nothing and opens on Standard, which is p23's own
   *  ruling — *"The rail lands on Catalogue → Standard, always; Custom is one
   *  click in, deliberately, because on day one it is empty at every
   *  utility."* */
  initialOrigin?: "standard" | "custom";
  client?: ApiClient; // test seam
}

const STANDARD = "standard";
const CUSTOM = "custom";

export function ReportLibraryPage(props: ReportLibraryPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const cell = useAccessCell(REPORTS_PERMISSION, client);

  // ── `CR-142-BRC07` `P5.10` (2026-09-27) · `/reports/custom` IS A REAL
  // ADDRESS NOW, AND IT IS STILL A RESERVED SEGMENT ───────────────────────
  //
  // ⚠ **THE WORD STAYS RESERVED EVEN THOUGH IT NOW OPENS A SCREEN**, exactly
  // as `history` did in `P3.2`: a tenant may still try to name a report
  // *Custom*, and `apps/reports/definitions.RESERVED_KEYS` still refuses it
  // by name. The segment claims the address; the save refuses the collision.
  // Both halves are required and `P5.2`'s own ⚠ says so.
  //
  // ⚠ **`initialOrigin` RATHER THAN A SECOND COMPONENT.** `/reports` and
  // `/reports/custom` are ONE screen on two sub-tabs — p23's DOORS row calls
  // the strip *"the whole argument for a sub-tab over a filter"* — and a
  // second page would be a second catalogue read, a second toolbar and a
  // second empty state to keep in step.
  const [origin, setOrigin] = useState<"standard" | "custom">(
    props.initialOrigin ?? STANDARD,
  );
  const [query, setQuery] = useState<CatalogueQuery>({ q: "", group: "", service: "" });
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);

  const request: ReportLibraryQuery = useMemo(
    () => ({ ...query, origin, page, per }),
    [query, origin, page, per],
  );

  const libraryQuery = useQuery({
    queryKey: [...reportLibraryQueryKey, request],
    queryFn: () => getReportLibrary(client, request),
    retry: false,
    // A search that blanks the grid between keystrokes reads as "no reports",
    // which is the claim this whole screen is built not to make.
    placeholderData: keepPreviousData,
  });

  if (isDenied(cell) || (libraryQuery.isError && isPermissionDenied(libraryQuery.error))) {
    return (
      <PermissionDenied
        helper={t("reports.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const library = libraryQuery.data;

  return (
    <div className="fin-page">
      <PageHeader
        kicker={t("reports.kicker")}
        title={t("reports.library.title")}
        // ── `CR-142-BRC07` `P5.10` (2026-09-27) · THE HOLD HAS EXPIRED ────
        //
        // ⚠ **THIS BUTTON WAS HELD FOR FOUR PHASES AND THE HOLD IS RELEASED
        // IN THE SAME COMMIT AS THE BUILDER.** p20 callout ② held it —
        // *"not drawn until Phase 5, when the builder lands. Until then the
        // screen says the thing is not built rather than showing a button
        // that does nothing"* — and `phaseHolds.dom.test.tsx` is what made
        // sure somebody came back for it, which is `DEF-CWP-3925`'s whole
        // lesson: landing a screen and releasing the control that pointed at
        // it are two acts and only the first one feels like the work.
        //
        // ⚠ **IT SITS ABOVE THE SUB-TAB STRIP, NOT INSIDE `Custom`**, which
        // is callout ②'s own placement and was verified against p21's drawing
        // rather than taken from the sentence: 1·2A draws it at the top right
        // of the page head, beside the title and above BOTH strips. The
        // reason is in the callout — *"the usual way a custom report gets
        // made is opening a standard one and changing it"* — so a control
        // only reachable from the empty Custom tab would be the last place a
        // clerk looks.
        //
        // ⚠⚠ **IT WENT TO `/reports/custom` UNTIL 2026-09-28 AND THAT IS THE
        // PAGE IT IS STANDING ON (`DEF-REP-7640`).** The hold expired in the
        // same commit as `P5.10`, which mounted THIS catalogue's Custom
        // sub-tab at that address — so from `/reports/custom` the press was a
        // no-op and from `/reports` it switched sub-tab to an empty list. The
        // Product Owner pressed it on deployed `v2.388.0` and nothing
        // happened. **The hold-expiry test asserted the button was DRAWN and
        // never asserted where it LANDS**, and the three cases that had held
        // it were deleted rather than amended when the hold expired, so after
        // 2026-09-27 nothing in the repo mentioned this control at all.
        // `phaseHolds.dom.test.tsx` asserts the destination BY ADDRESS and BY
        // THE SCREEN THE ROUTER MOUNTS THERE now, which is what hard-won law
        // 2's mirror asks for and is the assertion that was missing.
        //
        // PO ruling 2026-09-28, verbatim: *"Opens the editor on a blank
        // definition, then Save as"*. `REPORT_BUILDER_NEW_ROUTE` is where,
        // and why that address rather than `/reports/new/edit` is recorded on
        // the constant itself.
        primaryAction={
          <Button
            variant="primary"
            onClick={() => navigate(tenantPath(REPORT_BUILDER_NEW_ROUTE))}
          >
            + {t("reports.library.buildYourOwn")}
          </Button>
        }
        rollup={
          library === undefined ? undefined : (
            <span className="fin-rollup">
              {/* p20 callout ①: the sub-line states the SHAPE of the catalogue
                  and never an availability count, because after Phase 1 every
                  card here runs. It describes the catalogue, not the page. */}
              <span className="fin-rollup-item">
                {/* ⚠ These three are the CATALOGUE's counts and not the
                    page's. Counting sub-groups from `library.groups` — the
                    groups this page draws — read "0 sub-groups" on the Custom
                    sub-tab, which draws none. Found by looking at the screen. */}
                {t("reports.library.shape", {
                  reports: library.total,
                  groups: library.group_total,
                  subGroups: library.sub_group_total,
                })}
              </span>
            </span>
          )
        }
      />

      {/* ── `CR-142-BRC07` `P3.2`/`P3.3` (2026-09-27) · THE DOOR TO HISTORY ──
          The strip above this one IS drawn now, and this comment used to say
          it was not. p20 callout ③ held it on a ruling — *"The strip is not
          drawn until the second tab exists — a one-tab strip is furniture"* —
          and Phase 3 is what makes a second tab exist. `SubTabs` enforces the
          ruling itself: it returns `null` below two tabs, so the strip could
          not have been drawn early even by accident.

          ⚠ **THIS IS THE DOOR, AND WITHOUT IT THE TOAST IS STILL BROKEN.**
          `P3.3` changes the export toast to name *History*; a name with no way
          to reach it is the same fault one word along. p39 counts three doors
          to `5·1` and records that TODAY THE COUNT IS ZERO. This is the first,
          and it is the one that is always there. */}
      <ReportsTabs active="catalogue" />

      {/* p20 callout ④ — Standard · Custom, and Custom reads 0 on day one,
          which is the point: an empty sub-tab is how a clerk learns they can
          author a report. */}
      <SubTabs
        data-sub-tabs="catalogue-origin"
        label={t("reports.library.tabsLabel")}
        activeId={origin}
        onSelect={(id) => {
          setOrigin(id as "standard" | "custom");
          setPage(1);
        }}
        tabs={[
          {
            id: STANDARD,
            label: t("reports.library.tab.standard"),
            count: library?.origin_counts.standard,
          },
          {
            id: CUSTOM,
            label: t("reports.library.tab.custom"),
            // ⚠ BOTH counts, always — callout ④. A bare `Custom` teaches a
            // clerk nothing, and the zero is the thing worth saying.
            count: library?.origin_counts.custom,
          },
        ]}
      />

      <CatalogueToolbar
        query={query}
        onChange={(next) => {
          setQuery(next);
          setPage(1);
        }}
        groups={library?.group_options ?? []}
        services={library?.vocabularies.services ?? []}
      />

      {libraryQuery.isError && library === undefined ? (
        <Panel role="alert">
          <h3>{t("finance.error.title")}</h3>
          <p className="fin-absent-reason">{apiErrorText(libraryQuery.error, translate)}</p>
        </Panel>
      ) : library === undefined ? (
        <LoadingSkeleton variant="card" />
      ) : library.cards.length === 0 ? (
        // ⚠ **P1.5's OUTCOME IS THIS BRANCH.** *"A catalogue with zero rows
        // renders the empty state, not 23 cards."* There is no literal tuple
        // behind this screen any more and no fallback to one; an empty answer
        // renders empty. `EmptyList` draws NO button when no `ctaLabel` is
        // given, which is what keeps the Phase 5 builder out of Phase 1.
        <EmptyList
          title={
            origin === CUSTOM
              ? t("reports.library.customEmpty.title")
              : t("reports.library.empty.title")
          }
          helper={
            origin === CUSTOM
              ? t("reports.library.customEmpty.helper")
              : t("reports.library.empty.helper")
          }
          // ⚠ **NO `ctaLabel` HERE, AND THAT IS DELIBERATE RATHER THAN A
          // MISSED CALLOUT.** p22 callout ③ draws the action twice — once in
          // the head and once in the empty state — and on `Custom` the second
          // one would point at the page the clerk is already standing on,
          // which is hard-won law 2's mirror: a live control that opens
          // nothing. The empty state's HELPER carries the path instead, in
          // p22's own words — *"Open a standard report. Change it. Save it
          // here."* — three sentences of three, which is rule 33's own
          // preference. `EmptyList` draws no button at all without a label.
          //
          // ⚠ **THE BUILD-FROM-SCRATCH DOOR IS BUILT (`DEF-REP-7640`,
          // 2026-09-28).** 1·2B draws a report whose *Based on* reads *from
          // scratch*, and `+ Build your own` in the page head above now opens
          // screen 2·2 on a blank definition at `REPORT_BUILDER_NEW_ROUTE` —
          // PO ruling 2026-09-28, *"Opens the editor on a blank definition,
          // then Save as"*. The path the callout itself calls *"the usual
          // way"* — open a standard report and change it — is live too.
          //
          // ⚠ **THIS PARAGRAPH CITED `DEF-REP-6866` UNTIL THAT DAY AND THAT
          // IS A REAL ROW ABOUT SOMETHING ELSE (`DEF-REP-7646`)** — the
          // catalogue asking VIEWERS rather than the runner, so every
          // tenant-authored report read *"This report cannot be produced
          // yet"*. Nothing in this repo checks that a cited defect is about
          // the thing it is cited for, so the sentence read as *tracked* for
          // two days while the from-scratch door was tracked nowhere. It is
          // `DEF-2804`'s shape one family over: a real id, read for a
          // different real id.
          //
          // The remaining gap is a PREVIEW before the first save:
          // `GET /reports/{key}` resolves a saved definition, so a draft that
          // has never been saved has no read path and the builder shows its
          // sections and its shape and no rows. Stated on screen in four
          // words and in the decision log of 2026-09-28, rather than left to
          // a citation.
        />
      ) : (
        <>
          {library.groups.map((group) => {
            const cards = library.cards.filter((card) => card.group === group.code);
            if (cards.length === 0) {
              return null;
            }
            return (
              <section key={group.code} className="mb-6 mt-2" data-report-group={group.code}>
                {/* p20 callout ⑦ — the group heading carries its sub-groups,
                    and both come from `report_categories`. Never a literal in
                    the front end, which is what P1.5 asserts. */}
                <Kicker>
                  {[group.name, ...group.sub_groups.map((sub) => sub.name)].join(" · ")}
                </Kicker>
                <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
                  {cards.map((card) => (
                    <ReportCardTile
                      key={card.key}
                      card={card}
                      t={translate}
                      tenantPath={tenantPath}
                    />
                  ))}
                </div>
              </section>
            );
          })}

          {/* p20 callout ⑧ — it pages. Forty-five cards do not need paging at
              T7 and `NFR-3` admits no exceptions, so it pages anyway; the rule
              exists because four endpoints in this product claimed an exception
              and are 13× short at T5. */}
          <ListPager
            total={library.count}
            page={library.page}
            per={library.per as PageSize}
            onPage={setPage}
            onPer={(next) => {
              setPer(next);
              setPage(1);
            }}
          />
        </>
      )}
    </div>
  );
}

export default ReportLibraryPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 1 · P1.2 · P1.3 · P1.5 · P1.8 (05-prototype/09 Reports Build Brief.pdf p19-p21 read as IMAGES per B14 rule 42) · PO ruling 2026-09-26 "go as per phases - tasks" (12-governance/02-decision-log.md, 76be101a3)
// screens: S44
// generated: 2026-08-16 by story-coder · REBUILT 2026-09-26 by lane REP-P1; AMENDED 2026-09-28 by lane REP-BUILD-YOUR-OWN (`DEF-REP-7640` — `+ Build your own` opens the builder at `REPORT_BUILDER_NEW_ROUTE` instead of the catalogue it is standing on; `DEF-REP-7646` — the Custom empty state cited a real defect about something else)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — catalogueScreen.dom.test.tsx found 23 cards in 3 groups, no search box, no filter and no sub-tab strip before this rebuild; phaseHolds.dom.test.tsx failed on the four-tab strip's absence being unasserted. [2026-09-28] The destination cases were run against this file with the old `/reports/custom` target restored: *expected '/brazosbend/reports/custom/new', received '/brazosbend/reports/custom'* from the catalogue, and *expected '/brazosbend/reports/custom' not to be '/brazosbend/reports/custom'* from the Custom sub-tab — the no-op the PO reported.
// exceptions: (0) the report NAME comes out of the row and the retired `reports.card.<key>.name` catalogue is no longer consulted — nine authored translations are lost and the gap is DEF-REP-6817 · (1) ⚠ **SUPERSEDED 2026-09-27/28**: the four-tab strip and `+ Build your own` are both drawn now, and the button's release is what `DEF-REP-7640` is about · (2) the drawn `▦` column chooser is not built: the document's own TABLE CONTROLS row says "Columns n/a, a card grid" · (3) the default page is 50 rather than the drawn 20 — B14 rule 37 makes a drawn number an illustration and 50 is one of rule 16's five ratified sizes
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
