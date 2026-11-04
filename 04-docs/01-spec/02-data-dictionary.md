# A2 — Field-Level Data Dictionary

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. THE keystone document — every field on every screen.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


> Enumerated for the high-value transactional screens. Screens marked stub in Doc 9 have `UNKNOWN` fields called out. Currency throughout is USD `$` with **2 decimals**; usage uses **kWh** (electric) and **kgal** (water, thousand gallons) — see currency/unit flags below.

### Setup wizard (S4–S6)
| Screen | Label | Field name | Type | Req | Edit | Default | Validation | Format | Options / formula | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| S4 | Utility name | utility_name | text | Y | edit | — | UNKNOWN | — | — | |
| S4 | Your web address | subdomain | text | Y | edit | — | UNKNOWN (uniqueness, charset) | `<sub>.smartbillhub.app` | — | tenant subdomain |
| S4 | State | state | select | Y | edit | Texas | — | — | Texas, California, Florida, New York, Other | list is illustrative — needs all US states |
| S4 | Services | services[] | multiselect | Y | edit | Electric, Water | ≥1 | — | Electric, Water, Gas, Sewer, Trash, Broadband | prototype earlier also referenced "Waste" |
| S5 | Rate style to start with | initial_rate_style | radio | Y | edit | Flat rate | — | — | Flat rate, Tiered / inclining, Time-of-use | |
| S5 | Billing cycle | billing_cycle | select | Y | edit | Monthly | — | — | Monthly, Bi-monthly, Quarterly | |
| S5 | Bill on | bill_day | select | Y | edit | 1st of the month | — | — | 1st, 15th, Last day | |
| S5 | Tax region | tax_region | select | Y | edit | Texas · State + Local (8.25%) | — | % | Texas 8.25%, California, No tax | **8.25% is a real constant (Doc 9)** |
| S5 | Currency | currency | select | Y | edit | USD ($) | — | — | USD ($), CAD ($) | |
| S5 | Load standard charge codes & lookup tables | load_defaults | checkbox | N | edit | on | — | — | — | seeds lookup tables |
| S6 | Your name | owner_name | text | Y | edit | — | — | — | — | |
| S6 | Work email | owner_email | email | Y | edit | — | email | — | — | becomes Owner login |
| S6 | Password | password | password | Y | edit | — | UNKNOWN (strength policy) | — | — | |
| S6 | Mobile (for alerts) | owner_mobile | tel | N | edit | — | UNKNOWN | — | — | |

### Account detail — Record payment modal (S22)
| Screen | Label | Field | Type | Req | Edit | Default | Validation | Format | Options / formula | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| S22 | Current balance | balance | money | — | read | — | — | `$0.00` | — | shown $247.30 sample |
| S22 | Amount | amount | money | Y | edit | =balance | > 0 | `$0.00` | — | |
| S22 | Payment date | pay_date | date | Y | edit | today | — | `Mon D, YYYY` | — | timezone UNKNOWN |
| S22 | Method | method | radio | Y | edit | ACH | — | — | ACH, Card, Check, Cash, Lockbox | |
| S22 | Confirmation / check # | confirmation | text | N | edit | — | — | — | — | |
| S22 | Apply to | apply_to | select | Y | edit | oldest open bill | — | — | Oldest open bill, Specific bill, Carry as credit, Split | |
| S22 | Memo | memo | text | N | edit | — | — | — | — | |

### Account detail — Adjust modal (S22)
| S22 | Direction | direction | radio | Y | edit | Credit | — | — | Credit (reduces balance), Debit (increases balance) | |
| S22 | Amount | amount | money | Y | edit | — | > 0 | `$0.00` | — | |
| S22 | Reason code | reason | select | Y | edit | Billing error correction | — | — | Billing error correction, Meter error, Leak credit, Goodwill credit, Dispute resolution, Waive late fee | |
| S22 | Apply to bill | bill_ref | select | Y | edit | latest | — | — | latest bill, Open balance | |
| S22 | GL account | gl_account | select | Y | edit | 4100 Electric Revenue | — | — | 4100 Electric Revenue, 4200 Water Revenue, 4910 Penalties | GL list is illustrative subset |
| S22 | Requires supervisor approval | needs_approval | checkbox | — | edit | on | — | — | — | Owner/Finance only |

