from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards.main_keyboard import main_menu
from config import sheet

router = Router()


@router.message(CommandStart())
@router.message(Command("start"))
async def cmd_start_handler(message: Message, state: FSMContext):
    """Команда /start - главное меню"""
    await state.clear()

    text = sheet.cell(2, 1).value if sheet.cell(2, 1).value else (
        "Привет! Давай вместе найдем идеальное путешествие💫\n\n"
        "Скажи, какой отдых хочешь - бюджет, даты, настроение - и я подберу варианты, "
        "подскажу, куда выгоднее лететь и где лучшие отели.\n\n"
        "Готов начать?"
    )

    await message.answer(text, reply_markup=main_menu)


@router.message(Command("tours"))
async def cmd_tours_handler(message: Message, state: FSMContext):
    """Команда /tours - быстрый переход к подбору тура"""
    await state.clear()

    from keyboards.find_tour_keyboard import inspiring_menu

    await message.answer(
        "🔍 **Подбор тура**\n\n"
        "Нажмите 'Ввести параметры', чтобы начать подбор.",
        reply_markup=inspiring_menu,
        parse_mode="Markdown"
    )


@router.message(Command("favorites"))
async def cmd_favorites_handler(message: Message, state: FSMContext):
    """Команда /favorites - показать заметки"""
    # Перенаправляем на handlers/favorites_handler.py
    from handlers.favorites_handler import show_favorites
    await show_favorites(message, state)


@router.message(Command("help"))
@router.message(F.text == "Что умеет бот")
async def cmd_help_handler(message: Message, state: FSMContext):
    """Команда /help - описание возможностей бота"""
    await state.clear()

    text = """
🤖 **Что умеет этот бот:**

🔍 **Подбор туров**
• Поиск туров по вашим параметрам
• Фильтрация по цене, звездности, удобствам
• Просмотр фотографий и описаний отелей

💾 **Заметки**
• Сохранение понравившихся туров
• Быстрый доступ к сохраненным турам
• Удаление туров из заметок

📋 **Информация об отелях**
• Подробное описание отеля
• Информация о номерах
• Ответы на вопросы об отеле (AI-помощник)

🔗 **Бронирование**
• Партнерские ссылки для бронирования
• Генерация PDF с деталями тура

**Команды:**
/start - Главное меню
/tours - Подобрать тур
/favorites - Заметки
/help - Эта справка
"""

    await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "start")
async def start_handler(callback: CallbackQuery, state: FSMContext):
    """Callback для возврата в главное меню"""
    await state.clear()

    text = sheet.cell(2, 1).value if sheet.cell(2, 1).value else (
        "Привет! Давай вместе найдем идеальное путешествие💫\n\n"
        "Скажи, какой отдых хочешь - бюджет, даты, настроение - и я подберу варианты, "
        "подскажу, куда выгоднее лететь и где лучшие отели.\n\n"
        "Готов начать?"
    )

    await callback.message.answer(text, reply_markup=main_menu)
    await callback.answer()
