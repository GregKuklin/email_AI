from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

inspiring_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Море, солнце, пляж", callback_data="sea")],
        [InlineKeyboardButton(text="Город и прогулки", callback_data="city")],
        [InlineKeyboardButton(text="Природа и активный отдых", callback_data="nature")],
        [InlineKeyboardButton(text="Премиум-отдых", callback_data="beauty")],
        [InlineKeyboardButton(text="Спокойный отдых", callback_data="calm")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="start")]
    ]
)