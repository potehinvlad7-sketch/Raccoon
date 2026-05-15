from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

RARITIES = ["Common", "Rare", "Epic", "Legendary", "Mythic"]
RACCOON_DEFAULT_CATEGORY = "Енотя"
FOX_DEFAULT_CATEGORY = "Лися"
RACCOON_DEFAULT_TRIGGERS = ["енот", "енотя", "raccoon", "raccoon girl", "аэлита"]
FOX_DEFAULT_TRIGGERS = ["лиса", "лися", "лисёнок", "лисенок", "fox", "kitsune"]


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
    media_type: Literal["photo", "document"] = "photo"

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
        media_type: Literal["photo", "document"] = "photo",
    ) -> "Card":
        now = datetime.now(timezone.utc).isoformat()
        return cls(card_id, file_id, local_path, filename, caption, rarity, category, triggers, True, now, now, uploaded_by, media_type)

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_trigger(value: str) -> str:
    return " ".join(value.strip().lower().split()).replace("ё", "е")


def normalize_triggers(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        n = normalize_trigger(item)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
