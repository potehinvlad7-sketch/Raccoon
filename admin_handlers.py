from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaDocument, InputMediaPhoto, Message

from config import Settings
from keyboards import add_category_keyboard, broadcast_confirm_keyboard, card_settings_keyboard, gallery_nav_keyboard
from models import FOX_DEFAULT_CATEGORY, FOX_DEFAULT_TRIGGERS, RACCOON_DEFAULT_CATEGORY, RACCOON_DEFAULT_TRIGGERS, RARITIES, Card, normalize_triggers
from storage import add_card, build_user_stats_report, delete_card, find_card_by_id, get_cards, get_cards_by_category, get_users, next_card_id, update_card

router = Router(name="admin")


class AddCardState(StatesGroup):
    waiting_image = State()
    waiting_caption = State()
    waiting_rarity = State()
    waiting_category = State()
    waiting_triggers = State()


class EditCardState(StatesGroup):
    waiting_caption = State()
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
    return (f"Арт {idx}/{total}\nФайл: {card.get('filename','-')}\n\nПодпись: {card.get('caption','')}\n"
            f"Редкость: {card.get('rarity','-')}\nКатегория: {card.get('category','-')}\nТриггеры: {trigs}\nСтатус: {status}")


def _defaults_from_mode(mode: str) -> tuple[str, list[str]]:
    if mode == "raccoon":
        return RACCOON_DEFAULT_CATEGORY, RACCOON_DEFAULT_TRIGGERS
    if mode == "fox":
        return FOX_DEFAULT_CATEGORY, FOX_DEFAULT_TRIGGERS
    return "Uncategorized", []


def _gallery_scope(command_text: str | None) -> str:
    txt = (command_text or "").split()[0] if command_text else ""
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


def _media_type(card: dict) -> str:
    return card.get("media_type", "photo")


async def _send_card(message: Message, card: dict, idx: int, total: int, scope: str):
    if _media_type(card) == "document":
        await message.answer_document(card["file_id"], caption=_card_text(card, idx, total), reply_markup=gallery_nav_keyboard(card["id"], scope))
    else:
        await message.answer_photo(card["file_id"], caption=_card_text(card, idx, total), reply_markup=gallery_nav_keyboard(card["id"], scope))


async def _show_gallery(message: Message, scope: str) -> None:
    cards = _cards_by_scope(scope)
    if not cards:
        await message.answer("В этой категории пока нет карточек.", reply_markup=add_category_keyboard())
        return
    await _send_card(message, cards[0], 1, len(cards), scope)


