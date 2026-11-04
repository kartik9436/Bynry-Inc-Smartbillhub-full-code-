# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9757 — Move-in completed reads "Messages 0 queued" when the
#           welcome email and letter WERE queued (M1, MVI-26-0009).
# ───────────────────────────────────────────────────────
"""The welcome seam reports a queued message by `code`, not by `state`.

`what_happened` counted rows whose `state` or `outcome` read queued — the
words `extra_messages` rows use — so the default welcome, which the seam
reports as `code: move_message_queued`, was never counted. Pure function.
"""

from apps.customers import move_in_complete, notifications_seam


def _messages(result):
    told = move_in_complete.what_happened(result)
    return next(item for item in told["items"] if item["key"] == "messages")


def test_the_queued_welcome_is_counted():
    item = _messages(
        {
            "move_message": [
                {
                    "code": notifications_seam.MOVE_MESSAGE_QUEUED,
                    "message_id": "m-1",
                    "channels": ["email", "pdf_print"],
                },
            ],
            "extra_messages": [{"state": "queued"}, {"state": "planned"}],
        }
    )
    # The welcome's two rows (email + printed letter) and the added message.
    assert item["queued"] == 3 and item["planned"] == 1


def test_an_already_queued_welcome_still_counts_and_a_suppressed_one_does_not():
    item = _messages(
        {
            "move_message": [
                {"code": notifications_seam.MOVE_MESSAGE_ALREADY_QUEUED, "message_id": "m-1"},
                {"code": notifications_seam.MOVE_MESSAGE_SUPPRESSED},
            ],
        }
    )
    assert item["queued"] == 1
