from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from config import Settings
from keyboards import add_category_keyboard, broadcast_confirm_keyboard, card_settings_keyboard, gallery_nav_keyboard
from models import (
    Card,
    FOX_DEFAULT_CATEGORY,
    FOX_DEFAULT_TRIGGERS,
    RACCOON_DEFAULT_CATEGORY,
    RACCOON_DEFAULT_TRIGGERS,
    RARITIES,
    normalize_triggers,
)
from storage import (
    add_card,
    build_user_stats_report,
    find_card_by_id,
    get_cards,
    get_cards_by_category,
    get_users,
    next_card_id,
)

router = Router(name="admin")


class AddCardState(StatesGroup):
    waiting_image = State()
    waiting_caption = State()
    waiting_rarity = State()
    waiting_category = State()
    waiting_triggers = State()


class BroadcastState(StatesGroup):
    waiting_content = State()
    waiting_confirmation = State()


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


def _defaults_from_mode(mode: str) -> tuple[str, list[str]]:
    if mode == "raccoon":
        return RACCOON_DEFAULT_CATEGORY, RACCOON_DEFAULT_TRIGGERS
    if mode == "fox":
        return FOX_DEFAULT_CATEGORY, FOX_DEFAULT_TRIGGERS
    return "Uncategorized", []


def _gallery_scope(command_text: str | None) -> str:
    if not command_text:
        return "all"
    txt = command_text.split()[0]
    if txt.startswith("/raccoonadmin"):
        return "raccoon"
    if txt.startswith("/galleryadmin"):
        return "fox"
    return "all"


def _cards_by_scope(scope: str) -> list[dict]:
    if scope == "raccoon":
        return get_cards_by_category(RACCOON_DEFAULT_CATEGORY)
    if scope == "fox":
        return get_cards_by_category(FOX_DEFAULT_CATEGORY)
    return get_cards()


async def _show_gallery(message: Message, scope: str) -> None:
    cards = _cards_by_scope(scope)
    if not cards:
        await message.answer("В этой категории пока нет карточек.", reply_markup=add_category_keyboard())
        return
    card = cards[0]
    await message.answer_photo(
        photo=card["file_id"],
        caption=_card_text(card, 1, len(cards)),
        reply_markup=gallery_nav_keyboard(card["id"], scope=scope),
    )