@router.message(Command("start", "ping", "raccoonadmin", "galleryadmin", "cards"))
async def admin_entry(message: Message, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    if (message.text or "").startswith("/ping"):
        await message.answer("pong")
        return
    await _show_gallery(message, _gallery_scope(message.text))


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
    mode = "raccoon" if cmd.startswith("/addraccoon") else "fox" if cmd.startswith("/addfox") else "all"
    await _begin_addcard(message, state, mode)


@router.callback_query(F.data.in_({"quickadd:raccoon", "quickadd:fox"}))
async def quickadd(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not _is_admin(callback.from_user.id, settings):
        return
    await _begin_addcard(callback.message, state, "raccoon" if callback.data.endswith("raccoon") else "fox")
    await callback.answer()


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext, settings: Settings):
    if _is_admin(message.from_user.id, settings):
        await state.clear()
        await message.answer("Действие отменено.")


@router.message(AddCardState.waiting_image)
async def addcard_image(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings):
        return
    media_type = "photo"
    if message.photo:
        file_id = message.photo[-1].file_id
        tg_file = await message.bot.get_file(file_id)
        filename = Path(tg_file.file_path).name
    elif message.document:
        if not (message.document.mime_type or "").lower().startswith("image/"):
            await message.answer("Document должен быть изображением.")
            return
        media_type = "document"
        file_id = message.document.file_id
        tg_file = await message.bot.get_file(file_id)
        filename = message.document.file_name or Path(tg_file.file_path).name
    else:
        await message.answer("Нужно отправить photo или document-изображение.")
        return

    card_id = next_card_id(get_cards())
    local_path = Path("arts") / f"{card_id}{Path(filename).suffix or '.jpg'}"
    local_path.parent.mkdir(exist_ok=True)
    await message.bot.download_file(tg_file.file_path, destination=str(local_path))
    await state.update_data(file_id=file_id, filename=filename, local_path=str(local_path), id=card_id, media_type=media_type)
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
    category = (message.text or "").strip()
    await state.update_data(category=data.get("default_category", "Uncategorized") if category in {"", "-"} else category)
    await state.set_state(AddCardState.waiting_triggers)
    await message.answer("Введите триггеры через запятую или '-' для дефолтных:")


@router.message(AddCardState.waiting_triggers)
async def addcard_triggers(message: Message, state: FSMContext):
    data = await state.get_data()
    txt = (message.text or "").strip()
    triggers = normalize_triggers(data.get("default_triggers", [])) if txt in {"", "-"} else normalize_triggers(txt.split(","))
    card = Card.create(
        card_id=data["id"], file_id=data["file_id"], local_path=data["local_path"], filename=data["filename"],
        caption=data.get("caption", ""), rarity=data.get("rarity", "Common"), category=data.get("category", "Uncategorized"),
        triggers=triggers, uploaded_by=message.from_user.id, media_type=data.get("media_type", "photo")
    )
    add_card(card)
    await state.clear()
    await message.answer("Карточка добавлена.")
    cards = _cards_by_scope(data.get("add_mode", "all"))
    idx = next(i for i, c in enumerate(cards, start=1) if c["id"] == card.id)
    await _send_card(message, find_card_by_id(card.id), idx, len(cards), data.get("add_mode", "all"))


@router.callback_query(F.data.startswith("gallery:settings:"))
async def gallery_settings(callback: CallbackQuery, settings: Settings):
    if not _is_admin(callback.from_user.id, settings):
        return
    _, _, card_id, scope = callback.data.split(":")
    await callback.message.edit_reply_markup(reply_markup=card_settings_keyboard(int(card_id), scope))
    await callback.answer()


@router.callback_query(F.data.startswith("edit:"))
async def edit_actions(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not _is_admin(callback.from_user.id, settings): return
    _, action, card_id, *rest = callback.data.split(":")
    card = find_card_by_id(int(card_id))
    if not card:
        await callback.answer("Карточка не найдена", show_alert=True); return
    scope = rest[0] if rest else "all"
    if action == "caption":
        await state.set_state(EditCardState.waiting_caption); await state.update_data(edit_card_id=int(card_id), edit_scope=scope)
        await callback.message.answer("Введите новую подпись:")
    elif action == "category":
        await state.set_state(EditCardState.waiting_category); await state.update_data(edit_card_id=int(card_id), edit_scope=scope)
        await callback.message.answer("Введите новую категорию:")
    elif action == "triggers":
        await state.set_state(EditCardState.waiting_triggers); await state.update_data(edit_card_id=int(card_id), edit_scope=scope)
        await callback.message.answer("Введите новые триггеры через запятую:")
    elif action == "rarity":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=r, callback_data=f"setrarity:{card_id}:{r}:{scope}")] for r in RARITIES])
        await callback.message.answer("Выберите редкость:", reply_markup=kb)
    elif action == "toggle":
        card["enabled"] = not card.get("enabled", True)
        update_card(card)
        await callback.message.answer("Статус обновлен.")
    elif action == "delete":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Подтвердить удаление", callback_data=f"confirmdelete:{card_id}:{scope}")],[InlineKeyboardButton(text="❌ Отмена", callback_data=f"gallery:show:{card_id}:{scope}")]])
        await callback.message.answer("Удалить карточку?", reply_markup=kb)
    await callback.answer()


