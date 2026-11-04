# T4-13 — Autopay enroll → cancel (x = no intents → y = capture-intents on every issue → intents stop)

---
id: T4-13
tier: 4
rules: [BR-PAY-015, BR-PAY-034, BR-CUS-059, BR-PAY-021, BR-BIL-004]
stories: [US-PAY-024, US-CUS-009, US-BIL-005, US-PAY-001]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = account not enrolled in autopay (bill issues produce no intent); y = enrolled — every bill issue records a CAPTURE-INTENT dated the due date (v1 is capture-only per BR-CUS-059/BR-PAY-015: no money moves until rails land in W7, staff record the actual payment); then cancel — subsequent issues stop producing intents. The boundary matters because the intent is an operational promise surfaced on S32/S33: enrolling must make it appear on the NEXT issue, cancelling must stop it on the NEXT issue, and neither change may touch existing intents, recorded payments, or issued bills.

**Fixture.** Tenant brazos-bend · ACC-1042, flat shape · Aug bill **$97.41**, due date = bill date + 21 cycle due-days (money-triples row `flat,cycle,full`).

**Fixture amendment (2026-08-22, CR-014 / DEF-556).** The flat account is **ACC-2042** (ACC-1042 is the signed WE-1 cast, billed 247.87 in July). The Aug bill figure, the shape and the due-date law (bill date + 21 cycle due-days → due 2026-09-22) are unchanged and are seeded for real by `seed_journey_fixture.py` (issued through the five-phase run, proved = 97.41).

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Clerk ENROLLS the account in autopay: enrollment + payment method stored | Capture-only state: enrollment + method columns populated; nothing charges, nothing schedules retroactively for already-issued bills | account header/overview shows the autopay pill (US-CUS-009); audit row; NO intent exists yet (intents are minted at issue, not at enrollment) | BR-CUS-059 · BR-PAY-015 |
| 2 | Aug cycle bill issues ($97.41) | Issue records ONE capture-intent row: amount 97.41, dated the DUE DATE | intent visible on S32/S33 ("autopay scheduled"); no payment row, no ledger movement, no AR change from the intent itself | BR-PAY-015 |
| 3 | Money actually arrives; Clerk records the payment (posting + clearing dates, both) | Normal payment lifecycle: allocation per BR-PAY-010; the intent's "fulfilled" state is COMPUTED — the matching recorded payment renders it, no stored transition in v1 | intent renders fulfilled; receipt auto-queued; balanced JE via posting service; audit | BR-PAY-034 · BR-PAY-021 |
| 4 | Clerk CANCELS the enrollment | Enrollment/method flags clear; nothing else moves | audit row with before/after; autopay pill gone; existing intent rows and payments untouched | BR-CUS-059 |
| 5 | Sep cycle bill issues | Issue records **NO intent** — enrollment absent at issue time | S32/S33 show no scheduled autopay for Sep; Sep bill otherwise identical in shape; dunning/collections treat Sep normally if unpaid | BR-PAY-015 |
| 6 | **INVARIANCE** — what must NOT have changed | Enroll/cancel are pure preference transitions: zero effect on issued bills, recorded payments, allocations, or the ledger at every step; the Aug intent row survives the cancellation as history | issued invoices byte-identical; payments append-only; intent rows never deleted or edited; both preference changes fully audited | BR-BIL-004 · BR-PAY-002 · hard rule 4 |
