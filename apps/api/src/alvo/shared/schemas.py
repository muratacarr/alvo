"""Base class for partial-update (PATCH) request bodies."""

from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, model_validator


class PatchModel(BaseModel):
    """Only declared fields are accepted; unset fields mean "leave unchanged".

    Fields listed in `not_nullable` may be omitted but not set to null.
    """

    model_config = ConfigDict(extra="forbid")
    not_nullable: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> Self:
        for name in self.not_nullable:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

    def changes(self) -> dict[str, object]:
        return self.model_dump(exclude_unset=True)
