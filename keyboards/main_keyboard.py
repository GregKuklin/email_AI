from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Подобрать тур"), KeyboardButton(text="Мои заметки")],
        [KeyboardButton(text="Что умеет бот")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)