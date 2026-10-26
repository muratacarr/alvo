"""Project domain record. Plain data; persistence and HTTP shapes live elsewhere."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ProjectRecord:
    id: UUID
    owner_id: UUID
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @property
    def archived(self) -> bool:
        return self.archived_at is not None
