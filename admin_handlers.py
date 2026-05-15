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
