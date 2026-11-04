# ── Trace ──────────────────────────────────────────────
# Story:   CR-112 — the City's address register becomes the source of addresses.
#          This file is the MATCH and the CLASSIFY: our rows beside their
#          snapshot, in our own database, with no further calls out.
# Rules:   BR-INT-073 (the match and the re-derivation) · BR-INT-074 (preview
#          writes nothing) · BR-MET-1173 (the keys live in their own columns) ·
#          PO rulings 2026-09-17 nos. 4, 6, 7, 8, 9 · hard rule 8 / BR-MET-1161
#          (an address is stored on `premises`; a unit refines it by LABEL) ·
#          BR-MET-1162 (a unit may carry its own point) · hard-won law 7
# Tests:   06-backend/tests/test_cr112_gis_match.py
# Impacts: apps/integrations/gis_parcels.py (the run that drives this) ·
#          apps/integrations/gis_layer.py (the snapshot it is handed)
# ───────────────────────────────────────────────────────
"""Their snapshot beside our register — matched and classified, nothing written.

⚠ **EVERY FUNCTION IN THIS FILE IS PURE, AND THAT IS THE DESIGN RATHER THAN A
CONVENIENCE.** They take our rows as dicts and their rows as a `Snapshot`, and
return decisions. Nothing here opens a transaction, calls the City or touches a
model. It means `preview` and `apply` can run **the same code** and differ only
in whether the caller acts on what came back — which is `BR-RBS-003`'s rule for
runbooks applied to this run, and the reason a preview cannot drift from the
thing it previews.

THE FOUR JOBS, IN THE ORDER THE RUN DOES THEM
-----------------------------------------------
1. **MATCH** the rows that have no key yet. One clean candidate → take the key.
   More than one, or none → queue with every candidate and store nothing.
2. **RE-DERIVE** the rows whose key no longer resolves. Ruling 7: treat them as
   keyless and match by address. One clean match applies the new key **and keeps
   what the old one was**; anything else queues and **the old key STAYS**.
3. **RECONCILE** every row that has a key, field by field, against the same
   snapshot. Unchanged fields are not written at all.
4. **DISPOSE** — look up what the utility said to do with each difference class.
   **The default is NEVER TOUCH** (ruling 9).

⚠ **RULING 8 IS AN ABSENCE AND IS IMPLEMENTED AS ONE.** A City address we have
no premises for is *"c) ignore"* — not a work item, not a queue row, not a
suggestion to create one. It is COUNTED in the run report, because a run that
examined 70,000 rows and one that examined 700 must not read the same
(hard-won law 7), and that count is the only trace it leaves.

⚠ **THRASH IS OUR BUG, NOT THE CITY'S, AND IT IS COUNTED SO SOMEBODY SEES IT.**
A key that changes on repeated runs means our MATCHING is wrong — the City does
not renumber a parcel nightly. `thrash_candidates` reports every row whose key
this run would change and which already carries a `gis_parcel_id_was`, i.e. one
we have changed before. A rising number there is a defect in this file and the
run report says so in those words, because the alternative is a register that
churns quietly for months.

WHAT WOULD MAKE THIS MATCH WRONGLY (hard-won law 7, habit 2)
---------------------------------------------------------------
* **A blank street on both sides matching everything.** Two premises with no
  address would have street key `""` and would match each other and every
  City row with a blank street. `_index_by` DROPS blank keys, so a row with no
  address matches nothing and queues, which is the safe direction.
* **A postcode difference on every row.** The City publishes ZIP+4 and a utility
  holds five digits. `normalise_postcode` compares the first five only.
* **Exactly one candidate that is one of two.** A building matched on street
  alone, where two postcodes share a street name, would be *one clean match* on
  a filtered set that was never complete. Premises match on **street AND
  postcode together**, and a premises with no postcode is matched on street
  alone only when that street key is unique in the whole snapshot.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from apps.integrations.gis_layer import (
    ParcelRow,
    Snapshot,
    normalise_postcode,
    normalise_street,
    normalise_unit,
)

# ── the difference classes `RB-120` names, and what each one MEANS ───────────
#: Both sides hold a value and they differ.
CONFLICT = "conflict"
#: They hold one and we hold nothing.
NEW_VALUE = "new_value"
#: We hold one and they hold nothing.
BLANK_THEIRS = "blank_theirs"
#: We hold nothing and they hold nothing — never reported; listed so the set is
#: complete and a reader does not go looking for it.
BLANK_OURS = "blank_ours"
#: Two of our premises carry one parcel key. A real thing a City does (a duplex
#: split into two properties on one lot) and a person's judgment, never ours.
TWO_PREMISES_ONE_PARCEL = "two_premises_one_parcel"
#: One premises matched two parcels in the snapshot.
ONE_PREMISES_TWO_PARCELS = "one_premises_two_parcels"
#: Our row has a key and the snapshot does not contain it.
UNMATCHED = "unmatched"

DIFFERENCE_CLASSES = (
    NEW_VALUE,
    BLANK_OURS,
    BLANK_THEIRS,
    CONFLICT,
    TWO_PREMISES_ONE_PARCEL,
    ONE_PREMISES_TWO_PARCELS,
    UNMATCHED,
)

#: ⚠ **THE DEFAULT, AND IT IS THE RULING RATHER THAN A CAUTIOUS CHOICE.**
#: PO 2026-09-17, ruling 9: *"c) never touch by default"*. A field with no
#: disposition recorded against it is NEVER written, whatever the class.
NEVER_TOUCH = "never_touch"
APPLY = "apply"
QUEUE = "queue"
DISPOSITIONS = (NEVER_TOUCH, APPLY, QUEUE)

#: The premises fields this run can compare at all. `gis_status` is on the list
#: because it is a fact ABOUT the City record; the three that decide tax are not
#: on it anywhere in this product (`RBR-17` / `BR-INT-051` 🔒) and this run has
#: no opinion about them.
PREMISES_FIELDS = ("address_line", "city", "state", "postal_code", "lat", "lng", "gis_status")
UNIT_FIELDS = ("lat", "lng", "gis_status")


# ═══════════════════════════════════════════════════════════════════════════
# The decisions
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class KeyDecision:
    """What this run would do about ONE row's key. A decision, not a write."""

    level: str  # "premises" | "unit"
    row_id: Any
    label: str
    #: "take" — it had none and exactly one candidate matched.
    #: "replace" — its key stopped resolving and exactly one candidate matched.
    #: "queue" — none matched, or more than one did. **Nothing is stored.**
    #: "keep" — its key still resolves; nothing to do.
    action: str
    new_key: str | None = None
    old_key: str | None = None
    #: Every candidate considered, so a queued row shows a person what we saw
    #: rather than only that we gave up (`RB-120`'s *Ours* and *Theirs*).
    candidates: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class FieldDifference:
    """One field, ours and theirs, with the class and what will happen."""

    level: str
    row_id: Any
    label: str
    field_name: str
    ours: Any
    theirs: Any
    difference_class: str
    disposition: str

    @property
    def will_apply(self) -> bool:
        return self.disposition == APPLY and self.difference_class in (NEW_VALUE, CONFLICT)


