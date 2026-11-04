// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-013 (the header columns and one relaxed key — two Water
//           templates in one list) · US-WRK-014 (the CONTENTS cell counts the
//           seven collections) · US-WRK-015 (the write service behind the
//           row actions) · US-WRK-018 (STATUS, and what v2 means).
//           Screens: Work-013 (`wireframes/Work-013.png`), template W1
// Rules:    BR-WRK-010 (more than one template per service) · BR-WRK-012
//           (Delete refused while referenced; Deactivate instead) ·
//           BR-MET-109 (the templates are the utility's OWN) · BR-SHL-025 (a
//           control that cannot act is DISABLED WITH ITS REASON) · B14 rules
//           2 (one page header) · 5 · 6 · 12 (one toolbar) · 15 (icons for
//           row actions) · 16 (the shared pager footer) · 17 (an empty state
//           that says how to fill it) · 19 · 20 (one table type) · 21
//           (Tailwind; on route-b-migrated.txt) · 31 (no database id is a
//           visible value) · 32 (one sentence per section)
// Tests:    src/features/work/TemplatesPage.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · WorkShell.tsx (the Templates
//           tab) · src/routing/screenIds.ts (WRK-04) · src/api/queryClient.ts
//           (`queryKeys.workTemplates`) · REPLACES WorkOrderTemplatesPage.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS SCREEN REPLACES A BLANK PAGE THAT WAS CORRECT WHEN IT WAS WRITTEN.**
// `WorkOrderTemplatesPage.tsx` shipped on 2026-08-25 as four sentences saying
// *not built yet*, on the PO's own ruling (*"Just keep it black - and show
// note that Work orders not yet build"*). Its own header recorded, measured,
// why: there was no writer for `work_order_templates` at all, `sample_data.py`
// said in as many words that *"a `create_work_order_template` service is
// OWED"*, and nothing read the 24 seeded starter rows. All three are now
// false — wave D built the service and this list is its reader — so the
// stated absence goes with the commit that makes it untrue. That is hard-won
// law 2's mirror: a refusal that has stopped being true is a live screen
// behind a dead door (`DEF-CWP-3925`).
//
// ⚠ **`ST-0002` IS THE VISIBLE REFERENCE AND THE UUID IS NEVER DRAWN** — B14
// rule 31, ruled by the PO in the words *"no Databse ID on screen - that is a
// rule"*. The uuid is what the pencil opens; `template_no` is what a
// supervisor reads down a phone. A DRAFT has no number at all, because a
// number is allocated on publish and never reused (`BR-TEN-035`), so the cell
// draws a dash rather than inventing one.
//
// ⚠ **THE CONTENTS CELL COUNTS ZERO RATHER THAN GOING BLANK** (`US-WRK-013`
// TC-4). A seeded starter with nothing behind it reads *0 tasks · 0 parts ·
// 0 readings*: a blank cell reads as a bug, and a zero reads as an answer.
//
// ⚠ **`+ New template` IS LIVE SINCE 2026-09-05 — THE HOLD EXPIRED AND THE
// TEST IT WAS WRITTEN WITH IS WHAT SAID SO.** This paragraph read *"is NOT
// rendered, because the builder is wave E's"*, beside a case asserting the
// button's absence by ADDRESS. `TemplateBuilder.tsx` landed, the case went red
// and named the button, and the primary is here — pointing at
// `…/work/templates/new`, opening `Work-014` at step 1.
//
// That is `DEF-CWP-3925`'s prevention run once end to end: **when you write a
// hold, write the test that fires when the hold expires, in the same commit**,
// and when you land the screen, grep for the control that was holding it. The
// row action is a PENCIL again for the same reason — the eye that opened the
// detail was a stand-in while there was no editor to point at.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ButtonLink } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { EyeIcon, PencilIcon } from "@/components/icons";
import { Note } from "@/components/TextBits";
import { FilterBar } from "@/components/FilterBar";
import { defaultRequestState } from "@/components/tableTypes";
import { seedQueryFromUrl } from "@/routing/seedQueryFromUrl";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { useTenantPath } from "@/routing/tenantPath";

