# ADR-028 — The photograph contract: declare with the data, send the bytes after

- **Status:** **Accepted** — rules R123–R126 (derived); R128 and R129 already in the repo.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-23**. Change request `CR-187-BRC10`.

## Context
A photograph is evidence, and a handset deletes its copy once the server has it.

## Decision
A photograph's **declaration** — id, sha256, what it proves, whether required — rides in the same payload as the reading. The **bytes** go up separately, binary multipart, one per request. **Never base64.** The **200 means durably stored, not enqueued.**

## What it reverses
An earlier framing in the design conversation, *"data first, photographs after"* — not wrong, thinner. No signed rule.

## Why
Because *required* is copied at declaration, *"required photographs still uploading"* is one query, and the office sees 2 of 3 received rather than a job that reads complete while its evidence is still in a van. Base64 is 33% larger (11 MB becomes 14.6 MB), cannot resume inside JSON, and holds the blob in memory as a string. The handset deletes its copy on confirmed receipt, so an optimistic acknowledgement loses evidence.

## Evidence
Already built: `work_photo_links` and `work_order_attachments`, with the idempotency key minted on the handset and scoped to the order (R128). `taken_at` is not `created_at` (R129).

## Cost
The upload endpoint must answer only after the bytes are durable; filing into the attachment runs in the background (R126).
