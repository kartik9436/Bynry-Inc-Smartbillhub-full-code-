# ── Trace ──────────────────────────────────────────────
# Story:    BR-CUS-092 (PO 2026-08-24, settling DEF-632) — "they are written
#           through the app-layer encryptor OQ-016 requires — which must be
#           BUILT, and `tenancy.ein` migrates onto it as the second caller,
#           because a helper with one caller is how the first one was skipped"
# Rules:    OQ-016 CLOSED (PO R6) — "app-layer encryption for high-sensitivity
#           columns, disk for rest" · B2 §6 · BR-CUS-089 (identity-match tiers
#           read the identifier) · BR-AUD-006 (identifiers enter the trail
#           masked) · BR-TEN-018 (the EIN's own display rule) ·
#           CLAUDE.md hard rule 7 (every money action writes audit_log — so the
#           audit blob is a read path this file has to answer for) ·
#           hard-won law 1 (a comment claiming a guarantee is not the guarantee)
#           · hard-won law 3 (defaults fail closed) · hard-won law 4 (a template
#           change never reaches a host that already has a `.env`)
# Tests:    06-backend/tests/test_be12_field_encryption.py ·
#           06-backend/tests/test_br_cus_092_ein_encryption.py
# Impacts:  apps/tenancy/models.Tenant.ein (the second caller — first through
#           the door is whichever column the customers lane encrypts under
#           BR-CUS-092(a)) · config/settings/{base,local,test,production}.py ·
#           06-backend/.env.example · 06-backend/pyproject.toml (cryptography)
# ───────────────────────────────────────────────────────
"""App-layer field encryption for high-sensitivity columns (OQ-016, B2 §6).

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md). HUMAN-REVIEW-PENDING — AI-authored
2026-08-24 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md. NOTHING HERE
IS RATIFIED: the four decisions this file makes on its own — where the key comes
from, what happens when it is absent, the rotation shape, and randomised-versus-
deterministic — are written into that ledger row in plain English with worked
values, and each waits on a recorded sign-off.

WHY THIS FILE EXISTS AT ALL, AND WHY IT IS NOT A NEW RULE
---------------------------------------------------------
`OQ-016` closed a long time ago — *"app-layer encryption for high-sensitivity
columns, disk for rest (PO R6)"* — and nothing was ever built. `tenants.ein`
shipped as nine plain digits with a source comment saying so, and the comment
had no expiry, no owner and no test. DEF-632 surfaced it only because a SCREEN
began promising a customer that their Social Security Number was *"stored
encrypted"*. So this file implements signed law; it invents none. The PO offered
to authorise overriding a law to get it built and that offer was DECLINED as
unnecessary, which is recorded in BR-CUS-092 and in the decision log.

THE SCHEME
----------
AES-256-GCM (`cryptography`, the vetted library already resolvable in this
environment — now DECLARED in pyproject.toml, see LAW 4 below), one random
96-bit nonce per encryption, authenticated with additional data that binds a
ciphertext to the column it was written for.

Envelope, a text column value:

    sbh1:<kid>:<b64u(nonce)>:<b64u(ciphertext||tag)>

`sbh1` is the SCHEME version, so the day the algorithm changes, every existing
value says which rules it was written under. `<kid>` is the KEY id, so every
value says which key made it — that is the whole of the rotation story and it is
in the value itself, never in a side table that can drift from it.

RANDOMISED, NOT DETERMINISTIC — AND WHAT THAT COSTS
----------------------------------------------------
Encrypting the same SSN twice produces two different envelopes. That is the
correct choice for a nine-digit secret and it is not a close call: a
deterministic scheme over a domain of 10^9 values, fed by a PUBLIC FORM that
will encrypt anything a stranger types, is a chosen-plaintext oracle — an
attacker with the ciphertext column and access to the form can confirm any
guess. Randomised GCM gives that attacker nothing.

The cost is real and is the hardest question in this work: **a randomised column
cannot be searched, joined or uniquely indexed.** And BR-CUS-089's match tiers
need exactly that — REQ-03.1 tells the applicant the identifier is *"used to
match you against any account you have held before"*.

**So matching runs on a BLIND INDEX, not on the ciphertext.** Alongside the
encrypted column a caller stores a second column:

    bix1:<kid>:<b64u(HMAC-SHA256(index_key, normalised_value))>

which is deterministic, equality-searchable and uniquely-indexable, while the
value itself stays in the randomised column. `blind_index()` writes it;
`blind_index_candidates()` is what a LOOKUP uses.

Three properties of that choice, stated rather than implied:

1. **It leaks equality, and only equality.** Two rows holding the same SSN carry
   the same index token, which is precisely what matching means; nothing else
   about the value is recoverable from it. Any scheme that can match at all
   leaks this much.
2. **It is KEYED, which is why it is an HMAC and not a hash.** A bare SHA-256 of
   a nine-digit number is broken by an afternoon of brute force against a
   database dump. The HMAC key is not in the database, so a dump alone yields
   nothing to enumerate. This is the single most important line in this file.
3. **It rotates with the data key, so a lookup asks about every key.** The token
   carries its kid; `blind_index_candidates()` returns one token per configured
   key and the caller queries `WHERE col IN (…)`. Rows written under a retired
   key stay findable without being rewritten. Rewriting them is a separate,
   deliberate re-key pass, never a side effect of a read.

The encryption key and the index key are DIFFERENT keys, derived from one
operator-managed secret by HKDF-SHA256 with distinct `info` strings, so an
operator manages one secret per kid and the two uses can never be confused.

WHERE THE KEY COMES FROM, AND WHAT HAPPENS WHEN IT IS ABSENT
-------------------------------------------------------------
One environment variable, read in `config/settings/base.py`:

    SBH_FIELD_ENCRYPTION_KEYS=<kid>:<base64url 32 bytes>[,<kid>:<key>…]

The FIRST entry is ACTIVE — it encrypts every new value. Every other entry is
DECRYPT-ONLY and exists so rotation is additive: put the new key first, leave
the old one behind it, and nothing has to be rewritten to keep reading.

**There is no default and there is no fallback (hard-won law 3).** With the
variable unset this module raises `FieldEncryptionUnavailable` on any encrypt,
any decrypt and any blind index. It does NOT store plaintext, it does not invent
a key, and it does not silently return the value it was handed. `sslmode=disable`
and `ALLOWED_HOSTS=localhost` each blocked a live deploy in this product because
the SAFE option was the default; here the unsafe option is not available at all.

`config/settings/production.py` refuses to import with the variable unset, so a
production deploy fails at boot with a message naming the variable rather than
at the moment a customer types their SSN into a form. It would have failed a few
seconds later anyway — the `tenancy` backfill migration cannot encrypt an
existing EIN without a key and refuses too — so this moves a certain failure
earlier and gives it a name.

`local.py` and `test.py` each carry a literal `insecure-dev` key, checked into
the repo, because a developer and a CI box need one and a per-machine secret
would just be typed wrong. That key CANNOT reach a real deployment: a kid
beginning `insecure-` is refused unless `FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS`
is True, which `base.py` sets False and only those two development modules turn
on. So "run production settings, get the dev key" is not a state this code can
be in.

⚠ LAW 4 — EDITING `.env.example` REACHES NO HOST THAT ALREADY HAS A `.env`.
This is worth saying in the file and not only in a report, because it is how the
`ALLOWED_HOSTS` trap survived to production. On EVERY already-provisioned
deployment somebody must put a real key into that host's own `.env` BY HAND
before the next deploy, or `migrate` stops on the tenancy backfill and gunicorn
never starts under production settings. Generate one with:

    python -c "import base64,os;print('k1:'+base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('='))"

WHAT THIS FILE DELIBERATELY DOES NOT DO
----------------------------------------
* **It does not decide any column's DISPLAY rule.** `last_four()` and `mask()`
  are offered because BR-CUS-092(c) requires last-four rendering for the SSN and
  the driver's licence; whether a given column uses them is that column's own
  signed rule. `tenants.ein` does NOT: BR-TEN-018 says the EIN is displayed
  `NN-NNNNNNN` in full on the Settings company tab, that rule is untouched here,
  and BR-AUD-006 already masks it into the audit trail. Encrypting a column and
  masking its display are two separate laws and this file is only the first.
* **It does not manage a key store.** The secret comes from the process
  environment, as `DJANGO_SECRET_KEY` does. A KMS/vault-backed key is a real
  improvement and is not in scope of BR-CUS-092; it is a settings-layer change
  when it comes, because everything below reads one parsed keyring.
* **It does not re-key existing rows.** Rotation makes new writes use the new key
  and leaves old values readable. A sweep that rewrites them is a separate,
  auditable job nobody has asked for yet.
* **It cannot stop a caller printing the value it returns.** `decrypt()` hands
  back cleartext; a `logger.info(ssn)` after that is a defect this file cannot
  see. The guards for that are the leak tests beside it, which grep a rendered
  response, an export and the captured log stream for the cleartext.
"""

