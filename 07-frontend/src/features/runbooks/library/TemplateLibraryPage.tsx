// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-018 (EP-RBS-01) — CR-075 wave D task D3.
// Screens: RBS-002.1 at `/{tenant}/runbooks/templates` · RBS-002.2 at
//          `/{tenant}/runbooks/templates/{key}`.
// Rules:   `NFR-3` (the page number travels to the server) · `BR-SHL-020` (a
//          refusal is plain language) · B14 rule 32.
// Tests:   TemplateLibrary.dom.test.tsx · TemplateDetail.dom.test.tsx
// Defects: DEF-520 / G40 (a component nothing mounts).
// ───────────────────────────────────────────────────────
// THE TWO PAGES THAT FEED THE TWO RENDERERS, AND WHY THEY ARE SEPARATE FILES.
//
// `TemplateLibrary` and `TemplateDetail` are PURE over their view models: no
// fetch, no query key, no router beyond the tenant slug. That is what lets the
// same component be asserted by a unit test, painted by the render-check in a
// real browser, and driven by the server, all from one definition of what it
// draws. This file is the only place that knows there is a server at all — the
// shape `RunbookSetupPage.tsx` established in wave C.
//
// ══════════════════════════════════════════════════════════════════════════
// THE DETAIL READS THE LIST, AND THAT IS THE SERVER'S OWN FILTER RATHER THAN A
// CLIENT-SIDE SEARCH
// ══════════════════════════════════════════════════════════════════════════
// **There is no `GET /runbooks/templates/{key}`** — `07-endpoints.md` has one
// library route and `apps/runbooks/api.py` registers one. `GET /runbooks/{key}`
// is not the answer either: it reads THIS TENANT's `runbooks` table, and a
// template that has not been added has no row there, so the screen whose whole
// job is *what would this be allowed to touch, before I add it* would 404 on
// exactly the case it exists for.
//
// So the detail asks the library for the one template, using `q` — which
// `selectors._template_definitions` matches against the key as well as the name
// — and then takes the EXACT key match. The filtering is the server's; the match
// is an identity test, not a search. A key that returns nothing is a 404 in
// words, not a blank screen.
//
// ⚠ **`per` IS THE DEFAULT 50 AND NOT 1.** `q=configuration_check` can match
// more than one template by substring, and asking for one row would silently
// take whichever the registry ordered first. Fifty is the clamp's own default
// and the whole library is smaller than that today.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { api } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import type { PageSize } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";

import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

import { addTemplate, getTemplates } from "./libraryEndpoints";
import type { TemplatesPage } from "./libraryEndpoints";
import { TemplateDetail } from "./TemplateDetail";
import { TemplateLibrary } from "./TemplateLibrary";

/**
 * **+ Add**, wired to the endpoint that landed under it.
 *
 * ⚠ **RELEASED IN THE SAME COMMIT AS THE ENDPOINT, WHICH IS THE HALF THAT GETS
 * FORGOTTEN.** `POST /runbooks` is wave `E1` and it landed while these screens
 * were being written. A control still refusing over a live route is hard-won
 * law 2's mirror — `DEF-CWP-3925`, eight portal doors shut over screens that had
 * shipped days earlier, every check green — so the toast is gone and the button
 * calls the route.
 *
 * On success the person lands on the runbook's own setup screen, because the
 * page they came from says *"Add one, then set it up."* and that is the next
 * thing they are there to do. On a refusal — a non-Admin, or `BR-RBS-043`'s
 * *add once, then clone* — the SERVER's sentence is shown, never one this screen
 * invented.
 */
