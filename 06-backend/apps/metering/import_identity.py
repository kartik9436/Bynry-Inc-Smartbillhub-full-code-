# ── Trace ──────────────────────────────────────────────
# Change:  BR-MET-1032 — a parked upload keeps its identifiers the way a
#          customer record does. The staging table stores an identity cell
#          app-layer encrypted with its blind index beside it, and the checking
#          screen serves the last four.
# Ruling:  PO 2026-09-01, verbatim: *"in spreadsheet we will porvide entire SSN
#          number if required"* — the FILE half, CONFIRMED. The SCREEN and
#          STORE halves are build judgments recorded in
#          `12-governance/02-decision-log.md` on the same day, decided there
#          rather than put back to the PO (CLAUDE.md law 13).
# Rules:   BR-MET-1032 (this rule) · BR-CUS-092 (SSN and driving licence
#          captured, app-layer encrypted, last four only on every read path) ·
#          BR-CUS-1022 (identity is per kind; a phone is a government
#          identifier for neither) · BR-MET-1030 (the premises file's owner
#          identity columns) · OQ-016 CLOSED (app-layer encryption, PO R6) ·
#          CLAUDE.md hard rule 1 (tenant scoping) · hard-won law 1 (a comment
#          claiming a guarantee is not the guarantee)
# Tests:   06-backend/tests/test_br_met_1032_staged_identity.py
# Impacts: apps/metering/import_runs (extract · transform · fix_row · rejects ·
#          the two verdicts · the failures CSV) · WFL-01.premises.3 ·
#          WFL-01.accounts.3 · components/workflow/RejectList
# ───────────────────────────────────────────────────────
"""The staged identity vault — one reserved key, four callers, no new mechanism.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides how a government identifier is held
while an upload waits, which is CLAUDE.md's 🔒 sensitive neighbourhood by
consequence: a migration file is the densest collection of government
identifiers this product will ever hold, every customer a utility has at once.
AI-authored 2026-09-01 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`.

⚠ **NOT ON THE G7 GLOB LIST (`10-scripts/gates/human_owned.txt`), AND THIS LANE
DID NOT PUT IT THERE.** Adding a glob is a PROCESS EVENT and the PO's call, not
a lane's (`OQ-441`, PO 2026-08-30). So the discrepancy is STATED here and
REPORTED, which is the posture `apps/customers/identity_match.py` and
`apps/customers/discounts.py` already take for the same gap. A marker no gate
reads is hard-won law 1; this paragraph says so rather than implying otherwise.

════════════════════════════════════════════════════════════════════════════
WHAT WAS WRONG, MEASURED RATHER THAN DESCRIBED
════════════════════════════════════════════════════════════════════════════
Read straight out of PostgreSQL, after `extract` and again after `transform`,
on a premises file carrying one owner:

    row 1 raw    = {"SSN": "123-45-6789", ..., "OWNER": "Rosa Alvarez", ...}
    row 1 mapped = {..., "owner_ssn": "123-45-6789", ...}

and the checking screen was served the same nine digits verbatim:

    rejects = [{... 'raw': {'SSN': '123-45-6789', ...}}]

Both doors, because both stage through `import_run_rows`.

════════════════════════════════════════════════════════════════════════════
THE SHAPE — A RESERVED KEY, NOT A COLUMN AND NOT A SECOND TABLE
════════════════════════════════════════════════════════════════════════════
`import_run_rows.raw` and `.mapped` are `jsonb`. The vault is a reserved key
inside each, exactly the convention `PARSE_PROBLEMS` and `LOAD_RESULT` already
use in `import_runs`:

    raw = {
        "SSN": "••••6789",          # what the screen draws and the editor edits
        ...,
        "__identity__": {"SSN": {"c": "<envelope>", "b": "<blind index>"}},
    }

**THE VISIBLE CELL IS REPLACED, NOT DUPLICATED.** A vault beside an untouched
plaintext cell would be theatre — the whole value of this change is that the
nine digits are not in the row any more.

**WHY THE MASK AND NOT THE BARE LAST FOUR.** `••••6789` is what
`customers`' own screens render (`customersShared.maskedGovId`), and putting the
rendered form in the cell means the generic reject table draws it correctly with
no screen having to remember to mask. A screen that must remember is a screen
that eventually forgets — and this way the full value is not in the payload at
all, so it cannot be widened by a component change.

════════════════════════════════════════════════════════════════════════════
WHICH COLUMNS, AND WHY A PHONE IS NOT MASKED
════════════════════════════════════════════════════════════════════════════
**THREE COLUMNS ARE PROTECTED AND THE PHONE IS NOT**, and the rule that decides
it is *"like every other surface in the product"* rather than a fresh judgment:
`customers.selectors.customer_detail` serves `ssn_last4`,
`driving_licence_last4` and `tax_id_last4` — and serves `phone` **IN FULL**. A
phone is the utility's contact handle and a government identifier for neither
kind (`BR-CUS-1022`).

⚠ **AND FOR A CELL SHOWN IN FULL, VAULTING IT WOULD ACHIEVE NOTHING.** The
visible cell is what the screen draws, so a field served whole has to keep its
plaintext there — a ciphertext copy beside a plaintext cell is a second copy of
the secret, not a protection of it. That is the honest reason the phone is left
alone, and it is stated because *"we encrypted all four"* would read better and
be false. On the accounts target `phone` is additionally a real column of the
account record and its plaintext is what the writer stores, exactly as before
this change.

════════════════════════════════════════════════════════════════════════════
TWO CONTEXTS, DELIBERATELY DIFFERENT, AND THE DIFFERENCE IS LOAD-BEARING
════════════════════════════════════════════════════════════════════════════
* **The BLIND INDEX uses `customers`' own context** (`customers.ssn`, …). It
  MUST: `blind_index` is an HMAC over `INDEX_SCHEME|context|normalised`, so a
  staged token computed under any other context would never equal the token on
  the customer row, and the matcher — the entire purpose of collecting the
  number — would look it up and find nothing.
* **The CIPHERTEXT uses the staging column's own context**
  (`import_run_rows.ssn`, …). `crypto._aad`'s stated job is that *"a value
  lifted out of one column and dropped into another does not decrypt"*, and a
  staged envelope is not a customer's: writing one into `customers.ssn` must
  raise rather than quietly work, so the value goes through the door
  `customers` owns or it does not go at all.

The contexts come from `customers` through `seams`, never copied, because a
mirrored cryptographic constant that drifts does not fail loudly — it produces
an index that matches nothing, which reads as *"no customer on file"*.

════════════════════════════════════════════════════════════════════════════
NOTHING ALREADY STAGED IS INVALIDATED — AND THE READ PATH SAYS SO IN CODE
════════════════════════════════════════════════════════════════════════════
A run parked before this landed has no `__identity__` key and holds its cells in
plain text. **`reveal_cell` returns such a cell as itself.** That is deliberate
and it is the only tolerance in this module: this rule governs what is WRITTEN
from now on, like every rule in its family, and a parked upload stays readable
and committable. `protect_cells` is what makes new rows protected; nothing
migrates old ones, and no row is rewritten on read.

⚠ **THE TOLERANCE IS ON READ ONLY.** `protect_cells` never leaves a cell it was
asked to protect in plain text: if the keyring is unavailable it RAISES, because
`crypto` raises rather than storing plaintext (hard-won law 3) and a staging
table that silently fell back would be the defect this file closes, wearing a
docstring that says otherwise.
"""

