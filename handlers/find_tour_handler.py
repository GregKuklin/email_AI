from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards.find_tour_keyboard import inspiring_menu
from config import sheet
router = Router()

@router.message(F.text == "Подобрать тур")
async def find_tour_menu(message: Message, state: FSMContext):
    """Показать меню выбора способа подбора тура"""
    # ВАЖНО: Сбрасываем состояние перед показом меню
    await state.clear()

    text = sheet.cell(4, 1).value if sheet.cell(4, 1).value else (
        "🔍 **Подбор тура**\n\n"
        "Нажмите 'Ввести параметры', чтобы начать подбор тура.\n"
        "Вы сможете указать город вылета, страну, даты, бюджет и другие критерии."
    )
    await message.answer(text, reply_markup=inspiring_menu, parse_mode="Markdown")