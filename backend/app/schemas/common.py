import datetime as dt
from typing import Annotated

from pydantic import AfterValidator

from app.utils.html_sanitize import sanitize_rich_text
from app.utils.time import to_utc

# Use for every datetime accepted from a client. See app.utils.time.to_utc for why:
# SQLite storage doesn't convert offsets, so anything not already normalized to UTC
# before it reaches the DB would be persisted as the wrong instant.
UTCDateTime = Annotated[dt.datetime, AfterValidator(to_utc)]

# Use for any client-supplied rich-text field that later gets rendered as HTML (e.g.
# TutorProfileUpdate.about). The frontend already sanitizes on every render/edit path
# (see RichTextEditor.vue), but the backend shouldn't rely on that as the only trust
# boundary - a value could reach the DB via a direct API call that never touched the
# frontend sanitizer at all.
SanitizedHtml = Annotated[str, AfterValidator(sanitize_rich_text)]
