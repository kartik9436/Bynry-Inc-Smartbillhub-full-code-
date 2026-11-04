# Module — customers

Billing accounts at units: move-in/move-out, status lifecycle, autopay, deposits, credit tier.

**Owns (B2):** accounts, contacts, addresses, service_agreements
**Screens:** S17–S24 Accounts list/detail/wizards
**Boundary rule (B1):** no other module writes this module's tables; cross-module reads via service functions only.

**PO rulings of 2026-08-12 that move this module** (each in `02-business-rules.md` with its worked figure): a **missed instalment lifts the dunning pause immediately** — PE-13's **$36.22** unpaid on 1 Oct, chasing resumes 2 Oct, no grace (BR-CUS-043) · a **write-off closes a payment plan**, and the product supplies the mechanism and the report, never the decision — a **$267.30** plan with only its **$50.00** down payment (BR-CUS-044) · a cutover row carrying the **retired plan column imports, the column is not applied, and the row reports what was discarded** — row 412, *"plan C1 ignored — this unit is on RES-STD"* (BR-CUS-046) · a **re-imported cutover file matches on something IN THE FILE**, never on an id the system minted (BR-CUS-047) · a customer owing on **another account is offset first** — **$57.13** credit against **$948.20** overdue pays nothing (BR-CUS-054) · **THE MID-PLAN DEPOSIT DIFFERENTIAL IS GONE** — the deposit settles only at closure, so neither **−$18.50** nor **−$68.50** is ever shown, and BR-CUS-042 and BR-CUS-062's differential clauses are both SUPERSEDED.
