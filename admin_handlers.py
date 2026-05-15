from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from config import Settings
from keyboards import card_settings_keyboard, gallery_nav_keyboard
from models import Card, RARITIES, normalize_triggers
from storage import add_card, find_card_by_id, get_cards, next_card_id

router = Router(name="admin")


class AddCardState(StatesGroup):
    waiting_image = State()
    waiting_caption = State()
    waiting_rarity = State()
    waiting_category = State()
    waiting_triggers = State()


def _is_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.admin_ids


def _card_text(card: dict, idx: int, total: int) -> str:
    trigs = ", ".join(card.get("triggers", []))
    status = "включена" if card.get("enabled", True) else "выключена"
    return (
        f"Арт {idx}/{total}\n"
        f"Файл: {card.get('filename','-')}\n\n"
        f"Подпись: {card.get('caption','')}\n"
        f"Редкость: {card.get('rarity','-')}\n"
        f"Категория: {card.get('category','-')}\n"
        f"Триггеры: {trigs}\n"
        f"Статус: {status}"
    )


@router.message(Command("start", "ping", "raccoonadmin", "galleryadmin", "cards"))
async def admin_entry(message: Message, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    if message.text and message.text.startswith("/ping"):
        await message.answer("pong")
        return
    cards = get_cards()
    if not cards:
        await message.answer("Галерея пуста. Добавьте карточку через /addcard")
        return
    card = cards[0]
    await message.answer_photo(
        photo=card["file_id"],
        caption=_card_text(card, 1, len(cards)),
        reply_markup=gallery_nav_keyboard(card["id"]),
    )


@router.message(Command("addcard"))
async def addcard(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    await state.clear()
    await state.set_state(AddCardState.waiting_image)
    await message.answer("Отправьте картинку (photo или document-изображение).")


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    await state.clear()
    await message.answer("Действие отменено.")


@router.message(AddCardState.waiting_image)
async def addcard_image(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    file_id = None
    filename = None
    tg_file = None
    if message.photo:
        obj = message.photo[-1]
        file_id = obj.file_id
        tg_file = await message.bot.get_file(file_id)
        filename = Path(tg_file.file_path).name
    elif message.document:
        mime = (message.document.mime_type or "").lower()
        if not mime.startswith("image/"):
            await message.answer("Document должен быть изображением.")
            return
        file_id = message.document.file_id
        tg_file = await message.bot.get_file(file_id)
        filename = message.document.file_name or Path(tg_file.file_path).name
    else:
        await message.answer("Нужно отправить photo или document-изображение.")
        return

    cards = get_cards()
    card_id = next_card_id(cards)
    ext = Path(filename).suffix or ".jpg"
    local_path = Path("arts") / f"{card_id}{ext}"
    local_path.parent.mkdir(exist_ok=True)
    await message.bot.download_file(tg_file.file_path, destination=str(local_path))

    await state.update_data(file_id=file_id, filename=filename, local_path=str(local_path), id=card_id)
    await state.set_state(AddCardState.waiting_caption)
    await message.answer("Введите подпись:")


@router.message(AddCardState.waiting_caption)
async def addcard_caption(message: Message, state: FSMContext):
    await state.update_data(caption=message.text or "")
    await state.set_state(AddCardState.waiting_rarity)
    await message.answer(f"Введите редкость ({', '.join(RARITIES)}):")


@router.message(AddCardState.waiting_rarity)
async def addcard_rarity(message: Message, state: FSMContext):
    rarity = (message.text or "").strip()
    if rarity not in RARITIES:
        await message.answer(f"Недопустимая редкость. Выберите: {', '.join(RARITIES)}")
        return
    await state.update_data(rarity=rarity)
    await state.set_state(AddCardState.waiting_category)
    await message.answer("Введите категорию:")


@router.message(AddCardState.waiting_category)
async def addcard_category(message: Message, state: FSMContext):
    await state.update_data(category=(message.text or "").strip())
    await state.set_state(AddCardState.waiting_triggers)
    await message.answer("Введите триггеры через запятую:")


@router.message(AddCardState.waiting_triggers)
async def addcard_triggers(message: Message, state: FSMContext):
    triggers = normalize_triggers((message.text or "").split(","))
    data = await state.get_data()
    card = Card.create(
        card_id=data["id"],
        file_id=data["file_id"],
        local_path=data["local_path"],
        filename=data["filename"],
        caption=data.get("caption", ""),
        rarity=data.get("rarity", "Common"),
        category=data.get("category", ""),
        triggers=triggers,
        uploaded_by=message.from_user.id,
    )
    add_card(card)
    await state.clear()
    await message.answer("Карточка добавлена.")
    cards = get_cards()
    idx = next(i for i, c in enumerate(cards, start=1) if c["id"] == card.id)
    created = find_card_by_id(card.id)
    await message.answer_photo(
        photo=created["file_id"],
        caption=_card_text(created, idx, len(cards)),
        reply_markup=gallery_nav_keyboard(card.id),
    )


@router.callback_query(F.data.startswith("gallery:settings:"))
async def gallery_settings(callback: CallbackQuery, settings: Settings):
    if not _is_admin(callback.from_user.id, settings):
        return
    card_id = int(callback.data.split(":")[-1])
    await callback.message.edit_reply_markup(reply_markup=card_settings_keyboard(card_id))
    await callback.answer()


@router.callback_query(F.data.startswith("gallery:"))
async def gallery_nav(callback: CallbackQuery, settings: Settings):
    if not _is_admin(callback.from_user.id, settings):
        return
    cards = get_cards()
    if not cards:
        await callback.answer("Галерея пуста")
        return

    parts = callback.data.split(":")
    action = parts[1]
    if action == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Закрыто")
        return

    card_id = int(parts[2])
    ids = [c["id"] for c in cards]
    idx0 = ids.index(card_id) if card_id in ids else 0

    if action == "prev":
        idx0 = (idx0 - 1) % len(cards)
    elif action == "next":
        idx0 = (idx0 + 1) % len(cards)

    card = cards[idx0]
    await callback.message.edit_media(
        media=InputMediaPhoto(media=card["file_id"], caption=_card_text(card, idx0 + 1, len(cards))),
        reply_markup=gallery_nav_keyboard(card["id"]),
    )
    await callback.answer()
