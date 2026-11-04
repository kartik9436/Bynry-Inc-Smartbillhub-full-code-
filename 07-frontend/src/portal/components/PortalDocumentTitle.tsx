// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CWP-10562 — every portal page shared the tab title
//           "SMART360 Next" (WCAG 2.4.2, tester finding F-07).
// Rules:    decision log 2026-10-23, "Portal accessibility, Group D" ruling 1:
//           the page name, then the utility's own name — *"Pay your bill · City
//           of Ann Arbor"*; every portal page and dialog has its own.
//           The staff app's equivalent is BR-SHL-004 in `components/AppShell.tsx`.
// Tests:    src/portal/components/PortalDocumentTitle.test.tsx ·
//           src/portal/routing/portalOutline.dom.test.tsx (every route)
// ───────────────────────────────────────────────────────
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { queryKeys } from "@/api/queryClient";

import { getPortalFront } from "../api/guestClient";

/**
 * The name of what is in front of the reader: an open dialog's heading if a
 * dialog is open, else the page's one `<h1>`. `null` when neither exists yet
 * (a screen still loading, or a page that failed before drawing its head).
 *
 * ⚠ **IT READS THE HEADING THE PAGE ALREADY DRAWS, AND THAT IS THE DESIGN.**
 * The portal has 56 routes and the h1 of each is already the page's own name
 * in the reader's language (the hidden one on signed-in Home included). A
 * per-page `useTitle("…")` would be 56 second copies of 56 strings, each free
 * to drift from the heading it duplicates — and the first page that forgot one
 * would quietly go back to "SMART360 Next". Reading the heading means a new
 * route gets a correct title with no line written for it, and
 * `portalOutline.dom.test.tsx` fails any route whose h1 is missing.
 */
export function portalPageName(root: ParentNode): string | null {
  const dialog = root.querySelector('[role="dialog"][aria-modal="true"], [role="alertdialog"], dialog[open]');
  const heading = dialog
    ? (dialog.querySelector("h1, h2, h3") ?? null)
    : root.querySelector('h1, [role="heading"][aria-level="1"]');
  const text = heading?.textContent?.replace(/\s+/g, " ").trim() ?? "";
  return text === "" ? null : text;
}

/**
 * `"Pay your bill · City of Ann Arbor"`, or the utility's name alone while no
 * heading is drawn.
 *
 * ⚠ **THE SEPARATOR IS NOT A CATALOGUE LINE, ON PURPOSE.** Both halves are
 * already in the reader's language — the page's own h1, and the utility's own
 * name, which is never translated — and what joins them is a middle dot with
 * no word in it. A catalogue key holding `{{page}} · {{utility}}` would be
 * eleven copies of one glyph, each read by `G15` as English pasted in. The
 * staff tab joins its leaf and the product name with the same dot
 * (`shell.docTitle`).
 */
export function portalDocumentTitle(page: string | null, utility: string): string {
  if (page === null) return utility;
  return `${page} · ${utility}`;
}

/**
 * Keeps `document.title` equal to the page in front of the reader, for the
 * whole portal. Mounted once, in `PortalApp`, beside `PortalLanguage`.
 *
 * ⚠ **A `MutationObserver`, BECAUSE A ROUTE CHANGE IS NOT THE ONLY TIME THE
 * HEADING CHANGES.** A wizard step, a "Sent" panel replacing a form, a loading
 * state giving way to the screen and a language switch all redraw the h1
 * without the address moving. Writing `document.title` touches `<head>`, which
 * the observer does not watch, so it cannot loop. Changes are coalesced into
 * one timer tick.
 */
export function PortalDocumentTitle() {
  const { i18n } = useTranslation();
  const frontQuery = useQuery({
    queryKey: queryKeys.portalFront,
    queryFn: () => getPortalFront(api),
  });
  const utility = frontQuery.data?.tenant.name ?? "";
  const language = i18n.language;

  useEffect(() => {
    if (typeof document === "undefined" || typeof MutationObserver === "undefined") return;
    const apply = () => {
      const page = portalPageName(document.body);
      const next =
        utility === ""
          ? (page ?? document.title)
          : portalDocumentTitle(page, utility);
      if (next !== "" && document.title !== next) document.title = next;
    };
    let pending: ReturnType<typeof setTimeout> | null = null;
    const schedule = () => {
      if (pending !== null) return;
      pending = setTimeout(() => {
        pending = null;
        apply();
      }, 0);
    };
    apply();
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { subtree: true, childList: true, characterData: true });
    return () => {
      observer.disconnect();
      if (pending !== null) clearTimeout(pending);
    };
  }, [utility, language]);

  return null;
}
