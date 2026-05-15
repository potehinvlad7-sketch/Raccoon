from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaDocument, InputMediaPhoto, Message
from config import Settings
from keyboards import broadcast_confirm_keyboard, card_settings_keyboard, gallery_nav_keyboard
from models import Card, RARITIES, normalize_triggers
from storage import add_card, get_cards, get_stats, get_users, next_card_id, rebuild_triggers, save_cards
router = Router(name='admin')
class AddCardState(StatesGroup): waiting_image=State(); waiting_caption=State(); waiting_rarity=State(); waiting_category=State(); waiting_triggers=State()
class BroadcastState(StatesGroup): waiting_message=State()
def _is_admin(u,s): return u in s.admin_ids

def _card_text(card,idx,total): return f"Арт {idx}/{total}\nПодпись: {card.get('caption','')}\nРедкость: {card.get('rarity','-')}\nКатегория: {card.get('category','-')}\nТриггеры: {', '.join(card.get('triggers',[]))}"
@router.message(Command('ping','raccoonadmin','galleryadmin','cards'))
async def admin_entry(message:Message, settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    if message.text.startswith('/ping'): return await message.answer('pong')
    cards=get_cards(); cmd=message.text.split()[0]
    if cmd=='/raccoonadmin': cards=[c for c in cards if c.get('category')=='Енотя']
    if cmd=='/galleryadmin': cards=[c for c in cards if c.get('category')=='Лися']
    if not cards: return await message.answer('В этой категории пока нет карточек.' if cmd in ['/raccoonadmin','/galleryadmin'] else 'Галерея пуста. Добавьте карточку через /addcard')
    c=cards[0]
    if c.get('media_type','photo')=='document': await message.answer_document(c['file_id'],caption=_card_text(c,1,len(cards)),reply_markup=gallery_nav_keyboard(c['id']))
    else: await message.answer_photo(c['file_id'],caption=_card_text(c,1,len(cards)),reply_markup=gallery_nav_keyboard(c['id']))
@router.message(Command('addcard','addraccoon','addfox'))
async def addcard(message:Message,state:FSMContext,settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    await state.clear(); await state.set_state(AddCardState.waiting_image)
    if message.text.startswith('/addraccoon'): await state.update_data(force_category='Енотя',force_triggers=['енот','енотя','raccoon','raccoon girl','аэлита'])
    if message.text.startswith('/addfox'): await state.update_data(force_category='Лися',force_triggers=['лиса','лися','лисёнок','лисенок','fox','kitsune'])
    await message.answer('Отправьте картинку (photo или document-изображение).')

@router.message(AddCardState.waiting_image)
async def addcard_image(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    file_id=None; media_type=None; filename=None
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
        filename = f"card_{message.photo[-1].file_unique_id}.jpg"
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        file_id = message.document.file_id
        media_type = "document"
        filename = message.document.file_name or f"card_{message.document.file_unique_id}"
    else:
        return await message.answer("Поддерживаются только photo или document image. Отправьте картинку ещё раз.")

    arts_dir = Path("arts")
    arts_dir.mkdir(parents=True, exist_ok=True)
    telegram_file = await message.bot.get_file(file_id)
    local_path = arts_dir / filename
    await message.bot.download_file(telegram_file.file_path, destination=local_path)

    await state.update_data(file_id=file_id, media_type=media_type, local_path=str(local_path), filename=filename)
    await state.set_state(AddCardState.waiting_caption)
    await message.answer("Введите подпись карточки.")

@router.message(AddCardState.waiting_caption)
async def addcard_caption(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    caption = (message.text or "").strip()
    if not caption:
        return await message.answer("Подпись не должна быть пустой. Введите подпись карточки.")
    await state.update_data(caption=caption)
    await state.set_state(AddCardState.waiting_rarity)
    await message.answer("Введите редкость: Common, Rare, Epic, Legendary или Mythic.")

async def _finalize_card(message: Message, state: FSMContext, data: dict, category: str, triggers: list[str]):
    cards = get_cards()
    card = Card.create(
        card_id=next_card_id(cards),
        file_id=data["file_id"],
        local_path=data["local_path"],
        filename=data["filename"],
        caption=data["caption"],
        rarity=data["rarity"],
        category=category,
        triggers=triggers,
        uploaded_by=message.from_user.id,
        media_type=data.get("media_type", "photo"),
    )
    add_card(card)
    await state.clear()
    card_dict = card.to_dict()
    preview = _card_text(card_dict, 1, 1)
    if card.media_type == "document":
        await message.answer_document(card.file_id, caption=f"Карточка добавлена.\n\n{preview}")
    else:
        await message.answer_photo(card.file_id, caption=f"Карточка добавлена.\n\n{preview}")

@router.message(AddCardState.waiting_rarity)
async def addcard_rarity(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    rarity = (message.text or "").strip()
    if rarity not in RARITIES:
        return await message.answer("Неверная редкость. Допустимые значения: Common, Rare, Epic, Legendary, Mythic.")
    await state.update_data(rarity=rarity)
    data = await state.get_data()
    force_category = data.get("force_category")
    force_triggers = data.get("force_triggers")
    if force_category and force_triggers:
        return await _finalize_card(message, state, data, force_category, normalize_triggers(force_triggers))
    await state.set_state(AddCardState.waiting_category)
    await message.answer("Введите категорию карточки.")

@router.message(AddCardState.waiting_category)
async def addcard_category(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    category = (message.text or "").strip()
    if not category:
        return await message.answer("Категория не должна быть пустой. Введите категорию карточки.")
    await state.update_data(category=category)
    await state.set_state(AddCardState.waiting_triggers)
    await message.answer("Введите триггеры через запятую.")

@router.message(AddCardState.waiting_triggers)
async def addcard_triggers(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    triggers = normalize_triggers([part.strip() for part in (message.text or "").split(",")])
    if not triggers:
        return await message.answer("Нужен хотя бы один триггер. Введите триггеры через запятую.")
    data = await state.get_data()
    await _finalize_card(message, state, data, data["category"], triggers)
@router.message(Command('cancel'))
async def cancel(message:Message,state:FSMContext,settings:Settings):
    if _is_admin(message.from_user.id, settings): await state.clear(); await message.answer('Действие отменено.')
@router.message(Command('broadcast'))
async def bstart(message:Message,state:FSMContext,settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    await state.set_state(BroadcastState.waiting_message); await message.answer('Отправьте сообщение для рассылки (text/photo/document image).')
@router.message(BroadcastState.waiting_message)
async def bprev(message:Message,state:FSMContext,settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    payload={'caption':message.caption,'text':message.text}
    if message.photo: payload|={'kind':'photo','file_id':message.photo[-1].file_id}
    elif message.document and (message.document.mime_type or '').startswith('image/'): payload|={'kind':'document','file_id':message.document.file_id}
    elif message.text: payload|={'kind':'text'}
    else: return await message.answer('Поддерживаются только text/photo/document image.')
    await state.update_data(broadcast=payload)
    if payload['kind']=='text': await message.answer(f"Предпросмотр:\n\n{payload['text']}",reply_markup=broadcast_confirm_keyboard())
    elif payload['kind']=='photo': await message.answer_photo(payload['file_id'],caption=payload.get('caption',''),reply_markup=broadcast_confirm_keyboard())
    else: await message.answer_document(payload['file_id'],caption=payload.get('caption',''),reply_markup=broadcast_confirm_keyboard())
@router.callback_query(F.data.startswith('broadcast:'))
async def bgo(c:CallbackQuery,state:FSMContext,settings:Settings):
    if not _is_admin(c.from_user.id, settings): return
    if c.data.endswith('cancel'): await state.clear(); return await c.message.answer('Рассылка отменена.')
    data=(await state.get_data()).get('broadcast',{}); ok=fail=0
    for uid in get_users().keys():
        try:
            if data.get('kind')=='text': await c.bot.send_message(int(uid),data.get('text',''))
            elif data.get('kind')=='photo': await c.bot.send_photo(int(uid),data['file_id'],caption=data.get('caption',''))
            else: await c.bot.send_document(int(uid),data['file_id'],caption=data.get('caption',''))
            ok+=1
        except Exception: fail+=1
        await asyncio.sleep(0.07)
    await state.clear(); await c.message.answer(f'Рассылка завершена. Успешно: {ok}. Ошибок: {fail}.')
@router.message(Command('userstats'))
async def userstats(message:Message,settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    users=get_users(); stats=get_stats(); await message.answer(f"Всего пользователей: {len(users)}\nВсего выпадений: {sum(stats.get('card_hits',{}).values())}")