import { useWorkTabs, WORK_ORDER_TEMPLATES_ROUTE } from "./WorkShell";
// CR-070 wave E — the eight-step builder. ONE function each says where a
// template is opened and where it is edited (law 5: one source, derive).
import { templateEditPath, WORK_TEMPLATE_NEW_ROUTE } from "./TemplateBuilder";
import { scopeWord } from "./TemplateSummary";
import { listTemplates } from "./workEndpoints";
import type { TemplateRow, TemplateStatus } from "./workEndpoints";

/** r10's own badge for the templates list — `01-overview.md` §6, Work-013 ↔
 *  WRK-04. `WRK-19` was the blank page's row and retires with it. */
export const WORK_TEMPLATES_SCREEN = "WRK-04";

/**
 * The Work order section's templates screen.
 *
 * ⚠ Tenant-relative, and the STATIC segment is the whole path — there is no id
 * converter above it, so the `/connections/new` trap `App.tsx` carries a
 * comment about cannot bite here. Declared before the detail route anyway, so
 * the ordering stays true the day somebody adds a looser one.
 */
export { WORK_ORDER_TEMPLATES_ROUTE } from "./WorkShell";

/** Where the pencil goes. ONE function, so the list, the detail's Duplicate
 *  and any later caller cannot disagree about where a template lives (law 5). */
export function templateDetailPath(templateId: string): string {
  return `${WORK_ORDER_TEMPLATES_ROUTE}/${templateId}`;
}

type Translate = (key: string, params?: Record<string, unknown>) => string;

const STATUS_TONE: Record<TemplateStatus, "success" | "info" | "muted"> = {
  published: "success",
  draft: "info",
  inactive: "muted",
};

/**
 * `Work-013`'s CONTENTS cell, in words rather than in three numbers a reader
 * has to decode. `2 tasks · 0 parts · 1 reading` is the drawing's own text.
 *
 * Exported so the test can assert the zero case without a DOM: *"never
 * blank"* is a rule about this function, not about a screenshot.
 */
export function contentsSentence(row: TemplateRow, t: Translate): string {
  // ⚠ **THE COUNT GOES THROUGH `{{count}}`, NEVER INTO A TEMPLATE STRING.**
  // `defaultValue: \`${n} readings\`` builds the sentence in JavaScript and
  // hands i18next a finished string — which loses the plural in every language
  // that has one, and puts a raw value into a text position, which is what
  // `G44` clause (c) refuses. The placeholder form is both the correct i18n
  // shape and the one the catalogue keys in `scratchpad/lane-WD-keys.json`
  // already use.
  return [
    t("work.templates.contents.tasks", {
      count: row.contents.tasks,
      defaultValue: "{{count}} tasks",
    }),
    t("work.templates.contents.parts", {
      count: row.contents.parts,
      defaultValue: "{{count}} parts",
    }),
    t("work.templates.contents.readings", {
      count: row.contents.readings,
      defaultValue: "{{count}} readings",
    }),
  ].join(" · ");
}

/**
 * The table's declaration — `Work-013`'s eight columns in the drawing's order.
 *
 * Exported so the test can read the column set without mounting anything, the
 * same posture `partsTableConfig` takes one tab along.
 */
