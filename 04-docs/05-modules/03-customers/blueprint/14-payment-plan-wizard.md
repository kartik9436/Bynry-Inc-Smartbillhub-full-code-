# 14 · Payment plan wizard EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 134–135. Extracted text, verbatim — **derived, do not edit.**

**3,433 characters over 2 page(s).**

---

```
Confirm · /brazosbend/accounts/a-10432/change-plan?step=3 · Commits to POST /accounts/{id}/plan-changes · preview at /plan-changes/preview
How you get here One door: the S21 icon rail's ⇄  Change plan (AccountDetailPage.tsx:581), live only on an account that currently holds its unit.
Primary action Confirm ✓
Walked Not walked.
⚠  Step 8 constraint Not on route-b-migrated.txt — legacy CSS.
Rules BR-CUS-041 · 042 (superseded) · 062 · BR-RAT-030
14 Payment plan wizard EXISTS BEHIND
/:tenant/accounts/:accountId/payment-plan  ·  S24  ·  three steps
The question: "They can't pay $612 today but they can pay $100 a month. Write it
down so nobody cuts them off."
All 3 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
▦
▤
⚙
←  Back Confirm ✓
/brazosbend/accounts/a-11488/payment-plan?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Account A-11488 / Payment plan ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
←  Account A-11488
PAYMENT PLAN
Terms
Step 1 of 3 · Terms
Save & exit
NO STEPPER IS RENDERED
The three steps exist in the code and no rail is drawn for them, so the running screen shows only the form — only the form and a disabled Continue. The three names below are the code’s model of this flow, kept here
because a build would start from them.
The steps as the code models them: Terms · Schedule · Agreement
Balance to spread *
$612.75
Down payment
$112.75
The arrears position, not the current bill.
The current bill is still due alongside the plan — the screen says so.
Terms · /brazosbend/accounts/a-11488/payment-plan?step=1
Schedule · /brazosbend/accounts/a-11488/payment-plan?step=2
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
✦
▩
▦
▤
⚙
Instalments *
5
Cadence
Monthly ▼
First due *
01/10/2026 📅
Take by autopay
✓ Suspend late fees while the plan runs
✓ Suspend disconnect while the plan runs
Continue →
/brazosbend/accounts/a-11488/payment-plan?step=2
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
Account A-11488 / Payment plan ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Account A-11488
PAYMENT PLAN
The schedule
Step 2 of 3 · Schedule
Save & exit
NO STEPPER IS RENDERED
The three steps exist in the code and no rail is drawn for them, so the running screen shows only the form — only the form and a disabled Continue. The three names below are the code’s model of this flow, kept here
because a build would start from them.
The steps as the code models them: Terms · Schedule · Agreement
# DUE AMOUNT LEFT
1 01/10 $100.00 $400.00
2 01/11 $100.00 $300.00
3 01/12 $100.00 $200.00
4 01/01 $100.00 $100.00
5 01/02 $100.00 $0.00
The remainder lands on the FINAL row, never spread across the others.
Progress 0 of 5 paid
←  Back Recalculate Continue →
/brazosbend/accounts/a-11488/payment-plan?step=3
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Account A-11488 / Payment plan ⚲  Search accounts, premises, meters… ⚑ ?
▦
←  Account A-11488
PAYMENT PLAN
Theagreement
Save & exit
```
