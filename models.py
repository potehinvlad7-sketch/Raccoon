from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

RARITIES = ["Common", "Rare", "Epic", "Legendary", "Mythic"]


@dataclass(slots=True)
class Card:
    id: int
    file_id: str
    local_path: str
    filename: str
    caption: str
    rarity: str
    category: str
    triggers: list[str]
    enabled: bool
    created_at: str
    updated_at: str
    uploaded_by: int

    @classmethod
    def create(
        cls,
        card_id: int,
        file_id: str,
        local_path: str,
        filename: str,
        caption: str,
        rarity: str,
        category: str,
        triggers: list[str],
        uploaded_by: int,
    ) -> "Card":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            id=card_id,
            file_id=file_id,
            local_path=local_path,
            filename=filename,
            caption=caption,
            rarity=rarity,
            category=category,
            triggers=triggers,
            enabled=True,
            created_at=now,
            updated_at=now,
            uploaded_by=uploaded_by,
        )

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_trigger(value: str) -> str:
    return " ".join(value.strip().lower().split())


def normalize_triggers(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        norm = normalize_trigger(item)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(norm)
    return result