export function templatesTableConfig(
  t: Translate,
  cells: {
    template: (row: TemplateRow) => React.ReactNode;
    gate: (row: TemplateRow) => React.ReactNode;
    status: (row: TemplateRow) => React.ReactNode;
    actions: (row: TemplateRow) => React.ReactNode;
  },
  serviceOptions: { value: string; label: string }[],
): TableConfig<TemplateRow> {
  return {
    screenId: WORK_TEMPLATES_SCREEN,
    getRowId: (row) => row.id,
    // B14 rule 19 — what the search MATCHES, as the server matches it
    // (`apps/work/selectors.templates_page`: the name OR the job type).
    searchFields: ["name", "job_type"],
    searchPlaceholder: "work.templates.search",
    // The drawing's own control: *Filter by service ▾*. It is the ONE filter
    // this list declares, and BR-SHL-010 says a screen renders only what it
    // declares — so there is no filter furniture for anything else.
    filters: [
      {
        name: "service",
        label: t("work.templates.filter.service", { defaultValue: "Service" }),
        options: serviceOptions,
      },
    ],
    defaultSort: { sort: "service", dir: "asc" },
    columns: [
      {
        key: "name",
        label: t("work.templates.col.template", { defaultValue: "Template" }),
        identity: true,
        cell: cells.template,
      },
      {
        key: "service",
        label: t("work.templates.col.service", { defaultValue: "Service" }),
        cell: (row) => (row.service === null ? <Dash /> : <span>{row.service.name}</span>),
      },
      {
        // P3.12 (`DEF-WRK-9577`) — what the template is DONE TO, the same word
        // the template's summary uses. Image 43 does not draw it; P3.12 asks
        // for it on the list (*"show a For column"*) and one fact keeps one
        // word, so it reads *Done to* here as on images 44 and 55.
        key: "scope",
        label: t("work.template.summary.doneTo", { defaultValue: "Done to" }),
        cell: (row) => {
          const word = scopeWord(row.scope, t);
          return word === null ? <Dash /> : <span>{word}</span>;
        },
      },
      {
        key: "job_type",
        label: t("work.templates.col.jobType", { defaultValue: "Job type" }),
        cell: (row) => (row.job_type === null ? <Dash /> : <span>{row.job_type.name}</span>),
      },
      {
        key: "contents",
        label: t("work.templates.col.contents", { defaultValue: "Contents" }),
        cell: (row) => <span>{contentsSentence(row, t)}</span>,
      },
      {
        key: "is_gate",
        label: t("work.templates.col.gate", { defaultValue: "Gate" }),
        cell: cells.gate,
      },
      {
        key: "skill",
        label: t("work.templates.col.skill", { defaultValue: "Skill" }),
        cell: (row) => (row.skill === null ? <Dash /> : <span>{row.skill.name}</span>),
      },
      {
        key: "est_duration_minutes",
        label: t("work.templates.col.est", { defaultValue: "Est." }),
        numeric: true,
        cell: (row) =>
          row.est_duration_minutes === null ? (
            <Dash />
          ) : (
            // One line: *150 min* broke over two once *Done to* joined the
            // row at 1440 (CR-168 P3.12).
            <span className="tabular-nums whitespace-nowrap">
              {t("work.templates.minutes", {
                count: row.est_duration_minutes,
                defaultValue: "{{count}} min",
              })}
            </span>
          ),
      },
      {
        key: "status",
        label: t("work.templates.col.status", { defaultValue: "Status" }),
        cell: cells.status,
      },
      {
        key: "actions",
        label: t("work.templates.col.actions", { defaultValue: "Actions" }),
        cell: cells.actions,
      },
    ],
  };
}

export interface TemplatesPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