@dataclass
class MatchReport:
    """Everything one run found. Counts as well as rows — law 7's habit 3.

    ⚠ **A RUN THAT EXAMINED NOTHING AND A RUN THAT FOUND NOTHING WRONG MUST NOT
    READ THE SAME**, so every count here is reported even when it is zero, and
    `city_rows_ignored` exists purely so ruling 8's deliberate silence has a
    number attached to it.
    """

    key_decisions: list[KeyDecision] = field(default_factory=list)
    differences: list[FieldDifference] = field(default_factory=list)
    #: Ruling 8 — a City address we have no premises for. Counted, never queued.
    city_rows_ignored: int = 0
    #: Our rows the snapshot could not answer about at all.
    unmatched_ours: int = 0
    #: Rows whose key this run would change AND which we have already changed
    #: before. **Our matching is wrong, not the City's** — see the module
    #: docstring.
    thrash_candidates: list[str] = field(default_factory=list)
    premises_examined: int = 0
    units_examined: int = 0

    @property
    def to_apply(self) -> list[FieldDifference]:
        return [one for one in self.differences if one.will_apply]

    def headline(self, *, fields_never_touch: int) -> str:
        """The sentence ruling 9 makes necessary.

        ⚠ **THE FIRST RUNS WILL CHANGE NO ADDRESSES AT ALL AND THAT IS
        CORRECT.** They store keys and stamp verified and nothing else, until
        somebody turns a field on in Settings. A report reading *"312
        differences found, 0 applied"* with no explanation is a screen a clerk
        reports as broken, so the reason is part of the sentence.
        """
        found = len(self.differences)
        applied = len(self.to_apply)
        if applied == 0 and fields_never_touch:
            return (
                f"{found} differences found, 0 applied, "
                f"all {fields_never_touch} fields set to never touch"
            )
        return f"{found} differences found, {applied} applied"