@router.message(Command("start", "ping", "raccoonadmin", "galleryadmin", "cards"))
async def admin_entry(message: Message, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    if message.text and message.text.startswith("/ping"):
        await message.answer("pong")
        return
    scope = _gallery_scope(message.text)
    await _show_gallery(message, scope)


async def _begin_addcard(message: Message, state: FSMContext, mode: str) -> None:
    await state.clear()
    category, triggers = _defaults_from_mode(mode)
    await state.update_data(add_mode=mode, default_category=category, default_triggers=triggers)
    await state.set_state(AddCardState.waiting_image)
    await message.answer("Отправьте картинку (photo или document-изображение).")


@router.message(Command("addcard", "addraccoon", "addfox"))
async def addcard(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    cmd = (message.text or "").split()[0]
    mode = "all"
    if cmd.startswith("/addraccoon"):
        mode = "raccoon"
    elif cmd.startswith("/addfox"):
        mode = "fox"
    await _begin_addcard(message, state, mode)


@router.callback_query(F.data.in_({"quickadd:raccoon", "quickadd:fox"}))
async def quickadd(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not _is_admin(callback.from_user.id, settings):
        return
    mode = "raccoon" if callback.data.endswith("raccoon") else "fox"
    await _begin_addcard(callback.message, state, mode)
    await callback.answer()


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
    await message.answer("Введите категорию или '-' для значения по умолчанию:")


@router.message(AddCardState.waiting_category)
async def addcard_category(message: Message, state: FSMContext):
    data = await state.get_data()
    default_category = data.get("default_category", "Uncategorized")
    category = (message.text or "").strip()
    if category == "-" or not category:
        category = default_category
    await state.update_data(category=category)
    await state.set_state(AddCardState.waiting_triggers)
    await message.answer("Введите триггеры через запятую или '-' для дефолтных:")


@router.message(AddCardState.waiting_triggers)
async def addcard_triggers(message: Message, state: FSMContext):
    data = await state.get_data()
    txt = (message.text or "").strip()
    if txt == "-" or not txt:
        triggers = normalize_triggers(data.get("default_triggers", []))
    else:
        triggers = normalize_triggers(txt.split(","))

    card = Card.create(
        card_id=data["id"],
        file_id=data["file_id"],
        local_path=data["local_path"],
        filename=data["filename"],
        caption=data.get("caption", ""),
        rarity=data.get("rarity", "Common"),
        category=data.get("category", "Uncategorized"),
        triggers=triggers,
        uploaded_by=message.from_user.id,
    )
    add_card(card)
    await state.clear()
    await message.answer("Карточка добавлена.")

    scope = data.get("add_mode", "all")
    cards = _cards_by_scope(scope)
    idx = next(i for i, c in enumerate(cards, start=1) if c["id"] == card.id)
    created = find_card_by_id(card.id)
    await message.answer_photo(
        photo=created["file_id"],
        caption=_card_text(created, idx, len(cards)),
        reply_markup=gallery_nav_keyboard(card.id, scope=scope),
    )


@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    await state.clear()
    await state.set_state(BroadcastState.waiting_content)
    await message.answer("Отправьте сообщение для рассылки (текст, photo или document-изображение).")


@router.message(BroadcastState.waiting_content)
async def broadcast_collect(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return

    payload: dict = {}
    if message.photo:
        payload = {"kind": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""}
        await message.answer_photo(
            photo=payload["file_id"], caption=payload["caption"] or "(без подписи)", reply_markup=broadcast_confirm_keyboard()
        )
    elif message.document:
        mime = (message.document.mime_type or "").lower()
        if not mime.startswith("image/"):
            await message.answer("Для document в рассылке поддерживаются только изображения.")
            return
        payload = {"kind": "document", "file_id": message.document.file_id, "caption": message.caption or ""}
        await message.answer_document(
            document=payload["file_id"], caption=payload["caption"] or "(без подписи)", reply_markup=broadcast_confirm_keyboard()
        )
    elif message.text:
        payload = {"kind": "text", "text": message.text}
        await message.answer(f"Предпросмотр:\n\n{payload['text']}", reply_markup=broadcast_confirm_keyboard())
    else:
        await message.answer("Поддерживается текст, photo или document-изображение.")
        return

    await state.update_data(broadcast_payload=payload)
    await state.set_state(BroadcastState.waiting_confirmation)


@router.callback_query(F.data.in_({"broadcast:confirm", "broadcast:cancel"}))
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not _is_admin(callback.from_user.id, settings):
        return
    if callback.data == "broadcast:cancel":
        await state.clear()
        await callback.message.answer("Рассылка отменена.")
        await callback.answer()
        return

    data = await state.get_data()
    payload = data.get("broadcast_payload")
    if not payload:
        await callback.message.answer("Нет данных для рассылки. Запустите /broadcast заново.")
        await state.clear()
        await callback.answer()
        return

    success = 0
    failed = 0
    users = get_users()
    for user in users:
        uid = user.get("user_id")
        if not uid:
            continue
        try:
            if payload["kind"] == "text":
                await callback.bot.send_message(uid, payload["text"])
            elif payload["kind"] == "photo":
                await callback.bot.send_photo(uid, payload["file_id"], caption=payload.get("caption", ""))
            else:
                await callback.bot.send_document(uid, payload["file_id"], caption=payload.get("caption", ""))
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.07)

    await state.clear()
    await callback.message.answer(f"Рассылка завершена. Успешно: {success}. Ошибок: {failed}.")
    await callback.answer()


@router.message(Command("userstats"))
async def userstats(message: Message, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    report = build_user_stats_report()

    top_users = "\n".join(
        f"{i}. {u.get('first_name') or u.get('username') or u.get('user_id')} — {u.get('total_finds', 0)}"
        for i, u in enumerate(report["top_users"], start=1)
    ) or "нет данных"

    top_cards = "\n".join(f"{i}. Карточка #{cid} — {count}" for i, (cid, count) in enumerate(report["top_cards"], start=1)) or "нет данных"

    text = (
        f"Всего пользователей: {report['total_users']}\n"
        f"Активных (30 дней): {report['active_users']}\n"
        f"Всего выпадений: {report['total_finds']}\n"
        f"Уникальных найденных карточек: {report['unique_found_cards']}\n\n"
        f"Топ 10 пользователей:\n{top_users}\n\n"
        f"Топ 10 карточек:\n{top_cards}"
    )
    await message.answer(text)


@router.callback_query(F.data.startswith("gallery:settings:"))
async def gallery_settings(callback: CallbackQuery, settings: Settings):
    if not _is_admin(callback.from_user.id, settings):
        return
    _, _, card_id, scope = callback.data.split(":")
    await callback.message.edit_reply_markup(reply_markup=card_settings_keyboard(int(card_id), scope=scope))
    await callback.answer()


@router.callback_query(F.data.startswith("gallery:"))
async def gallery_nav(callback: CallbackQuery, settings: Settings):
    if not _is_admin(callback.from_user.id, settings):
        return
    parts = callback.data.split(":")
    action = parts[1]
    scope = parts[3] if len(parts) > 3 else "all"

    cards = _cards_by_scope(scope)
    if not cards:
        await callback.message.answer("В этой категории пока нет карточек.", reply_markup=add_category_keyboard())
        await callback.answer()
        return

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
        reply_markup=gallery_nav_keyboard(card["id"], scope=scope),
    )
    await callback.answer()
