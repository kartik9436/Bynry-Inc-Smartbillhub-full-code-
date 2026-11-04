// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CWP-10547 (F-02, WCAG 4.1.3 — no message is announced) ·
//           DEF-CWP-10548 (F-03, 1.3.1/3.3.1/3.3.2/4.1.2 — no input is marked
//           invalid, described or required) · DEF-CWP-10552 (F-04, 2.4.3 —
//           focus drops to the body) · DEF-CWP-10553 (F-17, 3.2.2 — the
//           selectors)
// Rulings:  decision log 2026-10-23 "Portal accessibility: three product
//           answers" · "Groups B and C: the selectors switch on the arrow
//           keys" · "Groups B and C: how they are built" (our judgments 1–8)
// Tests:    src/portal/components/a11y.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PORTAL'S ACCESSIBILITY PLUMBING, IN ONE FILE, SO NO SCREEN CAN
// FORGET IT.** Measured on 2026-10-23: one `.focus()` in the whole portal, no
// always-present place for a message to be announced, and a field kit that
// SUPPORTED `aria-invalid` / `aria-describedby` / `aria-required` while six
// callers passed the first and none the third — hard-won law 2, *built is not
// wired*. Everything here is reached THROUGH the kit (`FormField`,
// `TextInput`, the frames, `PortalApp`) rather than by each screen
// remembering to call it, because forty screens remembering is the design
// that produced the finding.
//
// Five pieces:
//   1. `moveFocusTo` — the ONE focus helper. Everything below uses it.
//   2. the ANNOUNCER — one polite and one assertive region, always present.
//      `announcePage` is the single entry point for *a page arrived* (lane
//      A11Y-D may pass the page title to it).
//   3. `FocusRescue` + `RouteFocus` — when the focused control is REMOVED
//      (a card opens a form, a submit replaces the form, a selector re-renders
//      the page) focus is put back on the same control if it is still there,
//      else on the page's heading; never left on the body.
//   4. field WIRING — `FormField` publishes its id, error, helper and
//      `required` and the box inside reads them.
//   5. the FORM SCOPE — a required box left empty is caught before sending,
//      and a failed submit lands on an ERROR SUMMARY that links each box.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import { RefusalStrip } from "@/components/Surfaces";

import { portalPageName } from "./PortalDocumentTitle";

/* ═══════════════════════════════════════════════════════════════════════════
 * 1 · THE FOCUS HELPER
 * ═══════════════════════════════════════════════════════════════════════════ */

const NATIVELY_FOCUSABLE = new Set(["A", "BUTTON", "INPUT", "SELECT", "TEXTAREA"]);

/**
 * Move focus to `target`, making it focusable first if it is a heading or a
 * message (`tabindex="-1"`: reachable by script, never added to the Tab
 * order). Answers whether focus actually arrived — a disabled button or an
 * element no longer in the page cannot take it, and a caller that assumed
 * otherwise would leave focus on the body exactly as before.
 */
