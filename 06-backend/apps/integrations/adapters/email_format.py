# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 · lane EMAIL-CORE (maintenance defect fix)
# Defect:   DEF-NOT-10420 — the internal message dict was the body of every email
# Rules:    PO 2026-10-22 ("don't do any hardcoding") · BR-INT-038 (an adapter
#           TRANSLATES; it decides nothing)
# Tests:    06-backend/tests/test_def_not_10420_email_payload.py
# Impacts:  adapters/email_smtp.py · esp_email.py (SendGrid, Postmark) ·
#           oauth_mailbox.py (Google, Microsoft)
# ───────────────────────────────────────────────────────
"""What one email IS, before any provider's shape is put on it.

Every email adapter used to take the work item's `subject` and `body`, `str()`
them, and fall back to a subject of its own when there was none — so when the
seam handed over the wrong thing (`DEF-NOT-10420`: the dispatcher's whole
artifact dict as the body, and no subject at all), every customer received
`{'subject': …, 'body': 'Hi ——,\\n\\n…'}` under *Message from your utility*,
and nothing anywhere refused it.

This module is the ONE place that turns a rendered subject and body into an
email's content, and it is used by SMTP, SendGrid, Postmark, Google and
Microsoft alike:

  * **It refuses rather than invents.** A subject or body that is missing, blank
    or not a string raises `EmailContentMissing`. There is no default subject
    and no default body anywhere in this file — the words a customer reads come
    from the utility's template and from nowhere else (PO 2026-10-22, *"don't do
    any hardcoding"*). An adapter's *Send test email* path supplies its own test
    words explicitly; that is the only place an adapter's words belong.
  * **It makes the HTML alternative from the text, never the other way round.**
    Templates are authored as plain text. The text part is the rendered body
    exactly as rendered; the HTML part is that same text HTML-escaped, with each
    blank-line-separated block a paragraph and each single newline a `<br/>`, in
    a minimal wrapper that uses inline styles only and loads nothing (no
    stylesheet, no font, no image, no tracking pixel). So a `<script>` typed
    into a template reaches an inbox as the text `<script>`, and a mail client
    that blocks remote content shows the message exactly as sent.
  * **It decides nothing about a provider.** Each adapter puts `subject`,
    `text` and `html` into its own API's shape — a MIME `multipart/alternative`
    for SMTP and Gmail, SendGrid's `content` list (plain first, which SendGrid
    requires), Postmark's `TextBody` + `HtmlBody`, and Graph's single `body` with
    `contentType: HTML` (Graph's JSON send carries one body, so it gets the HTML
    alternative, whose visible text is the plain body).
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from email.message import EmailMessage

#: Ours, B14 rule 33 (a fact ≤ 6 words). Returned as an item's text when an
#: adapter is handed a message it cannot send without inventing words.
NO_SUBJECT = "The message has no subject."
NO_BODY = "The message has no body."

_BLANK_LINE = re.compile(r"\n[ \t]*\n+")

#: A BCP 47 language tag as the catalogues spell them (`en`, `es`, `es-MX`).
_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")

#: The wrapper. Presentation only — no words, no remote asset. `{title}` is the
#: escaped subject and `{paragraphs}` the escaped body; both are always ours to
#: escape, never a caller's to pre-format.
_WRAPPER = (
    "<!DOCTYPE html>"
    '<html{lang}><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    "<title>{title}</title></head>"
    '<body style="margin:0;padding:0;background-color:#ffffff;">'
    '<div style="max-width:600px;margin:0 auto;padding:16px;'
    "font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;"
    'color:#1f2933;word-wrap:break-word;">'
    "{paragraphs}"
    "</div></body></html>"
)
_PARAGRAPH = '<p style="margin:0 0 16px 0;">{text}</p>'


class EmailContentMissing(ValueError):
    """A subject or body that is absent, blank or not text. Never defaulted."""

    def __init__(self, sentence: str) -> None:
        super().__init__(sentence)
        self.sentence = sentence


@dataclass(frozen=True)
class EmailContent:
    """One email's words, in the two forms every provider is given."""

    subject: str
    text: str
    html: str


def _normalise(body: str) -> str:
    return body.replace("\r\n", "\n").replace("\r", "\n")


def _lang_attribute(language: object) -> str:
    """` lang="<tag>"` for a well-formed language tag, else nothing.

    `DEF-NOT-10571` (WCAG 3.1.1): the wrapper declared no language, so a
    screen reader read a Spanish reminder with an English voice. The tag is
    the MESSAGE's language — the template variant it was rendered from, or the
    utility's own language for a `default` variant — handed in by the seam
    (`seams/notifications.py`). Nothing is invented: no tag, no attribute."""
    if not isinstance(language, str):
        return ""
    tag = language.strip().replace("_", "-")
    if not _LANGUAGE_TAG.match(tag):
        return ""
    return f' lang="{_html.escape(tag)}"'


def html_alternative(subject: str, body: str, language: object = None) -> str:
    """The HTML part: escaped, paragraphs from blank lines, `<br/>` for the rest,
    in a wrapper that declares the message's language."""
    blocks = [block.strip("\n") for block in _BLANK_LINE.split(_normalise(body))]
    paragraphs = "".join(
        _PARAGRAPH.format(text="<br/>".join(_html.escape(line) for line in block.split("\n")))
        for block in blocks
        if block.strip()
    )
    return _WRAPPER.format(
        lang=_lang_attribute(language), title=_html.escape(subject), paragraphs=paragraphs
    )


def compose(
    *, subject: object, body: object, language: object = None, html: object = None
) -> EmailContent:
    """The rendered subject and body as one email — or a refusal, never a guess.

    ⚠ **A NON-STRING IS REFUSED, NOT `str()`-ED.** That is the whole of
    `DEF-NOT-10420`: `str()` turns a dict into a perfectly sendable string, and
    a perfectly sendable string is what reached every customer.

    ⚠ **`html` — `CR-199-BRC10` S6.** When the render built the email's own
    branded HTML (`notifications.email_layout`, from the closed markup of
    `notifications.rich_text`, every value escaped there), it is sent as the
    HTML alternative AS GIVEN and `body` is its plain-text part. This adapter
    does not re-escape it: it is the renderer's output, never a clerk's. With
    no `html` (a test send, an older caller) the alternative is made from the
    text exactly as before.
    """
    if not isinstance(subject, str) or not subject.strip():
        raise EmailContentMissing(NO_SUBJECT)
    if not isinstance(body, str) or not body.strip():
        raise EmailContentMissing(NO_BODY)
    # A header may not carry a line break; a template subject is one line, and
    # one that is not is folded to spaces rather than allowed to inject a header.
    clean_subject = " ".join(subject.split())
    return EmailContent(
        subject=clean_subject,
        text=body,
        html=(
            html
            if isinstance(html, str) and html.strip()
            else html_alternative(clean_subject, body, language)
        ),
    )


def mime_alternative(content: EmailContent, *, sender: str, to: str) -> EmailMessage:
    """RFC 5322 `multipart/alternative` — text first, HTML preferred — for the
    two adapters that speak MIME (SMTP and Gmail). Headers beyond these three
    are the adapter's own to add."""
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = content.subject
    message.set_content(content.text)
    message.add_alternative(content.html, subtype="html")
    return message


__all__ = [
    "NO_BODY",
    "NO_SUBJECT",
    "EmailContent",
    "EmailContentMissing",
    "compose",
    "html_alternative",
    "mime_alternative",
]
