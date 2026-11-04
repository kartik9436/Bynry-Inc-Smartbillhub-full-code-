# J4 — Collections

---
id: J4
tier: 1
stories: [US-CUS-015, US-CUS-018, US-BIL-005, US-PAY-001, US-PAY-014]
---

<!-- FRONTMATTER ADDED 2026-08-15 (DEF-102). Not a pure transcription: the step
     table names US-CUS-015 and US-CUS-018 explicitly and uses the WILDCARDS
     US-BIL-** and US-PAY-**. Resolved to US-BIL-005 (the issued bill a
     collection acts on), US-PAY-001 (recording the payment that clears it) and
     US-PAY-014 (the collection sequence engine itself, built 2026-08-15).
     Stated so the choice is reviewable. -->
**Fixture.** (authored 2026-08-22, CR-014) Tenant brazos-bend · the CR-014 flat money cohort (see J2's Fixture): account **ACC-2042** with its issued August bill **97.41 UNPAID** (money-triples `flat,cycle,none`: outstanding 97.41, next late fee **$5.00** floor) · due **Sep 22**. Past-due-ness is evaluated at a journey-chosen date after the due date (BR-TEN-043 — business moments are parameters); the fixture never back-dates a bill into the finance-signed July window to fake overdue-ness (DEF-556).

past-due → late fee → reminder → notices → plan/write-off.
| # | Story | Handoff |
|---|---|---|
| 1 | US-BIL-** late fee (BR-BIL-001/008) | non-taxable fee line on overdue portion after grace |
| 2 | US-PAY-** reminder / US-CUS-015 disconnect notice (A15 tiers, A19 §2) | notice_history appended; medical-hold skipped; certified mail on final tier |
| 3 | US-CUS-018 payment plan / US-PAY-** write-off | plan active on signature → dunning + disconnect paused while current (BR-CUS-043/044) / bad-debt GL + Owner approval + audit |
