from __future__ import annotations

from aiogram import F, Router
import logging
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InputMediaDocument, InputMediaPhoto
from aiogram.types import Message

from config import Settings
from keyboards import user_gallery_nav_keyboard
from storage import get_cards, get_user_profile, random_card_for_trigger, update_stats, upsert_user_profile

router = Router(name="user")

def _is_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.admin_ids

def _my_gallery_caption(card: dict, idx: int, total: int) -> str:
    return f"🎴 Карточка {idx}/{total}\n\nРедкость: {card.get('rarity', '-')}\nКатегория: {card.get('category', '-')}\n\n{card.get('caption', '')}"

@router.message(Command("start"))
async def start_user(message: Message):
    upsert_user_profile(message.from_user)
    await message.answer("Привет! Пиши триггер и я покажу карточку 🦝")

@router.message(Command("help"))
async def help_cmd(message: Message, settings: Settings):
    text=("📘 Помощь по боту\n\n/start — начать работу с ботом\n/help — помощь\n/mygallery — моя галерея найденных карточек\n\nКак получать карточки:\nНапиши триггер вроде: «енотя», «енот», «лися», «лисёнок», «neko», «fox», «raccoon».\nКарточки выпадают случайно по триггерам.\nЕсли карточка выпала, она сохраняется в личную галерею.")
    if _is_admin(message.from_user.id, settings):
        text += "\n\n🛠 Админ-команды:\n/raccoonadmin — админка Еноти\n/galleryadmin — админка Лиси\n/addcard — добавить обычную карточку\n/addraccoon — добавить карточку Еноти\n/addfox — добавить карточку Лиси\n/broadcast — рассылка всем пользователям\n/userstats — статистика пользователей\n/cards — список карточек\n/cancel — отменить текущий режим"
    await message.answer(text)

@router.message(Command("mygallery"))
async def my_gallery(message: Message):
    profile = upsert_user_profile(message.from_user)
    found_ids = profile.get("found_cards", [])
    if not found_ids: return await message.answer("Пока пусто. Напиши триггер вроде «енотя» или «лися», чтобы найти первую карточку.")
    cards_map = {c["id"]: c for c in get_cards()}
    found_cards = [cards_map[cid] for cid in found_ids if cid in cards_map]
    first = found_cards[0]; caption=_my_gallery_caption(first,1,len(found_cards))
    try:
        if first.get("media_type","photo")=="document": await message.answer_document(document=first["file_id"],caption=caption,reply_markup=user_gallery_nav_keyboard(first["id"]))
        else: await message.answer_photo(photo=first["file_id"],caption=caption,reply_markup=user_gallery_nav_keyboard(first["id"]))
    except Exception:
        logging.exception('failed send mygallery card %s', first.get('id'))
        await message.answer('Не удалось отправить карточку. Возможно, файл повреждён.')

@router.message(F.text)
async def trigger_card(message: Message):
    card = random_card_for_trigger(message.text or "")
    if not card: return
    caption=f"🎴 {card.get('category', 'Карточка')}-карточка\n\nРедкость: {card.get('rarity', '-')}\nКатегория: {card.get('category', '-')}\n\n{card.get('caption', '')}"
    try:
        if card.get("media_type","photo")=="document": await message.answer_document(document=card["file_id"], caption=caption)
        else: await message.answer_photo(photo=card["file_id"], caption=caption)
    except Exception:
        logging.exception('failed send trigger card %s', card.get('id'))
        return await message.answer(f'Не удалось отправить карточку #{card.get("id")}. Возможно, file_id устарел или повреждён.')
    update_stats(card_id=card["id"], trigger=message.text or "", user_id=message.from_user.id); upsert_user_profile(message.from_user, found_card_id=card["id"])

@router.callback_query(F.data.startswith("mygallery:"))
async def my_gallery_nav(callback: CallbackQuery):
    profile = get_user_profile(callback.from_user.id) or upsert_user_profile(callback.from_user)
    found_ids = profile.get("found_cards", [])
    cards_map = {c["id"]: c for c in get_cards()}
    found_cards = [cards_map[cid] for cid in found_ids if cid in cards_map]
    if not found_cards: return await callback.answer("Пока нет найденных карточек")
    p=callback.data.split(":")
    if p[1]=="back":
        await callback.message.edit_reply_markup(reply_markup=None); return await callback.answer("Закрыто")
    ids=[c["id"] for c in found_cards]; idx=ids.index(int(p[2])) if int(p[2]) in ids else 0
    idx=(idx-1)%len(found_cards) if p[1]=="prev" else (idx+1)%len(found_cards)
    card=found_cards[idx]
    media = InputMediaDocument(media=card["file_id"], caption=_my_gallery_caption(card, idx+1, len(found_cards))) if card.get("media_type","photo")=="document" else InputMediaPhoto(media=card["file_id"], caption=_my_gallery_caption(card, idx+1, len(found_cards)))
    await callback.message.edit_media(media=media, reply_markup=user_gallery_nav_keyboard(card["id"])); await callback.answer()
