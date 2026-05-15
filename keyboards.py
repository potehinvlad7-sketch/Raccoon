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
            [InlineKeyboardButton(text="Включить/выключить", callback_data=f"edit:toggle:{card_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"edit:delete:{card_id}")],
            [InlineKeyboardButton(text="Назад", callback_data=f"gallery:show:{card_id}")],
        ]
    )
