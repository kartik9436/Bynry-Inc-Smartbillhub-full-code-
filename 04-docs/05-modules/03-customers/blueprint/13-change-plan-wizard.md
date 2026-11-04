# 13 · Change plan wizard EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 132–133. Extracted text, verbatim — **derived, do not edit.**

**3,701 characters over 2 page(s).**

---

```
Money on an account
Three ways money moves on an account that is not a bill: a payment gets
recorded, the plan changes, or the arrears get spread.
13 Change plan wizard EXISTS BEHIND
/:tenant/accounts/:accountId/change-plan  ·  S23  ·  three steps
The question: "They want the bigger tariff. What does it cost them, and from when?"
All 3 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
Plan · /brazosbend/accounts/a-10432/change-plan?step=1
/brazosbend/accounts/a-10432/change-plan?step=1
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
Account A-10432 / Change plan ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Account A-10432
CHANGE PLAN
Pick a plan
Step 1 of 3 · Plan
Save & exit
NO STEPPER IS RENDERED
The three steps exist in the code and no rail is drawn for them, so the running screen shows only the form — only the form and a disabled Continue. The three names below are the code’s model of this flow, kept here
because a build would start from them.
The steps as the code models them: Plan · Effective · Confirm
New plan
Choose a published plan ▼
I understand this drops Water
Current plan Residential Standard · current
Current base $30.50 / mo
Only plans that cover this account's services are offered.
A plan that drops a service cannot continue without this acknowledgement.
Continue →
/brazosbend/accounts/a-10432/change-plan?step=2
SMARTBillHub ☰
BB Brazos Bend Utilities
Account A-10432 / Change plan ⚲  Search accounts, premises, meters… ⚑ ?
←  Account A-10432
Effective · /brazosbend/accounts/a-10432/change-plan?step=2
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
CHANGE PLAN
When does it take effect?
Step 2 of 3 · Effective
Save & exit
NO STEPPER IS RENDERED
The three steps exist in the code and no rail is drawn for them, so the running screen shows only the form — only the form and a disabled Continue. The three names below are the code’s model of this flow, kept here
because a build would start from them.
The steps as the code models them: Plan · Effective · Confirm
Effective
Immediately
Next cycle
A date I choose
Effective on *
01/10/2026 📅
PREVIEW
Current base $30.50
New base $42.00
Base delta +$11.50
Net impact +$11.50 / mo
DEPOSIT DIFFERENTIAL
The deposit is not worked out again in this version. The amount set at move-in stands.
Computed by the server.
←  Back Show preview →
/brazosbend/accounts/a-10432/change-plan?step=3
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
Account A-10432 / Change plan ⚲  Search accounts, premises, meters… ⚑ ?
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
←  Account A-10432
CHANGE PLAN
Confirm the change
Step 3 of 3 · Confirm
Save & exit
NO STEPPER IS RENDERED
The three steps exist in the code and no rail is drawn for them, so the running screen shows only the form — only the form and a disabled Continue. The three names below are the code’s model of this flow, kept here
because a build would start from them.
The steps as the code models them: Plan · Effective · Confirm
Reason
Customer moved to a larger tariff
✓ Notify the customer
Log eligibility proof
Eligibility is advisory — it records what was checked, it does not block.
History row who · when · from →  to · reason · source
```
