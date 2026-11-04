// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 3 (`P3.2` screens
//          `5·1`/`5·2`, `P3.3` the toast's destination, `P3.4` re-run,
//          `P3.5` retention on screen). Drawing p39 · p42 · p43, read as
//          IMAGES per B14 rule 42.
// Rules:   CLAUDE.md hard-won law 2 AND ITS MIRROR (a live screen behind a
//          dead control; nothing asks whether a REFUSAL is still true) · its
//          fixture clause (mount the routed component under the REAL path
//          pattern) · law 7 clause 2 (ask what would make this check pass
//          WRONGLY) · B14 rule 31 · BR-SHL-021 (a toast is text only)
//          Screens: `5·1` · `5·2`
// ───────────────────────────────────────────────────────
//
// THE ASSERTION THIS FILE EXISTS FOR, IN ONE SENTENCE:
// **an export made on `2·1` is findable on `5·1`, and the row whose FILE IS
// GONE offers no download.**
//
// ⚠ **`P3.3` SAYS "THE TOAST LINKS TO HISTORY". A TOAST CANNOT HOLD A LINK ON
// THIS DEPLOYMENT, AND THAT IS A SIGNED RULE RATHER THAN A GAP.**
// `components/Toast.tsx` takes a `string`, renders inside
// `pointer-events-none`, and auto-dismisses after 2,500 ms; its own comment
// cites BR-SHL-021 — *"the content is text only — no actions"* — and
// `Toast.test.tsx` asserts nothing in it is focusable. So the toast is made
// TRUE (it names History, and *Jobs* leaves all eleven catalogues) and the DOOR
// is the tab strip, which is always there and does not vanish in two and a half
// seconds. The lane's instruction — *assert the destination BY ADDRESS AND BY
// THE SCREEN ID IT OPENS* — is honoured against that door, which is the thing a
// clerk actually clicks. DIVERGENCE FROM `P3.3`'s WORDING, REPORTED.
//
// ⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY** (law 7 clause 2), because a
// check you cannot describe a false pass for is one you do not understand:
//   · mounting `ReportRunsPage` bare would leave `useParams().tenant`
//     undefined, every address would come out `//reports/history/…`, and
//     `toContain` would read that as fine — the portal's own defect. Every
//     mount here is under `/:tenant/reports`, and one case asserts the `//`
//     prefix is absent by name.
//   · asserting *a download control exists somewhere on the screen* would pass
//     over an expired row, because the ready rows have one. The expired case
//     asserts the absence WITHIN THAT ROW, and a sibling case asserts the
//     ready row in the same table HAS one — so "no downloads rendered at all"
//     cannot pass either.
//   · asserting the toast merely CHANGED would pass on any new wording. The
//     case asserts *Jobs* is gone from ALL ELEVEN catalogues and History is
//     named, in both directions.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter, matchRoutes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import type { ReportRun } from "@/api/runHistoryEndpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider, createToastQueue } from "@/components/Toast";

import de from "@/i18n/locales/de.json";
import en from "@/i18n/locales/en.json";
import esMX from "@/i18n/locales/es-MX.json";
import es from "@/i18n/locales/es.json";
import frFR from "@/i18n/locales/fr-FR.json";
import hi from "@/i18n/locales/hi.json";
import idID from "@/i18n/locales/id-ID.json";
import itIT from "@/i18n/locales/it-IT.json";
import jaJP from "@/i18n/locales/ja-JP.json";
import koKR from "@/i18n/locales/ko-KR.json";
import ptBR from "@/i18n/locales/pt-BR.json";

import { ReportRunsPage } from "./ReportRunsPage";
import { HISTORY_ROUTE } from "./ReportsTabs";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";

const USER: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "Reports", access: "Full" }],
};

const PERIOD = {
  fy_label: "FY2026",
  period: 9,
  start: "2026-09-01",
  end: "2026-09-30",
  status: "open",
};