# ═══════════════════════════════════════════════════════════════════════════
# Indexing their side
# ═══════════════════════════════════════════════════════════════════════════


def _index_by(rows: Iterable[ParcelRow], key: str) -> dict[str, list[ParcelRow]]:
    """Group their rows by a normalised key. **A BLANK KEY IS DROPPED.**

    ⚠ Without that, two City rows with no street would sit under `""` and match
    every premises that also has no street — *one clean candidate* out of a
    bucket that means *we know nothing about either of these*.
    """
    index: dict[str, list[ParcelRow]] = defaultdict(list)
    for row in rows:
        value = getattr(row, key)
        if value:
            index[value].append(row)
    return dict(index)


@dataclass
class SnapshotIndex:
    """One pass over the snapshot, three ways of asking about it."""

    by_parcel: dict[str, list[ParcelRow]]
    by_point: dict[str, ParcelRow]
    by_street_postcode: dict[str, list[ParcelRow]]
    by_street: dict[str, list[ParcelRow]]

    @classmethod
    def of(cls, snapshot: Snapshot) -> "SnapshotIndex":
        by_parcel: dict[str, list[ParcelRow]] = defaultdict(list)
        by_point: dict[str, ParcelRow] = {}
        by_pair: dict[str, list[ParcelRow]] = defaultdict(list)
        for row in snapshot.rows:
            if row.parcel_id:
                # Compared case-insensitively — `BR-MET-1173` stores the key as
                # the City gives it and never normalises what it writes back.
                by_parcel[row.parcel_id.casefold()].append(row)
            if row.point_id:
                by_point[row.point_id.casefold()] = row
            if row.street_key and row.postcode_key:
                by_pair[f"{row.street_key}|{row.postcode_key}"].append(row)
        return cls(
            by_parcel=dict(by_parcel),
            by_point=by_point,
            by_street_postcode=dict(by_pair),
            by_street=_index_by(snapshot.rows, "street_key"),
        )

    def building_point(self, parcel: str) -> ParcelRow | None:
        """The point whose `Unit` is EMPTY — the BUILDING's own, or nothing.

        ⚠ **RULING 6, AND THE `None` IS THE RULING.** PO 2026-09-17: *"a) leave
        the building's pin blank"*. Never borrow a unit's point, never average
        the units' points. A parcel whose every point carries a unit gives the
        premises no pin, and that is the correct, intended outcome.
        """
        for row in self.by_parcel.get(str(parcel or "").casefold(), ()):
            if row.is_building_point:
                return row
        return None

    def candidates_for(self, street: Any, postcode: Any) -> list[ParcelRow]:
        """Their rows for one of our addresses — street AND postcode together.

        ⚠ **STREET ALONE IS ALLOWED ONLY WHEN IT IS UNIQUE IN THE WHOLE
        SNAPSHOT.** A premises with no postcode matched on street alone would
        otherwise take *one clean match* from a bucket that two postcodes share
        — `100 Main St` exists in more cities than not. Unique means unique
        across the register, which is a claim the index can actually check.
        """
        street_key = normalise_street(street)
        if not street_key:
            return []
        postcode_key = normalise_postcode(postcode)
        if postcode_key:
            return list(self.by_street_postcode.get(f"{street_key}|{postcode_key}", ()))
        found = list(self.by_street.get(street_key, ()))
        parcels = {one.parcel_id.casefold() for one in found if one.parcel_id}
        return found if len(parcels) == 1 else []


# ═══════════════════════════════════════════════════════════════════════════
# 1 + 2 · the keys
# ═══════════════════════════════════════════════════════════════════════════


