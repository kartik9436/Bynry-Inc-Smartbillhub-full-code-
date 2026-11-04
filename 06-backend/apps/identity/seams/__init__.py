"""identity → other-module SEAMS — one READ-ONLY file per module.

The shape `apps/work/seams/` established and `apps/portal/seams/` repeated:
every cross-module read identity makes goes through one file here and nowhere
else, each file resolves the owning module at CALL time, and no public name
here starts with `create_`, `set_`, `update_`, `delete_` or `post_`, because
nothing here writes.

Today there is one: `audit_seam`, which reads the Security tab's own change
history back onto the Security tab (the approved redesign of 2026-09-29).

⚠ **THE POINT OF THE SEAM IS THAT IDENTITY NEVER QUERIES `audit_log`.** That
table is monthly RANGE-partitioned, RLS `FORCE`d with a `WITH CHECK`, and
bounded by a retention floor that only `apps/audit/selectors.py` knows about
(`BR-AUD-013`). A second reader in identity would be a second definition of
what an audit query MEANS, free to drift — and the drift would be invisible,
because both readers would keep passing their own tests. Hard-won law 5's
shape for a query rather than for a file.
"""