// ⚠ **THESE TWO ROWS ARE THE DRAWING'S OWN, NOT INVENTED.** p39 draws a READY
// `Billing Register` run by Dana W. over 09/01–09/30 with 38,412 rows and a
// `↓ CSV`, and an EXPIRED `AR Ageing` run by Schedule over *as of 08/31* with
// 1,188 rows and an EM-DASH where the file would be. The shapes are the ones
// the running server produced on 2026-09-27 (`/api/brazosbend/reports/history`,
// read off a real PostgreSQL 16).
const READY: ReportRun = {
  id: "01a0e0d2-dd78-74b5-9c04-b5bf68ce33d2",
  report: "billing_register",
  ran_at: new Date().toISOString(),
  started_by: "Dana Whitfield",
  filters: { from: "09/01/2026", to: "09/30/2026" },
  status: "ready",
  progress: { done: 38412, total: null },
  rows: 38412,
  error: null,
  expires_at: new Date(Date.now() + 3 * 86_400_000).toISOString(),
  file: "/api/exports/01a0e0d2-dd78-74b5-9c04-b5bf68ce33d2/file",
};

const EXPIRED: ReportRun = {
  id: "01a0e0ce-268b-7079-aef9-8f6024b3568c",
  report: "ar_aging",
  ran_at: new Date(Date.now() - 9 * 86_400_000).toISOString(),
  // p39 ④ — a run nobody started by hand. The SERVER sends null; the SCREEN
  // says the word.
  started_by: null,
  filters: { as_of: "08/31/2026" },
  status: "expired",
  progress: { done: 1188, total: null },
  rows: 1188,
  error: null,
  expires_at: new Date(Date.now() - 6 * 86_400_000).toISOString(),
  // ⚠ **THE WHOLE POINT.** No address ⇒ no control.
  file: null,
};

/**
 * The reply as the SERVER really builds it.
 *
 * ⚠ **`{count, next, previous, results}`, NOT `{rows, total, …}`.** A fixture
 * answering the selector's dict would pass against a client typed from the
 * same wrong shape and fail only in a browser — which is exactly how three
 * Work screens shipped drawing empty tables (`DEF-WRK-4119`). The two extras
 * ride beside the four, because `_envelope` discards every other key and the
 * view spreads them back.
 */
function page(rows: ReportRun[]) {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    reports: ["ar_aging", "billing_register"],
    statuses: ["queued", "running", "ready", "failed", "expired"],
    // `DEF-RPT-9030` — the server states how long files are kept (CR-142,
    // 97ac0ddd0) and the note is drawn only over a stated figure.
    retention_days: 90,
  };
}

function server(rows: ReportRun[], posts: { path: string; body: unknown }[] = []): ApiClient {
  const get = async (path: string) => {
    if (path.startsWith("/reports/history/")) {
      const id = path.slice("/reports/history/".length);
      return { data: rows.find((row) => row.id === id) ?? rows[0], status: 200 };
    }
    if (path.startsWith("/reports/history")) {
      return { data: page(rows), status: 200 };
    }
    return { data: {}, status: 200 };
  };
  const post = async (path: string, body: unknown) => {
    posts.push({ path, body });
    return { data: { job_id: "new-job", status_url: "/api/jobs/new-job" }, status: 202 };
  };
  return {
    request: get,
    get,
    post,
    put: post,
    patch: post,
    delete: post,
  } as unknown as ApiClient;
}

function mount(rows: ReportRun[], options: { at?: string; posts?: { path: string; body: unknown }[] } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  const client = server(rows, options.posts);
  // ⚠ **MOUNTED UNDER THE REAL `/:tenant/reports` PATTERN**, including the
  // `:runId` child, so every address the screen builds carries a tenant.
  const router = createMemoryRouter(
    [
      { path: `/:tenant${HISTORY_ROUTE}`, element: <ReportRunsPage client={client} /> },
      { path: `/:tenant${HISTORY_ROUTE}/:runId`, element: <ReportRunsPage client={client} /> },
    ],
    { initialEntries: [options.at ?? `/${TENANT}${HISTORY_ROUTE}`] },
  );
  const queue = createToastQueue();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider queue={queue}>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { queue, router };
}

