# CR-085 lane 1 · The blueprint's rules register R-01 … R-24 — which twelve are not ratified anywhere

**Source:** `05-prototype/SMARTBillHub Customer Portal Blueprint.pdf`, md5
`1bf92dd196920750e9360a9e8ece501b`, appendix table **A · Every rule this document states**,
pages 115–116. Read with `10-scripts/pdf/pdf_text.py` and de-joined (the text layer glues
words with `U+FFFE`, so `Standards as A` arrives as `StandardsasA` and a naive match reports
false absences).

The register's own `HOME` column is the finding. **Twelve of the twenty-four are marked
`NO HOME` — "stated only here"** — meaning the blueprint is the only place in the product's
record where the rule appears. The other twelve are `INHERITED` from B14, `CLAUDE.md` or a PO
ruling, or `EXTENDS` one of those.

---

## The twelve that are stated only in the blueprint

Verbatim, in register order, with the block each sits in and the register's own note.

| id | the rule as stated | block | the register's note |
|---|---|---|---|
| **R-04** | *"No emoji as a section marker."* | Standards A | Stated only here |
| **R-05** | *"Amount due and due date appear in the same place on every screen."* | Standards B | Stated only here |
| **R-06** | *"Never ask a customer to compute — show the difference, not two numbers."* | Standards B | Stated only here |
| **R-07** | *"One filled button per screen."* | Standards B | Stated only here |
| **R-09** | *"Never make a customer remember an account number to do something."* | Standards B | Stated only here |
| **R-10** | *"Bad news never appears without the way out beside it."* | Standards B | Stated only here, **"and it is the strongest rule on the page"** |
| **R-13** | *"A route existing is not a door."* | Standards E | Stated only here, **"and it is the finding that produced this whole block. Nothing in the repo states it"** |
| **R-15** | *"Position, order and wording never move; a back-link sits under the bar, never inside it."* | Standards D | Stated only here |
| **R-18** | *"Assistance is a first-class path, not a page behind a sign-in."* | Standards C | Stated only here |
| **R-19** | *"The portal is a second channel; every bill is printed regardless."* | Standards C | Stated only here |
| **R-22** | *"Three states — loading, empty, failed — can never render as the same picture."* | Masthead | Stated only here |
| **R-23** | *"No sentence states a fact it does not derive."* | Masthead | Stated only here, **"with its own evidence: twenty-three of thirty-eight were wrong"** |

**That is exactly twelve, and the register's claim checks out.** Counted from the same table,
the other twelve are R-01 (EXTENDS the staff icon rule), R-02, R-03 (B14), R-08 (EXTENDS B14
rule 32), R-11 (PO ruling 2026-09-08, the bars wave), R-12 (B14 rule 31), R-14 (PO ruling
2026-09-08), R-16 (`CLAUDE.md` hard rule 2), R-17 (hard rule 3), R-20 (B14 rule 35), R-21
(EXTENDS rule 35) and R-24 (the portal's phone-width rule).

---

## One of the twelve has since acquired a home, and the register is stale about it

**R-13 — *a route existing is not a door*.** The register says *"Nothing in the repo states
it."* That was true when the blueprint was written and is **no longer true**:

* `12-governance/02-decision-log.md`, section dated **2026-09-08** — *"THE PO ASKED WHETHER
  THE DOORS WERE RIGHT, AND FIVE OF NINE DRAWINGS WERE WRONG"* — states it in those words
  twice, with the reasoning;
* `07-frontend/src/portal/routing/everyRouteHasADoor.test.ts` enforces the cheap half of it
  over all fifty routes, and its header states honestly which half it cannot enforce.

**It is still not a numbered B14 rule**, so a lane reading B14 alone still will not meet it.

Grepped for the distinctive phrase of each of the other eleven across `04-docs/`,
`12-governance/` and `07-frontend/src/`: **none returns a ratified home.** R-05's phrase
appears in the decision log in another context and R-07's wording appears in three
*conformance* notes as a convention a lane applied — neither is a ratification.

---

## Why this matters more than a tidy-up

**A rule with no home is a rule the next lane cannot obey.** Two of the twelve are not style
preferences:

* **R-10** — *bad news never appears without the way out beside it* — is the rule
  `DEF-CWP-4143` breaches today (*"THE OVERDUE SCREEN OFFERS NO WAY TO PAY"*, open, high).
  The defect was found by a person looking at the screen. Had R-10 been a numbered rule,
  the screen would have been built to it.
* **R-22** — *loading, empty and failed can never render as the same picture* — is the one
  rule that would have caught the shared stack's own state: on `brazosbend` today every
  signed-in portal address renders the same `FailedWithRetry` card whether the read failed,
  the session expired or the tenant was never switched on.

**Ratifying them is a PO act, not ours.** What is ours is to say which twelve they are and to
stop citing the blueprint as though it were law: `05-prototype/…Blueprint.pdf` is a drawing,
and B14 rule 37 is explicit that *a figure drawn in a wireframe is an illustration, never a
fact to build to*. A **rule** drawn in a wireframe deck is in the same position.

---

## Two warnings about reading this PDF, both paid for already

1. **It is truncated at the tail.** Page 129 is a table cut off mid-row. Anything read from
   the last page is incomplete by construction.
2. **Its text layer joins words with `U+FFFE` (and soft hyphens).** `How￾you-get-here`,
   `CPB￾09`, `Standardsas A`. **Strip `￾` and `­` before matching or you get false
   absences** — an earlier quick parse of this same table reported two of fourteen sections
   missing and both were present in full, and ran two register rows together.