from __future__ import annotations

import base64
import hmac
import os
import re
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core.exceptions import FieldError
from django.db import models

#: Envelope prefix for an encrypted value. Bumping it is how an algorithm change
#: announces itself in every row that predates it.
SCHEME = "sbh1"

#: Envelope prefix for a blind-index token. Separate namespace on purpose — an
#: index token is not a ciphertext and must never be handed to `decrypt`.
INDEX_SCHEME = "bix1"

#: HKDF domain separation. Two keys out of one operator secret; an encryption
#: key can never be used as an index key by accident.
_ENC_INFO = b"smartbillhub/field-encryption/v1"
_IDX_INFO = b"smartbillhub/blind-index/v1"

#: 32 bytes = AES-256. 12 bytes = the GCM nonce size everything sane uses.
KEY_BYTES = 32
NONCE_BYTES = 12

#: A key id is short, lowercase and greppable. It appears inside every stored
#: value, so it may never contain the `:` the envelope splits on.
_KID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

#: A kid under this prefix is a DEVELOPMENT key committed to the repo. It is
#: refused unless the settings module explicitly allows insecure keys, which
#: only config/settings/local.py and config/settings/test.py do.
INSECURE_KID_PREFIX = "insecure-"


class FieldEncryptionError(Exception):
    """Base for every refusal in this module. Never caught to fall back."""


