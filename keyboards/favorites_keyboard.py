"""
Клавиатуры для работы с избранным.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def create_favorites_list_keyboard(favorites: list) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру со списком избранных туров.

    Args:
        favorites: Список избранных туров

    Returns:
        InlineKeyboardMarkup
    """
    buttons = []

    # Кнопка для каждого тура
    for fav in favorites:
        hotel_name = fav['hotel_name']
        # Ограничиваем название 25 символами
        if len(hotel_name) > 25:
            hotel_name = hotel_name[:22] + "..."

        buttons.append([
            InlineKeyboardButton(
                text=f"{hotel_name} - {fav['price']:,} ₽",
                callback_data=f"view_favorite_{fav['id']}"
            )
        ])

    # Кнопка "Очистить все" внизу
    if len(favorites) > 0:
        buttons.append([
            InlineKeyboardButton(
                text="🗑️ Удалить все",
                callback_data="clear_all_favorites"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_clear_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения очистки всего избранного"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить все", callback_data="confirm_clear_yes"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_clear_no")
        ]
    ])
