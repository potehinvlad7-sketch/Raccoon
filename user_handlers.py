from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InputMediaDocument, InputMediaPhoto, Message

from keyboards import mygallery_nav_keyboard
from storage import (
    get_cards,
    get_user_profile,
    random_card_for_trigger,
    register_found_card,
    update_stats,
    upsert_user_profile,
)

router = Router(name="user")


@router.message(Command("start"))
async def user_start(message: Message):
    upsert_user_profile(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer("Привет! Напиши триггер, чтобы получить карточку.")


@router.message(Command("mygallery"))
async def mygallery(message: Message):
    profile = get_user_profile(message.from_user.id)
    if not profile or not profile.get("found_cards"):
        await message.answer("Пока пусто. Напиши триггер вроде «енотя» или «лися», чтобы найти первую карточку.")
        return

    cards_map = {c["id"]: c for c in get_cards() if c.get("enabled", True)}
    found_enabled = [cards_map[cid] for cid in profile.get("found_cards", []) if cid in cards_map]
    if not found_enabled:
        await message.answer("Пока пусто. Напиши триггер вроде «енотя» или «лися», чтобы найти первую карточку.")
        return

    rarity_count: dict[str, int] = {}
    for c in found_enabled:
        rarity = c.get("rarity", "Unknown")
        rarity_count[rarity] = rarity_count.get(rarity, 0) + 1

    rarity_text = "\n".join(f"- {k}: {v}" for k, v in rarity_count.items())
    summary = (
        f"Моя галерея\n\n"
        f"Уникальных найдено: {len(found_enabled)}\n"
        f"Всего карточек в системе: {len(cards_map)}\n"
        f"Всего выпадений: {profile.get('total_finds', 0)}\n\n"
        f"По редкостям:\n{rarity_text}"
    )
    first = found_enabled[0]
    if first.get("media_type", "photo") == "document":
        await message.answer_document(
            document=first["file_id"],
            caption=summary + f"\n\nКарточка 1/{len(found_enabled)}: {first.get('caption', '')}",
            reply_markup=mygallery_nav_keyboard(0),
        )
    else:
        await message.answer_photo(
            photo=first["file_id"],
            caption=summary + f"\n\nКарточка 1/{len(found_enabled)}: {first.get('caption', '')}",
            reply_markup=mygallery_nav_keyboard(0),
        )


@router.callback_query(F.data.startswith("mygallery:"))
async def mygallery_nav(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id)
    if not profile:
        await callback.answer("Нет данных")
        return

    cards_map = {c["id"]: c for c in get_cards() if c.get("enabled", True)}
    found_enabled = [cards_map[cid] for cid in profile.get("found_cards", []) if cid in cards_map]
    if not found_enabled:
        await callback.answer("Пусто")
        return

    _, action, idx_str = callback.data.split(":")
    idx = int(idx_str)
    if action == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Закрыто")
        return
    if action == "prev":
        idx = (idx - 1) % len(found_enabled)
    elif action == "next":
        idx = (idx + 1) % len(found_enabled)

    card = found_enabled[idx]
    caption=(
        f"Моя галерея\n"
        f"Карточка {idx + 1}/{len(found_enabled)}\n"
        f"Редкость: {card.get('rarity', '-')}\n"
        f"Категория: {card.get('category', '-')}\n\n"
        f"{card.get('caption', '')}"
    )
    media = InputMediaDocument(media=card["file_id"], caption=caption) if card.get("media_type", "photo") == "document" else InputMediaPhoto(media=card["file_id"], caption=caption)
    await callback.message.edit_media(media=media, reply_markup=mygallery_nav_keyboard(idx))
    await callback.answer()


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
    if card.get("media_type", "photo") == "document":
        await message.answer_document(document=card["file_id"], caption=caption)
    else:
        await message.answer_photo(photo=card["file_id"], caption=caption)
    update_stats(card_id=card["id"], trigger=text, user_id=message.from_user.id)
    register_found_card(message.from_user.id, message.from_user.username, message.from_user.first_name, card["id"])
