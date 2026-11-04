// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 §2 row 8 and §5 (PO 2026-10-04, option (a), verbatim:
//          "Also hide customer details shown on screen (names, addresses,
//          amounts, account numbers). Menus, buttons and labels stay visible,
//          so you can still see what people clicked and where they got stuck.")
// Rules:   CLAUDE.md hard-won law 3 — mask by default, unmask only the chrome,
//          so a screen added later is private until someone decides otherwise.
// Tests:   src/analytics/privacy.dom.test.ts (through the real recorder)
// ───────────────────────────────────────────────────────
//
// TWO JOBS, BOTH ABOUT WHAT LEAVES THE BROWSER:
//
// 1. **The recorder's masking.** `maskTextSelector: "*"` hands EVERY text node
//    to `maskText`, which keeps a text readable only when its element sits in
//    the chrome — navigation, menus, tabs, buttons, labels, column headings and
//    section headings (h3–h6) — and is not inside an always-masked place. Even
//    chrome text has its digits and email addresses scrubbed, so "Pay $186.40"
//    records as "Pay $***.**". Every input is masked. Attributes are kept only
//    from a short list that draws the page (class, role, …); `href` is cleaned
//    like an address and everything else (title, alt, aria-label, data-*) is
//    masked.
//
//    ⚠ **h1 AND h2 ARE MASKED ON PURPOSE.** `PageHeader` renders a record's
//    page title as h1 — or h2 under Settings — and on a record that title IS the
//    customer's name ("Maria Lopez"). Section headings (h3–h6) are the
//    product's own words. Breadcrumbs (`.crumbs`) are masked for the same
//    reason: their last crumb is the record. The signed-in person's own name,
//    initials and email in the frame (`.foot-name`, `.av`, `.foot-menu-*`) are
//    masked too.
//
//    To unmask a piece of chrome the selectors below do not reach, add
//    `data-analytics-chrome`; to force-mask anything, `data-analytics-mask`.
//
// 2. **Addresses on every event.** `$current_url`, `$pathname`, the
//    `$initial_*` family and the recorder's own page address are passed through
//    `errorReport.ts`'s cleaner — the SAME `redactPath`/`redactSearch`, with
//    printed references withheld too (`keepReferences: false`). `$title` is
//    dropped: a record's page title can be a customer's name.

import { WITHHELD, redactPath, redactSearch } from "@/components/errorReport";

/** Never readable, whatever contains it. */
const ALWAYS_MASKED = [
  "h1",
  "h2",
  ".crumbs",
  ".foot-name",
  ".foot-menu-name",
  ".foot-menu-identity",
  ".av",
  "input",
  "textarea",
  "select",
  "[contenteditable]",
  "[data-analytics-mask]",
].join(", ");

/** The chrome: what a person clicks and the words that say what a thing is. */
const CHROME = [
  "nav",
  '[role="navigation"]',
  '[role="menu"]',
  '[role="menubar"]',
  '[role="menuitem"]',
  '[role="tab"]',
  '[role="tablist"]',
  "button",
  '[role="button"]',
  "label",
  "legend",
  "th",
  '[role="columnheader"]',
  "h3",
  "h4",
  "h5",
  "h6",
  "[data-analytics-chrome]",
].join(", ");

const EMAIL = /[^\s@]+@[^\s@]+/g;
const DIGIT = /[0-9]/g;
const NON_SPACE = /\S/g;

/** Every visible character replaced — the recorder's own default spelling. */
function hide(text: string): string {
  return text.replace(NON_SPACE, "*");
}

/** Chrome text: readable, with digits and emails scrubbed. */
function scrub(text: string): string {
  return text.replace(EMAIL, (match) => hide(match)).replace(DIGIT, "*");
}

export function isChrome(element: Element | null | undefined): boolean {
  if (!element || typeof element.closest !== "function") {
    return false;
  }
  return element.closest(ALWAYS_MASKED) === null && element.closest(CHROME) !== null;
}

/** The recorder's text mask (rrweb `maskTextFn`). */
export function maskText(text: string, element: HTMLElement | null): string {
  return isChrome(element) ? scrub(text) : hide(text);
}

/** Every typed value, every input type (rrweb `maskInputFn`). */
export function maskInput(text: string): string {
  return hide(text);
}

