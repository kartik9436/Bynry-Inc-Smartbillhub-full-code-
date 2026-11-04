// ── Trace ──────────────────────────────────────────────
// Change:  CR-076 item 3 — a Print / Export PDF control on SET-10's preview.
//          PO 2026-09-07, on the snippet they proposed themselves: *"you should
//          print real rendered document"*.
// Screens: SET-10 (the template designer)
// Rules:   BR-SHL-025 (a control that cannot act is disabled with its reason —
//          the caller's half) · B14 rule 21 (this file writes no class at all)
// ───────────────────────────────────────────────────────
/**
 * PRINT THE DOCUMENT THAT IS ON THE SCREEN, NOT A RE-RENDER OF ITS TEXT.
 *
 * ══════════════════════════════════════════════════════════════════════════
 *  WHY THIS FILE EXISTS AND WHY THE ONE-LINE VERSION IS WRONG
 * ══════════════════════════════════════════════════════════════════════════
 * The obvious implementation — and the one the request arrived with — is:
 *
 *     const w = window.open("");
 *     w.document.write(`<pre>${preview.body}</pre>`);
 *     w.print();
 *
 * **What comes out of that is a DIFFERENT DOCUMENT from the one the person is
 * looking at.** `preview.body` is the rendered TEXT. Everything that makes the
 * pane a document rather than a paragraph is drawn by `PreviewBody` around it:
 * the page and its margin on a printable, the subject and preheader lines on an
 * email, the phone-sized bubble on an SMS, the bell panel on an in-app notice —
 * and, sitting outside the body entirely, the LOCKED RIGHTS BLOCKS (BR-NOT-015)
 * and the sample-data notice. A `<pre>` carries none of them. So a person
 * checking a regulated notice would print a page with no rights footer on it
 * and no statement that it is a preview, and would have no way to tell.
 *
 * That is the same class of fault as `DEF-PAY-4409` the day before: a preview
 * showing values the real document does not have. Here it points the other way
 * — a printout missing what the real document has — and it is worse, because
 * paper leaves the building.
 *
 * ⚠ **AND THERE IS NO SERVER-SIDE PDF TO ASK FOR INSTEAD, WHICH IS WHY THE
 * BROWSER DOES THE PRINTING.** `apps/notifications/rendering.py` produces a
 * `RenderedArtifact` whose `body` is text; the detail payload says so in the
 * one field that answers it, `can_download_pdf: false`, beside the reason *"the
 * platform's page writer is billing's and it writes bills"*. So the rendered
 * document in this product IS the server's rendered body inside this screen's
 * per-surface drawing, and the honest thing to put on paper is exactly that
 * node, with the page's own stylesheets so it prints as it looks.
 *
 * ══════════════════════════════════════════════════════════════════════════
 *  WHY IT IS A SEPARATE WINDOW AND NOT `window.print()` ON THIS PAGE
 * ══════════════════════════════════════════════════════════════════════════
 * `RouteDetailPage` prints with `window.print()` and Tailwind `print:` variants,
 * which is the right shape THERE: the route sheet is the whole page's subject.
 * Here the document is one column of a designer, so printing this page would
 * need every other thing on it — the shell, the rail, the merge-field table,
 * the tabs — marked `print:hidden`, in files this change does not own. A hold
 * on somebody else's file is how a screen ends up half-printed.
 *
 * A window holding the node and nothing else needs no such coordination and
 * cannot be broken by a sibling adding a panel. The cost is stated rather than
 * hidden: **a blocked pop-up means nothing prints**, so the caller must say so
 * to the person who pressed the button — `printRenderedDocument` returns
 * `false` and never fails silently.
 *
 * ══════════════════════════════════════════════════════════════════════════
 *  THE SPLIT: ASSEMBLY IS PURE, PRINTING IS NOT
 * ══════════════════════════════════════════════════════════════════════════
 * `printableDocument` builds the sheet into any `Document` and returns what it
 * put there. That is the half a test can hold: it can be handed
 * `document.implementation.createHTMLDocument()` and asked whether the inbox
 * lines travelled. `printRenderedDocument` is the half that needs a real window
 * and is therefore kept to almost nothing — open, assemble, wait, print.
 */

/** The pieces of a window this module actually uses.
 *
 *  Narrower than `Window` on purpose: a test supplies a document and two
 *  functions, and does not have to fake a browser to prove what gets printed.
 */
export interface PrintTarget {
  readonly document: Document;
  focus?: () => void;
  print: () => void;
  setTimeout?: (handler: () => void, ms: number) => unknown;
  addEventListener?: (type: string, listener: () => void) => void;
}

/** How long to wait for the page's own stylesheets before printing anyway.
 *
 *  A ceiling and not a delay: every sheet is same-origin and already in this
 *  browser's cache, so the load events normally arrive in the same tick. What
 *  this stops is a print that never happens because one `<link>` never fires —
 *  an unstyled page is a bad printout, a page that never prints is a dead
 *  button (hard-won law 2's mirror). */