class FieldEncryptionUnavailable(FieldEncryptionError):
    """No usable key is configured. Raised instead of storing anything."""


class FieldEncryptionKeyError(FieldEncryptionError):
    """A key is configured but unusable — bad kid, bad base64, wrong length."""


class FieldDecryptionError(FieldEncryptionError):
    """A stored value did not decrypt: unknown key, wrong key, wrong column,
    or a tampered envelope. ALWAYS an exception, never a fallback value."""


@dataclass(frozen=True)
class _Key:
    kid: str
    enc: bytes
    idx: bytes


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _derive(secret: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=None, info=info).derive(secret)


# Parsed keyrings, cached by the RAW setting string. Keying the cache on the
# value (not on a boolean) means @override_settings in a test invalidates it for
# free — there is no signal to remember to connect and nothing to go stale.
_KEYRING_CACHE: dict[tuple[str, bool], tuple[_Key, ...]] = {}


def _configured() -> tuple[str, bool]:
    raw = getattr(settings, "FIELD_ENCRYPTION_KEYS", "") or ""
    allow_insecure = bool(getattr(settings, "FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS", False))
    return str(raw).strip(), allow_insecure


def keyring() -> tuple[_Key, ...]:
    """Every configured key, ACTIVE FIRST. Raises rather than returning empty."""
    cache_key = _configured()
    raw, allow_insecure = cache_key
    cached = _KEYRING_CACHE.get(cache_key)
    if cached is not None:
        return cached
    if not raw:
        raise FieldEncryptionUnavailable(
            "SBH_FIELD_ENCRYPTION_KEYS is not set, so high-sensitivity columns "
            "cannot be read or written (OQ-016, BR-CUS-092). Nothing is stored "
            "in plaintext instead. Generate a key with: python -c "
            "\"import base64,os;print('k1:'+base64.urlsafe_b64encode(os.urandom(32))"
            '.decode().rstrip(chr(61)))" — and note that editing .env.example '
            "reaches no host that already has a .env (hard-won law 4)."
        )
    keys: list[_Key] = []
    seen: set[str] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        kid, sep, material = entry.partition(":")
        if not sep:
            raise FieldEncryptionKeyError(
                "SBH_FIELD_ENCRYPTION_KEYS entries are '<kid>:<base64url-32-bytes>'; "
                f"got an entry with no ':' separator ({kid[:8]}…)"
            )
        kid = kid.strip()
        if not _KID_RE.match(kid):
            raise FieldEncryptionKeyError(
                f"key id {kid!r} is not lowercase [a-z0-9_-], 1-32 chars. The kid is "
                "stored inside every ciphertext, so it may never contain ':'."
            )
        if kid in seen:
            raise FieldEncryptionKeyError(f"key id {kid!r} appears twice — a kid must be unique")
        if kid.startswith(INSECURE_KID_PREFIX) and not allow_insecure:
            raise FieldEncryptionKeyError(
                f"key id {kid!r} is a development key and FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS "
                "is False. Only config/settings/local.py and config/settings/test.py turn that "
                "on; a real deployment must supply a real key (hard-won law 3)."
            )
        try:
            secret = _b64d(material.strip())
        except Exception as exc:  # noqa: BLE001 — any decode failure is the same refusal
            raise FieldEncryptionKeyError(f"key {kid!r} is not valid base64url") from exc
        if len(secret) != KEY_BYTES:
            raise FieldEncryptionKeyError(
                f"key {kid!r} decodes to {len(secret)} bytes; AES-256 needs {KEY_BYTES}"
            )
        seen.add(kid)
        keys.append(_Key(kid=kid, enc=_derive(secret, _ENC_INFO), idx=_derive(secret, _IDX_INFO)))
    if not keys:
        raise FieldEncryptionUnavailable("SBH_FIELD_ENCRYPTION_KEYS is set but holds no key")
    parsed = tuple(keys)
    _KEYRING_CACHE[cache_key] = parsed
    return parsed


