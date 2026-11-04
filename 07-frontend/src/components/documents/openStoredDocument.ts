// ── Trace ──────────────────────────────────────────────
// Change:  **B14 rule 43**. The store's read side, made addressable — so a
//          screen that lists documents is never again a list of facts with
//          nothing to press over them.
// Rules:   hard-won law 2's MIRROR (a live screen behind a dead control; here,
//          a live ENDPOINT behind no control at all) · hard-won law 1 (a
//          comment claiming a guarantee is not the guarantee) · `BR-TEN-003`
//          (the row is resolved under this tenant before a link is minted)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ENDPOINT HAS BEEN LIVE AND CALLED BY NOTHING.**
// `GET /service-requests/{id}/documents/{docId}/download` landed with the
// store on 2026-09-19 and `GET /accounts/{id}/documents/{docId}` before it.
// **Three front-end surfaces draw service-request documents and not one of
// them can open a file**: the capture step's table, the request detail's
// Documents tab (which can VERIFY and REJECT a file nobody can read) and the
// move-in block, which draws a file name, what it proves and where it stands
// over ZERO clickable controls. This is the one wrapper all three were
// missing.
import { api, apiPath, currentTenant, DEFAULT_BASE_URL } from "@/api/client";
import type { ApiClient } from "@/api/client";

/**
 * What every `document_link` in this product answers with — the service
 * request's, the account's and `work.evidence`'s all share this shape, which is
 * why this helper takes a PATH and names no route of its own.
 *
 * ⚠ **THE URL IS A BEARER TOKEN.** `document_store.download_url` mints it at
 * `document_storage.url_ttl_seconds()`, capped at four hours by the PO ruling
 * of 2026-08-30. Whoever holds it reads that one file with no session until it
 * expires, so it is opened and never stored, logged or put in a query cache.
 */
export interface StoredDocumentLink {
  url: string;
  expires_in_seconds: number;
}

/**
 * A link this browser can actually follow.
 *
 * ⚠ **THE DEV STORAGE BACKEND MINTS `file://` URLs AND A BROWSER CANNOT
 * FOLLOW ONE.** `LocalDocumentStorage.temporary_read_url` returns
 * `file:///…`; `window.open` on it is blocked silently, which is a control
 * that looks alive and does nothing — the exact shape this folder exists to
 * stop building. So the scheme is CHECKED and an unfollowable link is refused
 * BY NAME instead. That refusal is true only on a developer's machine; in
 * production the store hands back `https:` and it never fires.
 */
export function isBrowsableDocumentUrl(url: string): boolean {
  return url.startsWith("https://") || url.startsWith("http://");
}

/**
 * Ask for a document's link and open it.
 *
 * `path` is the host's own download route — this helper deliberately knows no
 * route, because a kit component that named one would be usable by exactly the
 * screen it was written for. Rejects with an `ApiError` the host already knows
 * how to turn into a sentence (a row with no file answers
 * `customers.serviceRequest.documentHasNoFile` from the server), or with
 * `DOCUMENT_LINK_NOT_BROWSABLE` when the store hands back a scheme the browser
 * will not follow.
 */
export const DOCUMENT_LINK_NOT_BROWSABLE = "DOCUMENT_LINK_NOT_BROWSABLE";

export async function openStoredDocument(
  path: string,
  options?: {
    client?: ApiClient;
    /** The test seam. Defaults to the browser's own opener. */
    open?: (url: string) => void;
  },
): Promise<StoredDocumentLink> {
  const client = options?.client ?? api;
  const response = await client.get<StoredDocumentLink>(path);
  const link = response.data;
  if (link === null) {
    throw new Error(DOCUMENT_LINK_NOT_BROWSABLE);
  }
  if (!isBrowsableDocumentUrl(link.url)) {
    throw new Error(DOCUMENT_LINK_NOT_BROWSABLE);
  }
  const open =
    options?.open ??
    ((url: string) => {
      // `noopener` — the link is a bearer token and the opened tab has no
      // business holding a handle on the app that minted it.
      window.open(url, "_blank", "noopener,noreferrer");
    });
  open(link.url);
  return link;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * THE FILE ITSELF — `CR-158-BRC10`, PO 2026-10-01
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * *"clark should able to view those document in new request"*. The link above
 * is a bearer URL straight to the object store; this is the file THROUGH our
 * own route (`…/documents/{docId}/content?as=view|download`), which is what
 * lets the response carry `Content-Disposition`, `nosniff` and a policy that
 * forbids any script inside the file — and it works on every storage backend,
 * the developer's `file://` one included.
 *
 * ⚠ **A NAVIGATION, NOT A `fetch`.** The session is an httpOnly cookie
 * (`api/client.ts`), so a new tab opened on the route carries it exactly as a
 * request from the app would; a `fetch` into a blob URL would lose the file's
 * own name and the server's `Content-Disposition` with it.
 */
export type DocumentContentMode = "view" | "download";

/** The absolute address of a document's content route, under THIS tenant. */
export function documentContentUrl(path: string, mode: DocumentContentMode): string {
  return `${DEFAULT_BASE_URL}${apiPath(currentTenant(), path)}?as=${mode}`;
}

/** Open (`view`) or save (`download`) one document through its content route. */
export function openDocumentContent(
  path: string,
  mode: DocumentContentMode,
  options?: { open?: (url: string) => void },
): string {
  const url = documentContentUrl(path, mode);
  const open =
    options?.open ??
    ((target: string) => {
      window.open(target, "_blank", "noopener,noreferrer");
    });
  open(url);
  return url;
}