@router.message(EditCardState.waiting_caption)
async def edit_caption_input(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    data = await state.get_data(); card = find_card_by_id(data["edit_card_id"])
    if not card: await message.answer("Карточка не найдена."); await state.clear(); return
    card["caption"] = message.text or ""; update_card(card); await state.clear(); await message.answer("Подпись обновлена.")


@router.message(EditCardState.waiting_category)
async def edit_category_input(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    data = await state.get_data(); card = find_card_by_id(data["edit_card_id"])
    if not card: await message.answer("Карточка не найдена."); await state.clear(); return
    card["category"] = (message.text or "").strip(); update_card(card); await state.clear(); await message.answer("Категория обновлена.")


@router.message(EditCardState.waiting_triggers)
async def edit_triggers_input(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    data = await state.get_data(); card = find_card_by_id(data["edit_card_id"])
    if not card: await message.answer("Карточка не найдена."); await state.clear(); return
    card["triggers"] = normalize_triggers((message.text or "").split(",")); update_card(card); await state.clear(); await message.answer("Триггеры обновлены.")


@router.callback_query(F.data.startswith("setrarity:"))
async def set_rarity(callback: CallbackQuery, settings: Settings):
    if not _is_admin(callback.from_user.id, settings): return
    _, card_id, rarity, _scope = callback.data.split(":")
    card = find_card_by_id(int(card_id))
    if not card: await callback.answer("Карточка не найдена", show_alert=True); return
    card["rarity"] = rarity; update_card(card); await callback.answer("Редкость обновлена")


@router.callback_query(F.data.startswith("confirmdelete:"))
async def confirm_delete(callback: CallbackQuery, settings: Settings):
    if not _is_admin(callback.from_user.id, settings): return
    _, card_id, _scope = callback.data.split(":")
    ok = delete_card(int(card_id))
    await callback.answer("Удалено" if ok else "Карточка не найдена", show_alert=not ok)


@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    await state.clear(); await state.set_state(BroadcastState.waiting_content)
    await message.answer("Отправьте сообщение для рассылки (текст, photo или document-изображение).")


@router.message(BroadcastState.waiting_content)
async def broadcast_collect(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    payload = {}
    if message.photo:
        payload = {"kind": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""}
        await message.answer_photo(payload["file_id"], caption=payload["caption"] or "(без подписи)", reply_markup=broadcast_confirm_keyboard())
    elif message.document and (message.document.mime_type or "").lower().startswith("image/"):
        payload = {"kind": "document", "file_id": message.document.file_id, "caption": message.caption or ""}
        await message.answer_document(payload["file_id"], caption=payload["caption"] or "(без подписи)", reply_markup=broadcast_confirm_keyboard())
    elif message.text:
        payload = {"kind": "text", "text": message.text}
        await message.answer(f"Предпросмотр:\n\n{payload['text']}", reply_markup=broadcast_confirm_keyboard())
    else:
        await message.answer("Поддерживается текст, photo или document-изображение."); return
    await state.update_data(broadcast_payload=payload); await state.set_state(BroadcastState.waiting_confirmation)


@router.callback_query(F.data.in_({"broadcast:confirm", "broadcast:cancel"}))
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not _is_admin(callback.from_user.id, settings): return
    if callback.data == "broadcast:cancel":
        await state.clear(); await callback.message.answer("Рассылка отменена."); await callback.answer(); return
    data = await state.get_data(); payload = data.get("broadcast_payload")
    if not payload:
        await callback.message.answer("Нет данных для рассылки. Запустите /broadcast заново."); await state.clear(); await callback.answer(); return
    success = failed = 0
    for user in get_users():
        uid = user.get("user_id")
        if not uid: continue
        try:
            if payload["kind"] == "text": await callback.bot.send_message(uid, payload["text"])
            elif payload["kind"] == "photo": await callback.bot.send_photo(uid, payload["file_id"], caption=payload.get("caption", ""))
            else: await callback.bot.send_document(uid, payload["file_id"], caption=payload.get("caption", ""))
            success += 1
        except Exception: failed += 1
        await asyncio.sleep(0.07)
    await state.clear(); await callback.message.answer(f"Рассылка завершена. Успешно: {success}. Ошибок: {failed}."); await callback.answer()


@router.message(Command("userstats"))
async def userstats(message: Message, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    r = build_user_stats_report()
    top_users = "\n".join(f"{i}. {u.get('first_name') or u.get('username') or u.get('user_id')} — {u.get('total_finds', 0)}" for i, u in enumerate(r["top_users"], 1)) or "нет данных"
    top_cards = "\n".join(f"{i}. Карточка #{cid} — {count}" for i, (cid, count) in enumerate(r["top_cards"], 1)) or "нет данных"
    await message.answer(f"Всего пользователей: {r['total_users']}\nАктивных (30 дней): {r['active_users']}\nВсего выпадений: {r['total_finds']}\nУникальных найденных карточек: {r['unique_found_cards']}\n\nТоп 10 пользователей:\n{top_users}\n\nТоп 10 карточек:\n{top_cards}")


@router.callback_query(F.data.startswith("gallery:"))
async def gallery_nav(callback: CallbackQuery, settings: Settings):
    if not _is_admin(callback.from_user.id, settings): return
    parts = callback.data.split(":"); action = parts[1]; scope = parts[3] if len(parts) > 3 else "all"
    cards = _cards_by_scope(scope)
    if not cards:
        await callback.message.answer("В этой категории пока нет карточек.", reply_markup=add_category_keyboard()); await callback.answer(); return
    if action == "back":
        await callback.message.edit_reply_markup(reply_markup=None); await callback.answer("Закрыто"); return
    card_id = int(parts[2]); ids = [c["id"] for c in cards]; idx0 = ids.index(card_id) if card_id in ids else 0
    if action == "prev": idx0 = (idx0 - 1) % len(cards)
    elif action == "next": idx0 = (idx0 + 1) % len(cards)
    card = cards[idx0]
    media = InputMediaDocument(media=card["file_id"], caption=_card_text(card, idx0 + 1, len(cards))) if _media_type(card) == "document" else InputMediaPhoto(media=card["file_id"], caption=_card_text(card, idx0 + 1, len(cards)))
    await callback.message.edit_media(media=media, reply_markup=gallery_nav_keyboard(card["id"], scope))
    await callback.answer()