def active_kid() -> str:
    """The kid every NEW value is written under — the first configured key."""
    return keyring()[0].kid


def _key(kid: str) -> _Key:
    for key in keyring():
        if key.kid == kid:
            return key
    raise FieldDecryptionError(
        f"stored value was written under key {kid!r}, which is not in "
        "SBH_FIELD_ENCRYPTION_KEYS. A retired key must stay on the ring until every "
        "value written under it has been re-keyed."
    )


def _aad(context: str) -> bytes:
    """Additional authenticated data: the column a value belongs to.

    Binding the ciphertext to `"tenants.ein"` means a value lifted out of one
    column and dropped into another does not decrypt — it raises. Costs nothing
    and turns a whole class of copy-paste into a loud failure.
    """
    if not context or ":" in context:
        raise FieldEncryptionError(
            "an encryption context is required and may not contain ':' — pass the "
            "column it belongs to, e.g. 'tenants.ein'"
        )
    return f"{SCHEME}|{context}".encode()


def encrypt(value: str | None, *, context: str) -> str | None:
    """Encrypt one value under the ACTIVE key. `None` and `''` pass through.

    Empty is passed through deliberately: there is nothing to protect, and every
    `if not tenant.ein` in the product keeps meaning what it meant.
    """
    if value is None or value == "":
        return value
    if not isinstance(value, str):
        raise FieldEncryptionError(f"encrypt() takes str, got {type(value).__name__}")
    key = keyring()[0]
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(key.enc).encrypt(nonce, value.encode("utf-8"), _aad(context))
    return f"{SCHEME}:{key.kid}:{_b64e(nonce)}:{_b64e(sealed)}"


def decrypt(token: str | None, *, context: str) -> str | None:
    """Decrypt an envelope. Raises on ANY failure — never returns the input."""
    if token is None or token == "":
        return token
    parts = token.split(":", 3)
    if len(parts) != 4 or parts[0] != SCHEME:
        raise FieldDecryptionError(
            "value is not an app-layer ciphertext envelope. It is NOT returned as "
            "cleartext: a column declared high-sensitivity that holds a plain value "
            "is a defect to fix, not a case to fall through (BR-CUS-092)."
        )
    _, kid, nonce_b64, sealed_b64 = parts
    key = _key(kid)
    try:
        nonce = _b64d(nonce_b64)
        sealed = _b64d(sealed_b64)
    except Exception as exc:  # noqa: BLE001
        raise FieldDecryptionError(f"ciphertext under key {kid!r} is not valid base64url") from exc
    try:
        return AESGCM(key.enc).decrypt(nonce, sealed, _aad(context)).decode("utf-8")
    except InvalidTag as exc:
        raise FieldDecryptionError(
            f"ciphertext under key {kid!r} failed authentication for context {context!r}. "
            "It was written with a different key, for a different column, or it has been "
            "altered. No value is returned."
        ) from exc


