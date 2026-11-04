#!/usr/bin/env python3
"""Unwired-prop check — the largest single defect category (4 of 21, DEF-007..010).

A component declares an OPTIONAL prop, renders a whole feature behind it, is
fully styled and fully tested — and no caller ever passes it. Every test passes,
every gate is green, and the feature simply does not exist in the running app.

That is how the sidebar user block, sign-out, the tenant name and the language
switch all shipped absent. Twelve gates had nothing to say about any of them,
because each gate asks about law, traceability or output shape — none asks
whether a component was given its data.

The rule: for every prop consumed through an OPTIONALITY IDIOM, a JSX attribute
`X={...}` / `X="..."` must appear SOMEWHERE in non-test source — any file,
including the same one, since a component may legitimately be used by a sibling
in its own module. What the check refuses is a prop that NOTHING anywhere
supplies. That is dead UI.

WHICH IDIOMS, AND WHY THE LIST GREW (DEF-041, widened 2026-08-15)
-----------------------------------------------------------------
Until 2026-08-15 this check knew exactly ONE idiom — `props.X !== undefined` and
`props.X &&` — and React has three more that mean the same thing. The cost was
measured on AppShell and it was not small: **7 of AppShell's 10 optional props
had ZERO non-test callers and this check reported "every guarded prop has a
caller"**. The RBAC nav gating, the global search handler and the whole
notifications feed could each have shipped dead exactly as the user block did,
on the same component, and the gate written to stop that would have stayed
green. The four idioms now read:

  1. `props.X !== undefined` / `props.X &&`   — the original explicit guard
  2. `props.X?.(...)`                          — the OPTIONAL CALL
  3. `props.X ?? fallback`                     — the NULLISH DEFAULT
  4. `helper(props.X)` where `X?:` is declared optional IN THE SAME FILE
     — an optional prop handed straight to a helper, which is how
     `visibleNavItems(nav, props.accessibleModules)` hid the RBAC nav gating

Idiom 4 is deliberately the INTERSECTION of "passed as a bare argument" and
"declared optional here", not either alone. Bare-argument alone fires on
REQUIRED props (`describedBy(props.quantityId, …)` — `quantityId: string`, no
`?`) and proves nothing. Declared-optional alone was measured too: **34
findings**, most of them props with a live consumer, i.e. exactly the
40-findings gate DEF-041's prevention column warns about — "a widened gate that
fires on 40 legitimately-later props teaches people to add ALLOW entries, which
is how a gate stops being a gate". That measurement is recorded here so the next
lane can decide about idiom 5 without re-investigating; it is NOT enabled.

WHAT THE WIDENING ALSO HAD TO FIX: CALLER DETECTION
---------------------------------------------------
The old caller test was `\\bX=\\{` — a brace only. `entityType="premises"` and
`stem="rating.status"` are ordinary JSX string attributes and were read as NO
CALLER, so the widening's first run carried two findings that were wired all
along. Quoted attributes count now. `children` is excluded structurally rather
than allowlisted: React passes it by JSX NESTING, so no `children=` attribute
ever exists and the check can only ever be wrong about it.

Exemptions: test files (they exercise props deliberately, so a test caller is
NOT a wiring — that is the whole shape of DEF-007..010) and props listed in
ALLOW below. **Every ALLOW entry needs a reason AND a revisit condition, and
that is enforced, not requested**: an entry whose text contains no `REVISIT`
fails this check. An allow-list without revisit conditions is a list of silent
permanent exemptions, and this file exists because of what silence costs.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "07-frontend" / "src"

# Props deliberately optional with no caller today. Each needs a REASON and a
# REVISIT condition, so this list stays a record of decisions rather than a
# place to silence the check.
#
# KEYS ARE SCOPED. `"components/AppShell.tsx:collapsed"` exempts that prop on
# that component only; `"*:client"` exempts a name repo-wide and should stay
# rare — a bare name is an exemption for every component that ever uses the word.
#
# ⚠ **THE KEYS ARE SCOPED AND THE DETECTION IS NOT, AND THIS SENTENCE USED TO
# IMPLY OTHERWISE (DEF-3462, 2026-09-03).** `has_caller()` below matches the
# prop NAME across every non-test body and never asks which component receives
# it. So an exemption is precise while the check it exempts from is not: a prop
# whose name ANY other component also takes is effectively unguarded here,
# whatever its ALLOW key says. Measured live — `AppShell.onSearch` was satisfied
# for months by `features/rating/PlanWizard.tsx` passing `onSearch` to a
# SearchSelectField, and deleting AppShell's real wiring left this gate GREEN.
# It is written here, at the sentence that creates the belief, rather than only
# in the register: this example used to BE `AppShell.tsx:onSearch`, a key that no
# longer exists, which is how a comment outlives the thing it describes.
ALLOW = {
    # ── repo-wide (test seams that every page takes) ─────────────────────────
    "*:client": (
        "test seam — every page takes an injectable ApiClient; the real one is "
        "the module-level `api` singleton, imported not passed. "
        "REVISIT IF: a page is ever given a client by a caller, which would mean "
        "the singleton is no longer the wiring."
    ),
    "*:nav": (
        "config override for tests; SHELL_NAV is the default. "
        "REVISIT IF: a second nav configuration ships (per-tenant nav), at which "
        "point a real caller exists and this entry must go."
    ),
    "*:basis": (
        "MoneyCell's BR-REP-001 date-basis label. Built ahead of its consumer: "
        "the reports screens that declare a basis ship in W5/R3. "
        "REVISIT IF: the reports screens land — remove this entry then."
    ),
    # ── AppShell: DEF-041's own seven, triaged 2026-08-15 ────────────────────
    # These are the reason this check was widened. Each is LATENT, not broken:
    # AppShell renders a working default for every one. They are recorded here,
    # named, with the story that ends each exemption — which is the record the
    # ALLOW list is meant to be, and is the opposite of the silence that let
    # DEF-007..010 ship.
    "components/AppShell.tsx:accessibleModules": (
        "BR-SHL-025 RBAC nav gating. `visibleNavItems` shows the FULL nav when "
        "this is undefined, so today every signed-in user sees every module in "
        "the sidebar and the server refuses what they may not open. "
        "REVISIT IF: /me starts serving the accessible-module set (BE-09) — and "
        "note this is the sharpest entry in the list, because the day the server "
        "sends it, a shell that does not pass it silently keeps showing modules "
        "the user cannot use."
    ),
    "components/AppShell.tsx:bellItems": (
        "BR-SHL-007 notifications feed, newest-first as served. Defaults to an "
        "empty list, so the bell renders with no items rather than crashing. "
        "REVISIT IF: BE-09 lands the bell endpoint — the feed is dead UI until a "
        "caller passes this, which is DEF-007..010's exact shape."
    ),
    "components/AppShell.tsx:onBellSelect": (
        "deep-link from a bell item to its subject record. Inert while "
        "`bellItems` is empty — it cannot fire with nothing to click. "
        "REVISIT IF: `bellItems` gains a caller; these two are one feature and "
        "must be wired in the same change."
    ),
    "components/AppShell.tsx:onMarkAllRead": (
        "the bell's mark-all-read action, same feature as `bellItems`. "
        "REVISIT IF: `bellItems` gains a caller."
    ),
    # ⚠ `components/AppShell.tsx:onSearch` WAS HERE AND IS GONE (2026-09-03).
    #
    # Its REVISIT condition was "FI-01 lands the search endpoint — a caller
    # passes this and the box goes live with nothing else to change". That
    # happened: `GET /search` is served by `06-backend/apps/tenancy/search_api.py`
    # and `components/ShellWithSession.tsx` passes the handler.
    #
    # **REMOVING IT IS PART OF THE WORK, NOT A TIDY-UP.** An exemption left
    # behind after its reason is gone is worse than one never written: the gate
    # goes on reporting "every guarded prop has a caller" about a prop it has
    # been told to ignore, so the next lane to break the wiring is not told —
    # DEF-007..010's shape wearing the costume of its own exemption. The entry
    # survived one amendment (DEF-2423) and that is precisely when a stale
    # exemption is easiest to keep: the text was updated, so it looked tended.
    #
    # ⚠ **AND REMOVING IT BUYS LESS THAN IT LOOKS — SAY SO RATHER THAN IMPLY
    # OTHERWISE (DEF-3462, found by red-proofing this removal).** `has_caller()`
    # below matches the prop NAME across every non-test body and never asks
    # which component receives it, while the ALLOW keys above are component-
    # SCOPED — which reads as though the detection is too. It is not.
    # `features/rating/PlanWizard.tsx` passes `onSearch` to a SearchSelectField
    # three times, so **AppShell's `onSearch` has had a satisfying caller since
    # that wizard shipped**, and deleting the real wiring here leaves this check
    # GREEN. Proved: the attribute was removed from ShellWithSession and this
    # gate still reported PASS. So the exemption was belt on a brace that was
    # never fastened, and what actually guards the wiring is
    # `ShellWithSession.wiring.test.tsx`, which names the component.
    "components/AppShell.tsx:collapsed": (
        "BR-SHL-002 controlled sidebar collapse. AppShell keeps its own state "
        "when unpassed, so collapsing WORKS — what is missing is PERSISTENCE "
        "across sessions. "
        "REVISIT IF: US-SHL-013's preference service ships."
    ),
    "components/AppShell.tsx:onCollapsedChange": (
        "the write half of BR-SHL-002 persistence, same feature as `collapsed`. "
        "REVISIT IF: US-SHL-013's preference service ships; wire both together."
    ),
    # ── other components, triaged 2026-08-15 ────────────────────────────────
    "components/Toast.tsx:queue": (
        "declared test seam in its own comment — 'the optional `queue` prop lets "
        "tests drive a queue they also inspect'. Production uses the internal "
        "FIFO (BR-SHL-022). "
        "REVISIT IF: a screen ever needs to inject a toast queue, which would "
        "make this a real prop with a real caller."
    ),
    "components/WizardFrame.tsx:controller": (
        "declared test seam, 'like ToastProvider's queue prop'. Production uses "
        "the internally-owned commit controller. "
        "REVISIT IF: a wizard needs an externally-driven controller."
    ),
    "components/WizardFrame.tsx:onDownloadErrorReport": (
        "A18 §4 partial-failure affordance; falls back to a no-op. Built ahead of "
        "its consumer — no shipped wizard operation produces a downloadable error "
        "report yet. "
        "REVISIT IF: an import/bulk operation starts producing one (the metering "
        "and assets importers are the likely first)."
    ),
    "components/WizardFrame.tsx:onViewFailingRows": (
        "A18 §4 partial-success link target; falls back to a no-op. Same feature "
        "and same wait as `onDownloadErrorReport`. "
        "REVISIT IF: a wizard reports partial success with row-level failures."
    ),
    "components/FormModal.tsx:quantityError": (
        "an OVERRIDE, not a feed: `props.quantityError ?? quantityContextError`. "
        "The form-error context supplies the value in production, so the field "
        "shows its error today with nothing passed. "
        "REVISIT IF: the context fallback is removed, at which point an unpassed "
        "prop means a validation error that never reaches the screen."
    ),
    "components/FormModal.tsx:unitError": (
        "an OVERRIDE of the form-error context, same shape as `quantityError`. "
        "REVISIT IF: the context fallback is removed."
    ),
    "components/DataTable.tsx:visibleColumns": (
        "controlled column visibility; DataTable keeps internal state when "
        "unpassed, so the column picker WORKS — what is missing is persistence. "
        "REVISIT IF: US-SHL-013's preference service ships (same service as "
        "AppShell's `collapsed`, and they should be wired together)."
    ),
    "components/DataTable.tsx:onVisibleColumnsChange": (
        "the write half of controlled column visibility. "
        "REVISIT IF: `visibleColumns` gains a caller."
    ),
    "features/identity/SignInPage.tsx:tenant": (
        "declared test seam in its own comment — the real value comes from the "
        "route (`useTenant`), per BR-IDN-001 path tenancy. "
        "REVISIT IF: the tenant ever stops resolving from the URL."
    ),
    "features/tenancy/SignupWizard.tsx:initialNav": (
        "declared test seam — 'renders a later step statically'. Production "
        "always starts at step 1. "
        "REVISIT IF: deep-linking into a signup step ships."
    ),
    "features/exports/ListExportButton.tsx:disabledReason": (
        "BR-SHL-025 'disabled WITH its reason'. Null when unpassed, so the button "
        "is enabled — correct for every list that ships today. "
        "REVISIT IF: a read-only role or a blocked export state needs to explain "
        "itself; the prop exists precisely so the reason is never omitted."
    ),
}

#: Idiom 1 — the original explicit guard.
GUARD = re.compile(r"props\.([a-zA-Z_][\w]*)\s*(?:!==\s*undefined|&&)")
#: Idiom 2 — the optional call: `props.onSearch?.(q)`.
OPTIONAL_CALL = re.compile(r"props\.([a-zA-Z_][\w]*)\s*\?\.")
#: Idiom 3 — the nullish default: `props.bellItems ?? []`.
NULLISH_DEFAULT = re.compile(r"props\.([a-zA-Z_][\w]*)\s*\?\?")
#: Idiom 4a — `props.X` handed straight to a call as a bare argument. Only
#: counts INTERSECTED with 4b; alone it fires on required props.
BARE_ARGUMENT = re.compile(r"[(,]\s*props\.([a-zA-Z_]\w*)\s*[,)]")
#: Idiom 4b — the prop is DECLARED optional in this file's own props type.
OPTIONAL_DECL = re.compile(r"^\s*([a-zA-Z_]\w*)\?\s*:", re.M)

#: React passes `children` by JSX NESTING, so a `children=` attribute never
#: exists and this check could only ever be wrong about it. Structural, not an
#: ALLOW entry — an ALLOW entry would imply a decision was made about a feature.
NEVER_AN_ATTRIBUTE = frozenset({"children"})


def consumed_props(body: str) -> set[str]:
    """Every prop this file consumes through an optionality idiom."""
    found: set[str] = set()
    for pattern in (GUARD, OPTIONAL_CALL, NULLISH_DEFAULT):
        found |= {m.group(1) for m in pattern.finditer(body)}
    declared_optional = set(OPTIONAL_DECL.findall(body))
    found |= {m.group(1) for m in BARE_ARGUMENT.finditer(body)} & declared_optional
    return found - NEVER_AN_ATTRIBUTE


def has_caller(prop: str, bodies) -> bool:
    """Is there a JSX attribute passing `prop` anywhere in non-test source?

    Brace or quoted literal — `x={v}`, `x="v"`, `x='v'`. Deliberately NOT a bare
    `\\bprop\\s*=`, which matches an ordinary assignment (`const collapsed = false`)
    and would silently declare every prop wired.
    """
    attribute = re.compile(rf"\b{re.escape(prop)}\s*=\s*[{{\"']")
    return any(attribute.search(body) for body in bodies)


def allow_reason(rel_path: str, prop: str) -> str | None:
    """The ALLOW reason covering this (file, prop), scoped first then repo-wide."""
    return ALLOW.get(f"{rel_path}:{prop}") or ALLOW.get(f"*:{prop}")


# ── Self-test (hard-won law 7): the guard must go RED on each idiom ─────────
#: One synthetic component per idiom, each with a prop NOTHING passes. If a
#: future edit narrows a pattern enough to miss one of these, the check fails
#: ITSELF rather than reporting a green tree. The first three are the idioms
#: DEF-041 measured as invisible; the fourth is the RBAC-nav shape.
MUST_STILL_BITE = (
    ("props.onlyGuard !== undefined && render()", "onlyGuard", "idiom 1: explicit guard"),
    ("props.onlyOptionalCall?.(q)", "onlyOptionalCall", "idiom 2: optional call"),
    ("const x = props.onlyNullish ?? [];", "onlyNullish", "idiom 3: nullish default"),
    (
        "interface P {\n  onlyBareArg?: readonly string[];\n}\n"
        "visibleNavItems(nav, props.onlyBareArg)",
        "onlyBareArg",
        "idiom 4: optional prop handed straight to a helper",
    ),
)
#: …and the shapes it must NOT bite, so the widening stays usable.
MUST_NOT_BITE = (
    ("interface P {\n  req: string;\n}\ndescribedBy(props.req, false)", "req",
     "a REQUIRED prop passed as a bare argument is not an optionality idiom"),
    ("const v = props.children;", "children",
     "children is passed by JSX nesting, never as an attribute"),
)


def self_test() -> list[str]:
    """Blind spots this check must not have. Empty list = every idiom bites."""
    blind = []
    for body, prop, why in MUST_STILL_BITE:
        if prop not in consumed_props(body):
            blind.append(f"BLIND: {why} — an unwired prop in this shape would pass")
    for body, prop, why in MUST_NOT_BITE:
        if prop in consumed_props(body):
            blind.append(f"FALSE POSITIVE: {why}")
    # A caller written as a quoted JSX attribute must count as a caller — the
    # widening's own first-run false positives (`entityType="premises"`).
    if not has_caller("entityType", ['<AuditTab entityType="premises" />']):
        blind.append("BLIND: a quoted JSX attribute is a caller and must count as one")
    if has_caller("collapsed", ["const collapsed = false;"]):
        blind.append("FALSE POSITIVE: an ordinary assignment is not a JSX attribute")
    # Every exemption must carry a revisit condition. Enforced, not requested.
    for key, reason in ALLOW.items():
        if "REVISIT" not in reason:
            blind.append(
                f"ALLOW entry {key!r} has no REVISIT condition — an exemption with no "
                "end condition is a silent permanent one"
            )
    return blind


def main() -> int:
    blind = self_test()
    if blind:
        print("FAIL unwired-prop check — the check's own self-test is blind:")
        for line in blind:
            print(f"  · {line}")
        return 1

    files = [p for p in SRC.rglob("*.tsx") if ".test." not in p.name]
    text = {p: p.read_text(encoding="utf-8") for p in files}
    bodies = list(text.values())

    findings: list[str] = []
    for path, body in text.items():
        rel = str(path.relative_to(SRC)).replace("\\", "/")
        for prop in sorted(consumed_props(body)):
            if allow_reason(rel, prop) is not None:
                continue
            if not has_caller(prop, bodies):
                findings.append(
                    f"{path.relative_to(ROOT)}: renders behind `props.{prop}` but no caller passes it"
                )

    if findings:
        print("FAIL unwired props — a feature is guarded by a prop nothing supplies:")
        for line in findings:
            print(f"  · {line}")
        print(
            "\nEither pass the prop from a caller, or add "
            "'<path-under-src>:<prop>' to ALLOW with a reason AND a REVISIT condition."
        )
        return 1
    print(
        f"PASS unwired-prop check — {len(files)} components, 4 optionality idioms, "
        f"every consumed prop has a caller or a reasoned exemption ({len(ALLOW)} in ALLOW)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
