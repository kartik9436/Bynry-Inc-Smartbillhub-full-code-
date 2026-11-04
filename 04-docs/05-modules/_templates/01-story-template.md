---
id: US-XXX-000
epic: EP-XXX-00
module: <module>
screens: [S0]
wave: 0
status: draft            # draft | ready | blocked | done
blocked_by: []           # OQ-IDs
depends_on: []           # upstream US-IDs whose contracts this story consumes — READ THEM BEFORE CODING
journeys: []             # J-IDs (08-qa/01-e2e/journeys/) this story belongs to
rules: []                # BR-IDs referenced
golden_tests: []         # GT-IDs or []
finance_calc: none       # none | proposed | confirmed
---
### US-XXX-000 — <Title>

**1 · Details** — As a <role>, I want <capability>, so that <outcome>. Flow/entry/exit. Screens cited.

**2 · Business Rules** — table: BR-ID | statement | status (CONFIRMED cite source / PROPOSED cite derivation / OPEN cite OQ).

**3 · Test Cases** — table: TC-# | scenario | expected. ≥1 negative; +1 tenant-isolation TC if tenant data.

**4 · Test Data** — concrete, realistic values (never "foo").

**5 · Data Fields / Mapping** — table: field | screen | spec source (A2 § / prototype-extracted / GAP) | DB target (B2 table.column) | type/unit | origin (user-input / system-derived / reference-data / integration / computed-display) | validation.

**6 · Acceptance** — Given/When/Then, demoable.

**7 · Finance Calculation** — formula + worked example + GT ref, or "N/A".

**8 · Open Questions** — table: OQ-ID | question | blocks | routed to | status — or "None".