### Payments — Outstandings table (S34)
| S34 | (select) | selected | checkbox | — | edit | — | — | — | — | bulk |
| S34 | # | rank | int | — | computed | — | — | — | sort by balance desc | |
| S34 | Account | account_no | text | — | read | — | — | `A-#####` | — | |
| S34 | Customer | customer_name | text | — | read | — | — | — | — | |
| S34 | Days late | days_late | int | — | computed | — | — | days | UNKNOWN exact base date | |
| S34 | Age | age_bucket | enum | — | computed | — | — | — | 1–30, 31–60, 61–90, 90+ | derived from days_late |
| S34 | Balance | balance | money | — | read | — | — | `$0.00` | — | |
| S34 | Last payment | last_payment_date | date | — | read | — | — | `Mon D, YYYY` | — | |
| S34 | Notice history | notice_history | text | — | read | — | — | — | — | e.g. "1st + 2nd sent" |
| S34 | Autopay | autopay | enum | — | read | — | — | — | —, Failed | UNKNOWN full set |
| S34 | Payment plan | payment_plan | enum | — | read | None | — | — | None, Active | |
| S34 | Action | row_action | select | — | edit | — | — | — | Send reminder, Send disconnect, Send 2nd notice, Send final notice, Schedule disconnect, Payment plan, Record payment, Retry autopay, Update method, Field visit, Write off | varies per row |

### Run Bills Step 3 — exception cases (S31.3)
Columns vary per case; all cases share row checkbox + per-row action select + bulk toolbar. Enumerated action options:
- **Used a lot more (high):** Bill it anyway / Look into this / Cap at 2× average
- **No usage:** Bill base only (vacant) / Check meter / Skip this month
- **Estimated:** Keep estimate / Override / Field visit
- **Owes a lot:** Bill anyway / Offer payment plan / Hold bill
- **Way past due:** Add 2nd disconnect notice / Add final notice / Schedule disconnect / Offer payment plan
- **Late fee:** Apply fee / Waive (first-time) / Waive
- **Extra charges:** Apply / Waive / Defer / Investigate first

`UNKNOWN — exact numeric thresholds for high (shown 2×/"312%"), low (<20%), day-threshold (shown 20–45 days), and estimation method (shown "trailing-3 / 3-cycle average"). Confirm the real rule engine values.`

### Remaining screens
`UNKNOWN — full field dictionary for Settings sub-tabs (S8), Routes/Cycles (S26/S27), New Plan/Rate wizards internals (S10/S11), and Dashboard KPI definitions (S7). These are designed at varying fidelity; a human must confirm each field, its validation, and computed formulas before build.`

**Currency/format consistency flags:**
- Money is consistently `$` 2-dp across screens observed. ✅
- Water usage appears as **kgal** (thousand gallons) in Reads/Billing but tables also show raw meter counts (e.g. 412,000 → 438,240). `UNKNOWN — is billed water unit kgal or gallons? confirm meter register units vs billed units.`
- Electric usage in **kWh**; some meters carry a **meter factor / multiplier (×10)**. Confirm multiplier applies before or after tier evaluation.
- Dates shown as `Mon D, YYYY` and `Mon D · HH:MM`; **timezone is never stated → UNKNOWN.**

---


## Addendum — Asset lookups (2026-08-07 r4)
New lookup tables (Settings → Lookup tables): **Asset types** (meter, net meter, sub-meter, backflow, communication, PV/solar, battery, EV charger, transformer, generator) and **Asset statuses** (inventory, active, needs repair, in repair, retired). Manufacturer/model is a free-text field (not a lookup). Existing **Meter types** (AMI/AMR/walk-by) reused for read method.
