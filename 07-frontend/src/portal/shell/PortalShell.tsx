// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-020 (EP-CWP-03) — the shell a customer lands in ·
//           US-CWP-023 — the account set on screen. Screens: CWP-022 and every
//           signed-in screen after it
// Defects:  DEF-CWP-3902 (two of the six tabs pointed at addresses no route
//           serves) · DEF-CWP-3901 (`messageCount` was a prop nothing passed) ·
//           DEF-CWP-4359 (a customer who signed in could not sign out — the
//           route and the client call both existed and no screen called
//           either, so a session ended only when the cookie expired).
//           ⚠ **IT WAS FILED AGAINST THE NUMBER 4357 AND THAT NUMBER WAS
//           ALREADY TAKEN** — `DEF-PAY-4357` was pushed in `1ff13a82` while
//           the portal row sat unpushed in a shared tree two commits behind.
//           CLAUDE.md law 11's `DEF-1787` mechanism, live: two lanes each
//           computed `max + 1` correctly, from different worlds. The register
//           is the pushed world, so this one renumbered. The commit that
//           landed the control (`caca79bb`) still names the old number in its
//           message; no id is written here that no register issued, which is
//           what `G106` refuses.
// Rules:    09-component-inventory.md §1 `PortalShell` (header · AccountSwitcher
//           · Messages · Help · Avatar; the tab strip with `aria-current`) ·
//           BR-CWP-010 (changing the switcher re-scopes EVERY tab, and the
//           scope is applied in the QUERY) · BR-CWP-013 (the set is FLAT — no
//           tree, no parent) · BR-CWP-099 + PO ruling 2026-09-04 (our style
//           guide is the default and a utility's hex OVERRIDES it — one
//           variable, no second helper) · B14 rule 8 (a real `<select>`) ·
//           rule 21 (Tailwind utilities; `portal/` is on route-b-migrated.txt)
//           · rule 31 (no database id is ever the visible value of a field) ·
//           rule 36 (the pack gives layout, r10 gives the look, the shared kit
//           is how you comply) · BR-CWP-104 (sign out ends the session on the
//           SERVER and returns to this utility’s own portal front door)
// Tests:    src/portal/shell/PortalShell.test.tsx ·
//           src/portal/shell/SignOut.dom.test.tsx ·
//           src/portal/shell/currentAccount.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · every signed-in screen
// ───────────────────────────────────────────────────────
//
// ⚠ EVERY CLASS HERE WAS ASKED OF THE COMPILER BEFORE IT WAS WRITTEN, for the
// reason `primitives.tsx` states in capitals: this theme clears Tailwind's
// stock palette, so `bg-white` and every `slate` shade compile to NOTHING while
// `tsc` and every `toContain` pass. The portal writes the theme's own names —
// `bg-[white]`, `text-neutral-*`, `text-body` — and the walkthrough asserts
// COMPUTED STYLE so the next lane cannot lose this quietly.

