# Runbook — Monthly Billing Run
The money moment. Operator flow is S29–S31.3; this is the operational envelope around it.
Pre-checks: cycle reads imported + validated (S28), estimation review done, tariff versions effective-dated, prior run closed.
Execution: run is an idempotent async job (unique key: tenant+cycle+period). Target < 5 min for ~1,100 accounts (B6).
Failure: job is resumable; partial invoice sets stay in draft — drafts are never delivered.
Post: summary + compliance capture, delivery (print/email/SMS), spot-check n≥5 bills vs golden expectations, ledger postings balanced.
Correction path: issued bills are immutable — corrections via credit note / rebill (S30 Bill correction), never edit.