from __future__ import annotations

from typing import Any

from apps.metering import seams
from core import crypto

#: Reserved key inside `import_run_rows.raw` and `.mapped`. Same convention as
#: `import_runs.PARSE_PROBLEMS` / `LOAD_RESULT`, and stripped by the same
#: `_NOT_A_COLUMN` tuple so it can never reach `Premises(**record)`.
VAULT = "__identity__"

#: Keys inside one vault entry. Short because this rides in every staged row of
#: a 10,000-row file and the envelope is already ~90 bytes.
CIPHER = "c"
INDEX = "b"

#: The AAD each staged column's ciphertext is bound to. NOT `customers.*` — see
#: the module docstring: a staged envelope must not decrypt in a customer
#: column. The blind index is the opposite and comes from `seams`.
#: ⚠ **NO `phone` ENTRY, AND ITS ABSENCE IS THE STATEMENT.** A phone is shown in
#: full, so it is never vaulted; an entry here would read as a promise this
#: module does not keep (hard-won law 1). Adding one is not enough to protect a
#: phone — `PROTECTED_FIELDS` decides that, and the docstring says why it should
#: not.
STAGED_CONTEXT: dict[str, str] = {
    "ssn": "import_run_rows.ssn",
    "driving_licence": "import_run_rows.driving_licence",
    "tax_id": "import_run_rows.tax_id",
}

#: The three government identifiers this module protects and masks. Mirrors
#: `customers.selectors.customer_detail`'s three `*_last4` keys exactly; `phone`
#: is deliberately absent — see the module docstring, which says why vaulting a
#: cell that is shown in full would add a copy of the secret rather than remove
#: one.
PROTECTED_FIELDS: frozenset[str] = frozenset({"ssn", "driving_licence", "tax_id"})


def field_contexts() -> dict[str, str]:
    """`{'ssn': 'customers.ssn', …}` — the BLIND-INDEX context per identity fact.

    Read from `customers` through the seam rather than copied. A copy that
    drifted would not raise; it would produce an index that equals nothing,
    which the matcher reports as *"no customer on file"* — a wrong answer with
    no error, which is the shape every docstring in this repo keeps warning
    about.

    Empty while `customers` cannot answer, and an empty map protects nothing
    rather than protecting under a guessed context — a value encrypted under the
    wrong context is a value nobody can ever match.
    """
    return seams.identity_crypto_contexts()


