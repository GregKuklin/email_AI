"""
Обработчик выбора удобств отеля.
Используется в процессе подбора туров для фильтрации по amenities.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from keyboards.amenities_keyboard import (
    create_amenities_keyboard,
    format_selected_amenities
)
from keyboards.meal_keyboard import (
    create_meal_types_keyboard,
    format_selected_meals
)
from states.tour_states import TourSearchFlow
from utils.message_cleanup import send_and_delete_previous, delete_last_bot_message

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("amenity_toggle_"))
async def toggle_amenity(callback: CallbackQuery, state: FSMContext):
    """
    Toggle выбора удобства (вкл/выкл).
    
    Callback data format: amenity_toggle_{amenity_code}
    """
    # Извлекаем код удобства из callback_data
    amenity_code = callback.data.replace("amenity_toggle_", "")
    
    # Получаем текущий список выбранных удобств
    data = await state.get_data()
    selected_amenities = data.get('selected_amenities', [])
    
    # Toggle: если уже выбрано - убираем, если нет - добавляем
    if amenity_code in selected_amenities:
        selected_amenities.remove(amenity_code)
        logger.info(f"Удобство {amenity_code} снято с выбора")
    else:
        selected_amenities.append(amenity_code)
        logger.info(f"Удобство {amenity_code} добавлено к выбору")
    
    # Сохраняем обновленный список
    await state.update_data(selected_amenities=selected_amenities)
    
    # Обновляем клавиатуру
    new_keyboard = create_amenities_keyboard(selected_amenities)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка обновления клавиатуры: {e}")
        await callback.answer("Ошибка обновления")


@router.callback_query(F.data == "amenities_done")
async def amenities_done(callback: CallbackQuery, state: FSMContext):
    """
    Завершение выбора удобств, переход к подтверждению параметров.

    MEAL FILTER DISABLED (2025-12-14): Пропускаем выбор типа питания,
    сразу переходим к подтверждению параметров.
    """
    data = await state.get_data()
    selected_amenities = data.get('selected_amenities', [])

    logger.info(f"Пользователь завершил выбор удобств: {selected_amenities}")

    await callback.answer()

    # ========================================
    # MEAL FILTER DISABLED (2025-12-14)
    # ========================================
    # Раньше здесь был переход к выбору питания, теперь сразу переходим к подтверждению
    # await ask_for_meal_types(callback.message, state)

    # Переходим сразу к подтверждению параметров
    await state.set_state(TourSearchFlow.confirm_params)

    from handlers.params_handler import show_params_confirmation
    await show_params_confirmation(callback.message, state)


# ========================================
# MEAL FILTER DISABLED (2025-12-14)
# ========================================
# Обработчики выбора типа питания отключены, так как фильтр питания больше не используется
#
# @router.callback_query(F.data.startswith("meal_toggle_"))
# async def toggle_meal_type(callback: CallbackQuery, state: FSMContext):
#     """
#     Toggle выбора типа питания (вкл/выкл).
#
#     Callback data format: meal_toggle_{meal_code}
#     """
#     # Извлекаем код типа питания из callback_data
#     meal_code = callback.data.replace("meal_toggle_", "")
#
#     # Получаем текущий список выбранных типов питания
#     data = await state.get_data()
#     selected_meals = data.get('selected_meals', [])
#
#     # Toggle: если уже выбрано - убираем, если нет - добавляем
#     if meal_code in selected_meals:
#         selected_meals.remove(meal_code)
#         logger.info(f"Тип питания {meal_code} снят с выбора")
#     else:
#         selected_meals.append(meal_code)
#         logger.info(f"Тип питания {meal_code} добавлен к выбору")
#
#     # Сохраняем обновленный список
#     await state.update_data(selected_meals=selected_meals)
#
#     # Обновляем клавиатуру
#     new_keyboard = create_meal_types_keyboard(selected_meals)
#
#     try:
#         await callback.message.edit_reply_markup(reply_markup=new_keyboard)
#         await callback.answer()
#     except Exception as e:
#         logger.error(f"Ошибка обновления клавиатуры: {e}")
#         await callback.answer("Ошибка обновления")
#
#
# @router.callback_query(F.data == "meal_done")
# async def meal_done(callback: CallbackQuery, state: FSMContext):
#     """
#     Завершение выбора типов питания, переход к подтверждению параметров.
#     """
#     data = await state.get_data()
#     selected_meals = data.get('selected_meals', [])
#
#     logger.info(f"Пользователь завершил выбор типов питания: {selected_meals}")
#
#     # Переходим к следующему состоянию (подтверждение параметров)
#     await state.set_state(TourSearchFlow.confirm_params)
#
#     await callback.answer()
#
#     # Импортируем здесь чтобы избежать circular import
#     from handlers.params_handler import show_params_confirmation
#     # Подтверждение будет в итоговом summary всех параметров
#     await show_params_confirmation(callback.message, state)


@router.callback_query(F.data == "amenities_skip")
async def amenities_skip(callback: CallbackQuery, state: FSMContext):
    """
    Пропустить выбор удобств.
    """
    # Очищаем список удобств
    await state.update_data(selected_amenities=[])
    
    logger.info("Пользователь пропустил выбор удобств")
    
    # Переходим к подтверждению
    await state.set_state(TourSearchFlow.confirm_params)
    
    await callback.message.answer(
        "Поиск будет выполнен без фильтров по удобствам."
    )
    await callback.answer()
    
    # Показываем подтверждение параметров
    from handlers.params_handler import show_params_confirmation
    await show_params_confirmation(callback.message, state)


async def ask_for_amenities(message, state: FSMContext):
    """
    Запросить выбор удобств у пользователя.

    Args:
        message: Message объект для отправки сообщения
        state: FSMContext
    """
    await state.set_state(TourSearchFlow.waiting_amenities)

    keyboard = create_amenities_keyboard()

    # Удаляем предыдущий вопрос, отправляем новый
    await send_and_delete_previous(
        message=message,
        text="🏊 **Выберите важные для вас удобства отеля:**\n\n"
             "Нажмите на нужные удобства, чтобы добавить их в фильтр.\n"
             "Можно выбрать несколько или продолжить без фильтров.",
        state=state,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# ========================================
# MEAL FILTER DISABLED (2025-12-14)
# ========================================
# Функция запроса выбора типа питания отключена
#
# async def ask_for_meal_types(message, state: FSMContext):
#     """
#     Запросить выбор типов питания у пользователя.
#
#     Args:
#         message: Message объект для отправки сообщения
#         state: FSMContext
#
#     Note:
#         Клиентская фильтрация - туры будут отфильтрованы после получения от API.
#     """
#     await state.set_state(TourSearchFlow.waiting_amenities)  # Используем то же состояние
#
#     keyboard = create_meal_types_keyboard()
#
#     # Удаляем предыдущий вопрос, отправляем новый
#     await send_and_delete_previous(
#         message=message,
#         text="🍽️ **Выберите тип питания:**\n\n"
#              "Можно выбрать нужный вариант или продолжить без фильтра.",
#         state=state,
#         reply_markup=keyboard,
#         parse_mode="Markdown"
#     )
