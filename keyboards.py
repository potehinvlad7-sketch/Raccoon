from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def gallery_nav_keyboard(card_id: int, scope: str = "all") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Предыдущий", callback_data=f"gallery:prev:{card_id}:{scope}"),
                InlineKeyboardButton(text="⚙️ Настроить", callback_data=f"gallery:settings:{card_id}:{scope}"),
                InlineKeyboardButton(text="Далее ▶️", callback_data=f"gallery:next:{card_id}:{scope}"),
            ],
            [InlineKeyboardButton(text="← Назад", callback_data=f"gallery:back:0:{scope}")],
        ]
    )


def card_settings_keyboard(card_id: int, scope: str = "all") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Изменить подпись", callback_data=f"edit:caption:{card_id}")],
            [InlineKeyboardButton(text="Изменить редкость", callback_data=f"edit:rarity:{card_id}")],
            [InlineKeyboardButton(text="Изменить категорию", callback_data=f"edit:category:{card_id}")],
            [InlineKeyboardButton(text="Изменить триггеры", callback_data=f"edit:triggers:{card_id}")],
            [InlineKeyboardButton(text="Включить/выключить", callback_data=f"edit:toggle:{card_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"edit:delete:{card_id}")],
            [InlineKeyboardButton(text="Назад", callback_data=f"gallery:show:{card_id}:{scope}")],
        ]
    )


def add_category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить Енотю", callback_data="quickadd:raccoon")],
            [InlineKeyboardButton(text="➕ Добавить Лисю", callback_data="quickadd:fox")],
        ]
    )


def mygallery_nav_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"mygallery:prev:{index}"),
                InlineKeyboardButton(text="Далее ▶️", callback_data=f"mygallery:next:{index}"),
            ],
            [InlineKeyboardButton(text="← Назад", callback_data="mygallery:back:0")],
        ]
    )


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast:confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")],
        ]
    )