def protect_cells(cells: dict[str, Any], columns: dict[str, str]) -> dict[str, Any]:
    """Return `cells` with each named cell replaced by its masked form, its
    ciphertext and its blind index moved into the vault.

    `columns` is `{cell key: identity field}` — the cell key is the operator's
    own source header in `raw` and our target column in `mapped`, and the field
    is `customers`' vocabulary (`ssn`, `driving_licence`, `phone`, `tax_id`).

    ⚠ **IDEMPOTENT.** A cell already in the vault is left exactly as it is, so
    re-running `transform` over a run does not encrypt a mask. This matters:
    r10 invites a remap (*"You can still remap at the next stage"*), so stage 2
    runs more than once over the same rows as a matter of course.

    ⚠ **AN EMPTY CELL IS NOT PROTECTED AND NOT INDEXED.** `crypto.blind_index`
    passes `''` through deliberately, so an absent identifier indexes to nothing
    rather than to a constant every absent identifier shares. Vaulting a blank
    would put that constant back.
    """
    contexts = field_contexts()
    if not contexts:
        return cells
    out = dict(cells)
    vault: dict[str, Any] = dict(out.get(VAULT) or {})
    for key, field in columns.items():
        if key in vault:
            continue  # already protected — see the idempotence note above
        if field not in PROTECTED_FIELDS:
            continue  # a phone is shown in full; see the module docstring
        context = contexts.get(field)
        staged = STAGED_CONTEXT.get(field)
        if context is None or staged is None:
            continue  # a field `customers` does not index is not ours to invent
        value = out.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        vault[key] = {
            # RAISES rather than falling back to plaintext (hard-won law 3).
            CIPHER: crypto.encrypt(value, context=staged),
            # `customers`' OWN context — this token must equal the one on the
            # customer row or the matcher cannot use it.
            INDEX: crypto.blind_index(value, context=context),
        }
        out[key] = display_form(value)
    if vault:
        out[VAULT] = vault
    return out


def display_form(value: str) -> str:
    """What a screen, a log line and the stored visible cell may hold.

    `••••6789` — the exact string `customers`' own
    `customersShared.maskedGovId` renders, so the import's checking screen and
    the customer screens cannot drift into two spellings of the same mask.

    A value with no alphanumerics at all comes back as itself: `crypto.last_four`
    returns `None` for it, and inventing four bullets over nothing would show a
    mask where there is no identifier to mask.
    """
    last4 = crypto.last_four(value)
    return f"••••{last4}" if last4 else value


def reveal_cell(cells: dict[str, Any], key: str, field: str) -> str | None:
    """The operator's own value for one cell, or `None` when there is none.

    ⚠ **A CELL WITH NO VAULT ENTRY IS RETURNED AS ITSELF.** That is the whole of
    *"nothing already staged is invalidated"*: a run parked before `BR-MET-1032`
    holds its identifier in plain text and must stay readable and committable.
    Nothing is rewritten on read and nothing is migrated.
    """
    entry = (cells.get(VAULT) or {}).get(key)
    if isinstance(entry, dict) and entry.get(CIPHER):
        staged = STAGED_CONTEXT.get(field)
        if staged is None:  # pragma: no cover — defensive; see protect_cells
            return None
        return crypto.decrypt(str(entry[CIPHER]), context=staged)
    value = cells.get(key)
    return value if isinstance(value, str) and value.strip() else None


def reveal_cells(cells: dict[str, Any], columns: dict[str, str]) -> dict[str, Any]:
    """`cells` with every named identity cell back in the operator's own words.

    The vault key is dropped: this is the view the mapper, the load and the
    operator's own failures file read, and none of them has any use for an
    envelope.
    """
    out = {key: value for key, value in cells.items() if key != VAULT}
    for key, field in columns.items():
        if key not in out and key not in (cells.get(VAULT) or {}):
            continue
        revealed = reveal_cell(cells, key, field)
        out[key] = revealed if revealed is not None else out.get(key)
    return out


def blind_index_of(cells: dict[str, Any], key: str) -> str | None:
    """The staged blind index for one cell — the token the matcher looks up.

    `None` for a cell staged before `BR-MET-1032`, which is honest: no index was
    written for it, and computing one here would hide the fact that the row is
    old rather than that the value is absent.
    """
    entry = (cells.get(VAULT) or {}).get(key)
    return str(entry[INDEX]) if isinstance(entry, dict) and entry.get(INDEX) else None


def masked_keys(cells: dict[str, Any]) -> list[str]:
    """The cell keys this row is showing MASKED, for the screen to say so.

    ⚠ **IT READS THE VAULT AND NOT A COLUMN MAP, DELIBERATELY.** Every vault
    entry IS a masked cell by construction — `protect_cells` only ever vaults a
    `PROTECTED_FIELDS` member — so the row itself is the answer, and no caller
    has to re-derive which mapping was in force when it was staged. A row parked
    before `BR-MET-1032` has no vault and reports nothing masked, which is true
    of it.

    The inline "Fix here" editor is what needs this: an input pre-filled with
    `••••6789` that an operator appends a digit to sends a number nobody typed,
    and `crypto.normalise_identifier` strips the bullets — so `••••67891` would
    be filed as the identifier `67891` with nothing objecting. Named cells are
    edited EMPTY against the mask as a placeholder instead.
    """
    return sorted(cells.get(VAULT) or {})
