from __future__ import annotations
import asyncio
import logging
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InputMediaDocument, InputMediaPhoto, Message

from config import Settings
from keyboards import (
    broadcast_confirm_keyboard,
    card_settings_keyboard,
    delete_confirm_keyboard,
    gallery_nav_keyboard,
    rarity_keyboard,
)
from models import Card, RARITIES, normalize_triggers
from storage import add_card, get_cards, get_stats, get_users, next_card_id, rebuild_triggers, save_cards

router = Router(name='admin')
MAIN_ADMIN_ID = 811133301

class AddCardState(StatesGroup): waiting_image=State(); waiting_caption=State(); waiting_rarity=State(); waiting_category=State(); waiting_triggers=State()
class BroadcastState(StatesGroup): waiting_message=State()
class EditCardState(StatesGroup): waiting_edit_caption=State(); waiting_edit_category=State(); waiting_edit_triggers=State()

def _is_admin(u,s): return u in s.admin_ids

def _card_text(card,idx,total): return f"Арт {idx}/{total}\nПодпись: {card.get('caption','')}\nРедкость: {card.get('rarity','-')}\nКатегория: {card.get('category','-')}\nТриггеры: {', '.join(card.get('triggers',[]))}\nАктивна: {'Да' if card.get('enabled', True) else 'Нет'}"
def _find_card(cards, cid): return next((c for c in cards if c.get('id')==cid), None)
def _context_filter(cards, data):
    cat=data.get('gallery_category')
    return [c for c in cards if c.get('category')==cat] if cat else cards

def _user_top_text() -> str:
    try: users = get_users()
    except Exception:
        logging.exception('users.json damaged')
        return 'Пользователей пока нет.'
    if not users: return 'Пользователей пока нет.'
    rows = sorted(users.values(), key=lambda u: int(u.get('total_finds', 0)), reverse=True)
    lines=['Пользователи:']
    for i, u in enumerate(rows[:20], start=1):
        lines += [f"{i}. ID: {u.get('user_id', '-')}", f"   username: @{u.get('username')}" if u.get('username') else '   username: -', f"   имя: {u.get('first_name') or '-'}", f"   находок: {int(u.get('total_finds',0))}", f"   уникальных карточек: {len(set(u.get('found_cards',[])))}", '']
    if len(rows) > 20: lines.append(f"...и ещё {len(rows)-20} пользователей. Полный список можно выгрузить через /export_users")
    return '\n'.join(lines).strip()

async def _show_card(target: Message | CallbackQuery, card: dict, idx: int, total: int):
    caption=_card_text(card,idx,total); kb=gallery_nav_keyboard(card['id'])
    msg = target.message if isinstance(target, CallbackQuery) else target
    try:
        if isinstance(target, CallbackQuery):
            media = InputMediaDocument(media=card['file_id'], caption=caption) if card.get('media_type','photo')=='document' else InputMediaPhoto(media=card['file_id'], caption=caption)
            await msg.edit_media(media=media, reply_markup=kb)
        elif card.get('media_type','photo')=='document':
            await msg.answer_document(card['file_id'], caption=caption, reply_markup=kb)
        else:
            await msg.answer_photo(card['file_id'], caption=caption, reply_markup=kb)
    except Exception:
        logging.exception('Failed to send card %s', card.get('id'))
        if isinstance(target, CallbackQuery):
            await msg.delete()
        await msg.answer(f"Не удалось отправить карточку #{card.get('id')}. Возможно, file_id устарел или повреждён.")

