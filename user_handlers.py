from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from storage import random_card_for_trigger, update_stats

router = Router(name="user")


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