/** `Work-013` at wave D: the head, the toolbar, the list and its footer. */
export function TemplatesPage(props: TemplatesPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const translate: Translate = (key, params) => t(key, params);

  // ── DEF-WRK-4094 · CR-073 ────────────────────────────────────────────
  // Universal search's per-group "View all" opens this list as
  // `?q=<term>` (BR-SHL-011's grammar). This screen held its table state
  // locally and never read the query string, so that link promised a
  // filtered list and delivered the whole register — with `tsc` green, the
  // route resolving and the screen rendering perfectly.
  // Seeded ONCE, at mount, and only `q`: this screen does not WRITE the URL
  // back, so reading a page or a sort it will never write would restore, on
  // reload, a state the user had since left. See seedQueryFromUrl's docstring.
  const [searchParams] = useSearchParams();
  const [state, setState] = useState<TableRequestState>(() =>
    seedQueryFromUrl(
      defaultRequestState(templatesTableConfig(translate, EMPTY_CELLS, [])),
      searchParams,
    ),
  );

  const listQuery = useQuery({
    queryKey: queryKeys.workTemplates(state.q, state.filters.service ?? "", state.page, state.per),
    queryFn: () =>
      listTemplates(
        { q: state.q, service: state.filters.service, page: state.page, per: state.per },
        client,
      ),
  });

  // The service options come from the rows themselves rather than from a
  // second endpoint: the filter can only usefully offer services this tenant
  // HAS templates for, and asking `/settings/services` would offer eleven
  // options of which nine find nothing.
  const serviceOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const row of listQuery.data?.results ?? []) {
      if (row.service !== null) seen.set(row.service.code, row.service.name);
    }
    return [...seen].map(([value, label]) => ({ value, label }));
  }, [listQuery.data]);

  const config = useMemo(
    () =>
      templatesTableConfig(
        translate,
        {
          template: (row) => (
            <span className="flex flex-col">
              <Link className="font-medium" to={tenantPath(templateDetailPath(row.id))}>
                {row.name}
              </Link>
              {/* B14 rule 31 — the NUMBER is the visible reference. A draft has
                  none yet, so the second line is simply absent rather than a
                  placeholder that looks like a number. */}
              {row.template_no !== null && (
                <span className="text-sm text-neutral-600 tabular-nums">{row.template_no}</span>
              )}
            </span>
          ),
          // GATE — whether THIS template is the job that turns the service on,
          // and where it is not, the utility's own reason why its service has
          // none (`DEF-WRK-4048`).
          //
          // ⚠ **THE DRAWING NAMES THE GATE AND THIS COLUMN CANNOT, BECAUSE THE
          // TWO COUNT A TEMPLATE DIFFERENTLY.** `Work-013` draws one row per
          // job SET — *New connection · Electric*, GATE *Meter set ⚑* — so its
          // GATE cell names a step INSIDE the row. Here a template IS that
          // step: the seeded electric set is *Service drop* and *Meter set*,
          // two rows, and `is_gate` is on the second. Printing *Meter set* in
          // this cell would repeat the TEMPLATE column beside it, which is
          // B14 rule 32's *a row never repeats what its own control offers*.
          // Stamped in `08-screen-layouts.md`'s divergence table.
          //
          // ⚠ **`no_gate_reason` WAS SEEDED, SERVED, TYPED AND RENDERED BY
          // NOTHING FOR TWO DAYS.** `sample_data.py` says of it, in as many
          // words, *"`no_gate_reason` IS shown — it is what `Work-013`'s GATE
          // column has to say when the cell is empty and somebody asks why"*,
          // and `test_tc3_the_ungated_services_carry_a_reason_a_clerk_can_read`
          // repeats it. The cell drew a bare dash. That is hard-won law 2 with
          // law 1 on top of it: a column built for one screen, reaching that
          // screen's props, and dropped one line short of a reader — with
          // `tsc`, `G13` and every test green, because G13 asks whether a PROP
          // is passed and this value arrives inside a row.
          //
          // ⚠ **THE SENTENCE IS THE TENANT'S, NOT OURS, WHICH IS WHY IT MAY RUN
          // PAST B14 RULE 33's SIX-WORD FACT CAP** — *"gated on the water
          // service it derives from"* is eight. The cap governs copy we author;
          // this string is a column on a row the utility owns and edits
          // (`BR-MET-109`), the seeded wording is quoted verbatim from
          // `US-WRK-019` TC-3, and a backend test pins it. Shortening it here
          // would put two different sentences in front of one clerk.
          gate: (row) =>
            row.is_gate ? (
              <StatusPill tone="danger">
                {translate("work.templates.gate.yes", { defaultValue: "Gate" })}
              </StatusPill>
            ) : row.no_gate_reason !== null && row.no_gate_reason !== "" ? (
              <span className="text-sm text-neutral-600" data-no-gate-reason="">
                {row.no_gate_reason}
              </span>
            ) : (
              // No gate AND no reason stored — a template the utility wrote
              // itself, where nobody has said why. A dash is the honest answer;
              // inventing one would be this screen deciding what a tenant meant.
              <Dash />
            ),
          status: (row) => (
            <StatusPill tone={STATUS_TONE[row.status]}>
              {translate(`work.templates.status.${row.status}`, {
                defaultValue:
                  row.status === "published"
                    ? "Published"
                    : row.status === "draft"
                      ? "Draft"
                      : "Inactive",
              })}
            </StatusPill>
          ),
          actions: (row) => (
            <RowActions>
              {/* B14 rule 15 — ICONS with accessible names, never text links.
                  `Work-013` draws the PENCIL, and the pencil edits: it opens
                  the eight-step builder on this template (CR-070 wave E). The
                  eye beside it opens the detail, which is where Versions,
                  Usage and Audit live — two different destinations, so two
                  glyphs rather than one that has to mean both. */}
              <RowActionLink
                label={translate("work.templates.action.edit", {
                  defaultValue: "Edit this template",
                })}
                icon={<PencilIcon />}
                to={tenantPath(templateEditPath(row.id))}
              />
              <RowActionLink
                label={translate("work.templates.action.open", {
                  defaultValue: "Open this template",
                })}
                icon={<EyeIcon />}
                to={tenantPath(templateDetailPath(row.id))}
              />
            </RowActions>
          ),
        },
        serviceOptions,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, serviceOptions],
  );

  // The module strip, as the shared header's own props — read at the top level
  // of the component, never inside the JSX, so the hook rule holds by shape.
  const strip = useWorkTabs(
    t("work.templates.sentence", {
      defaultValue:
        "The jobs each service needs, written down once. Every work order you raise is a copy of one of these.",
    }),
  );

  const counts = listQuery.data?.counts;

  return (
    <div data-work-templates="" data-screen={WORK_TEMPLATES_SCREEN}>
      <PageHeader
        // ⚠ `Work-013`'s own primary, live since CR-070 wave E. It is a
        // `ButtonLink` and not a button because it NAVIGATES, so middle-click
        // and open-in-new-tab keep working (the kit's own reason for having
        // one). `secondaryActions` rather than a hand-rolled row: the kit
        // decides where a header's actions sit (B14 rules 2 and 36).
        secondaryActions={
          <ButtonLink
            variant="primary"
            data-new-template=""
            to={tenantPath(WORK_TEMPLATE_NEW_ROUTE)}
          >
            {t("work.templates.new", { defaultValue: "New template" })}
          </ButtonLink>
        }
        // B14 rule 2 — ONE page header, and it carries the module's tab strip:
        // kicker · title · the strip · the one sentence. Until 2026-09-05 the
        // strip was a hand-rolled `<nav>` drawn ABOVE this header by
        // `WorkShell`, which is what made Work the only module in the product
        // whose tabs were boxed rather than underlined (`DEF-WRK-3955`).
        //
        // ⚠ THE SENTENCE IS THE TAB'S EXPLAINER AND NOT A ROLL-UP: the roll-up
        // slot sets no width and `.page-header-explainer` sets
        // `max-width: var(--desc-measure)` — B14 rule 18's 80% cap, which this
        // description ran past on every screen wider than the sentence.
        kicker={t("work.templates.kicker", { defaultValue: "Work" })}
        title={t("work.templates.title", { defaultValue: "Work order templates" })}
        {...strip}
      />

      <DataTable<TemplateRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? {
                reason: t("work.templates.loadFailed", {
                  defaultValue: "The templates could not be loaded.",
                }),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        filterBarSlot={<FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />}
        empty={{
          // B14 rule 17 — what is missing, AND the action that fills it. Until
          // 2026-09-05 the action shipped DISABLED with the reason *"the
          // template builder opens with the next release"*, because it did
          // not. It does; the reason is gone with the same commit that made it
          // untrue, and the button opens the builder.
          title: t("work.templates.empty.title", { defaultValue: "No templates yet" }),
          helper: t("work.templates.empty.helper", {
            defaultValue: "Your utility has not written down the jobs a service needs.",
          }),
          ctaLabel: t("work.templates.empty.cta", { defaultValue: "New template" }),
          onCta: () => navigate(tenantPath(WORK_TEMPLATE_NEW_ROUTE)),
        }}
      />

      {/* `Work-013`'s CountFooter — *"4 published · 1 draft · 1 inactive"*.
          The kit's own pager sits above this and answers rule 16's *Showing
          1–50 of N*; these three figures are about the WHOLE list and a pager
          cannot carry them, so they are a sentence beside it rather than a
          second, competing pager.

          ⚠ The three numbers come from the SERVER's `counts`, not from
          `results`. Counting the rows in hand would be a true sentence about
          the wrong set the moment the list runs past one page — the same trap
          `Work-009`'s *oldest waiting* records one tab along. */}
      {counts !== undefined && (
        <Note className="tabular-nums" data-templates-footer="">
          {t("work.templates.footer", {
            published: counts.published,
            draft: counts.draft,
            inactive: counts.inactive,
            defaultValue:
              "{{published}} published · {{draft}} draft · {{inactive}} inactive",
          })}
        </Note>
      )}
    </div>
  );
}

