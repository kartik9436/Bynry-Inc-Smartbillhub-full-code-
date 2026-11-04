"""One file per module integrations hands to or reads from (CR-069 §11).

A seam is READ-ONLY unless the neighbour's own published callable writes: this
module owns five tables and writes nothing of anyone else's. Each file here
resolves the neighbour's callable AT CALL TIME by name — the idiom
`apps/notifications/provider_seam.py`, `apps/tenancy/seams.py` and
`apps/metering/seams.py` all use — so a neighbour that has not published one
yet answers `None` and the caller says so honestly rather than inventing an
answer (DEF-075's rule).
"""
