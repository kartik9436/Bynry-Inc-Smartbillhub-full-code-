# Prototype r10 — received 2026-08-16

**What this is.** The design bundle the Product Owner handed over on 2026-08-16
(`SMARTBillHub_UI_Mockups.zip`), stored verbatim as a new revision. Raised as
**CR-002** in `12-governance/11-change-requests.md`.

**Status: THE DEFAULT UI REFERENCE, and NOT re-extracted.** Two facts, both true,
and the gap between them is the thing to understand before using this folder.

**PO ruling 2026-08-16**, verbatim: *"So for this session we will be refering to
r10 - as default; make that note"*. So when the question is *"what should this
screen look like"*, the answer is this folder. **Where r10 and r9 disagree, r10
wins.** (This reverses what this file said when it was first written — it
originally told you to cite r9 for anything already specified. That instruction
is dead; the ruling replaced it.)

**But nothing in `04-docs/01-spec` has been re-extracted.** All seventeen
A-series documents carry `05-prototype/UtilityBilling.html` in their own header
line as their extraction source, and they were extracted from it. **So the spec
describes r9 screens while the default reference is r10, and nothing in the repo
reconciles the two.** See "How to use this" below — that is not a footnote, it is
the operating instruction.

---

## What changed against r9

Established by comparing module identifiers in `SMARTBillHub.dc.html` against
`05-prototype/UtilityBilling.reference.html.txt`, not from the covering note.

### A new module that the module map does not have: **Work**

Nine tabs (`workTab` values in the source):

`orders` · `dispatch` · `wmap` (map view) · `crews` · `parts` · `templates` ·
`rules` · `mobile` · `perf`

The seed data in `work-map.js` shows what it is: dispatched field work — work
orders `WO-4821`…`WO-4831`, types *Disconnect · non-pay*, *Meter exchange*,
*Leak investigation*, *Reconnect*, *Read verification*, *Move-in activation*,
*Backflow inspection*, *Main repair*, each with a technician, a priority, a due
time and a status (`Queued` → `Scheduled` → `En route` → `On site`), plotted on
a Leaflet basemap.

**This is field service management, and CLAUDE.md's module map has no module
that owns it.** That is `OQ-249`, not a thing to decide while coding.

### A second new module: **Workflows** (a guided runner)

`module:'workflows'` with `wfView:'runner'`, `wfStep`, and a `wfReturn` that
sends the user back where they came from. Four kinds so far: `reads`, `rates`,
`cost`, `stock`. Entered from Work (`openWfParts` returns to `'work'`).

### **Assets** grew from a stub to seven tabs

`meters` · `sub` · `btm` (behind-the-meter) · `inventory` · `lifecycle` ·
`imports` · `map`

`btm` is new vocabulary — `assets-map.js` seeds solar inverters (`PV-1180`,
`PV-1204`, "Exported 412 kWh · Jul") and an EV charger (`EV-2210`) alongside
meters and sub-meters. Net metering already exists as a rating input (CHANGELOG
r4); behind-the-meter devices as first-class assets do not.

### `UI-RULES.md` — twenty binding UI conventions, new in this bundle

Its own framing: *"The binding conventions for every screen. Anything new must
follow these; anything found violating them is a bug."*

That sentence makes it a **rules document**, and rules belong in module
`02-business-rules.md` files under hard-won law 10, not in a loose markdown file
inside a prototype folder. Several of its rules contradict nothing yet and
several almost certainly contradict shipped screens — rule 16 (pagination footer
on *every* list table, page size remembered per table), rule 15 (max 2 row-action
icons + overflow, fixed icon vocabulary), rule 11 (consequence-preview box before
any commit that writes money or service state). **None of that has been checked
against the running app.** Filed as part of CR-002; do not treat the file as
enforced merely because it is present.

---

## Files, and what actually loads

`SMARTBillHub.dc.html` references exactly three siblings:

```
href="./styles.css"   src="./support.js"   src="./table-tools.js"
```

So the reference renders standalone from this folder. But note what that list
does **not** contain:

| File | Loaded by `.dc.html`? |
|---|---|
| `styles.css` | yes |
| `support.js` | yes |
| `table-tools.js` | yes — new in r10, the list-table assembly behind UI rules 12–17 |
| `ds-base.js` | no |
| `assets-map.js` | **no** — defines `<asset-map>`; no `<asset-map>` tag appears in the file |
| `work-map.js` | **no** — defines `<work-map>`; no `<work-map>` tag appears in the file |

The two map components ship but nothing instantiates them. This is hard-won
law 2 ("built is not wired") in the design bundle rather than in our code, so it
is recorded here rather than fixed: **the map tabs `assets/map` and `work/wmap`
cannot be evaluated from this bundle as delivered.** Whether the maps are
intended, and against which basemap licence, is part of `OQ-249`.

`uploads/pasted-*.png` are ~50 screenshots pasted during the design session.
Nothing in the bundle references them. They are kept because hard-won law 6 —
"diff the running app against `05-prototype/`" — is the only check that has ever
caught a rendering defect here, and it needs pictures to diff against.

`uploads/Modernist/utility-billing/design_handoff_smartbillhub/README.md` is the
covering handoff note. **It is stale in this bundle**: its sidebar order and its
"Screens / Views" list stop at Reports and mention neither Assets, Work nor
Workflows, and its sidebar puts Settings second — which PO ruling 2026-08-10
already reversed (BR-SHL-001, Settings moves to last). Read the `.dc.html`, not
the README.

---

## How to use this

**Read the DESIGN for the screen. Read the SPEC for the rules.**

1. **Screen questions — layout, copy, flows, states, tabs, button grammar —
   answer from `SMARTBillHub.dc.html` in this folder.** It is the default.
2. **Rule questions — money math, state machines, permissions, isolation,
   idempotency — answer from the signed documents**, which this bundle does not
   touch and cannot change. B4/B5 are ❄️ FROZEN; a design file never moves a
   finance figure.
3. **Where A1–A17's screen description contradicts r10, r10 is right and the
   spec is stale.** File it — a defect row, or an amendment to the citing
   document, dated — **before building on it**. Do not silently follow the stale
   text and do not silently follow r10 without recording the divergence you hit.
   That write-back is the only thing keeping the two from drifting further.
4. **A reference default is not a scope decision.** `OQ-249` is still OPEN: is
   Work in scope at all, is it a tenth code module owning its own B2 tables or
   tabs on `assets`, where does it sit in the build order, is `btm` R2. **Never
   resolve it by choosing.** Reading r10 as the default does not authorise
   building its nine Work tabs, minting their S-IDs, or adding tables no module
   owns.
5. **`UI-RULES.md` is not enforced yet.** It calls itself binding on every
   screen; no gate checks it and no audit has run. Treat it as the design's
   intent, not as a passed check — hard-won law 1.

**r9 (`05-prototype/UtilityBilling.html`) is kept, not deleted**, precisely
because the A-series still cites it by path. It is the record of what the spec
was extracted from, and it stays readable until re-extraction closes the gap.
