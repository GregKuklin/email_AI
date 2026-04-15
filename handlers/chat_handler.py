from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from services.openai_service import OpenAIService
from services.leveltravel_service import LeveltravelService
from handlers.tour_feed_handler import format_hotel_context
import logging

logger = logging.getLogger(__name__)
router = Router()
openai_service = OpenAIService()

# Список reply-кнопок, которые нужно игнорировать
REPLY_BUTTONS = [
    "Найти тур",
    "Получить вдохновение",
    "Задать вопросы",
    "Описать параметры"
]

# Состояния, в которых разрешено общение с нейросетью
ALLOWED_CHAT_STATES = [
    "TourParams:search_tours",
    "ImprovedTourSearch:search_tours"
]

@router.message(F.text & ~F.text.in_(REPLY_BUTTONS))
async def handle_chat_message(message: Message, state: FSMContext):
    """Обработчик для общения с нейромоделью Navia"""
    
    # Проверяем, что сообщение не является командой или callback
    if message.text.startswith('/'):
        return
    
    # Проверяем текущее состояние
    current_state = await state.get_state()
    if current_state and current_state not in ALLOWED_CHAT_STATES:
        # Если пользователь в процессе заполнения формы (но не просматривает туры), не перехватываем сообщение
        return
    
    try:
        # Показываем индикатор печати
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # Получаем историю диалога из состояния
        user_data = await state.get_data()
        chat_history = user_data.get('chat_history', [])
        
        # Если пользователь просматривает туры, добавляем контекст текущего тура
        context_info = ""
        if current_state in ALLOWED_CHAT_STATES:
            # ✅ ИСПРАВЛЕНО: используем правильные ключи hotels и current_index
            hotels = user_data.get('hotels', [])
            current_index = user_data.get('current_index', 0)
            request_id = user_data.get('request_id')

            if hotels and current_index < len(hotels):
                current_hotel = hotels[current_index]

                # Проверяем наличие закэшированных данных о номерах
                cached_key = f"cached_hotel_rooms_{current_hotel.hotel_id}"
                hotel_rooms = user_data.get(cached_key)

                # Ленивая загрузка: запрашиваем данные только при первом вопросе
                if hotel_rooms is None and request_id:
                    try:
                        logger.info(f"Загружаю данные о номерах для отеля {current_hotel.hotel_name}...")
                        service = LeveltravelService()
                        hotel_rooms = await service.get_hotel_rooms(request_id, current_hotel.hotel_id)

                        # Сохраняем в кэш для последующего использования
                        await state.update_data({cached_key: hotel_rooms})
                        logger.info(f"Загружены данные о {len(hotel_rooms) if hotel_rooms else 0} типах номеров")
                    except Exception as e:
                        logger.warning(f"Не удалось загрузить данные о номерах: {e}")
                        hotel_rooms = []
                elif hotel_rooms is None:
                    hotel_rooms = []

                # Используем существующую функцию форматирования полного контекста
                full_context = format_hotel_context(current_hotel, hotel_rooms)
                context_info = f"\n\n📋 ИНФОРМАЦИЯ О ПРОСМАТРИВАЕМОМ ТУРЕ:\n{full_context}"

        # Проверяем длину сообщения перед отправкой в GPT
        TELEGRAM_MAX_LENGTH = 4096
        user_message_with_context = message.text + context_info

        if len(user_message_with_context) > 3500:  # Резерв для ответа GPT
            # Контекст слишком большой - используем краткую версию
            if current_state in ALLOWED_CHAT_STATES and hotels and current_index < len(hotels):
                current_hotel = hotels[current_index]
                context_info = (
                    f"\n\nПользователь просматривает: {current_hotel.hotel_name} "
                    f"({current_hotel.stars}⭐), {current_hotel.city}, "
                    f"от {current_hotel.format_price()}₽"
                )
            user_message = message.text + context_info
        else:
            user_message = user_message_with_context
        chat_history.append({"role": "user", "content": user_message})
        
        # Ограничиваем историю последними 10 сообщениями (5 пар вопрос-ответ)
        if len(chat_history) > 10:
            chat_history = chat_history[-10:]
        
        # Получаем ответ от нейромодели с учетом контекста
        response = await openai_service.get_navia_response_with_context(message.text, chat_history)
        
        # Добавляем ответ ассистента в историю
        chat_history.append({"role": "assistant", "content": response})
        
        # Сохраняем обновленную историю в состоянии
        await state.update_data(chat_history=chat_history)
        
        # Отправляем ответ пользователю
        await message.answer(response)
        
        logger.info(f"Navia ответила пользователю {message.from_user.id}: {message.text[:50]}...")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения через Navia: {e}")
        await message.answer(
            "😔 Извините, произошла техническая ошибка. Попробуйте позже или воспользуйтесь кнопками меню."
        )