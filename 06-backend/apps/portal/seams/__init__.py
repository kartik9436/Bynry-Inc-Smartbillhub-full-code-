"""The portal READS other modules through these files and through nothing
else (BR-CWP-012 — no second copy of billing, payments, ledger, metering,
rating, customers, notifications, documents or audit). One file per module
read from; none of them writes (G81 refuses an ORM write anywhere in here)."""
