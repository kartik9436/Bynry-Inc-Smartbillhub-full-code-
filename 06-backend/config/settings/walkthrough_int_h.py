"""Walkthrough settings for CR-069 wave H — local, plus the recorded exchange.

⚠ **BOTH FLAGS ARE HERE AND NOT IN `local.py`, DELIBERATELY.** A hook that
arrives by default is a hook nobody typed, which is hard-won law 3 exactly: the
unsafe option must be the one you type. `local.py` is what every lane runs, and
a recorded token exchange living there would eventually store a synthetic
consent as somebody's real mailbox credential.

`oauth._default_exchanger` refuses the recording outright when `DEBUG` is off,
so this module cannot be mistaken for a deployment even if it were copied.

    DJANGO_SETTINGS_MODULE=config.settings.walkthrough_int_h \\
      python3 06-backend/manage.py runserver 127.0.0.1:8160 --noreload
"""

from config.settings.local import *  # noqa: F401,F403

#: Use `oauth_fixtures.recorded_exchange` instead of dialling Microsoft. A
#: browser walkthrough has to press the REAL start and return endpoints
#: (hard-won law 6), and `login.microsoftonline.com` is not ours to dial.
INTEGRATION_OAUTH_RECORDED = True

#: OUR registration with each provider. Obviously synthetic — `_client()`
#: refuses by name when it is absent, so the walkthrough needs one to get past
#: the start endpoint at all.
INTEGRATION_OAUTH_CLIENTS = {
    "email_microsoft": {
        "client_id": "walkthrough-client",
        "client_secret": "walkthrough-secret",
    },
    "email_google": {
        "client_id": "walkthrough-client",
        "client_secret": "walkthrough-secret",
    },
}
