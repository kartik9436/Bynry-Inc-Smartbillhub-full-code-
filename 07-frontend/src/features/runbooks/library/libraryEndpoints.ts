// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-018 · US-RBS-003 — CR-075 wave D tasks D3 and D4.
// Screens: RBS-002 (`S148`) · RBS-003 (`S149`).
// Rules:   `07-endpoints.md` rows 1 and 4 · `NFR-3` (universal server
//          pagination, `per` clamped 50/100/200/500/1000) · `NFR-5` (no caps) ·
//          `BR-SHL-011` (the `f.<name>` filter grammar).
// Defects: DEF-WRK-4119 · DEF-AST-4120 (three shipped screens drew empty
//          tables over rows the server HAD returned, because each described
//          the reply by hand).
// ───────────────────────────────────────────────────────
// THE TWO READS THESE SCREENS MAKE, AND NEITHER DESCRIBES THE ENVELOPE.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE IS HERE AND NOT IN `src/api/`
// ══════════════════════════════════════════════════════════════════════════
// `src/api/runbooksEndpoints.ts` is wave C's and `src/api/queryClient.ts` is
// shared by every module; three lanes are editing this feature this hour. Law
// 11 mechanism two is two lanes appending to one file, where the second to
// commit silently reverts the first with a correct file count and its own hunks
// present. `RunbookSetupPage.tsx` made the same call for the same reason — it
// keeps its query key local and says so — so this is the module's convention
// rather than an exception to it. Nothing here is shared with another screen:
// when a second consumer appears, the file moves in one commit that nobody is
// racing.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ENVELOPE IS ASSERTED, NEVER DESCRIBED
// ══════════════════════════════════════════════════════════════════════════
// `readListPage`/`readListPageWith` are the ONE reader of a paged list in this
// product (`G114` fails a second description). They check `results` is an array
// and `count` is a number BEFORE handing anything back, so a payload shaped like
// the SELECTOR's dict — `{rows, page, per, total}` — raises a named error here
// instead of rendering as *"No results"*. That is exactly how three Work screens
// shipped empty in one day with every suite green.
import { readListPage, readListPageWith } from "@/api/paginated";
import type { PagedRows } from "@/api/paginated";
import type { ApiClient } from "@/api/client";
import { api } from "@/api/client";

import type { CatalogueRow, TemplateChipCounts, TemplateRow } from "./libraryTypes";

/** What both lists take. `q`, `page` and `per` are `BR-SHL-011`'s own names and
 *  travel unchanged; a filter travels as `f.<name>`, which is the grammar the
 *  server reads and the only one it reads. */
export interface LibraryQuery {
  q?: string;
  page: number;
  per: number;
  kind?: string;
  category?: string;
}

/**
 * Turn a screen's request into the query the server understands.
 *
 * ⚠ **AN EMPTY FILTER IS OMITTED RATHER THAN SENT EMPTY.** `api.py::_filter`
 * treats a blank as absent anyway, but sending `f.kind=` puts a meaningless
 * parameter in the address bar and in every cache key derived from it, so two
 * identical requests would look different to React Query.
 */
export function libraryParams(query: LibraryQuery): Record<string, string | number> {
  const params: Record<string, string | number> = { page: query.page, per: query.per };
  if (query.q !== undefined && query.q !== "") {
    params.q = query.q;
  }
  if (query.kind !== undefined && query.kind !== "") {
    params["f.kind"] = query.kind;
  }
  if (query.category !== undefined && query.category !== "") {
    params["f.category"] = query.category;
  }
  return params;
}

/** What `RBS-002.1` gets back: the page, the true total, and the CHIPS. */
export type TemplatesPage = PagedRows<TemplateRow> & { body: TemplateChipCounts };

/**
 * `GET /runbooks/templates` — the shipped library with this tenant's state.
 *
 * ⚠ **`readListPageWith`, NOT `readListPage`, AND THE DIFFERENCE IS THE WHOLE
 * OF `TC-RBS-20`.** The chip counts ride ON the envelope
 * (`{**_envelope(...), "category_chips": …}`) because `_envelope` builds a fresh
 * dict and discards every other key — `DEF-AST-4120` is a figure that never left
 * the server for exactly that reason. Reading them from the SAME object the rows
 * came out of is what stops a screen describing a second shape to reach them.
 */
export async function getTemplates(
  query: LibraryQuery,
  client: ApiClient = api,
): Promise<TemplatesPage> {
  return readListPageWith<TemplateRow, TemplateChipCounts>(
    "/runbooks/templates",
    libraryParams(query),
    client,
  );
}

/**
 * `GET /runbooks` — this tenant's configured runbooks, for `RBS-003`.
 *
 * ⚠ **THE PAGE NUMBER TRAVELS AND NOTHING HERE SLICES AN ARRAY.** `NFR-3` is
 * universal server pagination and CLAUDE.md's opening paragraph makes it the
 * deliverable rather than the background: four endpoints in this product already
 * page in Python behind a comment naming the old 3,000-account ceiling as the
 * excuse, correct at the bottom tier and 13× short of the top of the one we now
 * sell to (`DEF-PAY-4221`). This one does not join them.
 */
export async function getMyRunbooks(
  query: LibraryQuery,
  client: ApiClient = api,
): Promise<PagedRows<CatalogueRow>> {
  return readListPage<CatalogueRow>("/runbooks", libraryParams(query), client);
}

/**
 * `POST /runbooks` — add a shipped template to My runbooks.
 *
 * ⚠ **THIS WIRE WAS A TOAST FOR ONE COMMIT AND THAT IS THE DEFECT THIS REPO
 * PAYS FOR MOST.** When these screens were written the route was `GET` only and
 * **+ Add** said *"Adding is not connected yet."* — correct that hour. Wave `E1`
 * landed `POST /runbooks` while the wave was in flight, and a refusal that
 * outlives its condition is hard-won law 2's MIRROR: on 2026-09-05 the customer
 * portal's front page had two working doors out of eight, five of them refusing
 * over screens that had shipped days earlier, with `tsc`, 391 cases and every
 * gate green (`DEF-CWP-3925`). The law's own instruction is *"when you land a
 * screen, grep for the control that was holding it"* — this is that grep, run in
 * the other direction: the endpoint landed, so the control is released in the
 * same commit rather than left saying something that is no longer true.
 *
 * `07-endpoints.md` row 5: body `{template_key}`, **Admin**, `201` with the new
 * runbook. `BR-RBS-043` — add once, then clone: a second add is REFUSED rather
 * than answered `201` over a row that already existed, so the screen's job on a
 * failure is to show the server's sentence, never to guess one.
 */
export async function addTemplate(
  templateKey: string,
  client: ApiClient = api,
): Promise<{ key: string }> {
  const response = await client.post<{ key: string }>("/runbooks", {
    template_key: templateKey,
  });
  if (response.data === null) {
    throw new Error("empty 201 body from /runbooks where the contract promises one");
  }
  return response.data;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-018 · US-RBS-003 (CR-075 wave D tasks D3/D4) · 07-endpoints.md rows 1, 4 and 5 · NFR-3 · BR-SHL-011
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler) · vitest · G114 (one envelope description — this file adds none)
// exceptions: the file lives in the feature rather than in src/api/ while three lanes edit that folder; the reason is in the header and the move is one commit when a second consumer appears
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