/** Attributes that only draw the page. Anything else is masked. */
const DRAWING_ATTRIBUTES = new Set([
  "class",
  "id",
  "style",
  "role",
  "type",
  "rel",
  "for",
  "tabindex",
  "disabled",
  "hidden",
  "width",
  "height",
  "colspan",
  "rowspan",
  "dir",
  "lang",
  "viewbox",
  "d",
  "fill",
  "stroke",
  "stroke-width",
  "points",
  "x",
  "y",
  "cx",
  "cy",
  "r",
  "rx",
  "ry",
  "x1",
  "x2",
  "y1",
  "y2",
  "transform",
  "xmlns",
  "aria-hidden",
  "aria-expanded",
  "aria-selected",
  "aria-current",
  "aria-disabled",
  "aria-pressed",
  "aria-checked",
  "data-screen-id",
  "data-portal",
]);

/** The recorder's attribute mask (rrweb `maskAttributeFn`). */
export function maskAttribute(name: string, value: string): string {
  const lower = name.toLowerCase();
  if (DRAWING_ATTRIBUTES.has(lower)) {
    return value;
  }
  if (lower === "href" || lower === "src" || lower === "action") {
    return cleanPathAndQuery(value);
  }
  return hide(value);
}

/** The options `client.ts` hands PostHog's `session_recording` (and the test hands rrweb). */
export const RECORDING_PRIVACY = {
  maskAllInputs: true,
  maskTextSelector: "*",
  maskTextFn: maskText,
  maskInputFn: maskInput,
  maskAttributeFn: maskAttribute,
} as const;

function cleanPathAndQuery(value: string): string {
  if (value.startsWith("data:") || value.startsWith("blob:")) {
    return WITHHELD;
  }
  try {
    const base = typeof window !== "undefined" ? window.location.origin : "http://localhost";
    const url = new URL(value, base);
    if (/^[a-z]+:\/\//i.test(value)) {
      return cleanUrl(url.href);
    }
    return redactPath(url.pathname, { keepReferences: false }) + redactSearch(url.search);
  } catch {
    return WITHHELD;
  }
}

/**
 * One full address cleaned: the origin, then the path and query through
 * `errorReport.ts`'s cleaner. The fragment is dropped. A FOREIGN address (a
 * referrer from somebody's webmail) keeps its origin only — its path is not
 * ours to know the shape of.
 */
export function cleanUrl(value: string, ownOrigin?: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return WITHHELD;
  }
  const own = ownOrigin ?? (typeof window !== "undefined" ? window.location.origin : url.origin);
  const ours = url.origin === own || /(^|\.)bynry\.com$/.test(url.hostname);
  if (!ours) {
    return `${url.origin}/`;
  }
  return url.origin + redactPath(url.pathname, { keepReferences: false }) + redactSearch(url.search);
}

const URL_KEYS = new Set([
  "$current_url",
  "$referrer",
  "$initial_current_url",
  "$initial_referrer",
  "$session_entry_url",
  "$session_entry_referrer",
  "$prev_pageview_url",
]);
const PATH_KEYS = new Set([
  "$pathname",
  "$initial_pathname",
  "$session_entry_pathname",
  "$prev_pageview_pathname",
]);
const DROPPED_KEYS = new Set(["$title", "title", "$el_text", "$elements_chain", "$elements"]);

/**
 * Clean every address-shaped property on one event, nested `$set` /
 * `$set_once` included. Returns a new object; the input is not changed.
 */
export function cleanEventUrls<T extends Record<string, unknown>>(properties: T, ownOrigin?: string): T {
  const out: Record<string, unknown> = {};
  for (const [name, value] of Object.entries(properties)) {
    if (DROPPED_KEYS.has(name)) {
      continue;
    }
    if (URL_KEYS.has(name) && typeof value === "string") {
      out[name] = value === "$direct" || value === "" ? value : cleanUrl(value, ownOrigin);
    } else if (PATH_KEYS.has(name) && typeof value === "string") {
      out[name] = redactPath(value, { keepReferences: false });
    } else if ((name === "$set" || name === "$set_once") && value && typeof value === "object") {
      out[name] = cleanEventUrls(value as Record<string, unknown>, ownOrigin);
    } else {
      out[name] = value;
    }
  }
  return out as T;
}

/**
 * The recorder's own page address (`$snapshot` meta events carry `data.href`).
 * Walks the batch and cleans each one in place on a copy.
 */
export function cleanSnapshotUrls(snapshotData: unknown, ownOrigin?: string): unknown {
  if (!Array.isArray(snapshotData)) {
    return snapshotData;
  }
  return snapshotData.map((event) => {
    if (event && typeof event === "object" && "data" in event) {
      const data = (event as { data?: unknown }).data;
      if (data && typeof data === "object" && typeof (data as { href?: unknown }).href === "string") {
        return {
          ...(event as object),
          data: { ...(data as object), href: cleanUrl((data as { href: string }).href, ownOrigin) },
        };
      }
    }
    return event;
  });
}
