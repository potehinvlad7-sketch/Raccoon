from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.types import Message

from keyboards import user_gallery_nav_keyboard
from storage import (
    get_cards,
    get_user_profile,
    random_card_for_trigger,
    update_stats,
    upsert_user_profile,
)

router = Router(name="user")


def _my_gallery_caption(card: dict, idx: int, total: int) -> str:
    return (
        f"🎴 Карточка {idx}/{total}\n\n"
        f"Редкость: {card.get('rarity', '-')}\n"
        f"Категория: {card.get('category', '-')}\n\n"
        f"{card.get('caption', '')}"
    )


@router.message(Command("start"))
async def start_user(message: Message):
    upsert_user_profile(message.from_user)
    await message.answer("Привет! Пиши триггер и я покажу карточку 🦝")


@router.message(Command("mygallery"))
async def my_gallery(message: Message):
    profile = upsert_user_profile(message.from_user)
    found_ids = profile.get("found_cards", [])
    if not found_ids:
        await message.answer("Пока пусто. Напиши триггер вроде «енотя» или «лися», чтобы найти первую карточку.")
        return

    cards = get_cards()
    cards_map = {c["id"]: c for c in cards}
    found_cards = [cards_map[cid] for cid in found_ids if cid in cards_map]
    rarity_counts: dict[str, int] = {}
    for card in found_cards:
        rarity = card.get("rarity", "-")
        rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1

    rarity_text = "\n".join(f"- {rarity}: {count}" for rarity, count in sorted(rarity_counts.items()))
    summary = (
        f"🖼 Личная галерея\n\n"
        f"Уникальных карточек: {len(found_cards)}\n"
        f"Всего карточек в системе: {len(cards)}\n"
        f"Всего выпадений: {profile.get('total_finds', 0)}\n\n"
        f"По редкостям:\n{rarity_text}"
    )
    first_card = found_cards[0]
    await message.answer_photo(
        photo=first_card["file_id"],
        caption=f"{summary}\n\n{_my_gallery_caption(first_card, 1, len(found_cards))}",
        reply_markup=user_gallery_nav_keyboard(first_card["id"]),
    )


@router.message(F.text)
async def trigger_card(message: Message):
    text = message.text or ""
    card = random_card_for_trigger(text)
    if not card:
        return

    caption = (
        f"🎴 {card.get('category', 'Карточка')}-карточка\n\n"
        f"Редкость: {card.get('rarity', '-')}\n"
        f"Категория: {card.get('category', '-')}\n\n"
        f"{card.get('caption', '')}"
    )
    await message.answer_photo(photo=card["file_id"], caption=caption)
    update_stats(card_id=card["id"], trigger=text, user_id=message.from_user.id)
    upsert_user_profile(message.from_user, found_card_id=card["id"])


@router.callback_query(F.data.startswith("mygallery:"))
async def my_gallery_nav(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id) or upsert_user_profile(callback.from_user)
    found_ids = profile.get("found_cards", [])
    if not found_ids:
        await callback.answer("Пока нет найденных карточек")
        return

    cards_map = {c["id"]: c for c in get_cards()}
    found_cards = [cards_map[cid] for cid in found_ids if cid in cards_map]
    if not found_cards:
        await callback.answer("Карточки не найдены")
        return

    parts = callback.data.split(":")
    action = parts[1]
    if action == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Закрыто")
        return

    card_id = int(parts[2])
    ids = [c["id"] for c in found_cards]
    idx0 = ids.index(card_id) if card_id in ids else 0
    if action == "prev":
        idx0 = (idx0 - 1) % len(found_cards)
    elif action == "next":
        idx0 = (idx0 + 1) % len(found_cards)

    card = found_cards[idx0]
    await callback.message.edit_media(
        media=InputMediaPhoto(media=card["file_id"], caption=_my_gallery_caption(card, idx0 + 1, len(found_cards))),
        reply_markup=user_gallery_nav_keyboard(card["id"]),
    )
    await callback.answer()
