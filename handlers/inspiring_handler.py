from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards.inspiring_keyboard import inspiring_menu
from services.openai_service import OpenAIService
from config import sheet
import logging

logger = logging.getLogger(__name__)
router = Router()
openai_service = OpenAIService()

@router.message(F.text == "Получить вдохновение")
async def inspiring(message: Message, state: FSMContext):
    # ВАЖНО: Сбрасываем состояние перед показом меню
    await state.clear()

    text = sheet.cell(2, 3).value
    await message.answer(text, reply_markup=inspiring_menu)

@router.callback_query(F.data.in_(["sea", "city", "nature", "beauty", "calm"]))
async def process_inspiration_category(callback: CallbackQuery):
    """Обработка выбора категории вдохновения"""
    await callback.answer()
    
    category = callback.data
    
    # Показываем сообщение о загрузке
    loading_msg = await callback.message.edit_text("🤖 Генерирую персональные рекомендации...")
    
    try:
        # Получаем рекомендации от ChatGPT-4
        recommendation = await openai_service.get_travel_inspiration(category)
        
        # Отправляем рекомендации
        await loading_msg.edit_text(
            f"✨ **Персональные рекомендации для вас:**\n\n{recommendation}",
            parse_mode="Markdown"
        )
        
        logger.info(f"Успешно сгенерированы рекомендации для категории: {category}")
        
    except Exception as e:
        logger.error(f"Ошибка при генерации рекомендаций: {e}")
        await loading_msg.edit_text(
            "❌ Произошла ошибка при генерации рекомендаций. Попробуйте позже."
        )

@router.callback_query(F.data == "start")
async def back_to_start(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.answer()
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=None  # Здесь должна быть главная клавиатура
    )