import type { ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { BuildVersion } from "@/components/BuildVersion";
import { BrandMark } from "@/features/tenancy/BrandMark";
import type { PortalFront } from "../api/guestClient";
import type { PortalAccount } from "../api/portalClient";
import { signOut } from "../api/portalClient";
import { announce, PortalAnnouncer, refocus } from "../components/a11y";
import { PortalRegionalProvider } from "../components/regional";
import { NavActionWord, usePortalPath } from "../components/primitives";
import { PORTAL_SCREENS } from "../routing/screenIds";
import { portalFrameStyle } from "./GuestFrame";

/**
 * The six tabs, in the inventory's order. `to` is relative to the portal root.
 *
 * ⚠ **`to` IS THE ROUTE, NOT A GUESS AT ONE** (`DEF-CWP-3902`). Two of these
 * six pointed at addresses `screenIds.ts` does not register: `details` at
 * `/details` when the screen it means (`CWP-024`, live since wave G) is served
 * at `/my-details`, and `requests` at `/requests`, whose screen is wave 3.
 * `useRoutes` returns `null` for an unmatched path, so both drew a blank page
 * under a live header — and every test passed, because a
 * `toContain('data-tab="details"')` assertion asks whether the tab EXISTS and
 * never whether it goes anywhere. `tabIsRouted` below closes that, and
 * `PortalShell.test.tsx` names the one tab still unrouted, so the day wave 3
 * lands `/requests` the test says so out loud.
 */
export const PORTAL_TABS: readonly { key: string; to: string }[] = [
  { key: "home", to: "/home" },
  { key: "bills", to: "/bills" },
  { key: "usage", to: "/usage" },
  { key: "payments", to: "/payments" },
  { key: "requests", to: "/requests" },
  { key: "details", to: "/my-details" },
];

/**
 * `CWP-053` — *Messages*, the screen behind the header word (`US-CWP-067`).
 *
 * ⚠ **THE ID IS THE HOLD, WRITTEN AS DATA** (`DEF-CWP-3982`). Naming the
 * screen here rather than leaving *"wave 3"* in a comment is what lets the
 * control release itself and lets a test say, in a sentence, what has to
 * happen next when it does.
 */
export const MESSAGES_SCREEN_ID = "CWP-053";

/** The address `CWP-053` is served at, or `null` while it is unbuilt. */
export function messagesRoute(): string | null {
  return PORTAL_SCREENS.find((screen) => screen.id === MESSAGES_SCREEN_ID)?.path ?? null;
}

/**
 * `CWP-015` — the utility's own portal front door, and where a sign-out lands
 * (`BR-CWP-104`).
 *
 * ⚠ **THE DESTINATION IS THE ONE THING A SIGN-OUT CAN GET WRONG IN A WAY
 * NOBODY NOTICES** — the staff app landed on the bare public host for a day
 * and dropped the tenant on every sign-out (`DEF-037`, PO on a live deploy),
 * which is why `routing/tenantPath.ts` has `signOutDestination` and why this
 * has a name of its own rather than a string inside a callback.
 *
 * ⚠ **IT IS NOT THE STAFF SIGN-IN PAGE AND THE DIFFERENCE IS NOT COSMETIC.**
 * `/{tenant}/signin` reads the STAFF credential store; a customer's email is
 * unknown there and gets the ordinary failure (`BR-CWP-004`, from the other
 * side). Landing a customer on it would show them a door their own password
 * cannot open, which is worse than the bare host — it looks like their
 * password stopped working.
 */
export const SIGN_OUT_SCREEN_ID = "CWP-015";

/**
 * The address `CWP-015` is served at.
 *
 * ⚠ **THE FALLBACK IS THE PORTAL ROOT AND NEVER `null`.** `messagesRoute()`
 * above returns `null` and its control DISAPPEARS, which is right for a word
 * whose screen is unbuilt. A sign-out that disappeared would be
 * `DEF-CWP-4359` again, so an unregistered `CWP-015` degrades to the portal's
 * own front page — still this utility, still signed out, still a way back in.
 * `PortalShell.test.tsx` asserts the register really holds `CWP-015` at
 * `/sign-in`, so the fallback cannot ship unnoticed.
 */
export function signOutRoute(): string {
  return PORTAL_SCREENS.find((screen) => screen.id === SIGN_OUT_SCREEN_ID)?.path ?? "/";
}

/**
 * *Sign out* — the header word, and the whole of `DEF-CWP-4359`.
 *
 * ⚠ **THE SHELL OWNS IT; NO SCREEN PASSES A PROP.** Twenty-five screens
 * render `PortalShell`, and an `onSignOut` prop would be optional for
 * twenty-four of them by the end of the first week — which is hard-won law 2's
 * front half exactly (a component with a prop nothing passes is dead UI, four
 * defects in one day). A control every signed-in screen must have is a control
 * the frame supplies.
 *
 * ⚠ **THE SESSION ENDS ON THE SERVER, NOT IN THE BROWSER.** `POST
 * portal/auth/sign-out` revokes the session row and deletes the cookie; a
 * handler that only navigated would leave a live session behind on a library
 * computer, which is the reason this defect is `high` and not a missing
 * convenience.
 *
 * ⚠ **`onSettled`, NOT `onSuccess` — the staff shell's ruling, and it applies
 * here for the same reason.** A failed POST still means the customer asked to
 * leave; keeping them on the screen because the network hiccuped is the wrong
 * side to fail on. The cache is cleared either way, so nothing they were
 * reading survives on the machine.
 *
 * ⚠ **`replace: true`** so Back cannot re-enter a dead session — a browser
 * button is exactly how the next person at a shared machine would get there.
 */
export function PortalSignOut() {
  const { t } = useTranslation();
  const path = usePortalPath();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Computed during render from the route that is open, not inside the
  // callback — the same reason `ShellWithSession` computes `signOutTo` where
  // it does.
  const destination = path(signOutRoute());
  const leaving = useMutation({
    mutationFn: () => signOut(api),
    onSettled: () => {
      queryClient.clear();
      navigate(destination, { replace: true });
    },
  });
  return (
    <NavActionWord
      name="sign_out"
      label={t("portal.shell.signOut")}
      disabled={leaving.isPending}
      onClick={() => leaving.mutate()}
    />
  );
}

/** Does the portal actually serve this tab’s address today? */
export function tabIsRouted(tab: { to: string }): boolean {
  return PORTAL_SCREENS.some((screen) => screen.path === tab.to);
}

/**
 * The tabs a customer may press — the declared six, less any whose screen is
 * not built yet.
 *
 * ⚠ **AN UNBUILT TAB IS ABSENT, NOT DISABLED AND NOT A DEAD LINK**
 * (`BR-CWP-093`, *nothing empty ever appears*). Five tabs today: `requests`
 * waits on `US-CWP-060`’s `CWP-046` in wave 3 and returns the moment that
 * route is registered, with no change to this file. A greyed sixth tab would
 * be a control that looks broken — the same reason the switcher is a LABEL
 * rather than a one-option `<select>`.
 */
export function routedTabs(): readonly { key: string; to: string }[] {
  return PORTAL_TABS.filter(tabIsRouted);
}

/** `Maria Alvarez` → `MA`. Two letters, the reader's own name, never an id. */
export function initialsOf(name: string | null | undefined): string {
  const words = String(name ?? "")
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) return "?";
  const first = words[0]?.[0] ?? "";
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

/**
 * The account switcher.
 *
 * ⚠ **A LABEL WHEN THE SET HAS ONE ENTRY, A REAL `<select>` WHEN IT HAS MORE**
 * (`09-component-inventory.md` §1). Maria holds one account and sees
 * *1408 Elm St · A* as text she cannot press; the landlord holds four and gets
 * a control. A disabled `<select>` with one option is a control that looks
 * broken, and a `<div>` styled like a control is worse — B14 rule 8 asks for
 * the real element wherever there is a choice to make.
 *
 * ⚠ **THE VISIBLE VALUE IS THE ADDRESS, NEVER THE ID** (B14 rule 31). The id
 * is the `<option value>`, which is a wire value and not a field a person
 * reads.
 */
export function AccountSwitcher(props: {
  accounts: PortalAccount[];
  current: string | null;
  onChange: (accountId: string) => void;
}) {
  const { t } = useTranslation();
  if (props.accounts.length <= 1) {
    const only = props.accounts[0];
    return (
      <span
        className="truncate text-body text-neutral-900"
        data-account-switcher="label"
        data-account-count={props.accounts.length}
      >
        {only ? only.label : t("portal.shell.noAccount")}
      </span>
    );
  }
  return (
    <select
      // ⚠ **F-17 (`DEF-CWP-10553`), RULED 2026-10-23: IT STILL SWITCHES ON
      // EVERY PICK, ARROW KEYS INCLUDED.** What changed is around the switch:
      // the label says it changes the page, focus is put back on this control
      // once the page has re-rendered under it, and the change is announced —
      // *"Showing account AC-2026-00057"*.
      aria-label={t("portal.shell.switcherChangesPage")}
      className="h-9 max-w-[280px] border border-field-border bg-[white] px-3 text-body text-neutral-900"
      data-account-switcher="select"
      data-account-count={props.accounts.length}
      value={props.current ?? props.accounts[0]?.id}
      onChange={(event) => {
        const picked = props.accounts.find((account) => account.id === event.target.value);
        props.onChange(event.target.value);
        refocus('select[data-account-switcher="select"]', () =>
          announce(t("portal.a11y.showingAccount", { number: picked?.account_no ?? "" })),
        );
      }}
    >
      {props.accounts.map((account) => (
        <option key={account.id} value={account.id}>
          {account.label}
        </option>
      ))}
    </select>
  );
}

/**
 * THE ACCOUNT BAR — one line under the menu, on EVERY signed-in screen.
 *
 * PO ruling 2026-09-08, reviewing the portal wireframes: *"here header bar
 * should ahve menu - and below that we should have a line for account - this
 * should be consitent across registered user login"*.
 *
 * ⚠ **WHAT WAS WRONG, AND IT IS NOT THAT THE INFORMATION WAS MISSING.** The
 * account WAS on screen — squeezed into the top row between the utility's name
 * and *Help*, as a `truncate`d label or a bare `<select>`, competing for width
 * with five other controls. So on a narrow window the one fact a customer needs
 * to trust the page — **which of my properties am I looking at** — was the first
 * thing clipped, and it was never labelled as an account at all. Giving it its
 * own row costs 40 pixels and removes it from that competition entirely.
 *
 * ⚠ **THE SWITCHER MOVES HERE; IT IS NOT COPIED.** Two account controls in one
 * frame would be two answers to one question, and a customer who changed the
 * top one and saw the bottom one disagree would be right to distrust both. The
 * header row now carries the utility, the errands and the way out — nothing
 * about which account.
 *
 * ⚠ **THE NUMBER IS SHOWN AND B14 RULE 31 IS NOT BROKEN.** `account_no` is the
 * utility's own printed reference — it is on the bill, the customer reads it
 * down the phone, and it is what a clerk asks for. The DATABASE id
 * (`account.id`, a uuid) is never drawn, which is what rule 31 forbids. The two
 * are different fields and only one of them is meaningful to a person.
 *
 * ⚠ **IT DRAWS NOTHING RATHER THAN AN EMPTY ROW.** A login with no account yet
 * — enrolled but not linked — gets no bar at all. `BR-CWP-093`'s rule against
 * empty containers is the same rule that drops an unbuilt tab instead of
 * greying it: a labelled row with nothing after the label reads as a fault.
 */
export function AccountBar(props: {
  accounts: PortalAccount[];
  currentAccountId: string | null;
  onAccountChange: (accountId: string) => void;
}) {
  const { t } = useTranslation();
  const current =
    props.accounts.find((account) => account.id === props.currentAccountId) ?? props.accounts[0];
  if (!current) return null;
  return (
    <div className="border-b border-neutral-200 bg-[white]" data-account-bar="">
      <div className="mx-auto flex max-w-[1100px] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2 text-body">
        <span className="font-semibold text-neutral-900" data-account-bar="number">
          {t("portal.shell.accountNumbered", { number: current.account_no })}
        </span>
        {/* The service address, which is what `label` is (`portalClient.ts`) —
            and the reason this bar is legible at a glance rather than a code a
            person has to recognise. */}
        <span className="truncate text-neutral-600" data-account-bar="where">
          {current.label}
        </span>
        {current.is_master ? (
          <span className="text-neutral-600" data-account-bar="owner">
            {t("portal.accounts.billedToOwner")}
          </span>
        ) : null}
        {/* ⚠ Pushed right and drawn ONLY when there is a choice to make —
            `AccountSwitcher` already decides label-versus-control from the
            SERVER's count, and repeating that decision here is how two screens
            end up disagreeing. It renders its own label form for one account,
            which would duplicate the address two spans left, so the single-
            account case skips it entirely. */}
        {props.accounts.length > 1 ? (
          <span className="ml-auto">
            <AccountSwitcher
              accounts={props.accounts}
              current={props.currentAccountId}
              onChange={props.onAccountChange}
            />
          </span>
        ) : null}
      </div>
    </div>
  );
}

/**
 * The frame every signed-in screen sits inside.
 *
 * ⚠ **CHANGING THE SWITCHER RE-SCOPES EVERY TAB, AND THE SCOPE IS APPLIED IN
 * THE QUERY** (`BR-CWP-010`). This component raises `onAccountChange` and does
 * NOT filter anything itself: the account id travels to the server on every
 * read, and the server intersects it with the session's set. A shell that
 * filtered client-side would be a screen enforcing a rule the query is supposed
 * to enforce — which is the exact shape of a rule that holds until somebody
 * calls the endpoint directly.
 */
export function PortalShell(props: {
  front: PortalFront;
  displayName: string | null;
  accounts: PortalAccount[];
  currentAccountId: string | null;
  onAccountChange: (accountId: string) => void;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  // ⚠ **`usePortalPath` AND NOT A HAND-BUILT PREFIX.** The kit already owns
  // *"a path inside THIS utility's portal"* and states why: the tenant is read
  // off the address the browser is on, never typed (`BR-CWP-005`,
  // `BR-CWP-007`). Building `/${tenant}/portal` here would be a second
  // implementation of that rule — and the first draft of this file did exactly
  // that, which is how `PortalShell.test.tsx` found six tabs pointing at
  // `//portal/...` with `aria-current` on none of them.
  const path = usePortalPath();
  return (
    // ⚠ **EVERY SCREEN OF THIS HALF OF THE PORTAL PASSES THROUGH HERE, WHICH
    // IS WHY THE PROVIDER IS HERE** (`DEF-CWP-3994`). The tenant's date format
    // and time zone arrive on the front payload; publishing them at the frame
    // means a screen cannot be born outside the provider — the exact failure
    // that made this defect, one route tree up.
    <PortalRegionalProvider front={props.front}>
    <div
      className="min-h-screen bg-bg text-neutral-900"
      // ⚠ **`portalFrameStyle` CARRIES THE SURFACE AS WELL AS THE ACCENT**
      // (`DEF-CWP-3987`). The portal's `Card` is white and the shared `Panel`
      // reads `--color-surface`, which is the staff app's grey — so a screen
      // with a rail drew a white main column beside a grey one until this
      // frame moved the token. See `GuestFrame.tsx` for why it is the
      // variable and not the component.
      //
      // ⚠ `brandStyle` is IMPORTED and not re-implemented. The PO ruled on
      // 2026-09-04 that our style guide is the default and a utility's hex
      // overrides it; that is ONE variable (`--color-accent`) with its two
      // derived steps, and a second helper here would be the second source
      // law 5 exists to prevent — and the one place the guest surface and the
      // signed-in surface could end up different colours.
      style={portalFrameStyle(props.front.tenant)}
      data-portal-frame="shell"
    >
      <header className="border-b border-neutral-200 bg-[white]">
        <div className="mx-auto flex h-14 max-w-[1100px] items-center gap-4 px-5">
          {/* ⚠ **THE SIGNED-IN SHELL HAD THE SAME GAP AS THE GUEST ONE** —
              the utility's name was plain text, so from any inner screen the
              only way back was the browser. PO, 2026-09-05. The signed-in home
              already has a tab, so the brand is the link and no word is added
              here. */}
          {/* CR-172-BRC10 / DEF-TEN-9705 — the utility's logo (or its generated
              two-letter mark) beside its name, from the one logo address the
              staff app uses. Drawn only when the server sent the mark. */}
          {props.front.tenant.mark !== undefined && (
            <BrandMark
              mark={props.front.tenant.mark}
              hasLogo={props.front.tenant.has_logo === true}
              logoRef={props.front.tenant.logo_ref ?? null}
              size={32}
              name={props.front.tenant.name}
            />
          )}
          <Link
            to={path("/home")}
            className="truncate font-bold text-neutral-900 no-underline hover:underline"
            data-portal-tenant-name=""
            data-link="brand_home"
          >
            {props.front.tenant.name}
          </Link>
          {/* ⚠ **THE ACCOUNT SWITCHER USED TO SIT HERE** and moved to
              `AccountBar` below the menu on 2026-09-08 (PO: *"below that we
              should have a line for account"*). It is MOVED and not copied —
              see that component for why two of them would be worse than one in
              the wrong place. */}
          <div className="ml-auto flex items-center gap-5 text-body">
            {/* ⚠ **MESSAGES WAS A `<span>` BESIDE `Help`, WHICH IS A LINK —
                `DEF-CWP-3982`, `14-layout-audit.md` row D7.** Plain text with
                no destination, no count and no sentence, at the top right of
                every signed-in screen, next to a word that works. That is
                hard-won law 2's MIRROR: a control that looks live and is not,
                and a customer will click it.

                ⚠ **IT IS ABSENT UNTIL ITS SCREEN LANDS, NOT GREYED — the
                precedent is eight lines up in this same file.** `routedTabs`
                already drops an unbuilt tab rather than disabling it, and says
                why: *"a greyed sixth tab would be a control that looks
                broken"* (`BR-CWP-093`). Two doors in one header cannot answer
                the same question two different ways.

                ⚠ **AND IT RELEASES ITSELF, WHICH IS BETTER THAN A HOLD PLUS A
                TEST TO REMEMBER IT** (`DEF-CWP-3925` — a hold whose reason is
                *a screen is not built* has a clock in it, and landing the
                screen and releasing the control are two acts of which only the
                first feels like the work). This reads the front end's own
                register: the day `CWP-053` is registered, the word appears as
                a link to that address with no change here.

                ⚠ **THE COUNT IS STILL A GAP AND STILL DELIBERATE**
                (`DEF-CWP-3901`): it is `read_at IS NULL` on the portal's own
                per-recipient row, which is `US-CWP-067` and is not built —
                deliberately NOT a column on `outbound_message`, whose
                docstring forbids a recipient's read state (`DEF-CWP-3612`).
                `PortalShell.test.tsx`'s HOLD EXPIRY case is what fires when
                `CWP-053` lands and names the count as the remaining work. */}
            {messagesRoute() ? (
              <NavLink
                to={path(messagesRoute() as string)}
                className="text-neutral-900 no-underline hover:underline"
                data-shell-bell=""
              >
                {t("portal.shell.messages")}
              </NavLink>
            ) : null}
            <NavLink to={path("/help")} className="text-neutral-900 no-underline hover:underline">
              {t("portal.nav.help")}
            </NavLink>
            {/* ⚠ **`DEF-CWP-4359` — THERE WAS NO WAY OUT OF THIS PORTAL.**
                `POST portal/auth/sign-out` was served and `signOut()` was
                exported, and nothing in `src/portal/` imported it: a
                customer's session ended when the cookie expired, so the next
                person at a library or service-counter machine got their
                bills, their address and their payment history. It sits BEFORE
                the avatar so the drawing's right edge does not move, and
                after *Help* because that is where a person looks. */}
            <PortalSignOut />
            <span
              className="inline-flex h-8 w-8 items-center justify-center border border-neutral-300 text-base font-bold"
              data-shell-avatar=""
              aria-hidden="true"
            >
              {initialsOf(props.displayName)}
            </span>
          </div>
        </div>
      </header>
      <nav
        className="border-b border-neutral-200 bg-[white]"
        aria-label={t("portal.shell.tabsLabel")}
      >
        {/* ⚠ **`flex-wrap` IS WHY THE PORTAL NO LONGER SCROLLS SIDEWAYS ON A
              PHONE, AND IT IS A SHARED-FRAME FIX** (walked 2026-09-08 at 390px
              on `CWP-024`, `CWP-025`, `CWP-031`, `CWP-046`, `CWP-051` and
              `CWP-054`: `document.scrollWidth` was **461** against a **390**
              viewport, and the single element past the edge was this strip's
              last tab, *My details*). Six tabs at `gap-6` need ~450px and the
              row could not give way, so EVERY signed-in screen inherited a
              horizontal scrollbar — the guest frame, which wraps, did not.
              Wrapping keeps all six tappable rather than pushing two of them
              off the edge, which is what `overflow-x-auto` would have done:
              a door you cannot see is hard-won law 2's mirror.
              `gap-y-0` because each tab already carries `py-3`. */}
          <div className="mx-auto flex max-w-[1100px] flex-wrap gap-x-6 gap-y-0 px-5 text-body">
          {routedTabs().map((tab) => (
            <NavLink
              key={tab.key}
              to={path(tab.to)}
              data-tab={tab.key}
              // `aria-current="page"` is what the active tab is drawn FROM,
              // rather than a second `isActive` class: one source, and a
              // screen reader and the border read the same fact.
              className={({ isActive }) =>
                `-mb-px border-b-[3px] py-3 no-underline ${
                  isActive
                    ? "border-accent font-semibold text-neutral-900"
                    : "border-transparent text-neutral-600"
                }`
              }
            >
              {t(`portal.tab.${tab.key}`)}
            </NavLink>
          ))}
        </div>
      </nav>
      <AccountBar
        accounts={props.accounts}
        currentAccountId={props.currentAccountId}
        onAccountChange={props.onAccountChange}
      />
      {/* F-02 (`DEF-CWP-10547`) — see `GuestFrame`'s identical line. */}
      <main className="mx-auto max-w-[1100px] px-5 py-6">
        <PortalAnnouncer>{props.children}</PortalAnnouncer>
      </main>
      {/* `DEF-CWP-9162` — the build, on every signed-in page, as on every guest
          page (`GuestFrame`) and every staff page (`AppShell`): one source. */}
      <footer className="mx-auto flex max-w-[1100px] justify-end px-5 pb-6">
        <BuildVersion className="text-sm text-neutral-700" />
      </footer>
    </div>
    </PortalRegionalProvider>
  );
}
