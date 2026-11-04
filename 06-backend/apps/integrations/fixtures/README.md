# Fixtures — codec recordings, and one captured provider payload

⚠ **AMENDED 2026-09-06 (wave N).** This file opened *"One folder per registered codec"*
and that is no longer the whole truth: `payments_kiosk/` is a **provider capture**, not a
codec folder — the redacted kiosk payload `CR-069` §12's phase-5 exit test replays, read
by `tests/test_us_int_044_inbound_door.py`. Nothing in `codecs.py` looks at it:
`check_fixtures` walks the REGISTERED CODECS and asks each for its folder, so a folder no
codec is named after is never enumerated and cannot make an unsupported codec look
supported. The sentence is corrected rather than the folder moved, because `10-execution-plan.md`
task `N4` names this path (hard-won law 1 — a README claiming a rule is not the rule).

One folder per registered codec (`apps/integrations/codecs.py`). A codec is **supported**
only when its folder holds a recorded file AND the codec carries an encoder or a decoder
(`BR-INT-033`: *"a codec with no recorded fixture from the real provider is not a supported
format"*). Every folder carries a `PROVENANCE` line saying where its files came from — or
that there are none and which wave records the first. `PROVENANCE` and this README are
never counted as fixtures (`codecs.fixture_paths`).

⚠ **AMENDED AGAIN 2026-09-06 (wave J) — AND THE AMENDMENT IS A THIRD STATE, NOT A
LONGER LIST.** This paragraph said *"`json · xml · csv · mime` … the seven vendor
formats and `pdf` hold a `PROVENANCE` line and nothing else"*, which read as two
positions: code-and-a-file, or neither. **There are three.**

* **SUPPORTED — code AND a recorded file.** `json · xml · csv · mime`, and now
  **`iif`**. Every one is OUR OWN emitter's output on the worked payment
  `PAY-2609-0311 · $142.18` (and the worked bill notice for `mime`), checked
  byte-for-byte — `tests/test_us_int_039_codecs.py` for the first four,
  `tests/test_us_int_038_export_target.py` for `iif`. There is no "real provider"
  file to record for a format WE write and QuickBooks reads, which is why an
  own-emitter recording is the honest one here.
* **CODE, AND NO RECORDED FILE — `camt053` since wave J.** It DECODES a bank's
  ISO 20022 statement, and `is_supported()` still answers **False**, because
  `BR-INT-033` makes the FIXTURE decide rather than the code. Its `PROVENANCE`
  says so in full. What is owed is an **artefact** — a redacted statement from a
  going-live utility's own bank — and not a decision anybody can rule.
* **NAME ONLY — `xero · qbo · ofx · qfx · bai2 · pdf`.** A `PROVENANCE` line and
  nothing else, on purpose, each saying what brings it. ⚠ For `xero` that is now
  a MODULE rather than a wave: its column layout is a projection, and projections
  are Runbooks' (`BR-INT-054`, `CR-069` §20.4).

⚠ **AND A TYPED SAMPLE MUST NEVER LIVE HERE, IN ANY OF THE THREE.** `camt053`'s
decoder is proved against a structural fixture held under `06-backend/tests/`,
deliberately OUTSIDE this directory, and a test asserts this folder is still
empty — because a file written to exercise a parser is the one thing that could
make the conformance kit say *supported* about a format no real bank has been
read with, and that is the failure this whole directory exists to prevent.
