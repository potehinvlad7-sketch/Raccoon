from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class Settings:
    bot_token: str
    proxy_url: str | None
    admin_ids: list[int]



def _parse_admin_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    result: list[int] = []
    for part in raw.split(','):
        value = part.strip()
        if not value:
            continue
        if not value.isdigit():
            raise ValueError(f"ADMIN_IDS содержит нечисловой id: {value}")
        result.append(int(value))
    return result



def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Добавьте BOT_TOKEN в .env (пример: BOT_TOKEN=123456:ABCDEF)."
        )

    proxy_url = os.getenv("PROXY_URL", "").strip() or None
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS"))

    return Settings(bot_token=bot_token, proxy_url=proxy_url, admin_ids=admin_ids)
