// ── Trace ──────────────────────────────────────────────
// Story:    CR-048 wave E task E9 — ONE Templates screen over BOTH template
//           stores.  Screens: S8 → Configure → Templates (SET-09)
// Rules:    BR-NOT-026 (PO 2026-08-30 — one screen and one service, two stores,
//           no row moves) · BR-NOT-025 · BR-SHL-011 (list grammar)
// ───────────────────────────────────────────────────────
// `GET /template-library` — every template this utility has, whichever store it
// lives in.
//
// ⚠ **A FILE OF ITS OWN, AND NOT A DOZEN LINES IN `endpoints.ts`.** That file is
// ~13,000 lines and four lanes are inside it on any given day; a whole-file
// commit from any of them silently reverts the others (hard-won law 11,
// mechanism two, which has cost this repo real code twice). One small module per
// new surface costs nothing and cannot be caught by that.

import { api } from "./client";
import type { ApiClient } from "./client";

/** The two kinds. Mirrors `apps/notifications/unified_templates.KINDS` — the
 *  SERVER serves this list on every response so a chip for a kind it does not
 *  offer can never be drawn (DEF-782's lesson). */
export type TemplateKind = "notification" | "bill";

/** WHAT a row stores. The half of the ruling a merged list would hide: one kind
 *  holds words a person typed, the other holds which of five platform layouts a
 *  bill prints on. */
export type TemplateContentModel = "authored_words" | "layout_choice";

/** WHICH editor a row opens. The ruling asked for one LIST and one LIFECYCLE
 *  and did not ask for one editor — a text box over a layout key would be the
 *  wrong screen for both kinds. */
export type TemplateEditor = "template-detail" | "layout-chooser";

export interface TemplateLibraryRow {
  kind: TemplateKind;
  /** The code (notification) or the template's id (bill). Never a synthetic id
   *  minted here: a third identity would be a third thing to keep in step. */
  key: string;
  name: string;
  content_model: TemplateContentModel;
  editor: TemplateEditor;
  /** The live version number, or null where nothing is published yet. */
  live_version: number | null;
  version_count: number;
  /** ISO date, or null for a template nobody has touched — which is a true and
   *  common answer, not a gap. */
  edited: string | null;
}

export interface TemplateLibraryPage {
  results: TemplateLibraryRow[];
  count: number;
  kinds: TemplateKind[];
}

export const templateLibraryKey = ["template-library"] as const;

export async function getTemplateLibrary(
  query: { kind?: TemplateKind } = {},
  client: ApiClient = api,
): Promise<TemplateLibraryPage> {
  const params = new URLSearchParams();
  if (query.kind !== undefined) {
    params.set("kind", query.kind);
  }
  const suffix = params.toString();
  const response = await client.get<TemplateLibraryPage>(
    suffix === "" ? "/template-library" : `/template-library?${suffix}`,
  );
  if (response.data === null) {
    throw new Error("empty /template-library body where the contract promises one");
  }
  return response.data;
}
