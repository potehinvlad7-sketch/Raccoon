from __future__ import annotations

import json
from pathlib import Path
from random import choice

from models import Card, normalize_trigger, normalize_triggers

DATA_DIR = Path("data")
CARDS_PATH = DATA_DIR / "cards.json"
TRIGGERS_PATH = DATA_DIR / "triggers.json"
STATS_PATH = DATA_DIR / "stats.json"


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for p, default in [
        (CARDS_PATH, []),
        (TRIGGERS_PATH, {}),
        (STATS_PATH, {"card_hits": {}, "trigger_hits": {}, "users": {}}),
    ]:
        if not p.exists():
            p.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_cards() -> list[dict]:
    return _read_json(CARDS_PATH, [])


def save_cards(cards: list[dict]) -> None:
    _write_json(CARDS_PATH, cards)


def next_card_id(cards: list[dict]) -> int:
    return max((c["id"] for c in cards), default=0) + 1


def add_card(card: Card) -> None:
    cards = get_cards()
    cards.append(card.to_dict())
    save_cards(cards)
    rebuild_triggers(cards)


def rebuild_triggers(cards: list[dict] | None = None) -> None:
    if cards is None:
        cards = get_cards()
    mapping: dict[str, list[int]] = {}
    for card in cards:
        if not card.get("enabled", True):
            continue
        for trig in normalize_triggers(card.get("triggers", [])):
            mapping.setdefault(trig, []).append(card["id"])
    _write_json(TRIGGERS_PATH, mapping)


def find_card_by_id(card_id: int) -> dict | None:
    for card in get_cards():
        if card["id"] == card_id:
            return card
    return None


def find_cards_by_trigger(text: str) -> list[dict]:
    trig = normalize_trigger(text)
    if not trig:
        return []
    cards = get_cards()
    matched = []
    for card in cards:
        if not card.get("enabled", True):
            continue
        norms = normalize_triggers(card.get("triggers", []))
        if trig in norms:
            matched.append(card)
    return matched


def random_card_for_trigger(text: str) -> dict | None:
    cards = find_cards_by_trigger(text)
    return choice(cards) if cards else None


def update_stats(card_id: int, trigger: str, user_id: int) -> None:
    stats = _read_json(STATS_PATH, {"card_hits": {}, "trigger_hits": {}, "users": {}})
    cid = str(card_id)
    trig = normalize_trigger(trigger)
    uid = str(user_id)

    stats.setdefault("card_hits", {})
    stats.setdefault("trigger_hits", {})
    stats.setdefault("users", {})

    stats["card_hits"][cid] = stats["card_hits"].get(cid, 0) + 1
    stats["trigger_hits"][trig] = stats["trigger_hits"].get(trig, 0) + 1
    stats["users"][uid] = stats["users"].get(uid, 0) + 1

    _write_json(STATS_PATH, stats)