/** The config needs cells to compute its default state, and the default state
 *  is computed before the cells exist. These render nothing and are never
 *  drawn — `defaultRequestState` reads only `defaultSort` and `filters`. */
const EMPTY_CELLS = {
  template: () => null,
  gate: () => null,
  status: () => null,
  actions: () => null,
};

export default TemplatesPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-013/014/015/018@6eedbd26 (EP-WRK-03) · 08-screen-layouts.md Work-013 · 09-component-inventory.md W1 · wireframes/Work-013.png
// generated: 2026-09-05 by the CR-070 wave D build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work · G31 (via src/styles/route-b-migrated.txt) · G13
// exceptions: E4 the GATE cell does NOT name the gate the way `Work-013` draws it (*Meter set ⚑*) — the drawing counts one row per job SET and this list counts one row per STEP, so the gate's name IS the TEMPLATE column beside it and repeating it is B14 rule 32's *a row never repeats what its own control offers*. Where there is no gate the cell now carries the utility's own stored reason instead of a dash (DEF-WRK-4048) · E4 the drawing's *Filter by service ▾* renders as B14 rule 12's toolbar — `[All] [Service: Water ×] [+ Filter ▾]` — the shape DEF-442 put there on the PO's own instruction; the dimension is the same one, only the control differs · E4 there is no `YOUR TEMPLATES` caption above the table: no list screen in the product draws one (41 `DataTable` call sites, zero captions) and growing a Work-only convention is what B14 rule 36 forbids. Decided once for the module in `08-screen-layouts.md` · E4 no download glyph — CR-045 owns it and it is not built on any Work screen
// ⚠ THIS LINE CARRIED THREE EXPIRED HOLDS UNTIL 2026-09-05 (DEF-WRK-4046): it said `+ New template` was not rendered, that the row action was an eye rather than the drawing's pencil, and that the locale keys were still owed a follow-up commit. All three had been true when written and none was true when read — the builder landed in wave E, the pencil came back with it, and the keys are in all eleven catalogues. The file's own ⚠ paragraphs above were updated the day the button landed and this line was not, which is the whole mechanism: a lane corrects the prose it is reading and not the footer it is not.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
