from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def gallery_nav_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Предыдущий", callback_data=f"gallery:prev:{card_id}"),
                InlineKeyboardButton(text="⚙️ Настроить", callback_data=f"gallery:settings:{card_id}"),
                InlineKeyboardButton(text="Далее ▶️", callback_data=f"gallery:next:{card_id}"),
            ],
            [InlineKeyboardButton(text="← Назад", callback_data="gallery:back")],
        ]
    )


def card_settings_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Изменить подпись", callback_data=f"edit:caption:{card_id}")],
            [InlineKeyboardButton(text="Изменить редкость", callback_data=f"edit:rarity:{card_id}")],
            [InlineKeyboardButton(text="Изменить категорию", callback_data=f"edit:category:{card_id}")],
            [InlineKeyboardButton(text="Изменить триггеры", callback_data=f"edit:triggers:{card_id}")],
            [InlineKeyboardButton(text="Включить/выключить", callback_data=f"toggle:{card_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete:{card_id}")],
            [InlineKeyboardButton(text="Назад", callback_data=f"gallery:show:{card_id}")],
        ]
    )


def user_gallery_nav_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"mygallery:prev:{card_id}"),
                InlineKeyboardButton(text="Далее ▶️", callback_data=f"mygallery:next:{card_id}"),
            ],
            [InlineKeyboardButton(text="← Назад", callback_data="mygallery:back")],
        ]
    )


def rarity_keyboard(card_id: int) -> InlineKeyboardMarkup:
    rarities=["Common","Rare","Epic","Legendary","Mythic"]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=r, callback_data=f"setrarity:{card_id}:{r}")] for r in rarities])

def delete_confirm_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"deleteconfirm:{card_id}:yes")],[InlineKeyboardButton(text="❌ Отмена", callback_data=f"deleteconfirm:{card_id}:no")]])

def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast:confirm")],[InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")]])
