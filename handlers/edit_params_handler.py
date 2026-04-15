"""
Обработчик выборочного редактирования параметров.
Позволяет изменять отдельные параметры без повторного ввода всех данных.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from states.tour_states import TourSearchFlow
from keyboards.edit_params_keyboard import create_edit_params_keyboard, format_params_summary
from keyboards.find_tour_keyboard import (
    departure_city_keyboard,
    nights_keyboard,
    adults_keyboard,
    kids_keyboard,
    budget_keyboard,
    stars_keyboard
)
from keyboards.amenities_keyboard import create_amenities_keyboard
from models.tour_models import SearchParams, remove_duplicate_hotels
from services.leveltravel_service import LeveltravelService, LeveltravelAPIError
from utils.message_cleanup import send_and_delete_previous, delete_last_bot_message, clear_all_bot_messages

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "show_edit_menu")
async def show_edit_params_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню выборочного редактирования параметров"""
    data = await state.get_data()
    
    # Получаем параметры из state (могут быть из search_params или ai_parsed_params)
    search_params = data.get('search_params')
    ai_params = data.get('ai_parsed_params', {})
    
    # Объединяем параметры
    params = {}
    
    if search_params:
        # Если есть SearchParams объект
        params = {
            'from_city': search_params.from_city,
            'to_country': search_params.to_country,
            'to_city': search_params.to_city,
            'start_date': search_params.start_date,
            'nights': search_params.nights,
            'adults': search_params.adults,
            'kids': search_params.kids,
            'kids_ages': search_params.kids_ages,
            'min_price': search_params.min_price,
            'max_price': search_params.max_price,
            'min_stars': search_params.min_stars,
            'amenities': search_params.amenities
        }
    elif ai_params:
        # Если есть AI распознанные параметры
        params = {
            'from_city': ai_params.get('from_city'),
            'to_country': ai_params.get('country'),
            'to_city': ai_params.get('to_city'),
            'start_date': ai_params.get('start_date'),
            'nights': ai_params.get('nights'),
            'adults': ai_params.get('adults'),
            'kids': ai_params.get('kids'),
            'kids_ages': ai_params.get('kids_ages', []),
            'min_price': ai_params.get('min_budget'),
            'max_price': ai_params.get('max_budget'),
            'min_stars': ai_params.get('min_stars'),
            'amenities': ai_params.get('amenities', [])
        }
    else:
        # Берем из отдельных полей state
        params = {
            'from_city': data.get('from_city'),
            'to_country': data.get('to_country'),
            'to_city': data.get('to_city'),
            'start_date': data.get('start_date'),
            'nights': data.get('nights'),
            'adults': data.get('adults'),
            'kids': data.get('kids', 0),
            'kids_ages': data.get('kids_ages', []),
            'min_price': data.get('min_price'),
            'max_price': data.get('max_price'),
            'min_stars': data.get('min_stars'),
            'amenities': data.get('selected_amenities', [])
        }
    
    # Сохраняем в удобном формате для редактирования
    await state.update_data(editing_params=params)
    await state.set_state(TourSearchFlow.editing_params)
    
    # Формируем сообщение
    summary = format_params_summary(params)
    keyboard = create_edit_params_keyboard(**params)

    await callback.message.answer(
        summary,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_param_"), TourSearchFlow.editing_params)
async def edit_single_param(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование конкретного параметра"""
    param_name = callback.data.replace("edit_param_", "")
    
    # Сохраняем что редактируем
    await state.update_data(editing_param_name=param_name)
    
    # В зависимости от параметра переводим в нужное состояние и показываем клавиатуру
    if param_name == "from_city":
        await state.set_state(TourSearchFlow.editing_single_param)
        await callback.message.answer(
            "**Из какого города вылетаете?**",
            reply_markup=departure_city_keyboard,
            parse_mode="Markdown"
        )

    elif param_name == "country":
        from keyboards.find_tour_keyboard import create_country_keyboard
        await state.set_state(TourSearchFlow.editing_single_param)
        await callback.message.answer(
            "**Куда хотите полететь?**",
            reply_markup=create_country_keyboard(page=0),
            parse_mode="Markdown"
        )

    elif param_name == "dates":
        await state.set_state(TourSearchFlow.editing_single_param)
        await callback.message.answer(
            "**Введите дату вылета** (например: 20.10.2025):",
            parse_mode="Markdown"
        )

    elif param_name == "nights":
        await state.set_state(TourSearchFlow.editing_single_param)
        await callback.message.answer(
            "**Сколько ночей?**",
            reply_markup=nights_keyboard,
            parse_mode="Markdown"
        )

    elif param_name == "adults":
        await state.set_state(TourSearchFlow.editing_single_param)
        await callback.message.answer(
            "**Сколько взрослых?**",
            reply_markup=adults_keyboard,
            parse_mode="Markdown"
        )

    elif param_name == "kids":
        await state.set_state(TourSearchFlow.editing_single_param)
        await callback.message.answer(
            "**Сколько детей?** (от 0 до 18 лет)",
            reply_markup=kids_keyboard,
            parse_mode="Markdown"
        )

    elif param_name == "budget":
        await state.set_state(TourSearchFlow.editing_single_param)
        await callback.message.answer(
            "**Какой бюджет на всех?**",
            reply_markup=budget_keyboard,
            parse_mode="Markdown"
        )

    elif param_name == "stars":
        await state.set_state(TourSearchFlow.editing_single_param)
        await callback.message.answer(
            "**Минимальное количество звезд отеля?**",
            reply_markup=stars_keyboard,
            parse_mode="Markdown"
        )

    elif param_name == "amenities":
        await state.set_state(TourSearchFlow.editing_single_param)
        data = await state.get_data()
        params = data.get('editing_params', {})
        current_amenities = params.get('amenities', [])

        await callback.message.answer(
            "**Какие удобства важны?**\n\n"
            "Нажмите на нужные удобства, чтобы добавить их в фильтр.\n"
            "Можно выбрать несколько или продолжить без фильтров.",
            reply_markup=create_amenities_keyboard(current_amenities),
            parse_mode="Markdown"
        )
    
    await callback.answer()


# Обработчики для inline кнопок при редактировании

@router.callback_query(F.data.startswith("departure_"), TourSearchFlow.editing_single_param)
async def handle_departure_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора города вылета при редактировании"""
    city = callback.data.replace("departure_", "")
    
    data = await state.get_data()
    params = data.get('editing_params', {})
    
    if city == "other":
        await callback.message.answer("Введите название города на русском:")
        await callback.answer()
        return
    
    params['from_city'] = city
    await state.update_data(editing_params=params)
    
    # Возвращаемся к меню редактирования
    await return_to_edit_menu(callback, state)





@router.callback_query(F.data.startswith("country_page_"), TourSearchFlow.editing_single_param)
async def handle_country_page_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка навигации по страницам стран при редактировании."""
    page = int(callback.data.split('_')[-1])
    await callback.message.edit_reply_markup(
        reply_markup=create_country_keyboard(page=page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("country_"), TourSearchFlow.editing_single_param)
async def handle_country_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора страны при редактировании."""
    country_code = callback.data.replace("country_", "")
    
    data = await state.get_data()
    params = data.get('editing_params', {})
    params['to_country'] = country_code
    
    await state.update_data(editing_params=params)
    await return_to_edit_menu(callback, state)


@router.callback_query(F.data.startswith("nights_"), TourSearchFlow.editing_single_param)
async def handle_nights_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора количества ночей при редактировании"""
    nights = callback.data.replace("nights_", "")
    
    data = await state.get_data()
    params = data.get('editing_params', {})
    params['nights'] = nights
    
    await state.update_data(editing_params=params)
    await return_to_edit_menu(callback, state)


@router.callback_query(F.data.startswith("adults_"), TourSearchFlow.editing_single_param)
async def handle_adults_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора количества взрослых при редактировании"""
    adults = int(callback.data.replace("adults_", ""))
    
    data = await state.get_data()
    params = data.get('editing_params', {})
    params['adults'] = adults
    
    await state.update_data(editing_params=params)
    await return_to_edit_menu(callback, state)


@router.callback_query(F.data.startswith("kids_"), TourSearchFlow.editing_single_param)
async def handle_kids_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора количества детей при редактировании"""
    kids = int(callback.data.replace("kids_", ""))
    
    data = await state.get_data()
    params = data.get('editing_params', {})
    params['kids'] = kids
    
    if kids > 0:
        # Просим ввести возраста
        await callback.message.answer(
            f"Введите возраста {kids} детей через запятую:\n\n"
            f"Например: 5, 8"
        )
        await callback.answer()
        return
    else:
        params['kids_ages'] = []
        await state.update_data(editing_params=params)
        await return_to_edit_menu(callback, state)


@router.callback_query(F.data.startswith("budget_"), TourSearchFlow.editing_single_param)
async def handle_budget_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора бюджета при редактировании"""
    budget = callback.data.replace("budget_", "")
    
    data = await state.get_data()
    params = data.get('editing_params', {})
    
    if budget == "custom":
        await callback.message.answer("Введите ваш бюджет (в рублях):")
        await callback.answer()
        return
    elif budget == "no_limit":
        params['max_price'] = None
    else:
        params['max_price'] = int(budget)
    
    await state.update_data(editing_params=params)
    await return_to_edit_menu(callback, state)


@router.callback_query(F.data.startswith("stars_"), TourSearchFlow.editing_single_param)
async def handle_stars_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора звездности при редактировании"""
    stars = callback.data.replace("stars_", "")
    
    data = await state.get_data()
    params = data.get('editing_params', {})
    
    if stars == "no_filter":
        params['min_stars'] = None
    else:
        params['min_stars'] = int(stars)
    
    await state.update_data(editing_params=params)
    await return_to_edit_menu(callback, state)


@router.callback_query(F.data.startswith("amenity_toggle_"), TourSearchFlow.editing_single_param)
async def handle_amenity_toggle_edit(callback: CallbackQuery, state: FSMContext):
    """Обработка переключения удобства при редактировании"""
    amenity = callback.data.replace("amenity_toggle_", "")
    
    data = await state.get_data()
    params = data.get('editing_params', {})
    current_amenities = params.get('amenities', [])
    
    if amenity in current_amenities:
        current_amenities.remove(amenity)
    else:
        current_amenities.append(amenity)
    
    params['amenities'] = current_amenities
    await state.update_data(editing_params=params)
    
    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=create_amenities_keyboard(current_amenities)
    )
    await callback.answer()


@router.callback_query(F.data == "amenities_done", TourSearchFlow.editing_single_param)
async def handle_amenities_done_edit(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора удобств при редактировании"""
    await return_to_edit_menu(callback, state)


# Обработчик текстового ввода

@router.message(TourSearchFlow.editing_single_param)
async def handle_text_param_edit(message: Message, state: FSMContext):
    """Обработка текстового ввода при редактировании параметра"""
    data = await state.get_data()
    param_name = data.get('editing_param_name')
    params = data.get('editing_params', {})
    user_input = message.text.strip()
    
    if param_name == "dates":
        # Валидация даты
        from utils.helpers import validate_date
        is_valid, error_or_date = validate_date(user_input)
        
        if not is_valid:
            await message.answer(f"❌ {error_or_date}\n\nПопробуйте еще раз:")
            return
        
        params['start_date'] = error_or_date  # error_or_date содержит валидную дату
    
    elif param_name == "kids":
        # Обработка возрастов детей
        try:
            ages = [int(age.strip()) for age in user_input.split(',')]
            if any(age < 0 or age > 17 for age in ages):
                await message.answer("❌ Возраст детей должен быть от 0 до 17 лет.\n\nПопробуйте еще раз:")
                return
            
            params['kids_ages'] = ages
        except ValueError:
            await message.answer("❌ Неверный формат. Введите возраста через запятую, например: 5, 8")
            return
    
    elif param_name == "budget":
        # Обработка бюджета
        try:
            budget = int(user_input.replace(' ', '').replace(',', ''))
            if budget < 0:
                await message.answer("❌ Бюджет не может быть отрицательным.\n\nПопробуйте еще раз:")
                return
            params['max_price'] = budget
        except ValueError:
            await message.answer("❌ Введите число (например: 100000):")
            return
    
    elif param_name == "from_city":
        # Обработка города на русском
        from handlers.params_handler import RUSSIAN_CITIES
        city_lower = user_input.lower()
        
        if city_lower in RUSSIAN_CITIES:
            params['from_city'] = RUSSIAN_CITIES[city_lower]
        else:
            await message.answer(
                f"❌ Город '{user_input}' не найден в списке поддерживаемых городов.\n\n"
                f"Попробуйте один из: Москва, Санкт-Петербург, Казань, Екатеринбург, и т.д."
            )
            return
    
    await state.update_data(editing_params=params)
    await return_to_edit_menu(message, state)


async def return_to_edit_menu(message_or_callback, state: FSMContext):
    """Вернуться к меню редактирования параметров"""
    data = await state.get_data()
    params = data.get('editing_params', {})
    
    await state.set_state(TourSearchFlow.editing_params)
    
    summary = format_params_summary(params)
    keyboard = create_edit_params_keyboard(**params)
    
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.answer(
            summary,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await message_or_callback.answer()
    else:
        await message_or_callback.answer(
            summary,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )


@router.callback_query(F.data == "confirm_edited_params", TourSearchFlow.editing_params)
async def confirm_edited_params(callback: CallbackQuery, state: FSMContext):
    """Подтвердить отредактированные параметры и запустить поиск"""
    await callback.answer()
    await state.set_state(TourSearchFlow.searching_tours)
    
    loading_msg = await callback.message.answer("🔍 Ищем туры...")
    
    try:
        data = await state.get_data()
        params_dict = data.get('editing_params', {})
        
        # Создаем SearchParams
        params = SearchParams(
            from_city=params_dict.get('from_city', 'Moscow'),
            to_country=params_dict.get('to_country', 'TR'),
            to_city=params_dict.get('to_city'),  # ИСПРАВЛЕНО: добавлен город назначения
            adults=params_dict.get('adults', 2),
            start_date=params_dict.get('start_date', '20.10.2025'),
            nights=params_dict.get('nights', '7..9'),
            kids=params_dict.get('kids', 0),
            kids_ages=params_dict.get('kids_ages', []),
            min_price=params_dict.get('min_price'),
            max_price=params_dict.get('max_price'),
            min_stars=params_dict.get('min_stars'),
            amenities=params_dict.get('amenities', []),
            meal_types=data.get('selected_meals', [])
        )
        
        # Запускаем поиск
        service = LeveltravelService()
        request_id = await service.enqueue_search(params)
        
        logger.info(f"Поиск после редактирования запущен, request_id: {request_id}")
        
        await loading_msg.edit_text("🔍 Ищем туры..")
        
        # Ждем результатов
        await service.wait_for_results(request_id, timeout=60)
        
        await loading_msg.edit_text("🔍 Ищем туры...")
        
        # Получаем отели
        hotels, total_hotels_count = await service.get_hotels_page(
            request_id,
            search_params=params,
            page=1,
            limit=20
        )

        hotels = remove_duplicate_hotels(hotels)
        logger.info(f"После удаления дубликатов: {len(hotels)} отелей из {total_hotels_count} всего")

        # ========================================
        # MEAL FILTER DISABLED (2025-12-14)
        # ========================================
        # Фильтр по типу питания отключен. Пользователи видят все доступные варианты туров.
        # Закомментирован для возможности быстрого восстановления функционала.
        #
        # # Логируем типы питания первых 5 туров для отладки
        # if hotels:
        #     meal_types_sample = [h.meal_type for h in hotels[:5]]
        #     logger.info(f"Типы питания первых {min(5, len(hotels))} туров: {meal_types_sample}")
        #
        # # Применяем клиентский фильтр по типу питания
        # selected_meals = data.get('selected_meals', [])
        # logger.info(f"Selected meals from state: {selected_meals}")
        # if selected_meals:
        #     from models.tour_models import filter_hotels_by_meal
        #     from keyboards.meal_keyboard import expand_meal_types
        #
        #     # Разворачиваем упрощенные коды в полные списки API кодов
        #     expanded_meals = expand_meal_types(selected_meals)
        #     logger.info(f"Expanded meals after expand_meal_types: {expanded_meals}")
        #
        #     if expanded_meals:  # Фильтруем только если есть конкретные типы
        #         hotels_before_filter = len(hotels)
        #         hotels = filter_hotels_by_meal(hotels, expanded_meals)
        #         filtered_count = len(hotels)
        #         logger.info(f"Фильтр по питанию: {filtered_count} из {hotels_before_filter} отелей соответствуют критериям")
        #
        #         # Умная подгрузка: если отфильтрованных результатов < 10, загружаем еще страницы
        #         current_page = 1
        #         while filtered_count < 10 and current_page < 10:  # Лимит безопасности
        #             current_page += 1
        #             logger.info(f"Загружаем дополнительную страницу {current_page} для фильтрации")
        #
        #             new_hotels, _ = await service.get_hotels_page(
        #                 request_id,
        #                 search_params=params,
        #                 page=current_page,
        #                 limit=20
        #             )
        #
        #             if not new_hotels:
        #                 logger.info("Больше нет туров для загрузки")
        #                 break
        #
        #             new_hotels = remove_duplicate_hotels(new_hotels)
        #             new_hotels_filtered = filter_hotels_by_meal(new_hotels, expanded_meals)
        #             hotels.extend(new_hotels_filtered)
        #             filtered_count = len(hotels)
        #
        #             logger.info(f"Страница {current_page}: +{len(new_hotels_filtered)} туров, всего после фильтрации: {filtered_count}")
        #
        #         logger.info(f"Финальная фильтрация: {filtered_count} туров из {total_hotels_count} всего найденных")

        if not hotels:
            from utils.helpers import analyze_zero_results
            reason, suggestion = analyze_zero_results(params_dict)
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Изменить параметры", callback_data="show_edit_menu")],
                [InlineKeyboardButton(text="Главное меню", callback_data="start")]
            ])
            
            await loading_msg.edit_text(
                f"😔 {reason}\n\n{suggestion}",
                reply_markup=keyboard
            )
            return
        
        # Сохраняем результаты
        await state.update_data(
            request_id=request_id,
            hotels=hotels,
            current_index=0,
            current_page=1,
            search_params=params,
            total_hotels_count=total_hotels_count  # Сохраняем общее количество
        )

        await state.set_state(TourSearchFlow.browsing_tours)

        await loading_msg.edit_text(f"Найдено {total_hotels_count} туров! Сейчас покажу...")

        # Показываем первый тур
        from handlers.tour_feed_handler import show_tour_card
        await show_tour_card(callback.message, state, hotels[0], 0, total_hotels_count)
        
    except LeveltravelAPIError as e:
        logger.error(f"Ошибка API: {e}")
        await loading_msg.edit_text("😔 Произошла ошибка при поиске туров. Попробуйте позже.")
        await state.clear()


# Обработчики для callback'ов которые не должны делать ничего
@router.callback_query(F.data == "param_display")
@router.callback_query(F.data == "separator")
async def handle_display_callbacks(callback: CallbackQuery):
    """Обработка callback'ов для отображения (не интерактивных)"""
    await callback.answer()