export function moveFocusTo(target: Element | null | undefined): boolean {
  if (!(target instanceof HTMLElement) || !target.isConnected) return false;
  if (target.hasAttribute("disabled")) return false;
  const natively = NATIVELY_FOCUSABLE.has(target.tagName) && !target.hasAttribute("disabled");
  if (!natively && !target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
  target.focus();
  return document.activeElement === target;
}

/** The page's own heading: the `h1` inside `main` (or anywhere), else an `h2`. */
export function pageHeading(root: ParentNode = document): HTMLElement | null {
  const main = root.querySelector("main") ?? root;
  return (main.querySelector("h1") ?? main.querySelector("h2")) as HTMLElement | null;
}

/** Focus the first heading inside `root` — opened or replaced content. */
export function focusHeadingIn(root: ParentNode | null | undefined): boolean {
  if (!root) return false;
  return moveFocusTo(root.querySelector("h1, h2, h3"));
}

/**
 * A selector that finds THIS control again after a re-render replaces the
 * element: its id, else its tag plus its `data-*` hooks (the portal's own
 * stable handles — `data-action`, `data-account-switcher`, `data-sort` …).
 * `null` when the element carries nothing stable, so a caller never refocuses
 * a different control that merely shares a tag.
 */
export function stableSelector(element: Element): string | null {
  if (element.id) return `#${CSS.escape(element.id)}`;
  const hooks = element
    .getAttributeNames()
    .filter((name) => name.startsWith("data-") && name !== "data-variant" && name !== "data-size")
    .map((name) => `[${name}="${CSS.escape(element.getAttribute(name) ?? "")}"]`);
  if (hooks.length === 0) return null;
  return `${element.tagName.toLowerCase()}${hooks.join("")}`;
}

/** Waits that cover a synchronous re-render, a fetched catalogue and a
 *  suspended subtree coming back. Past the last one focus is left alone. */
const RETRY_MS = [0, 60, 200, 500, 1000];

function focusIsLost(): boolean {
  const active = document.activeElement;
  return active === null || active === document.body || !active.isConnected;
}

/**
 * Put focus back on the control `selector` names once it is drawn again —
 * Back returning to the card that opened a form, a selector after the page
 * re-rendered under it. Then run `after` (an announcement), once.
 */
export function refocus(selector: string, after?: () => void): void {
  let done = false;
  for (const wait of RETRY_MS) {
    window.setTimeout(() => {
      if (done) return;
      const found = document.querySelector(selector);
      if (found !== null && (document.activeElement === found || moveFocusTo(found))) {
        done = true;
        after?.();
      } else if (wait === RETRY_MS[RETRY_MS.length - 1]) {
        done = true;
        after?.();
      }
    }, wait);
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 2 · THE ANNOUNCER
 * ═══════════════════════════════════════════════════════════════════════════ */

interface Announcer {
  polite: (text: string) => void;
  assertive: (text: string) => void;
}

const AnnouncerContext = createContext<Announcer | null>(null);

/** The announcer most recently mounted — what a call from outside React
 *  (`announcePage`, `refocus`'s callback) speaks through. */
let mounted: Announcer | null = null;

/**
 * One polite and one assertive region, ALWAYS in the tree — a region that is
 * inserted together with its text is not reliably read, which is F-02's
 * whole mechanism. `PortalApp` mounts one around every route so it survives
 * navigation; each frame mounts one only when nothing above it did (a frame
 * rendered on its own in a test, or the three addresses outside a frame).
 *
 * ⚠ **THE SAME SENTENCE TWICE IS ANNOUNCED TWICE.** Each message gets a new
 * `key`, so React replaces the region's child NODE rather than setting the
 * same text again — two wrong passwords in a row are heard twice (judgment 1).
 */
export function PortalAnnouncer(props: { children: ReactNode }) {
  const above = useContext(AnnouncerContext);
  const [polite, setPolite] = useState({ n: 0, text: "" });
  const [assertive, setAssertive] = useState({ n: 0, text: "" });
  const announcer = useMemo<Announcer>(
    () => ({
      polite: (text) => setPolite((was) => ({ n: was.n + 1, text })),
      assertive: (text) => setAssertive((was) => ({ n: was.n + 1, text })),
    }),
    [],
  );
  useEffect(() => {
    if (above !== null) return undefined;
    mounted = announcer;
    return () => {
      if (mounted === announcer) mounted = null;
    };
  }, [above, announcer]);
  if (above !== null) return <>{props.children}</>;
  return (
    <AnnouncerContext.Provider value={announcer}>
      {props.children}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-portal-status="">
        <span key={polite.n}>{polite.text}</span>
      </div>
      <div className="sr-only" role="alert" aria-live="assertive" aria-atomic="true" data-portal-alert="">
        <span key={assertive.n}>{assertive.text}</span>
      </div>
    </AnnouncerContext.Provider>
  );
}

/** Speak through the nearest announcer. A no-op outside one, never a throw. */
export function useAnnounce(): Announcer {
  const near = useContext(AnnouncerContext);
  return useMemo(
    () => ({
      polite: (text: string) => (near ?? mounted)?.polite(text),
      assertive: (text: string) => (near ?? mounted)?.assertive(text),
    }),
    [near],
  );
}

/** Speak politely from outside React. */
export function announce(text: string, tone: "polite" | "assertive" = "polite"): void {
  if (text.trim() === "") return;
  mounted?.[tone](text);
}

/**
 * ⚠ **THE ONE ENTRY POINT FOR *A PAGE ARRIVED*** (coordinator, 2026-10-23:
 * lane A11Y-D owns page titles and passes the title here). `RouteFocus`
 * calls it with the page's heading until then. Polite, once per arrival.
 */
export function announcePage(title: string): void {
  announce(title, "polite");
}

/** What a message block SAYS: its child blocks' words with a space between
 *  them — `textContent` would run *"…account."* into *"Phone removed."*. */
function spokenText(element: HTMLElement): string {
  const blocks = [...element.children];
  // Only a stack of BLOCKS is joined; a sentence with an inline `<strong>` in
  // it is read whole, text nodes included.
  if (blocks.length < 2 || !blocks.every((one) => /^(P|DIV|UL|OL|LI|H[1-6]|SECTION)$/.test(one.tagName))) {
    return element.textContent ?? "";
  }
  return blocks.map((child) => (child.textContent ?? "").trim()).filter(Boolean).join(" ");
}

/**
 * A message that is ANNOUNCED and, by default, TAKES FOCUS when it appears —
 * the result of a submit or its refusal (F-02, F-04). It wraps the element a
 * screen already drew, with the same classes and `data-` hooks, so the page
 * looks exactly as it did.
 *
 * `tone="error"` speaks assertively; `status` politely. `signal` re-announces
 * when it changes while the element stays mounted (the same refusal again).
 */
export function Announced(
  props: {
    tone: "status" | "error";
    as?: "p" | "div" | "span";
    focus?: boolean;
    signal?: unknown;
    /** What to SAY when the element holds more than the message (a result
     *  panel): its heading, not every row of it. */
    say?: string;
    children: ReactNode;
  } & Omit<HTMLAttributes<HTMLElement>, "children">,
) {
  const { tone, as, focus, signal, say: sentence, children, ...rest } = props;
  const ref = useRef<HTMLElement | null>(null);
  const say = useAnnounce();
  useEffect(() => {
    const element = ref.current;
    if (element === null) return;
    const text = (sentence ?? spokenText(element)).replace(/\s+/g, " ").trim();
    if (text !== "") (tone === "error" ? say.assertive : say.polite)(text);
    if (focus !== false) moveFocusTo(element);
    // `children` is deliberately not a dependency: a re-render with the same
    // sentence is not a new message. `signal` is how a caller says it is.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signal]);
  const Tag = as ?? "p";
  return (
    <Tag ref={ref as never} data-announced={tone} {...rest}>
      {children}
    </Tag>
  );
}

/**
 * The staff kit's `RefusalStrip`, ANNOUNCED and FOCUSED when it appears — the
 * one refusal shape seven portal screens draw (Report, Track, Quick pay ×2,
 * Methods ×2, Preferences, Pay now). Same strip, same classes; the wrapper is
 * a plain `div`, so nothing moves.
 */
export function PortalRefusal(props: { children: ReactNode } & Record<`data-${string}`, string>) {
  const { children, ...hooks } = props;
  return (
    <Announced tone="error" as="div">
      <RefusalStrip {...hooks}>{children}</RefusalStrip>
    </Announced>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 3 · NEVER LEFT ON THE BODY
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * ⚠ **THE SHARED ROOT OF F-04.** Focus falls to the body whenever the focused
 * control is REMOVED from the page — an *Ask →* button replaced by the form it
 * opened, a Send replaced by its result, a selector whose page re-rendered.
 * Thirty-four of thirty-seven submits and every Ask card did this. Rather than
 * teach forty screens to catch it, this listens once: when a focused element
 * leaves the page and nothing else took focus, it goes back to the SAME
 * control if one is drawn again (by `stableSelector`), else to the page's
 * heading. An explicit move (`Announced`, the error summary, `refocus`) runs
 * first and wins, because this only acts while focus is still on the body.
 *
 * ⚠ **IT WATCHES THE PAGE, NOT `focusout`, AND THAT IS DELIBERATE.** Chromium
 * fires no `blur` or `focusout` when the focused node is REMOVED — focus just
 * becomes the body — so a listener on those events never hears the very case
 * it exists for. Instead it remembers the last control that took focus
 * (`focusin`) and, whenever the page changes (`MutationObserver`), asks whether
 * that control has left the page while focus sits on the body.
 */
export function useFocusRescue(): void {
  useEffect(() => {
    let last: Element | null = null;
    let selector: string | null = null;
    let around: Element[] = [];
    let pending = false;
    function took(event: FocusEvent) {
      if (!(event.target instanceof Element) || event.target === document.body) return;
      last = event.target;
      // ⚠ **ONLY A FORM BOX IS RE-FOUND BY ITS HOOKS.** A box (a selector,
      // a text box) that re-renders is the SAME control and focus belongs back
      // on it. A BUTTON that vanished was pressed to replace what it sat in —
      // a wizard's *Continue* finds another *Continue* on the next step — so
      // focus goes to the heading of the content that replaced it instead.
      selector = /^(INPUT|SELECT|TEXTAREA)$/.test(last.tagName) ? stableSelector(last) : null;
      around = [];
      for (let up = last.parentElement; up !== null && up !== document.body; up = up.parentElement) {
        around.push(up);
        if (up.tagName === "MAIN") break;
      }
    }
    function landing(wanted: string | null, chain: Element[]): boolean {
      if (wanted !== null && moveFocusTo(document.querySelector(wanted))) return true;
      // The nearest container that survived, and the first heading in it: the
      // form an *Ask →* opened, the next step of a wizard, the result.
      for (const box of chain) {
        if (box.isConnected && focusHeadingIn(box)) return true;
      }
      return moveFocusTo(pageHeading());
    }
    function rescue() {
      const leaving = last;
      if (pending || leaving === null || leaving.isConnected || !focusIsLost()) return;
      pending = true;
      const wanted = selector;
      const chain = around;
      for (const wait of RETRY_MS) {
        window.setTimeout(() => {
          if (wait === RETRY_MS[RETRY_MS.length - 1]) pending = false;
          if (!focusIsLost()) {
            pending = false;
            return;
          }
          if (landing(wanted, chain)) pending = false;
        }, wait);
      }
    }
    document.addEventListener("focusin", took);
    const watcher = new MutationObserver(rescue);
    watcher.observe(document.body, { childList: true, subtree: true });
    return () => {
      document.removeEventListener("focusin", took);
      watcher.disconnect();
    };
  }, []);
}

/**
 * After every change of address INSIDE the portal — never the first load —
 * focus goes to the new page's heading and the page is announced once
 * (judgment 6). Waits for the heading because a page fetches before it draws.
 *
 * ⚠ **THE LAST ADDRESS IS HELD FOR THE TAB, NOT FOR THE COMPONENT.** Signing
 * in moves from the sign-in tree to the signed-in one and re-mounts this
 * hook, so a per-mount memory read *Home* as a first load and left focus on
 * the body — the walk measured exactly that. Only the very first portal page
 * of the visit is a first load.
 */
let lastPortalPath: string | null = null;

/** Tests only: start a visit afresh. */
export function forgetLastPortalPath(): void {
  lastPortalPath = null;
}

export function useRouteFocus(): void {
  const { pathname } = useLocation();
  useEffect(() => {
    const was = lastPortalPath;
    lastPortalPath = pathname;
    if (was === null || was === pathname) return;
    let done = false;
    // A signed-in page fetches before it draws its heading; on a slow line
    // that is seconds, so the wait runs to eight.
    const timers = [60, 200, 500, 1000, 2000, 3500, 5000, 8000].map((wait) =>
      window.setTimeout(() => {
        if (done) return;
        const heading = pageHeading();
        if (heading === null) {
          // ⚠ **A PAGE WITH NO HEADING AT ALL** (measured: the signed-in Home
          // draws no `h1` — headings are lane A11Y-D's). After two seconds
          // focus goes to the page's `main` region and the document title is
          // said, so it is never left on the body; a heading, once drawn by
          // D's lane, wins on the very next visit.
          const main = document.querySelector("main");
          if (wait < 2000 || main === null) return;
          done = true;
          if (focusIsLost()) moveFocusTo(main);
          announcePage(document.title);
          return;
        }
        done = true;
        // A control on the new page that already has focus (the summary of a
        // refused submit, a refocused selector) is left where it is.
        if (focusIsLost() || document.activeElement === document.body) moveFocusTo(heading);
        // Lane A11Y-D (`DEF-CWP-10562`): the page's NAME, from the one function
        // the tab title reads, so what is heard and what the tab says agree.
        announcePage(portalPageName(document.body) ?? (heading.textContent ?? "").replace(/\s+/g, " ").trim());
      }, wait),
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [pathname]);
}

/** Mounted once, in `PortalApp`: the announcer, the rescue and route focus. */
export function PortalA11y(props: { children: ReactNode }) {
  return (
    <PortalAnnouncer>
      <RouteAndRescue />
      {props.children}
    </PortalAnnouncer>
  );
}

function RouteAndRescue() {
  useFocusRescue();
  useRouteFocus();
  return null;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 4 · THE FIELD WIRES ITSELF
 * ═══════════════════════════════════════════════════════════════════════════ */

export interface FieldWiring {
  id: string;
  errorId: string;
  helperId: string | null;
  invalid: boolean;
  required: boolean;
}

const FieldContext = createContext<FieldWiring | null>(null);

export function FieldWiringProvider(props: { value: FieldWiring; children: ReactNode }) {
  return <FieldContext.Provider value={props.value}>{props.children}</FieldContext.Provider>;
}

/**
 * What a box inside a `FormField` says about itself (judgment 2). Its own
 * props and the field's state are COMBINED (either one marks it), so a form that passes
 * nothing is still fully marked. Only the box whose id IS the field's id is
 * wired — a second control inside the same field (a reveal button) is not.
 */
export function useFieldWiring(
  id: string,
  own: { invalid?: boolean; describedBy?: string; required?: boolean },
): { "aria-invalid"?: true; "aria-describedby"?: string; "aria-required"?: true } {
  const field = useContext(FieldContext);
  const mine = field !== null && field.id === id ? field : null;
  const invalid = own.invalid === true || mine?.invalid === true;
  const required = own.required === true || mine?.required === true;
  const ids = [
    ...(own.describedBy ?? "").split(/\s+/),
    mine?.helperId ?? "",
    invalid && mine !== null ? mine.errorId : "",
  ].filter((one, index, all) => one !== "" && all.indexOf(one) === index);
  return {
    "aria-invalid": invalid ? true : undefined,
    "aria-describedby": ids.length > 0 ? ids.join(" ") : undefined,
    "aria-required": required ? true : undefined,
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 5 · THE FORM SCOPE AND ITS ERROR SUMMARY
 * ═══════════════════════════════════════════════════════════════════════════ */

interface ScopeField {
  label: string;
  required: boolean;
  /** An error the SCREEN gave the field (a server refusal, a format check). */
  given: string | null;
}

interface ScopeValue {
  /** The required-but-empty errors this scope found on its last check. */
  missing: Readonly<Record<string, string>>;
  register: (id: string, field: ScopeField) => void;
  unregister: (id: string) => void;
  clear: (id: string) => void;
  /** Bumped on every failed submit — the summary takes focus on each one. */
  attempt: number;
  fields: () => ReadonlyMap<string, ScopeField>;
}

const ScopeContext = createContext<ScopeValue | null>(null);

/** The scope a `FormField` is in, if any. */
export function useFormScope(): ScopeValue | null {
  return useContext(ScopeContext);
}

function isEmpty(id: string): boolean {
  const box = document.getElementById(id);
  if (box instanceof HTMLInputElement) {
    if (box.type === "checkbox" || box.type === "radio") return !box.checked;
    return box.value.trim() === "";
  }
  if (box instanceof HTMLSelectElement || box instanceof HTMLTextAreaElement) {
    return box.value.trim() === "";
  }
  // Not a box this scope can read (a radio group, a custom picker): it is not
  // judged here, and the server's own check still stands.
  return false;
}

export interface PortalForm {
  scope: ScopeValue;
  /**
   * Run before sending. Every field drawn REQUIRED (the asterisk) that is
   * empty gets *"Fill this in."*; if any is, or any field already carries an
   * error, the summary appears and takes focus and this answers `false`.
   */
  check: () => boolean;
  /** Say a submit failed on fields the SCREEN marked (a server refusal). */
  failed: () => void;
  /** `onClick={form.guard(send)}` — `send` runs only when `check` passes. */
  guard: (send: () => unknown) => () => void;
}

export function usePortalForm(): PortalForm {
  const { t } = useTranslation();
  const registry = useRef(new Map<string, ScopeField>());
  const [missing, setMissing] = useState<Record<string, string>>({});
  const [attempt, setAttempt] = useState(0);
  const register = useCallback((id: string, field: ScopeField) => {
    registry.current.set(id, field);
  }, []);
  const unregister = useCallback((id: string) => {
    registry.current.delete(id);
  }, []);
  const clear = useCallback((id: string) => {
    setMissing((was) => {
      if (!(id in was)) return was;
      const next = { ...was };
      delete next[id];
      return next;
    });
  }, []);
  const scope = useMemo<ScopeValue>(
    () => ({ missing, register, unregister, clear, attempt, fields: () => registry.current }),
    [missing, register, unregister, clear, attempt],
  );
  const check = useCallback(() => {
    const found: Record<string, string> = {};
    let given = false;
    for (const [id, field] of registry.current) {
      if (field.given) given = true;
      else if (field.required && isEmpty(id)) found[id] = t("portal.form.required");
    }
    setMissing(found);
    const ok = Object.keys(found).length === 0 && !given;
    if (!ok) setAttempt((n) => n + 1);
    return ok;
  }, [t]);
  const failed = useCallback(() => setAttempt((n) => n + 1), []);
  const guard = useCallback(
    (send: () => unknown) => () => {
      if (check()) void send();
    },
    [check],
  );
  return useMemo(() => ({ scope, check, failed, guard }), [scope, check, failed, guard]);
}

/**
 * The boundary of one form: its fields register here, and its ERROR SUMMARY
 * is drawn at the top of it after a failed submit — and only then, so a form
 * at rest looks exactly as before (judgment 4).
 */
export function FormScope(props: { form: PortalForm; children: ReactNode }) {
  return (
    <ScopeContext.Provider value={props.form.scope}>
      <ErrorSummary scope={props.form.scope} />
      {props.children}
    </ScopeContext.Provider>
  );
}

function ErrorSummary(props: { scope: ScopeValue }) {
  const { t } = useTranslation();
  const say = useAnnounce();
  const ref = useRef<HTMLDivElement | null>(null);
  const [rows, setRows] = useState<{ id: string; label: string; message: string }[]>([]);
  const { attempt, missing } = props.scope;
  // Read in a PASSIVE effect: every field has registered its current error
  // in a LAYOUT effect by then (`useScopedField`), whichever order they render.
  useEffect(() => {
    if (attempt === 0) return;
    const listed: { id: string; label: string; message: string }[] = [];
    for (const [id, field] of props.scope.fields()) {
      const message = field.given ?? missing[id];
      if (message) listed.push({ id, label: field.label, message });
    }
    listed.sort((a, b) => {
      const one = document.getElementById(a.id);
      const two = document.getElementById(b.id);
      if (!one || !two) return 0;
      return one.compareDocumentPosition(two) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    });
    setRows(listed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt, missing]);
  const shownAt = useRef(0);
  useEffect(() => {
    if (attempt === 0 || rows.length === 0 || shownAt.current === attempt) return;
    shownAt.current = attempt;
    moveFocusTo(ref.current);
    say.assertive(
      // Each message already ends in its own full stop; only the title needs one.
      [`${t("portal.form.summaryTitle")}.`, ...rows.map((row) => `${row.label}: ${row.message}`)].join(" "),
    );
  }, [attempt, rows, say, t]);
  if (attempt === 0 || rows.length === 0) return null;
  return (
    <div
      ref={ref}
      tabIndex={-1}
      className="mb-4 border-2 border-danger-700 bg-[white] p-4"
      data-error-summary=""
      aria-labelledby="portal-error-summary-title"
    >
      <h2 id="portal-error-summary-title" className="text-body font-bold text-danger-700">
        {t("portal.form.summaryTitle")}
      </h2>
      <ul className="mt-2 flex flex-col gap-1 text-body">
        {rows.map((row) => (
          <li key={row.id}>
            <a
              href={`#${row.id}`}
              className="text-danger-700 underline"
              data-error-summary-link={row.id}
              onClick={(event) => {
                event.preventDefault();
                moveFocusTo(document.getElementById(row.id));
              }}
            >
              {`${row.label}: ${row.message}`}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * What `FormField` calls: registers the field with its scope (when it is in
 * one) and answers the error to draw — the screen's own, else the scope's
 * *"Fill this in."*.
 */
export function useScopedField(
  id: string,
  label: string,
  required: boolean,
  given: string | null | undefined,
): string | null {
  const scope = useContext(ScopeContext);
  const register = scope?.register;
  const unregister = scope?.unregister;
  useLayoutEffect(() => {
    register?.(id, { label, required, given: given ?? null });
  });
  useEffect(() => () => unregister?.(id), [id, unregister]);
  return given ?? scope?.missing[id] ?? null;
}
