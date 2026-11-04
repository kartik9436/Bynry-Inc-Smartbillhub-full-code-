// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6723 — *"on this screen user is unable to see detail screen
//          of Journal entry - we cannot click on eye."* (PO, v2.351.84)
// Story:   US-LED-013 · A1 S56 (*"Journal list + detail"*, 11b §2.10 line 436)
// Drawing: 05-prototype/07 Finance Blueprint.pdf p020 item 7 (the eye), p079
//          gap G3 (why it never opened). Read as IMAGES (B14 rule 42).
// Rules:   see `JournalEntryDetail.tsx`, which does all the drawing. This file
//          is the ROUTE and the FETCH and nothing else (B14 rule 43).
// Tests:   07-frontend/src/features/ledger/journalEntryDoor.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE LINES PAGE IN THE URL, NOT IN COMPONENT STATE (`NFR-3` + BR-SHL-011)
// ══════════════════════════════════════════════════════════════════════════
// `?linePage=` rather than `?page=`, because this screen is opened FROM a
// paged list and a clerk who goes Back must land on the page of the JOURNAL
// they left. One name for one pager is how `CR-060` C14's round trip stays
// true. An out-of-range page CLAMPS server-side and never 4xx (BR-SHL-011).

import { useTranslation } from "react-i18next";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getJournalEntry } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { ReportGapList } from "@/features/reports/reportsShared";

import {
  FINANCE_TABS,
  FINANCE_TAB_GL,
  financeTabPath,
  gapSentence,
} from "./financeShared";
import {
  JOURNAL_ENTRY_DETAIL_SCREEN_ID,
  JournalEntryDetailBody,
  journalSourcePath,
} from "./JournalEntryDetail";

export { JOURNAL_ENTRY_DETAIL_ROUTE, journalEntryDetailPath } from "./JournalEntryDetail";

export interface JournalEntryDetailPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
  locale?: string;
}

export function JournalEntryDetailPage(props: JournalEntryDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const entryId = params.entryId ?? "";
  const linePage = Number(searchParams.get("linePage") ?? "1") || 1;

  const detail = useQuery({
    queryKey: ["ledger", "journal-entry", entryId, linePage],
    queryFn: () => getJournalEntry(entryId, { page: linePage }, client),
    enabled: entryId !== "",
  });

  const body = detail.data ?? null;
  const shown = body?.results.length ?? 0;
  const total = body?.count ?? 0;
  const pages = shown === 0 ? 1 : Math.max(Math.ceil(total / shown), 1);

  function goToPage(next: number): void {
    const updated = new URLSearchParams(searchParams);
    updated.set("linePage", String(next));
    setSearchParams(updated);
  }

  return (
    <>
      <PageHeader
        // B14 rule 31 — the ENTRY NUMBER in the eyebrow where there is one, and
        // the entry's uuid nowhere at all: it is in the URL and reaches no cell.
        //
        // ⚠ **NO EYEBROW WHERE THERE IS NO NUMBER, AND THAT IS RULE 32 RATHER
        // THAN TASTE.** The first build rendered *"NO ENTRY NUMBER"* here over
        // a facts panel whose `Entry no.` row already showed a `—`, so the
        // screen said the same absence twice, six lines apart — the identical
        // fault `RefundDetailPage` records against its own kicker (*"two facts
        // about one thing, contradicting each other at a glance"*). Found by
        // LOOKING at the shot, which is the only thing that finds it.
        kicker={body?.entry.je_number ?? undefined}
        // Rule 40 — the page-head title is 32px on every screen, and it is
        // `PageHeader`'s, never a local size.
        title={t("finance.entryDetail.title")}
        backTo={{
          to: tenantPath(`${financeTabPath(FINANCE_TAB_GL)}?view=journal`),
          label: t("finance.journal.title"),
        }}
        tabs={FINANCE_TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }))}
        activeTabId={FINANCE_TAB_GL}
        tabsLabel={t("finance.tabsLabel")}
        // ⚠ NO PRIMARY ACTION, AND THAT IS HARD RULE 4 RATHER THAN AN OMISSION.
        // A posted entry is immutable for ever; the one correction is reverse +
        // repost, which lives on the Journal row where the list's other row
        // actions are. A commit button here would teach a clerk the books can
        // be amended in place.
        data-screen={JOURNAL_ENTRY_DETAIL_SCREEN_ID}
      />
      {/* The screen id, asserted by the door test BY NAME beside the address —
          hard-won law 2's mirror: a test that asserts only a path passes when
          the router mounts a different screen there. */}
      <div data-screen-id={JOURNAL_ENTRY_DETAIL_SCREEN_ID} hidden />

      {detail.isError ? (
        <Panel role="alert">
          <h3>{t("finance.entryDetail.notFoundTitle")}</h3>
          <p className="fin-absent-reason">{apiErrorText(detail.error, translate)}</p>
        </Panel>
      ) : body === null ? (
        <LoadingSkeleton variant="card" />
      ) : (
        <>
          <JournalEntryDetailBody
            entry={body.entry}
            lines={body.results}
            lineCount={total}
            locale={props.locale}
            tenantPath={tenantPath}
            sourceHref={(() => {
              const path = journalSourcePath(body.entry.source_type, body.entry.source_id);
              return path === null ? null : tenantPath(path);
            })()}
            pager={
              pages <= 1 ? null : (
                // B14 rule 16 — a pagination footer, and rule 33 — a FACT is
                // six words: "Page 1 of 3". The count itself is on the facts
                // panel above, said once (rule 32).
                <div className="mt-4 flex items-center justify-end gap-3">
                  <Button
                    variant="secondary"
                    disabled={linePage <= 1}
                    onClick={() => goToPage(linePage - 1)}
                  >
                    {t("finance.entryDetail.previous")}
                  </Button>
                  <span className="text-sm">
                    {t("finance.entryDetail.pageOf", { page: linePage, pages })}
                  </span>
                  <Button
                    variant="secondary"
                    disabled={linePage >= pages}
                    onClick={() => goToPage(linePage + 1)}
                  >
                    {t("finance.entryDetail.next")}
                  </Button>
                </div>
              )
            }
          />
          {/* The served gaps, through the ONE renderer this module already
              has (B14 rule 43 — reused, never rebuilt). Today this entry's
              only possible gap is a DRAFT saved with no lines at all. */}
          <ReportGapList
            gaps={body.unavailable}
            title={t("finance.gap.title")}
            render={(gap) => gapSentence(gap, translate)}
          />
        </>
      )}
    </>
  );
}