@router.message(Command('ping','raccoonadmin','galleryadmin','cards','adminhelp','backup','export_users','cardinfo'))
async def admin_entry(message:Message, settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    cmd=message.text.split()[0]
    if cmd=='/ping': return await message.answer('pong')
    if cmd=='/adminhelp':
        return await message.answer('/raccoonadmin — админка Еноти, доступ только главному админу 811133301\n/galleryadmin — админка Лиси\n/addcard — добавить обычную карточку\n/addraccoon — добавить карточку Еноти\n/addfox — добавить карточку Лиси\n/broadcast — рассылка всем пользователям\n/userstats — статистика пользователей\n/backup — резервная копия данных\n/export_users — выгрузить users.json\n/cardinfo ID — информация о карточке по ID\n/cards — список/галерея карточек\n/cancel — отменить текущий режим\n\nКак добавлять: /addcard, затем картинка, подпись, редкость, категория, триггеры через запятую.\nРедкости: Common, Rare, Epic, Legendary, Mythic.')
    if cmd=='/backup':
        ts=datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        name=f'raccoon_backup_{ts}.tar.gz'
        with tempfile.TemporaryDirectory() as td:
            ap=Path(td)/name
            try:
                with tarfile.open(ap,'w:gz') as tar:
                    for fp in ['data/cards.json','data/users.json','data/stats.json','data/triggers.json']:
                        if Path(fp).exists(): tar.add(fp)
                    if Path('arts').exists(): tar.add('arts')
                await message.answer_document(FSInputFile(ap, filename=name))
            except Exception:
                logging.exception('backup failed')
                await message.answer('Не удалось собрать архив, отправляю JSON-файлы отдельно.')
                for fp in ['data/cards.json','data/users.json','data/stats.json','data/triggers.json']:
                    if Path(fp).exists(): await message.answer_document(FSInputFile(fp))
        return
    if cmd=='/export_users':
        p=Path('data/users.json'); p.parent.mkdir(exist_ok=True)
        if not p.exists(): p.write_text('{}', encoding='utf-8')
        return await message.answer_document(FSInputFile(p))
    if cmd=='/cardinfo':
        parts=message.text.split()
        if len(parts)!=2 or not parts[1].isdigit(): return await message.answer('Использование: /cardinfo ID')
        cid=int(parts[1]); card=_find_card(get_cards(), cid)
        if not card: return await message.answer(f'Карточка #{cid} не найдена.')
        hits=get_stats().get('card_hits',{}).get(str(cid),0)
        return await message.answer(f"ID: {card.get('id')}\nfile_id: {card.get('file_id')}\nfilename: {card.get('filename')}\nlocal_path: {card.get('local_path')}\nmedia_type: {card.get('media_type')}\ncaption: {card.get('caption')}\nrarity: {card.get('rarity')}\ncategory: {card.get('category')}\ntriggers: {', '.join(card.get('triggers',[]))}\nenabled: {card.get('enabled', True)}\ncreated_at: {card.get('created_at')}\nupdated_at: {card.get('updated_at')}\nuploaded_by: {card.get('uploaded_by')}\nвыпадала: {hits}")
    cards=get_cards()
    cat=None
    if cmd=='/raccoonadmin':
        if message.from_user.id != MAIN_ADMIN_ID: return await message.answer('Нет доступа к /raccoonadmin.')
        await message.answer(_user_top_text()); cat='Енотя'
    if cmd=='/galleryadmin': cat='Лися'
    cards=[c for c in cards if c.get('category')==cat] if cat else cards
    if not cards: return await message.answer('В этой категории пока нет карточек.' if cmd in ['/raccoonadmin','/galleryadmin'] else 'Галерея пуста. Добавьте карточку через /addcard')
    await _show_card(message, cards[0], 1, len(cards))

@router.callback_query(F.data.startswith(('gallery:','edit:','setrarity:','toggle:','delete:','deleteconfirm:')))
async def gallery_callbacks(c: CallbackQuery, state:FSMContext, settings:Settings):
    if not _is_admin(c.from_user.id, settings): return await c.answer('Нет доступа', show_alert=True)
    p=c.data.split(':')
    if p[0]=='gallery' and p[1]=='back':
        await c.message.edit_reply_markup(reply_markup=None); await c.message.answer('Админ-галерея закрыта.'); return await c.answer()
    if len(p)>=3 and p[2].isdigit(): cid=int(p[2])
    else: return await c.answer('Ошибка callback')
    all_cards=get_cards(); card=_find_card(all_cards, cid)
    if not card: return await c.answer('Карточка не найдена.', show_alert=True)
    if p[0]=='gallery' and p[1] in {'prev','next','show'}:
        data=await state.get_data(); cards=_context_filter(all_cards,data)
        ids=[x['id'] for x in cards]; idx=ids.index(cid) if cid in ids else 0
        if p[1]=='prev': idx=(idx-1)%len(cards)
        elif p[1]=='next': idx=(idx+1)%len(cards)
        await _show_card(c, cards[idx], idx+1, len(cards)); return await c.answer()
    if p[0]=='gallery' and p[1]=='settings':
        await c.message.edit_caption(caption=f'Настройки карточки #{cid}', reply_markup=card_settings_keyboard(cid)); return await c.answer()
    if p[0]=='edit' and p[1]=='caption': await state.set_state(EditCardState.waiting_edit_caption); await state.update_data(edit_card_id=cid); await c.message.answer('Введите новую подпись.'); return await c.answer()
    if p[0]=='edit' and p[1]=='category': await state.set_state(EditCardState.waiting_edit_category); await state.update_data(edit_card_id=cid); await c.message.answer('Введите новую категорию.'); return await c.answer()
    if p[0]=='edit' and p[1]=='triggers': await state.set_state(EditCardState.waiting_edit_triggers); await state.update_data(edit_card_id=cid); await c.message.answer('Введите триггеры через запятую.'); return await c.answer()
    if p[0]=='edit' and p[1]=='rarity': await c.message.edit_caption(caption=f'Выберите редкость для #{cid}', reply_markup=rarity_keyboard(cid)); return await c.answer()
    if p[0]=='setrarity':
        rarity=p[3] if len(p)>3 else ''
        if rarity not in RARITIES: return await c.answer('Неверная редкость', show_alert=True)
        card['rarity']=rarity; card['updated_at']=datetime.now(timezone.utc).isoformat(); save_cards(all_cards)
    elif p[0]=='toggle':
        card['enabled']=not card.get('enabled',True); card['updated_at']=datetime.now(timezone.utc).isoformat(); save_cards(all_cards); rebuild_triggers(all_cards)
    elif p[0]=='delete':
        await c.message.edit_caption(caption='Удалить карточку?', reply_markup=delete_confirm_keyboard(cid)); return await c.answer()
    elif p[0]=='deleteconfirm':
        if len(p)>3 and p[3]=='yes':
            all_cards=[x for x in all_cards if x.get('id')!=cid]; save_cards(all_cards); rebuild_triggers(all_cards); await c.message.answer('Карточка удалена.')
            return await c.answer()
        await c.message.edit_caption(caption=f'Настройки карточки #{cid}', reply_markup=card_settings_keyboard(cid)); return await c.answer()
    idx=[x['id'] for x in all_cards].index(cid)+1
    await _show_card(c, card, idx, len(all_cards)); await c.answer()

@router.message(EditCardState.waiting_edit_caption)
async def edit_caption(message:Message,state:FSMContext,settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    data=await state.get_data(); cid=data.get('edit_card_id'); cards=get_cards(); card=_find_card(cards,cid)
    if not card: await state.clear(); return await message.answer('Карточка не найдена.')
    card['caption']=(message.text or '').strip(); card['updated_at']=datetime.now(timezone.utc).isoformat(); save_cards(cards); await state.clear(); idx=[x['id'] for x in cards].index(cid)+1; await _show_card(message, card, idx, len(cards))
@router.message(EditCardState.waiting_edit_category)
async def edit_category(message:Message,state:FSMContext,settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    data=await state.get_data(); cid=data.get('edit_card_id'); cards=get_cards(); card=_find_card(cards,cid)
    if not card: await state.clear(); return await message.answer('Карточка не найдена.')
    card['category']=(message.text or '').strip(); card['updated_at']=datetime.now(timezone.utc).isoformat(); save_cards(cards); await state.clear(); idx=[x['id'] for x in cards].index(cid)+1; await _show_card(message, card, idx, len(cards))
@router.message(EditCardState.waiting_edit_triggers)
async def edit_triggers(message:Message,state:FSMContext,settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    data=await state.get_data(); cid=data.get('edit_card_id'); cards=get_cards(); card=_find_card(cards,cid)
    if not card: await state.clear(); return await message.answer('Карточка не найдена.')
    card['triggers']=normalize_triggers([p.strip() for p in (message.text or '').split(',')]); card['updated_at']=datetime.now(timezone.utc).isoformat(); save_cards(cards); rebuild_triggers(cards); await state.clear(); idx=[x['id'] for x in cards].index(cid)+1; await _show_card(message, card, idx, len(cards))

# keep old handlers unchanged below
@router.message(Command('addcard','addraccoon','addfox'))
async def addcard(message:Message,state:FSMContext,settings:Settings):
    if not _is_admin(message.from_user.id, settings): return
    await state.clear(); await state.set_state(AddCardState.waiting_image)
    if message.text.startswith('/addraccoon'): await state.update_data(force_category='Енотя',force_triggers=['енот','енотя','raccoon','raccoon girl','аэлита'])
    if message.text.startswith('/addfox'): await state.update_data(force_category='Лися',force_triggers=['лиса','лися','лисёнок','лисенок','fox','kitsune'])
    await message.answer('Отправьте картинку (photo или document-изображение).')
# ... keep rest same

@router.message(AddCardState.waiting_image)
async def addcard_image(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    file_id=None; media_type=None; filename=None
    if message.photo:
        file_id = message.photo[-1].file_id; media_type = 'photo'; filename = f"card_{message.photo[-1].file_unique_id}.jpg"
    elif message.document and (message.document.mime_type or '').startswith('image/'):
        file_id = message.document.file_id; media_type = 'document'; filename = message.document.file_name or f"card_{message.document.file_unique_id}"
    else: return await message.answer('Поддерживаются только photo или document image. Отправьте картинку ещё раз.')
    arts_dir = Path('arts'); arts_dir.mkdir(parents=True, exist_ok=True)
    telegram_file = await message.bot.get_file(file_id); local_path = arts_dir / filename
    await message.bot.download_file(telegram_file.file_path, destination=local_path)
    await state.update_data(file_id=file_id, media_type=media_type, local_path=str(local_path), filename=filename)
    await state.set_state(AddCardState.waiting_caption); await message.answer('Введите подпись карточки.')

@router.message(AddCardState.waiting_caption)
async def addcard_caption(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    caption = (message.text or '').strip()
    if not caption: return await message.answer('Подпись не должна быть пустой. Введите подпись карточки.')
    await state.update_data(caption=caption); await state.set_state(AddCardState.waiting_rarity)
    await message.answer('Введите редкость: Common, Rare, Epic, Legendary или Mythic.')

async def _finalize_card(message: Message, state: FSMContext, data: dict, category: str, triggers: list[str]):
    cards = get_cards(); card = Card.create(card_id=next_card_id(cards), file_id=data['file_id'], local_path=data['local_path'], filename=data['filename'], caption=data['caption'], rarity=data['rarity'], category=category, triggers=triggers, uploaded_by=message.from_user.id, media_type=data.get('media_type', 'photo'))
    add_card(card); await state.clear(); card_dict = card.to_dict(); preview = _card_text(card_dict, 1, 1)
    if card.media_type == 'document': await message.answer_document(card.file_id, caption=f'Карточка добавлена.\n\n{preview}')
    else: await message.answer_photo(card.file_id, caption=f'Карточка добавлена.\n\n{preview}')

@router.message(AddCardState.waiting_rarity)
async def addcard_rarity(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    rarity = (message.text or '').strip()
    if rarity not in RARITIES: return await message.answer('Неверная редкость. Допустимые значения: Common, Rare, Epic, Legendary, Mythic.')
    await state.update_data(rarity=rarity); data = await state.get_data(); force_category = data.get('force_category'); force_triggers = data.get('force_triggers')
    if force_category and force_triggers: return await _finalize_card(message, state, data, force_category, normalize_triggers(force_triggers))
    await state.set_state(AddCardState.waiting_category); await message.answer('Введите категорию карточки.')

@router.message(AddCardState.waiting_category)
async def addcard_category(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    category=(message.text or '').strip()
    if not category: return await message.answer('Категория не должна быть пустой. Введите категорию карточки.')
    await state.update_data(category=category); await state.set_state(AddCardState.waiting_triggers); await message.answer('Введите триггеры через запятую.')

@router.message(AddCardState.waiting_triggers)
async def addcard_triggers(message: Message, state: FSMContext, settings: Settings):
    if not _is_admin(message.from_user.id, settings): return
    triggers = normalize_triggers([part.strip() for part in (message.text or '').split(',')])
    if not triggers: return await message.answer('Нужен хотя бы один триггер. Введите триггеры через запятую.')
    data = await state.get_data(); await _finalize_card(message, state, data, data['category'], triggers)

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