/**
 * Wait for `5·1`'s TABLE to hold a report's name.
 *
 * ⚠ **`screen.findByText` IS PAGE-WIDE AND THE FILTER BAR NAMES THE REPORTS
 * TOO.** Wiring `filterBarSlot` turned four green cases red on *"Found
 * multiple elements with the text: Billing register"* — the row AND the *All
 * reports* option now carry it. That is the fixture being too loose rather
 * than the screen being wrong, and it is worth the helper: a case scoped to
 * the page would go on passing if the row vanished and only the filter option
 * remained.
 */
async function rowNamed(name: string): Promise<HTMLElement> {
  return await vi.waitFor(() => {
    const table = document.querySelector("table tbody") as HTMLElement | null;
    expect(table, "5·1 drew no table body").not.toBeNull();
    return within(table as HTMLElement).getByText(name);
  });
}

/**
 * Wait for `5·2` to have ANSWERED, not merely to have opened.
 *
 * ⚠ **THIS EXISTS BECAUSE THE OBVIOUS WAIT WAITED ON THE WRONG THING.** `5·1`
 * has a column headed *Parameters* and `5·2` has a field labelled the same, so
 * `findByText("Parameters")` resolved instantly against the table underneath
 * and every following assertion ran against a dialog whose query had not
 * returned — two cases failed on `expected null not to be null` and the cause
 * read like a missing control. `data-run-subline` is rendered only once the
 * run is in hand, so it cannot resolve early.
 */
