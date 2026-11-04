// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F1–F5 — the Templates workspace's URL state
// Rules:    BR-SHL-011 (a screen's state a person can link to lives in the URL)
// ───────────────────────────────────────────────────────
// The query parameters the list and the workspace share, in ONE place.
//
// `?template=` and `?variant=` are `TemplateCatalog`'s (DEF-212 (2)); `?view=`
// is the history's (CR-048 wave I). These three are the redesign's:
//
//   · `?mode=edit` — the workspace opens editing. The list's ✎ *Edit wording*
//     sets it, so the row's action survives the navigation it causes; *View*
//     and *Edit wording* in the action bar write it back.
//   · `?dialog=` — which of the drawn dialogs is up: `new` (`06`),
//     `duplicate` (`10`), `send-test` (`12`), `publish` (`11`). The list's
//     `…` → *Duplicate as variant* sets `duplicate`.
//
// ⚠ **CONSTANTS, NOT STRINGS AT EACH CALL SITE.** Two files write these and
// one reads them; a parameter spelt three times is a door that stops opening
// the day one spelling changes, with every test still green.

export const WORKSPACE_MODE_PARAM = "mode";
export const WORKSPACE_EDIT = "edit";
export const WORKSPACE_DIALOG_PARAM = "dialog";
export const WORKSPACE_VIEW_PARAM = "view";
export const WORKSPACE_HISTORY = "history";

export type WorkspaceDialog = "new" | "duplicate" | "send-test" | "publish";

export function workspaceDialogOf(raw: string | null): WorkspaceDialog | null {
  return raw === "new" || raw === "duplicate" || raw === "send-test" || raw === "publish"
    ? raw
    : null;
}
