# A10 — Mock vs. Real

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Dummy data vs real constants; designed vs stubbed; faked.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


**Illustrative dummy (ignore):** all customer names (Miller/Chen/Ridge Coffee/Northwind…), account numbers, meter numbers, specific $ amounts, dates, counts (1,124 customers, 184 accounts), sample GL numbers.
**Real business constants (preserve):** package prices **Starter $1,000 / Growth $5,000 / Scale $8,000 per month**; size tiers **≤300 / 300–1,000 / 1,000–3,000 accounts**; **14-day trial**; tax **8.25%** (6.25/1.00/2.00/0.20 split); **late fee $5 or 1.5%**; **NSF $30**, **reconnect $45** (confirm as real vs sample); aging buckets; status labels; service list (Electric/Water/Gas/Sewer/Trash/Broadband); charge-code mnemonics (CONN/DISC/NSF/LATE/TAMPER/SVCCALL/DEPO-R).
**Fully designed:** Accounts, Account detail, Reads, Billing run, Payments, Finance, Reports, Setup wizard.
**Stubbed / partial:** Settings sub-tabs, Routes/Cycles tabs, Dashboard drill-downs, User menu (S48).
**Faked for demo (need real backend):** every rule/rating calc, CSV/lockbox/bank imports, QuickBooks/Xero sync, email/SMS/print delivery, e-signature, autopay, proration math.

---

## Addendum — fee constants settled (2026-08-08, from B4)
NSF $30 and reconnect $45 are **samples only** (CONFIRMED): real values are tenant-configured charge codes; never hardcode. Late fee $5/1.5% and the 8.25% TX split remain real constants per B4.