def decide_premises_key(ours: Mapping[str, Any], index: SnapshotIndex) -> KeyDecision:
    """One premises' parcel key: keep it, take one, replace one, or queue.

    ⚠ **RULING 7 IS THE `replace` BRANCH AND ITS FALLBACK IS THE POINT.** PO
    2026-09-17: *"if we had a parcel ID and it does not match becuase of split -
    in such case you will have to use address matching and look for new parcel
    ID"*. A key that no longer resolves is treated as if there were none and
    re-derived the same way — **one clean match applies; anything else queues
    AND THE OLD KEY STAYS.** Dropping a key we can no longer confirm would lose
    the only handle we have on the row.
    """
    label = str(ours.get("label") or ours.get("premise_no") or ours.get("address_line") or "")
    held = str(ours.get("gis_parcel_id") or "").strip()

    if held and held.casefold() in index.by_parcel:
        return KeyDecision("premises", ours.get("id"), label, "keep", new_key=held, old_key=held)

    found = index.candidates_for(ours.get("address_line"), ours.get("postal_code"))
    parcels = sorted({one.parcel_id for one in found if one.parcel_id})

    if len(parcels) == 1:
        new_key = parcels[0]
        if not held:
            return KeyDecision(
                "premises", ours.get("id"), label, "take",
                new_key=new_key, candidates=tuple(parcels),
                reason="it had no key and exactly one parcel matched its address",
            )
        if new_key.casefold() == held.casefold():
            # Same key, different case. Not a change; nothing to record.
            return KeyDecision(
                "premises", ours.get("id"), label, "keep", new_key=held, old_key=held
            )
        return KeyDecision(
            "premises", ours.get("id"), label, "replace",
            new_key=new_key, old_key=held, candidates=tuple(parcels),
            reason="its key no longer resolves and exactly one parcel matched its address",
        )

    if not parcels:
        return KeyDecision(
            "premises", ours.get("id"), label, "queue",
            old_key=held or None, candidates=(),
            reason=(
                "its key no longer resolves and no parcel matched its address"
                if held
                else "it has no key and no parcel matched its address"
            ),
        )
    return KeyDecision(
        "premises", ours.get("id"), label, "queue",
        old_key=held or None, candidates=tuple(parcels),
        reason=f"{len(parcels)} parcels matched its address and only a person can choose",
    )


