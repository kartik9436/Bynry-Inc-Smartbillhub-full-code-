# The reusable deep-analysis prompt — r2, 2026-08-26

The Product Owner's standing instruction for a module/feature blueprint (the
shape the Meter Reads Blueprint came back in). **r2 folds in the rulings of
2026-08-26** — one import rail, write mode at stage 1–2, pages not side panels,
mixing as the normal case, the read-method vocabulary — so the next analysis
starts from the current agreement, not the 2026-08-24 one. Captured per CR-038;
the PO keeps a copy for their own reference.

---

Prepare a detailed design and engineering analysis for `<MODULE / FEATURE>`,
delivered as an HTML link (an artifact), not as repo files. Do not write
anything to the repository and do not allocate a CR number unless I confirm.

Ground every claim in the CODE AS IT RUNS TODAY, not in the documents.
State the product version you measured against, and the date. Where a
document and the code disagree, the code is the finding — say so.

Structure it in five sections, in this order:

SECTION 1 — THE SUBJECT
  · What the thing IS, defined plainly.
  · Its types — and if "type" means more than one thing (what was measured,
    how it was obtained, where it is in its life), separate them.
  · Why it is required — what breaks in the business without it.
  · A numbered catalogue of every SCENARIO that has to work, each with a
    status measured against the code: works / partial / not built.

SECTION 2 — PRODUCT DEFINITION AND DIAGRAMS
  · What the product area is: screens, tabs, wizards, and which are built.
  · Diagrams — as many as the subject genuinely needs, each earning its
    place by showing a MECHANISM prose cannot carry. Expect: where this
    sits in the wider chain, the data model, the main flow with its gates,
    a state/lifecycle diagram, and one diagram per hard case.
  · Treat MIXING as the normal case, never an edge case: a cycle mixes
    routes, a ROUTE mixes utility services (RT-001 electric·water ·
    RT-002 water · RT-003 gas), and a stop mixes meters, sub-meters and
    devices/assets. Any flow that assumes one service per file, per cycle
    or per route is wrong by design.
  · Label the arrows. Every figure gets a caption stating its ONE claim.

SECTION 3 — ENGINEERING SPECIFICATION
  One block per capability. For EACH one, all six:
      Field map · Screens · Endpoints/APIs · DB tables · Test cases · Seed data
  End every block with what is MISSING, named concretely.
  Mark each capability built / partial / not built.

SECTION 4 — OPEN QUESTIONS, SPLIT THREE WAYS
  4.1 Already RULED and never BUILT — these are work, not questions.
      Check the business rules before asking me anything: re-asking a
      settled question turns our gap into my new requirement.
  4.2 Genuinely open — each in plain English with a CONCRETE WORKED FIGURE,
      never as an ID for me to go and look up. Give a recommendation where
      you have one, and say it is a recommendation.
  4.3 Questions already on file that touch this work.

SECTION 5 — TASKS AND IMPLEMENTATION PLAN
  · Waves, logically grouped, each with its tasks numbered.
  · State for each wave what blocks it and what it unblocks.
  · A dependency table: which can start now, which wait on a ruling.
  · Say which single wave to build if only one gets built, and why.

STANDING PRODUCT RULES — honour these in every analysis and every plan
  · ONE import rail. Every bulk load — premises, units, meters, assets,
    accounts, readings, anything — runs on the shared five-stage Tailwind
    workflow (Extract · Transform · Validate · Load · Result), the same
    code for every target. Never design a second wizard; if the subject
    still has its own, the plan must retire it in one named commit.
  · The write mode — Insert new only · Insert & update, and there is no
    third (CR-042, PO 2026-08-27: "replace option is not required") — is
    chosen at STEP 1, because it decides what the file MEANS. It stays
    revisable up to the commit, where it is STATED and never re-offered
    (DEF-770). It is a premise, not a confirmation. One control serves
    every import: components/workflow/WriteModeChoice (BR-MET-210).
  · Committed financial and read data is immutable. "Update" and
    "replace" on such data mean SUPERSEDE as a correction — a new row
    with a reason, the old one visible forever — never an edit in place.
  · Detail views open as full PAGES, never side panels or drawers.
  · Support every metered utility service and every rate type — Flat,
    Tiered, Time-of-use, Demand, Seasonal — and state what each one needs
    from the subject. Readings and their kin are uploaded per CYCLE.
  · The read-method vocabulary is Manual · Walk-by · AMI · AMR · Mobile,
    and the method travels on the ROW (inheriting the batch's choice
    unless the row overrides), so a half-AMI, half-walked cycle is sayable.
  · Sub-meters and devices are handled explicitly or raised as an open
    question — never silently assumed to be ordinary meters.
  · UI follows the binding conventions (B14): Tailwind utilities, no new
    stylesheet classes, one table type, consistency everywhere.

RULES THROUGHOUT
  · Plain English. No IDs as the primary way of saying anything — a rule
    and its worked number, every time.
  · Never answer an open question by choosing a value. Build to the
    boundary and stop.
  · Count things and give the number. "Two of ten services configured"
    beats "some services are missing configuration".
  · If I said something in chat that changes the analysis, fold it in and
    say what changed.