def is_ciphertext(token: object) -> bool:
    """Structural check only — true for a well-formed envelope under a KNOWN key.

    Structure is not authentication: `decrypt()` is what proves a value is
    genuine. This exists so `encrypt()` can be idempotent (re-encrypting an
    already-encrypted value is a no-op, which is what makes the backfill
    migration safe to run twice).
    """
    if not isinstance(token, str):
        return False
    parts = token.split(":", 3)
    if len(parts) != 4 or parts[0] != SCHEME:
        return False
    try:
        _key(parts[1])
    except FieldEncryptionError:
        return False
    return bool(parts[2]) and bool(parts[3])


# ── Blind index — the ONLY way a randomised column is matched ────────────────


def normalise_identifier(value: str) -> str:
    """The canonical form a government identifier is indexed under.

    `123-45-6789`, `123 45 6789` and `123456789` are one identifier, and an
    applicant who types the hyphens on Tuesday and omits them on Thursday must
    still match (BR-CUS-089). So the index is taken over digits and letters only,
    upper-cased — letters because a driver's licence number carries them.

    This normalisation applies to the INDEX, never to what is encrypted: the
    stored value keeps exactly what the customer typed.
    """
    return re.sub(r"[^0-9A-Za-z]", "", value).upper()


def blind_index(value: str | None, *, context: str) -> str | None:
    """A deterministic, equality-searchable token for `value` under the ACTIVE key.

    Written beside the ciphertext. `None`/`''` pass through, so an absent
    identifier indexes to nothing rather than to a constant every absent
    identifier shares.
    """
    if value is None or value == "":
        return value
    key = keyring()[0]
    return _index_token(key, value, context)


def blind_index_candidates(value: str | None, *, context: str) -> list[str]:
    """Every token `value` could be stored under — ONE PER CONFIGURED KEY.

    This is what a LOOKUP uses: `Model.objects.filter(col__in=candidates)`. Rows
    written before a rotation carry the old kid and stay findable without being
    rewritten. Returns `[]` for an absent value, which makes an `__in` lookup
    match nothing — the correct answer, and not an accident.
    """
    if value is None or value == "":
        return []
    return [_index_token(key, value, context) for key in keyring()]


def _index_token(key: _Key, value: str, context: str) -> str:
    if ":" in context or not context:
        raise FieldEncryptionError("a blind-index context is required and may not contain ':'")
    mac = hmac.new(
        key.idx, f"{INDEX_SCHEME}|{context}|{normalise_identifier(value)}".encode(), "sha256"
    ).digest()
    return f"{INDEX_SCHEME}:{key.kid}:{_b64e(mac)}"


# ── Read-path projections — BR-CUS-092(c) ───────────────────────────────────


def last_four(value: str | None) -> str | None:
    """The last four characters of the identifier, and nothing else.

    BR-CUS-092(c): *"every read path renders last four only and the full value is
    never in a list response, an export, a log line or an audit `details` blob"*.
    A value shorter than four characters returns as-is; there is no fifth
    character to hide, and padding it would invent one.
    """
    if value is None or value == "":
        return value
    digits = normalise_identifier(value)
    return digits[-4:] if digits else None


def mask(value: str | None, *, keep: int = 4, fill: str = "•") -> str | None:
    """`'123456789'` → `'•••••6789'`. What a staff screen and a log line may hold."""
    if value is None or value == "":
        return value
    digits = normalise_identifier(value)
    if len(digits) <= keep:
        return fill * len(digits)
    return fill * (len(digits) - keep) + digits[-keep:]


# ── The Django field — how a column adopts all of the above ──────────────────