def decide_unit_key(
    ours: Mapping[str, Any], parcel: str | None, index: SnapshotIndex
) -> KeyDecision:
    """One unit's address-point key, WITHIN its building's parcel.

    ⚠ **A UNIT IS ONLY EVER MATCHED INSIDE THE PARCEL ITS BUILDING MATCHED.**
    Unit labels are `1`, `2`, `A`, `B` — the least distinctive strings in the
    product — and matching one across the whole register would pair our `Unit 2`
    with somebody else's `Unit 2` on the first run. **A building that did not
    match gives its units no key at all**, and they queue with it.
    """
    label = str(ours.get("label") or "")
    held = str(ours.get("gis_point_id") or "").strip()

    if held and held.casefold() in index.by_point:
        return KeyDecision("unit", ours.get("id"), label, "keep", new_key=held, old_key=held)

    if not parcel:
        return KeyDecision(
            "unit", ours.get("id"), label, "queue", old_key=held or None,
            reason="its building has no confirmed parcel, so there is nothing to look inside",
        )

    wanted = normalise_unit(label)
    siblings = index.by_parcel.get(str(parcel).casefold(), ())
    found = sorted({one.point_id for one in siblings if one.unit_key == wanted and one.point_id})

    if len(found) == 1:
        new_key = found[0]
        if not held:
            return KeyDecision(
                "unit", ours.get("id"), label, "take", new_key=new_key,
                candidates=tuple(found),
                reason="exactly one address point in its parcel carries this label",
            )
        if new_key.casefold() == held.casefold():
            return KeyDecision("unit", ours.get("id"), label, "keep", new_key=held, old_key=held)
        return KeyDecision(
            "unit", ours.get("id"), label, "replace", new_key=new_key, old_key=held,
            candidates=tuple(found),
            reason="its key no longer resolves and exactly one point in its parcel matches",
        )

    return KeyDecision(
        "unit", ours.get("id"), label, "queue", old_key=held or None, candidates=tuple(found),
        reason=(
            f"{len(found)} address points in its parcel carry this label"
            if found
            else "no address point in its parcel carries this label"
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3 + 4 · the fields
# ═══════════════════════════════════════════════════════════════════════════


def _comparable(field_name: str, value: Any) -> Any:
    """What two values are compared AS — never what either is stored as.

    Case and punctuation come off a street, a postcode is its first five
    digits, a coordinate is six decimal places. **The stored value is
    untouched**: normalising what we write back would be us adopting the City's
    spelling and then truthfully reporting that we agree with them.
    """
    if value in (None, ""):
        return None
    if field_name == "address_line":
        return normalise_street(value)
    if field_name == "postal_code":
        return normalise_postcode(value)
    if field_name in ("lat", "lng"):
        try:
            return Decimal(str(value)).quantize(Decimal("0.000001"))
        except (ArithmeticError, TypeError, ValueError):
            return None
    if field_name == "state":
        return str(value).strip().upper()
    return str(value).strip().casefold()


def classify(ours: Any, theirs: Any) -> str | None:
    """The difference class, or `None` when there is nothing to report.

    ⚠ **`None` FOR *THE SAME* AND FOR *NEITHER SIDE HAS ONE*, AND BOTH MATTER.**
    An unchanged field is **never written** (`BR-INT-073`), so it produces no
    difference at all rather than one classified as agreeing; and a field blank
    on both sides is not a finding a person should ever be shown.
    """
    if ours is None and theirs is None:
        return None
    if ours == theirs:
        return None
    if ours is None:
        return NEW_VALUE
    if theirs is None:
        return BLANK_THEIRS
    return CONFLICT


def disposition_for(
    field_name: str, difference_class: str, policy: Mapping[str, str] | None
) -> str:
    """What the utility said to do with this field. **DEFAULT: NEVER TOUCH.**

    Ruling 9 of 2026-09-17, verbatim: *"c) never touch by default"*. A field
    absent from the policy, a policy that is `None`, and a value nobody
    recognises all resolve to `never_touch` — hard-won law 3, the unsafe option
    must be the one somebody deliberately types.

    ⚠ **THE THREE STRUCTURAL CLASSES ARE NEVER APPLIED, WHATEVER THE POLICY
    SAYS.** *Two premises on one parcel*, *one premises on two parcels* and
    *unmatched* are not disagreements about a VALUE; there is no single value to
    write. They queue, always, and a utility cannot configure its way past that.
    """
    if difference_class in (TWO_PREMISES_ONE_PARCEL, ONE_PREMISES_TWO_PARCELS, UNMATCHED):
        return QUEUE
    chosen = str((policy or {}).get(field_name, "") or "").strip().lower()
    return chosen if chosen in DISPOSITIONS else NEVER_TOUCH


def compare_row(
    *,
    level: str,
    ours: Mapping[str, Any],
    theirs: ParcelRow | None,
    fields: Sequence[str],
    policy: Mapping[str, str] | None,
    label: str,
) -> list[FieldDifference]:
    """One of our rows against its City row, field by field.

    A `theirs` of `None` produces exactly one `UNMATCHED` difference and no
    field rows — reporting seven blank-theirs differences about a row the City
    simply does not have would be seven findings where there is one fact.
    """
    if theirs is None:
        return [
            FieldDifference(
                level, ours.get("id"), label, "—", None, None, UNMATCHED,
                disposition_for("—", UNMATCHED, policy),
            )
        ]
    mapped = {
        "address_line": theirs.address_line,
        "city": theirs.city,
        "state": theirs.state,
        "postal_code": theirs.postal_code,
        "lat": theirs.lat,
        "lng": theirs.lng,
        "gis_status": theirs.status,
    }
    found: list[FieldDifference] = []
    for name in fields:
        mine = _comparable(name, ours.get(name))
        yours = _comparable(name, mapped.get(name))
        klass = classify(mine, yours)
        if klass is None:
            # ⚠ **AN UNCHANGED FIELD IS NOT WRITTEN AND NOT REPORTED.** It is
            # the majority of every run, and a report listing it would bury the
            # handful of rows a person actually has to read.
            continue
        found.append(
            FieldDifference(
                level, ours.get("id"), label, name,
                ours.get(name), mapped.get(name), klass,
                disposition_for(name, klass, policy),
            )
        )
    return found


# ═══════════════════════════════════════════════════════════════════════════
# The whole pass
# ═══════════════════════════════════════════════════════════════════════════


def reconcile(
    *,
    snapshot: Snapshot,
    premises: Sequence[Mapping[str, Any]],
    units_by_premises: Mapping[Any, Sequence[Mapping[str, Any]]],
    policy: Mapping[str, str] | None = None,
) -> MatchReport:
    """Everything, in our database, with no further calls out (ruling 4).

    The City's layer is pulled ONCE and handed in as `snapshot`. This walks OUR
    register against it. PO 2026-09-17: *"please ensure you dont call ArcGis
    Apis for every Premsies or unit again and again … and against thse format
    match in loop with our premsies and units"*.
    """
    index = SnapshotIndex.of(snapshot)
    report = MatchReport()
    report.premises_examined = len(premises)

    claimed_parcels: dict[str, list[str]] = defaultdict(list)
    matched_city_parcels: set[str] = set()

    for one in premises:
        label = str(one.get("premise_no") or one.get("address_line") or one.get("id") or "")
        decision = decide_premises_key(one, index)
        report.key_decisions.append(decision)

        # ⚠ **THRASH IS OUR BUG.** A key we are changing on a row whose key we
        # have already changed once means our matching is unstable — the City
        # does not renumber a parcel nightly.
        if decision.action == "replace" and one.get("gis_parcel_id_was"):
            report.thrash_candidates.append(label)

        effective = decision.new_key if decision.action in ("keep", "take", "replace") else None
        if effective:
            claimed_parcels[effective.casefold()].append(label)
            matched_city_parcels.add(effective.casefold())
            theirs = index.building_point(effective)
            if theirs is None:
                # Ruling 6 — the parcel matched but no point on it is the
                # BUILDING's. The premises keeps no pin and this is not an
                # error; `lat`/`lng` are simply not compared for this row.
                theirs = next(iter(index.by_parcel.get(effective.casefold(), ())), None)
                comparable_fields = [f for f in PREMISES_FIELDS if f not in ("lat", "lng")]
            else:
                comparable_fields = list(PREMISES_FIELDS)
            report.differences.extend(
                compare_row(
                    level="premises", ours=one, theirs=theirs,
                    fields=comparable_fields, policy=policy, label=label,
                )
            )
        else:
            report.unmatched_ours += 1

        for unit in units_by_premises.get(one.get("id"), ()):
            report.units_examined += 1
            unit_label = f"{label} · {unit.get('label') or ''}".strip(" ·")
            unit_decision = decide_unit_key(unit, effective, index)
            report.key_decisions.append(unit_decision)
            if unit_decision.action == "replace" and unit.get("gis_point_id_was"):
                report.thrash_candidates.append(unit_label)
            point_key = (
                unit_decision.new_key
                if unit_decision.action in ("keep", "take", "replace")
                else None
            )
            their_point = index.by_point.get(point_key.casefold()) if point_key else None
            if their_point is not None:
                report.differences.extend(
                    compare_row(
                        level="unit", ours=unit, theirs=their_point,
                        fields=UNIT_FIELDS, policy=policy, label=unit_label,
                    )
                )

    # Two of ours on one of theirs — a person's judgment, never a write.
    for parcel, labels in claimed_parcels.items():
        if len(labels) > 1:
            report.differences.append(
                FieldDifference(
                    "premises", None, " · ".join(sorted(labels)), "gis_parcel_id",
                    " · ".join(sorted(labels)), parcel,
                    TWO_PREMISES_ONE_PARCEL, QUEUE,
                )
            )

    # ⚠ **RULING 8 — *"c) ignore"*.** A City parcel we have no premises for
    # raises nothing at all. It is COUNTED here and nowhere else, because a run
    # over 70,000 rows and a run over 700 must not read the same.
    all_city_parcels = {key for key in index.by_parcel}
    report.city_rows_ignored = len(all_city_parcels - matched_city_parcels)
    return report


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-112 (the ten PO rulings of 2026-09-17, decision log of that date)
# generated: 2026-09-17 by the CR-112 GIS build lane
# checklist: A✔ B=n/a(no screen reads this directly) C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr112_gis_match.py
# exceptions: none — every function here is pure, which is what lets preview and apply share one code path (BR-INT-074)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
