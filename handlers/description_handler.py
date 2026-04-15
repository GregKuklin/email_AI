from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from keyboards.main_keyboard import main_menu
from config import sheet
router = Router()

@router.message(F.text == "Описание бота")
async def description(message: Message, state: FSMContext):
    # ВАЖНО: Сбрасываем состояние перед показом описания
    await state.clear()

    text = sheet.cell(2, 2).value
    await message.answer(text, reply_markup=main_menu)