export const STYLE_WAIT_MS = 1500;

/**
 * Build the printable sheet: the page's own styles, then the node itself.
 *
 * Returns the number of stylesheet `<link>`s copied in, which is what the
 * caller has to wait for. `<style>` elements are inline and need no wait.
 *
 * ⚠ **THE NODE IS IMPORTED, NEVER MOVED.** `importNode(node, true)` takes a
 * deep copy into the other document; appending the live node would REMOVE the
 * preview from the screen a person is standing on.
 */
export function printableDocument(opts: {
  into: Document;
  node: Element;
  title: string;
  styleSource: Document;
}): number {
  const { into, node, title, styleSource } = opts;
  into.title = title;

  // The window is opened at `about:blank`, which has no base to resolve a
  // relative URL against — see the block below.
  const charset = into.createElement("meta");
  charset.setAttribute("charset", "utf-8");
  into.head.appendChild(charset);

  let links = 0;
  for (const source of styleSource.querySelectorAll('link[rel="stylesheet"], style')) {
    const copy = into.importNode(source, true) as HTMLElement;
    if (source.tagName === "LINK") {
      // ⚠ **ABSOLUTISE THE HREF OR THE SHEET SIMPLY NEVER LOADS — DEF-NOT-4414,
      // FOUND IN A BROWSER AND BY NOTHING ELSE.** The built page links its CSS
      // as `/assets/index-<hash>.css`, a ROOT-RELATIVE url. `window.open("")`
      // gives a document whose base URL is `about:blank`, so that path resolves
      // against nothing and the request is never made. What came out of the
      // first version of this file was the right DOM with no styles at all: no
      // page, no inbox chrome, no preserved line breaks — the whole notice as
      // one wall of serif text. **Every check passed on it**, because jsdom
      // loads no stylesheets, so the DOM case proving the node travelled was
      // true and said nothing about the printout.
      const href = source.getAttribute("href");
      if (href !== null) {
        (copy as HTMLLinkElement).setAttribute("href", new URL(href, styleSource.baseURI).href);
      }
      links += 1;
    }
    into.head.appendChild(copy);
  }
  into.body.replaceChildren(into.importNode(node, true));
  return links;
}

/**
 * Put the given node on paper. Returns FALSE when no window could be opened.
 *
 * `false` is the pop-up-blocked case and it is the caller's to report: a button
 * that appears to do nothing is worse than a refusal, and this module has no
 * business choosing the words (BR-SHL-025 — the reason is the screen's).
 */
export function printRenderedDocument(opts: {
  node: Element;
  title: string;
  styleSource: Document;
  target: PrintTarget | null;
}): boolean {
  const { node, title, styleSource, target } = opts;
  if (target === null || target === undefined) {
    return false;
  }
  const links = printableDocument({ into: target.document, node, title, styleSource });

  let printed = false;
  const go = () => {
    if (printed) return;
    printed = true;
    target.focus?.();
    target.print();
  };

  if (links === 0 || target.setTimeout === undefined) {
    go();
    return true;
  }
  // Wait for the sheets, with the ceiling above as the backstop. Both paths run
  // `go`, and `printed` makes the second one a no-op — a page printed twice is
  // two sheets of paper, so the guard is not decoration.
  let pending = links;
  for (const link of target.document.querySelectorAll('link[rel="stylesheet"]')) {
    const done = () => {
      pending -= 1;
      if (pending <= 0) go();
    };
    link.addEventListener("load", done, { once: true });
    link.addEventListener("error", done, { once: true });
  }
  target.setTimeout(go, STYLE_WAIT_MS);
  return true;
}

/** Open the print window, or `null` when the browser refused.
 *
 *  Separated so the screen's click handler holds no `window` reference of its
 *  own and a test can hand `printRenderedDocument` a plain object instead. */
export function openPrintWindow(): PrintTarget | null {
  if (typeof window === "undefined") {
    return null;
  }
  // A named target rather than `_blank`: pressing Print twice reuses the same
  // window instead of leaving a trail of them behind.
  return window.open("", "smartbillhub-print") as PrintTarget | null;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-076 item 3 (12-governance/change-requests/CR-076-template-designer.md)
// generated: 2026-09-07 by the CR-076 lane
// gates: tsc✔ · vitest templateSurfacePrint.dom.test.tsx, RED-proved first
// exceptions: (1) THE BROWSER DOES THE PRINTING, because this product renders
//         no PDF for a notice class — `can_download_pdf` is served false with
//         that reason, and it is unchanged by this file.
//         (2) A BLOCKED POP-UP MEANS NOTHING PRINTS. Reported to the person who
//         pressed the button rather than swallowed; there is no second path.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