class EncryptedTextField(models.TextField):
    """A TEXT column whose value is encrypted on the way in and decrypted out.

    `crypto_context` is REQUIRED and is deliberately not derived from the model.
    Deriving it from `db_table`/`name` would mean that renaming a table silently
    changes the AAD and every existing row stops decrypting — a rename would
    become a data-loss event with no diff to review. An explicit literal makes it
    a decision somebody has to type.

    Storage is unchanged (`text`), so adopting this field is an `AlterField` with
    no DDL — but the DATA has to be converted, which is what the backfill
    migration beside it does.

    ⚠ EQUALITY LOOKUPS ARE REFUSED, LOUDLY. The scheme is randomised, so
    `filter(ein="743182640")` cannot match and would return an empty queryset
    that looks exactly like "no such tenant". A silently wrong answer on an
    identity match is the failure mode BR-CUS-089 can least afford, so the field
    raises `FieldError` and names `blind_index_candidates()` instead. Only
    `__isnull` survives, because it reads the column's nullness and not its value.
    """

    #: `__isnull` asks whether the column is NULL; it never touches the value.
    ALLOWED_LOOKUPS = frozenset({"isnull"})

    def __init__(self, *args: Any, crypto_context: str = "", **kwargs: Any) -> None:
        if not crypto_context:
            raise ValueError(
                "EncryptedTextField requires crypto_context, e.g. "
                "crypto_context='tenants.ein' — it binds the ciphertext to this column"
            )
        self.crypto_context = crypto_context
        super().__init__(*args, **kwargs)

    def deconstruct(self) -> tuple[str, str, list[Any], dict[str, Any]]:
        name, path, args, kwargs = super().deconstruct()
        kwargs["crypto_context"] = self.crypto_context
        return name, path, args, kwargs

    def get_prep_value(self, value: Any) -> Any:
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        if is_ciphertext(value):
            # Idempotent: an already-encrypted value is stored as it stands, but
            # only after it PROVES it belongs to this column. Structure alone
            # would let an attacker-supplied `sbh1:…` string be stored raw.
            decrypt(value, context=self.crypto_context)
            return value
        return encrypt(str(value), context=self.crypto_context)

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        if value is None or value == "":
            return value
        return decrypt(value, context=self.crypto_context)

    def get_lookup(self, lookup_name: str) -> Any:
        if lookup_name not in self.ALLOWED_LOOKUPS:
            raise FieldError(
                f"{self.model.__name__}.{self.name} is app-layer encrypted with a RANDOMISED "
                f"scheme, so `__{lookup_name}` can never match: the same value encrypts "
                "differently every time. Store a blind index beside it and query "
                "`core.crypto.blind_index_candidates(value, context=…)` with `__in` "
                "(BR-CUS-092, BR-CUS-089)."
            )
        return super().get_lookup(lookup_name)

    def value_to_string(self, obj: Any) -> str:
        """Serialisation (`dumpdata`, fixtures) emits the CIPHERTEXT, never the value.

        A fixture is an export. `Field.value_to_string` normally reaches through
        `value_from_object`, which returns the decrypted attribute — so the
        default behaviour would write a customer's SSN into a JSON file on disk.
        `loaddata` round-trips because `get_prep_value` passes a valid envelope
        through unchanged.
        """
        value = self.value_from_object(obj)
        if value is None or value == "":
            return "" if value == "" else value
        if is_ciphertext(value):
            return str(value)
        return str(encrypt(str(value), context=self.crypto_context))


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-CUS-092@2026-08-24 (PO ruling settling DEF-632 · OQ-016 CLOSED, B2 §6)
# generated: 2026-08-24 by the BR-CUS-092 field-encryption lane
# checklist: A✔ B✔ C✔ D=n/a(no API half — this is platform plumbing) E=n/a(no frontend half; the SSN capture that renders it is apps/customers/, another lane) F✔ G✔ H=PENDING(🔒 sensitive path — human sign-off owed, see the review ledger)
# gates: ruff✔ black✔ makemigrations --check✔ pytest tests/test_be12_field_encryption.py✔ tests/test_br_cus_092_ein_encryption.py✔ · G6✔ G7 (needs the ledger row committed) G8✔ G26✔
# exceptions: (1) `tenants.ein` keeps its BR-TEN-018 full display — encrypting a column and masking its display are two laws and only the first is BR-CUS-092(b)'s. (2) The SSN/driver's-licence columns BR-CUS-092(a) requires are NOT built here: apps/customers/ belongs to another lane, and its capture path still REFUSES every identifier field by name (service_request_service.IDENTIFIER_FIELDS) — so the screen's "stored encrypted" claim is true of nothing yet, and stays off until that lane wires these helpers. (3) The key lives in the process environment, not a KMS. (4) No re-key sweep for rows under a retired key.
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
