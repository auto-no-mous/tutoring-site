import datetime as dt
from typing import Annotated

from pydantic import AfterValidator

from app.utils.time import to_utc

# Use for every datetime accepted from a client. See app.utils.time.to_utc for why:
# SQLite storage doesn't convert offsets, so anything not already normalized to UTC
# before it reaches the DB would be persisted as the wrong instant.
UTCDateTime = Annotated[dt.datetime, AfterValidator(to_utc)]