async function openDialog(): Promise<void> {
  await vi.waitFor(() => {
    expect(document.querySelector('[data-screen="5.2"]')).not.toBeNull();
    expect(document.querySelector("[data-run-subline]")).not.toBeNull();
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// `P3.3` — THE TOAST NOW NAMES A SCREEN THAT EXISTS
// ═══════════════════════════════════════════════════════════════════════════
describe("P3.3 · the toast's destination", () => {
  const CATALOGUES: Record<string, Record<string, string>> = {
    en, de, es, "es-MX": esMX, "fr-FR": frFR, hi, "id-ID": idID,
    "it-IT": itIT, "ja-JP": jaJP, "ko-KR": koKR, "pt-BR": ptBR,
  };

  // ⚠ **BOTH DIRECTIONS.** A defect shipped this week because a refusal stayed
  // on screen after the clerk fixed it and no case asked whether it had gone.
  // So: History is named AND the old word is gone, per language.
  it.each(Object.keys(CATALOGUES))("%s names History and no longer names Jobs", (lang) => {
    const toast = CATALOGUES[lang]["reports.export.queued"];
    const tab = CATALOGUES[lang]["reports.tabs.history"];
    expect(toast, `${lang} has no queued-export toast`).toBeTypeOf("string");
    expect(tab, `${lang} has no History tab label`).toBeTypeOf("string");
    // The toast names the TAB, in that language — B14 rule 35: a catalogue is
    // written in its own language, so this cannot be a check for the English
    // word "History".
    expect(toast).toContain(tab);
  });

  it("no catalogue still says the English word Jobs", () => {
    for (const [lang, catalogue] of Object.entries(CATALOGUES)) {
      expect(catalogue["reports.export.queued"], `${lang} still says "Jobs"`).not.toMatch(
        /\bJobs\b/,
      );
    }
  });

  // ⚠ **BY ADDRESS *AND* BY THE SCREEN ID IT OPENS.** The portal shipped a
  // hold-expiry test that asserted a screen was REGISTERED at an address while
  // the router mounted it somewhere else, and both addresses opened onto "not
  // built yet". So this asks the ROUTER's own table what `/reports/history`
  // resolves to, and then asserts the mounted screen carries `data-screen`.
  it("History is a real address in the router's own table", () => {
    const matches = matchRoutes(APP_ROUTES, `/${TENANT}${HISTORY_ROUTE}`);
    expect(matches, `${HISTORY_ROUTE} matches no route at all`).not.toBeNull();
    const pattern = (matches ?? []).map((m) => m.route.path ?? "").join("|");
    expect(pattern).toContain("reports/history");
  });

  it("and the screen at that address is 5·1", async () => {
    mount([READY]);
    expect(await rowNamed(en["reports.card.billing_register.name"])).toBeTruthy();
    // ⚠ **BY THE SCREEN ID, NOT BY "SOMETHING RENDERED".** The portal's
    // hold-expiry test asserted a screen was registered at an address while
    // the router mounted it elsewhere, and BOTH addresses opened onto "not
    // built yet" — so every check passed.
    expect(document.querySelector('[data-screen="5.1"]')).not.toBeNull();
  });

  it("the tab strip's History tab carries the tenant and opens 5·1", async () => {
    const { router } = mount([READY]);
    await rowNamed(en["reports.card.billing_register.name"]);
    const strip = document.querySelector('[data-sub-tabs="reports"]');
    expect(strip, "the reports tab strip is not drawn at all").not.toBeNull();
    const catalogue = within(strip as HTMLElement).getByText(en["reports.tabs.catalogue"]);
    fireEvent.click(catalogue);
    // Not `//reports` — a missing `:tenant` produces a protocol-relative URL
    // that every substring assertion reads as fine.
    expect(router.state.location.pathname.startsWith("//")).toBe(false);
    expect(router.state.location.pathname).toBe(`/${TENANT}${REPORTS_ROUTE}`);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// `P3.5` — THE ROW WHOSE FILE IS GONE
// ═══════════════════════════════════════════════════════════════════════════
describe("P3.5 · a purged file offers no download", () => {
  it("the expired row has no download control and the ready row does", async () => {
    mount([READY, EXPIRED]);
    await rowNamed(en["reports.card.billing_register.name"]);

    const readyLink = document.querySelector(`[data-run-file="${READY.id}"]`);
    expect(readyLink, "the READY row lost its download — the check would now pass vacuously")
      .not.toBeNull();
    expect((readyLink as HTMLAnchorElement).getAttribute("href")).toBe(READY.file);

    const expiredLink = document.querySelector(`[data-run-file="${EXPIRED.id}"]`);
    expect(expiredLink, "a download control is drawn over a file that is not there").toBeNull();
  });

  it("the expired row still says what ran, when and how many rows", async () => {
    mount([READY, EXPIRED]);
    // A row outliving its file is the DESIGNED state — it keeps every fact.
    expect(await rowNamed(en["reports.card.ar_aging.name"])).toBeTruthy();
    expect(screen.getByText("1,188")).toBeTruthy();
    const table = document.querySelector("table tbody") as HTMLElement;
    expect(within(table).getAllByText(en["reports.history.status.expired"]).length).toBe(1);
  });

  it("a run nobody started by hand reads Schedule, never an id", async () => {
    mount([EXPIRED]);
    expect(await screen.findByText(en["reports.history.schedule"])).toBeTruthy();
    // B14 rule 31 — the run's id is nowhere in the rendered text.
    expect(document.body.textContent).not.toContain(EXPIRED.id);
  });

  it("states the retention fact in six words and explains nothing", async () => {
    mount([READY]);
    await rowNamed(en["reports.card.billing_register.name"]);
    const note = document.querySelector("[data-retention-note]");
    expect(note).not.toBeNull();
    // The fact, with the tenant's own figure in it — six words.
    const fact = en["reports.history.retention"].replace("{{days}}", "90");
    expect(fact).toBe("Files are kept for 90 days.");
    const door = (note as HTMLElement).querySelector("[data-retention-door]");
    const expected = door === null ? fact : `${fact} ${en["reports.history.retentionDoor"]}`;
    expect((note as HTMLElement).textContent).toBe(expected);
    // B14 rule 33 — RATIONALE is zero words on screen. The page never explains
    // the policy, and never claims a record is permanent.
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/permanent|for ever|forever|retention policy/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// `P3.2` / `P3.4` — THE RUN OPENED, AND RE-RUN
// ═══════════════════════════════════════════════════════════════════════════
describe("P3.2 · 5·2, one run opened", () => {
  it("opens from a row's address and shows parameters, status and expiry", async () => {
    mount([READY], { at: `/${TENANT}${HISTORY_ROUTE}/${READY.id}` });
    await openDialog();
    const dialog = document.querySelector('[data-screen="5.2"]') as HTMLElement;
    expect(within(dialog).getByText(en["reports.history.run.parameters"])).toBeTruthy();
    expect(within(dialog).getByText(en["reports.history.run.expires"])).toBeTruthy();
    // p43 PRIMARY ACTION — LABELLED here, an icon on 2·1, and p43 says that is
    // not an inconsistency.
    const download = document.querySelector("[data-run-download]");
    expect(download).not.toBeNull();
    expect((download as HTMLElement).textContent).toBe(en["reports.history.run.download"]);
  });

  it("an EXPIRED run opened shows no download at all", async () => {
    mount([EXPIRED], { at: `/${TENANT}${HISTORY_ROUTE}/${EXPIRED.id}` });
    await openDialog();
    expect(document.querySelector("[data-run-download]")).toBeNull();
    // …and Re-run IS still offered: that is the case it exists for.
    expect(document.querySelector("[data-run-rerun]")).not.toBeNull();
  });
});

describe("P3.2 · the way OUT of 5·2", () => {
  // ⚠ **A DIALOG THAT IS THE ONLY WAY OUT IS A TRAP, AND THE CLOSE PATH WAS
  // ASSERTED IN CODE AND NOWHERE ELSE.** The lane brief's own instruction —
  // *assert messages in both directions; a defect shipped this week because a
  // refusal stayed on screen after the clerk fixed it and no case asked
  // whether it had gone* — is the same shape: something appears, and nobody
  // checks that it can disappear. The walkthrough opened the dialog and never
  // closed it.
  it("closes back to 5·1 and KEEPS the filters the clerk had applied", async () => {
    const { router } = mount([READY], {
      at: `/${TENANT}${HISTORY_ROUTE}/${READY.id}?f.status=ready`,
    });
    await openDialog();

    fireEvent.click(screen.getByLabelText(en["forms.close"]));

    await vi.waitFor(() => {
      expect(document.querySelector('[data-screen="5.2"]')).toBeNull();
    });
    // Not `//reports/history` — the protocol-relative address a missing
    // `:tenant` produces, which every substring assertion reads as fine.
    expect(router.state.location.pathname.startsWith("//")).toBe(false);
    expect(router.state.location.pathname).toBe(`/${TENANT}${HISTORY_ROUTE}`);
    // ⚠ **AND THE FILTER SURVIVES.** Dropping it would silently widen the list
    // a clerk had narrowed, which reads as the filter having failed.
    expect(router.state.location.search).toContain("f.status=ready");
  });
});

describe("P3.4 · re-run", () => {
  it("posts the ORIGINAL parameters back through POST /exports, unchanged", async () => {
    const posts: { path: string; body: unknown }[] = [];
    mount([READY], { at: `/${TENANT}${HISTORY_ROUTE}/${READY.id}`, posts });
    await openDialog();
    const button = screen.getByText(en["reports.history.run.rerun"]);
    fireEvent.click(button);
    await vi.waitFor(() => expect(posts.length).toBe(1));

    // §8.2's right path — the SAME `POST /exports` the export toast came from,
    // never a fourth call and never a re-render of this dialog.
    expect(posts[0].path).toBe("/exports");
    const body = posts[0].body as { resource: string; filters: Record<string, string> };
    expect(body.resource).toBe(READY.report);
    // ⚠ **UNCHANGED, ASSERTED AS EQUALITY AND NOT AS A SUBSET.** "last
    // quarter's report reproduces exactly" fails the moment one bound is
    // dropped, and a `toContain` on one key would pass over that.
    expect(body.filters).toEqual(READY.filters);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// THE HOLD — the ONE tab the drawing shows and this strip still does not
// ═══════════════════════════════════════════════════════════════════════════
// CLAUDE.md: *"WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD
// EXPIRES, in the same commit — assert the destination by ADDRESS and by the
// screen id it opens."*
//
// ⚠ **`scheduled` WAS HERE AND IS GONE — `CR-142-BRC07` `P4.5`, 2026-09-27,
// AND ITS REMOVAL IS THE MECHANISM WORKING RATHER THAN A TEST BEING WEAKENED.**
// This case named two segments. `P4.5` mounted `ScheduledTab` at
// `/reports/scheduled`, so the `scheduled` half went RED and said in its own
// failure message that `ReportsTabs` must now draw it. It does, and the case
// for that segment is DELETED in the same commit — a hold test that outlives
// its hold is the next reader's false alarm, and a red nobody can act on is
// how a true red acquires the protective colouring of a known one.
//
// ⚠ **`dashboard` WENT THE SAME WAY ON THE SAME DAY — `CR-142-BRC07`
// `P4.11`–`P4.13`, lane REP-P4-DASH — AND IT WAS THE LAST ONE.** `P4.11` mounts
// `ReportsDashboardPage` at `/reports/dashboard`, so this case went RED with its
// own sentence, *"no longer opens the placeholder — ReportsTabs must now draw
// it"*, and it was READ before anything was edited. The tab is drawn in
// `LIVE_REPORT_TABS` and the case is deleted here.
//
// ⚠ **SO THERE IS NO HOLD LEFT ON THIS STRIP, AND THIS SECTION IS KEPT AS A
// COMMENT RATHER THAN DELETED.** The next lane adding a tab needs to know what
// a hold looked like here and what retiring one looks like — that is the whole
// of CLAUDE.md's *"when you write a hold, write the test that fires when the
// hold expires, in the same commit"*, and it worked twice in one day.
//
// The remaining guarantee — that `/reports/:reportKey` never swallows one of
// the four reserved words — lives in `routing/reportsReservedSegments.test.tsx`
// and runs over all four.

// ═══════════════════════════════════════════════════════════════════════════
// `DEF-SHL-6915` — A FAILURE IS NOT AN EMPTINESS, ON `5·1`
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY** (law 7 clause 2), asked
// before they were written:
//
//   · **Asserting the failure copy alone** would pass over a screen that drew
//     BOTH the retry block and *"No results match these filters."* — and the
//     sentence that misleads a clerk is the one this case exists to forbid.
//     So the zero-results copy is asserted ABSENT, in both its forms: the
//     echo (`states.zeroResults.message`) and the filtered one
//     (`states.zeroResults.filtered`), because `5·1` opens with no search
//     term and therefore reaches the second.
//   · **Asserting a Retry button exists** would pass whether or not pressing
//     it asked the server again. The second case counts the CALLS.

/** A server that answers the run list with a 500 — nothing else changes. */
function failingServer(calls: { path: string }[] = []): ApiClient {
  const get = async (path: string) => {
    calls.push({ path });
    if (path.startsWith("/reports/history")) {
      throw new Error("500 Internal Server Error");
    }
    return { data: {}, status: 200 };
  };
  return {
    request: get,
    get,
    post: get,
    put: get,
    patch: get,
    delete: get,
  } as unknown as ApiClient;
}

function mountFailing(calls: { path: string }[] = []) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  const client = failingServer(calls);
  const router = createMemoryRouter(
    [{ path: `/:tenant${HISTORY_ROUTE}`, element: <ReportRunsPage client={client} /> }],
    { initialEntries: [`/${TENANT}${HISTORY_ROUTE}`] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider queue={createToastQueue()}>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("5·1 when the server does not answer", () => {
  afterEach(cleanup);

  it("draws the retry block and NEVER the zero-results copy", async () => {
    mountFailing();
    expect(await screen.findByText(en["table.failed.title"])).toBeTruthy();
    expect(screen.queryByText(en["states.zeroResults.filtered"])).toBeNull();
    expect(screen.queryByText(/clear filters/i)).toBeNull();
  });

  it("offers a retry that asks the server again", async () => {
    const calls: { path: string }[] = [];
    mountFailing(calls);
    await screen.findByText(en["table.failed.title"]);
    const before = calls.length;
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await vi.waitFor(() => {
      expect(calls.length).toBeGreaterThan(before);
    });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P3.2 · P3.3 · P3.4 · P3.5 (05-prototype/09 Reports Build Brief.pdf p13-p14, p39-p43, read as images per B14 rule 42)
// screens: 5·1 · 5·2
// generated: 2026-09-27 by lane REP-P3
// gates: RED PROVED FIRST — every describe failed on the tip: the three component imports did not resolve (`Cannot find module './ReportRunsPage'`), and the catalogue case read `"Your CSV is being written. It appears in Jobs when it is ready."` against a `reports.tabs.history` key that did not exist in any of the eleven.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
