"""Error-report filtering.

Django's debug page and its 500 error emails dump the settings module. It
masks names matching API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE,
which covers SECRET_KEY and EMAIL_HOST_PASSWORD but leaves connection URIs
untouched.

That is a problem here because MONGO_URL embeds its own username and password:

    mongodb+srv://user:password@cluster.mongodb.net/

so a single unhandled exception on a server running with DEBUG=True would show
the full database credentials to whoever triggered it. This widens the mask to
cover connection strings and addresses too.

DEBUG should still be False in any deployment. This is defence in depth for
when it is not.
"""

import re

from django.views.debug import SafeExceptionReporterFilter  # type: ignore


class OrcaExceptionReporterFilter(SafeExceptionReporterFilter):
    hidden_settings = re.compile(
        "API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE"
        # Added: connection strings that carry embedded credentials, and the
        # sending mailbox, which is personal data rather than a secret.
        "|MONGO|REDIS|DATABASE|DSN|CONN|EMAIL|URL|URI",
        flags=re.I,
    )