function useAddTemplate(client: ApiClient) {
  const { t } = useTranslation();
  const showToast = useToast();
  const navigate = useNavigate();
  const tenant = useTenant();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (templateKey: string) => addTemplate(templateKey, client),
    onSuccess: (added) => {
      // The library's *Added / Not added* pill is now stale on every cached
      // page of it, so the whole prefix goes rather than one key — a card that
      // says *Not added* over a runbook that exists is the same lie one level
      // down from the one this screen exists to avoid.
      void queryClient.invalidateQueries({ queryKey: ["runbooks"] });
      navigate(tenantPathFrom(tenant, `runbooks/${added.key}`));
    },
    onError: (error) => showToast(refusalText(t, error)),
  });
}

/** `RBS-002.1` — the gallery. */
export function RunbookTemplateLibraryPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const add = useAddTemplate(client);

  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);

  const query = useQuery<TemplatesPage>({
    // ONE key from the WHOLE request, so a page turn or a chip cannot answer
    // from the cache of a different one. The literal prefix is this screen's own
    // and is deliberately not in `api/queryClient.ts`: three lanes are editing
    // that shared file this hour and two lanes appending to one module is law
    // 11 mechanism two.
    queryKey: ["runbooks", "templates", q, kind, category, page, per],
    queryFn: () => getTemplates({ q, kind, category, page, per }, client),
  });

  if (query.isPending) {
    return <LoadingSkeleton variant="card" />;
  }

  const data = query.data;
  if (data === undefined) {
    return (
      <FailedWithRetry
        title={t("runbooks.library.failedTitle")}
        reason={refusalText(t, query.error)}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }

  return (
    <TemplateLibrary
      view={{
        rows: data.rows,
        total: data.total,
        categoryChips: data.body.category_chips,
        kindChips: data.body.kind_chips,
      }}
      request={{ q, kind, category, page, per }}
      onSearch={(next) => {
        setQ(next);
        setPage(1);
      }}
      onKind={(next) => {
        setKind(next);
        setPage(1);
      }}
      onCategory={(next) => {
        setCategory(next);
        setPage(1);
      }}
      onClearFilters={() => {
        setQ("");
        setKind("");
        setCategory("");
        setPage(1);
      }}
      onPage={setPage}
      onPer={(next) => {
        setPer(next);
        setPage(1);
      }}
      onAdd={(template) => add.mutate(template.template_key)}
    />
  );
}

/** `RBS-002.2` — one template. */
export function RunbookTemplateDetailPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const add = useAddTemplate(client);

  // ⚠ THE SLUG FROM THE REAL PATH PATTERN. A component mounted bare inside a
  // `MemoryRouter` with no `/:tenant/…` route gets `undefined` from
  // `useParams()` and builds every address as `//host/…` — a protocol-relative
  // URL that reads as a perfectly good string to `toContain` (`DEF-CWP-3925`).
  // The tests for this screen mount `APP_ROUTES` at a real address.
  const { key = "" } = useParams<{ key: string }>();

  const query = useQuery<TemplatesPage>({
    queryKey: ["runbooks", "templates", "one", key],
    queryFn: () => getTemplates({ q: key, page: 1, per: 50 }, client),
    enabled: key !== "",
  });

  if (query.isPending) {
    return <LoadingSkeleton variant="card" />;
  }

  const data = query.data;
  if (data === undefined) {
    return (
      <FailedWithRetry
        title={t("runbooks.library.failedTitle")}
        reason={refusalText(t, query.error)}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }

  const template = data.rows.find((row) => row.template_key === key);
  if (template === undefined) {
    // A key nobody ships. The screen says so in words rather than rendering a
    // head with an empty body, which reads as a broken page.
    return (
      <FailedWithRetry
        title={t("runbooks.library.detail.notFound")}
        reason={t("runbooks.library.detail.notFoundWhy")}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }

  return (
    <TemplateDetail template={template} onAdd={() => add.mutate(template.template_key)} />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-018 (EP-RBS-01; CR-075 wave D task D3) · 07-endpoints.md row 4 · NFR-3
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler) · vitest · G13 (every handler is required and passed here)
// exceptions: the detail reads the library route with `q` because no per-template read exists; the reason is in the header
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
