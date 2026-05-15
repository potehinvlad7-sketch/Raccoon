from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import choice

from models import Card, normalize_trigger, normalize_triggers

DATA_DIR = Path("data")
CARDS_PATH = DATA_DIR / "cards.json"
TRIGGERS_PATH = DATA_DIR / "triggers.json"
STATS_PATH = DATA_DIR / "stats.json"
USERS_PATH = DATA_DIR / "users.json"


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for p, default in [
        (CARDS_PATH, []),
        (TRIGGERS_PATH, {}),
        (STATS_PATH, {"card_hits": {}, "trigger_hits": {}, "users": {}}),
        (USERS_PATH, []),
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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_cards() -> list[dict]:
    return _read_json(CARDS_PATH, [])


def get_cards_by_category(category: str) -> list[dict]:
    return [c for c in get_cards() if c.get("category") == category]


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
    matched = []
    for card in get_cards():
        if not card.get("enabled", True):
            continue
        if trig in normalize_triggers(card.get("triggers", [])):
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


def get_users() -> list[dict]:
    return _read_json(USERS_PATH, [])


def save_users(users: list[dict]) -> None:
    _write_json(USERS_PATH, users)


def upsert_user_profile(user_id: int, username: str | None, first_name: str | None) -> None:
    users = get_users()
    current = now_iso()
    for user in users:
        if user.get("user_id") == user_id:
            user["username"] = username or user.get("username", "")
            user["first_name"] = first_name or user.get("first_name", "")
            user["last_seen"] = current
            save_users(users)
            return

    users.append(
        {
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "found_cards": [],
            "total_finds": 0,
            "first_seen": current,
            "last_seen": current,
        }
    )
    save_users(users)


def register_found_card(user_id: int, username: str | None, first_name: str | None, card_id: int) -> None:
    upsert_user_profile(user_id, username, first_name)
    users = get_users()
    current = now_iso()
    for user in users:
        if user.get("user_id") != user_id:
            continue
        found = set(user.get("found_cards", []))
        found.add(card_id)
        user["found_cards"] = sorted(found)
        user["total_finds"] = int(user.get("total_finds", 0)) + 1
        user["last_seen"] = current
        break
    save_users(users)


def get_user_profile(user_id: int) -> dict | None:
    for user in get_users():
        if user.get("user_id") == user_id:
            return user
    return None


def build_user_stats_report() -> dict:
    users = get_users()
    stats = _read_json(STATS_PATH, {"card_hits": {}})
    card_hits = stats.get("card_hits", {})

    all_found_cards: set[int] = set()
    for u in users:
        all_found_cards.update(u.get("found_cards", []))

    active_since = datetime.now(timezone.utc) - timedelta(days=30)
    active_users = 0
    for u in users:
        try:
            last_seen = datetime.fromisoformat(u.get("last_seen", ""))
            if last_seen >= active_since:
                active_users += 1
        except ValueError:
            continue

    top_users = sorted(users, key=lambda x: int(x.get("total_finds", 0)), reverse=True)[:10]
    top_cards = sorted(card_hits.items(), key=lambda kv: kv[1], reverse=True)[:10]

    total_finds = sum(int(u.get("total_finds", 0)) for u in users)
    return {
        "total_users": len(users),
        "active_users": active_users,
        "unique_found_cards": len(all_found_cards),
        "total_finds": total_finds,
        "top_users": top_users,
        "top_cards": top_cards,
    }
