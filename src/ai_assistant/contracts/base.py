"""Common primitives shared by typed contract models."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.functional_validators import AfterValidator

# Stable releases only: prerelease and build metadata are rejected so that a
# schema version identifies exactly one wire format.
SCHEMA_VERSION_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"

SchemaVersion = Annotated[str, Field(pattern=SCHEMA_VERSION_PATTERN, max_length=32)]


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


# AwareDatetime rejects naive input before normalization, so an offset is never
# assumed on the caller's behalf.
UtcDateTime = Annotated[AwareDatetime, AfterValidator(_to_utc)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)
