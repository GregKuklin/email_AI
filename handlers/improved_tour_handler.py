"""
Обработчик сценария свободного описания тура через AI.
Пользователь описывает желаемый тур свободным текстом,
ChatGPT парсит параметры и задает уточняющие вопросы.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging

from states.tour_states import TourSearchFlow
from services.openai_service import OpenAIService
from models.tour_models import SearchParams, format_search_summary, remove_duplicate_hotels
from services.leveltravel_service import LeveltravelService, LeveltravelAPIError
from keyboards.find_tour_keyboard import confirmation_keyboard
from utils.helpers import get_or_default
from utils.message_cleanup import send_and_delete_previous, delete_last_bot_message, clear_all_bot_messages

logger = logging.getLogger(__name__)
router = Router()
openai_service = OpenAIService()


@router.callback_query(F.data == "improved_questions")
async def start_free_text_flow(callback: CallbackQuery, state: FSMContext):
    """Начало сценария свободного описания"""
    # Очищаем state и начинаем новый flow
    await state.clear()
    await state.set_state(TourSearchFlow.waiting_free_text)

    # Отправляем первый вопрос и сохраняем его ID
    sent_msg = await callback.message.answer(
        "💬 **Опишите свободным текстом что хотите:**\n\n"
        "Например:\n"
        "_\"Хочу в Турцию из Москвы на неделю с 20 октября, 2 взрослых + ребенок 5 лет, "
        "бюджет до 80к, обязательно бассейн и детская анимация\"_\n\n"
        "Я проанализирую ваш запрос и помогу подобрать туры!",
        parse_mode="Markdown"
    )

    # Сохраняем ID первого вопроса
    await state.update_data(last_bot_message_id=sent_msg.message_id)
    await callback.answer()


@router.message(TourSearchFlow.waiting_free_text)
async def handle_free_text(message: Message, state: FSMContext):
    """Обработка свободного текста от пользователя"""
    user_text = message.text.strip()
    
    # Показываем индикатор
    loading_msg = await message.answer("🤖 Анализирую ваш запрос...")
    
    try:
        # Проверяем режим редактирования
        data = await state.get_data()
        is_editing = data.get('is_editing_context', False)
        
        if is_editing and data.get('ai_parsed_params'):
            # Режим редактирования с контекстом
            previous_params = data['ai_parsed_params']
            parsed_params = await openai_service.update_tour_params_with_context(
                previous_params, 
                user_text
            )
            # Сбрасываем флаг
            await state.update_data(is_editing_context=False)
            logger.info(f"Контекстное обновление параметров: {parsed_params}")
        else:
            # Обычный парсинг с нуля
            parsed_params = await openai_service.analyze_tour_params(user_text)
        
        # Сохраняем оригинальный текст и распознанные параметры
        await state.update_data(
            original_input=user_text,
            ai_parsed_params=parsed_params
        )
        
        logger.info(f"AI распознал параметры: {parsed_params}")
        
        # Определяем что распознано, что нет
        missing_params = []
        
        if not parsed_params.get('country'):
            missing_params.append('страна')
        if not parsed_params.get('start_date'):
            missing_params.append('даты')
        if not parsed_params.get('adults'):
            missing_params.append('количество взрослых')
        
        if missing_params:
            # Есть недостающие параметры - задаем уточняющий вопрос
            await state.set_state(TourSearchFlow.clarifying_params)
            await state.update_data(missing_params=missing_params, current_missing_index=0)
            
            await loading_msg.edit_text(
                f"✅ Понял!\n\n"
                f"Но мне нужно уточнить: **{', '.join(missing_params)}**\n\n"
                f"Давайте по порядку..."
            )
            
            # Задаем первый уточняющий вопрос
            await ask_missing_param(message, state, missing_params[0])
        else:
            # Все параметры распознаны - показываем подтверждение
            await loading_msg.delete()
            await show_ai_confirmation(message, state, parsed_params)
        
    except Exception as e:
        logger.error(f"Ошибка парсинга через AI: {e}", exc_info=True)
        await loading_msg.edit_text(
            "😔 Произошла ошибка при анализе. Попробуйте переформулировать запрос "
            "или воспользуйтесь сценарием 'Ввести параметры'."
        )


async def ask_missing_param(message: Message, state: FSMContext, param_name: str):
    """Задать уточняющий вопрос по недостающему параметру"""
    questions = {
        'страна': "🌍 **В какую страну хотите поехать?**\nНапример: Турция, Египет, ОАЭ, Таиланд",
        'даты': "📅 **Когда планируете поездку?**\nУкажите дату вылета в формате ДД.ММ.ГГГГ\nНапример: 20.07.2024",
        'количество взрослых': "👥 **Сколько взрослых едет?**\nНапример: 2"
    }
    
    await state.update_data(current_missing_param=param_name)
    await message.answer(questions.get(param_name, "Уточните параметр"), parse_mode="Markdown")


@router.message(TourSearchFlow.clarifying_params)
async def handle_clarification(message: Message, state: FSMContext):
    """Обработка ответа на уточняющий вопрос"""
    data = await state.get_data()
    param_name = data.get('current_missing_param')
    parsed_params = data.get('ai_parsed_params', {})
    missing_params = data.get('missing_params', [])
    current_index = data.get('current_missing_index', 0)

    # Обновляем параметр на основе ответа
    user_answer = message.text.strip()

    if param_name == 'страна':
        # Используем модуль country_data для распознавания страны
        from utils.country_data import get_country_iso_code

        country_code = get_country_iso_code(user_answer)

        if country_code:
            parsed_params['country'] = country_code
            logger.info(f"Страна распознана: {user_answer} -> {country_code}")
        else:
            # Страна не распознана - показываем ошибку и просим попробовать снова
            await message.answer(
                f"❌ **К сожалению, я не нашел такую страну.**\n\n"
                f"Пожалуйста, проверьте написание и попробуйте еще раз. Например: Турция, Египет, ОАЭ, Таиланд.\n\n"
                f"Или используйте кнопку **'Подобрать тур'** в меню, чтобы начать заново.",
                parse_mode="Markdown"
            )
            logger.warning(f"Не удалось распознать страну: '{user_answer}'")
            return  # Остаемся в том же состоянии, ждем нового ответа

    elif param_name == 'даты':
        parsed_params['start_date'] = user_answer

    elif param_name == 'количество взрослых':
        try:
            adults = int(user_answer)
            parsed_params['adults'] = adults
        except:
            pass

    await state.update_data(ai_parsed_params=parsed_params)

    # Проверяем есть ли еще недостающие параметры
    current_index += 1
    if current_index < len(missing_params):
        # Задаем следующий вопрос
        await state.update_data(current_missing_index=current_index)
        await ask_missing_param(message, state, missing_params[current_index])
    else:
        # Все параметры собраны - показываем подтверждение
        await show_ai_confirmation(message, state, parsed_params)


async def show_ai_confirmation(message: Message, state: FSMContext, parsed_params: dict):
    """Показать распознанные параметры для подтверждения"""
    await state.set_state(TourSearchFlow.ai_confirm_params)
    
    # Формируем сводку
    summary_text = "✅ **Вот что я понял из вашего запроса:**\n\n"
    
    summary_text += f"📍 **Откуда:** {parsed_params.get('from_city', 'Москва (по умолчанию)')}\n"
    summary_text += f"🌍 **Куда:** {get_country_name(parsed_params.get('country', ''))}\n"
    summary_text += f"📅 **Даты:** {parsed_params.get('start_date', 'не указано')}\n"
    
    if parsed_params.get('nights'):
        summary_text += f"🌙 **Ночей:** {parsed_params['nights']}\n"
    
    summary_text += f"👥 **Взрослых:** {parsed_params.get('adults', 'не указано')}\n"
    
    if parsed_params.get('kids'):
        kids_ages_str = ', '.join([str(age) for age in parsed_params.get('kids_ages', [])])
        summary_text += f"👶 **Детей:** {parsed_params['kids']} ({kids_ages_str} лет)\n"
    
    if parsed_params.get('min_budget') or parsed_params.get('max_budget'):
        budget_str = ""
        if parsed_params.get('min_budget') and parsed_params.get('max_budget'):
            budget_str = f"{parsed_params['min_budget']:,} - {parsed_params['max_budget']:,}₽"
        elif parsed_params.get('max_budget'):
            budget_str = f"до {parsed_params['max_budget']:,}₽"
        summary_text += f"💰 **Бюджет:** {budget_str}\n"
    
    if parsed_params.get('amenities'):
        amenities_names = get_amenities_names(parsed_params['amenities'])
        summary_text += f"\n🏊 **Удобства:** {', '.join(amenities_names)}\n"
    
    summary_text += "\n**Всё верно?**"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, искать туры!", callback_data="ai_confirm_search")],
        [InlineKeyboardButton(text="✏️ Уточнить ещё", callback_data="ai_clarify_more")],
        [InlineKeyboardButton(text="🔄 Начать сначала", callback_data="improved_questions")]
    ])
    
    await message.answer(summary_text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "ai_confirm_search")
async def confirm_ai_search(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и запуск поиска из AI сценария"""
    await callback.answer()
    await state.set_state(TourSearchFlow.searching_tours)

    # Удаляем последний вопрос бота (подтверждение)
    await delete_last_bot_message(callback.bot, callback.message.chat.id, state)

    # Показываем индикатор загрузки
    loading_msg = await callback.message.answer("🔍 Ищем туры...")

    try:
        # Получаем распознанные параметры
        data = await state.get_data()
        parsed_params = data.get('ai_parsed_params', {})
        
        # Создаем SearchParams с обработкой None значений
        # Используем get_or_default вместо dict.get, т.к. ChatGPT может вернуть явный None
        params = SearchParams(
            from_city=get_or_default(parsed_params.get('from_city'), 'Moscow'),
            to_country=get_or_default(parsed_params.get('country'), 'TR'),
            to_city=parsed_params.get('to_city'),  # None допустимо - поиск по всей стране
            adults=get_or_default(parsed_params.get('adults'), 2),
            start_date=get_or_default(parsed_params.get('start_date'), '20.10.2025'),
            nights=get_or_default(parsed_params.get('nights'), '7..9'),
            kids=get_or_default(parsed_params.get('kids'), 0),
            kids_ages=get_or_default(parsed_params.get('kids_ages'), []),
            min_price=parsed_params.get('min_budget'),  # None допустимо
            max_price=parsed_params.get('max_budget'),  # None допустимо
            amenities=get_or_default(parsed_params.get('amenities'), [])
        )
        
        # Валидация обязательных полей
        if not params.from_city or not params.to_country:
            await loading_msg.edit_text(
                "😔 Не удалось распознать направление тура.\n\n"
                "Пожалуйста, попробуйте указать:\n"
                "• Откуда летите (город)\n"
                "• Куда хотите поехать (страна/курорт)\n\n"
                "Например: 'Турция из Москвы'"
            )
            await state.clear()
            return
        
        # Запускаем поиск
        service = LeveltravelService()
        request_id = await service.enqueue_search(params)
        
        logger.info(f"AI поиск запущен, request_id: {request_id}")
        
        # Обновляем индикатор
        await loading_msg.edit_text("🔍 Ищем туры..")
        
        # Ждем результатов
        await service.wait_for_results(request_id, timeout=60)
        
        await loading_msg.edit_text("🔍 Ищем туры...")
        
        # Получаем первую страницу отелей с применением фильтров
        hotels, total_hotels_count = await service.get_hotels_page(
            request_id,
            search_params=params,  # Передаём SearchParams для применения фильтров
            page=1,
            limit=20
        )

        # Убираем дубликаты отелей
        hotels = remove_duplicate_hotels(hotels)
        logger.info(f"После удаления дубликатов осталось {len(hotels)} уникальных отелей из {total_hotels_count} всего")

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
            # Удаляем loading сообщение
            try:
                await loading_msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить loading: {e}")

            # Анализируем причину отсутствия результатов
            from utils.helpers import analyze_zero_results
            data = await state.get_data()
            reason, suggestion = analyze_zero_results(data)

            # Создаем клавиатуру для повторной попытки
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="improved_questions")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="start")]
            ])

            # Отправляем НОВОЕ сообщение об ошибке
            await callback.message.answer(
                f"😔 {reason}\n\n{suggestion}",
                reply_markup=keyboard
            )
            return
        
        # Сохраняем результаты в state
        await state.update_data(
            request_id=request_id,
            hotels=hotels,
            current_index=0,
            current_page=1,
            search_params=params,
            total_hotels_count=total_hotels_count  # Сохраняем общее количество
        )

        # Переходим к просмотру туров
        await state.set_state(TourSearchFlow.browsing_tours)

        # Удаляем loading сообщение перед показом туров
        try:
            await loading_msg.delete()
        except Exception as e:
            logger.debug(f"Не удалось удалить loading: {e}")

        # Импортируем и показываем первый тур
        from handlers.tour_feed_handler import show_tour_card
        await show_tour_card(callback.message, state, hotels[0], 0, total_hotels_count)
        
    except LeveltravelAPIError as e:
        logger.error(f"Ошибка API: {e}")

        # Удаляем loading сообщение
        try:
            await loading_msg.delete()
        except Exception as e:
            logger.debug(f"Не удалось удалить loading: {e}")

        # Отправляем НОВОЕ сообщение об ошибке
        await callback.message.answer(
            "😔 Произошла ошибка при поиске туров. Попробуйте позже."
        )
        await state.clear()


@router.callback_query(F.data == "ai_clarify_more")
async def clarify_more(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет уточнить параметры"""
    # Сохраняем флаг что это редактирование с контекстом
    await state.update_data(is_editing_context=True)
    
    await callback.message.answer(
        "📝 **Напишите что хотите изменить:**\n\n"
        "Например:\n"
        "• 'изменить бюджет на 120к'\n"
        "• 'добавить бассейн и спа'\n"
        "• 'вместо Турции в Египет'\n"
        "• '3 детей: 5, 7 и 10 лет'\n\n"
        "Я обновлю только то, что вы укажете, остальное останется без изменений.",
        parse_mode="Markdown"
    )
    await state.set_state(TourSearchFlow.ai_editing_context)
    await callback.answer()


@router.message(TourSearchFlow.ai_editing_context)
async def handle_contextual_edit(message: Message, state: FSMContext):
    """Обработка контекстного изменения параметров через AI"""
    user_text = message.text.strip()
    loading_msg = await message.answer("🤖 Обновляю параметры...")
    
    try:
        data = await state.get_data()
        previous_params = data.get('ai_parsed_params', {})
        
        if not previous_params:
            # Нет предыдущих параметров - переключаемся на обычный парсинг
            await loading_msg.edit_text("😔 Не могу найти предыдущие параметры. Давайте начнем заново.")
            await state.set_state(TourSearchFlow.waiting_free_text)
            return
        
        # Используем новый метод с контекстом
        updated_params = await openai_service.update_tour_params_with_context(
            previous_params, 
            user_text
        )
        
        # Сохраняем обновленные параметры
        await state.update_data(ai_parsed_params=updated_params)
        
        logger.info(f"Параметры обновлены контекстно: {updated_params}")
        
        # Показываем подтверждение
        await loading_msg.delete()
        await show_ai_confirmation(message, state, updated_params)
        
    except Exception as e:
        logger.error(f"Ошибка обновления параметров: {e}", exc_info=True)
        await loading_msg.edit_text(
            "😔 Не удалось обновить параметры. Попробуйте переформулировать или начните заново."
        )


# Вспомогательные функции

def get_country_name(country_code: str) -> str:
    """Получить название страны по коду"""
    countries = {
        'TR': '🇹🇷 Турция',
        'EG': '🇪🇬 Египет',
        'AE': '🇦🇪 ОАЭ',
        'TH': '🇹🇭 Таиланд',
        'GR': '🇬🇷 Греция',
        'ES': '🇪🇸 Испания',
    }
    return countries.get(country_code, country_code or 'не указано')


def get_amenities_names(amenities_codes: list) -> list:
    """Получить названия удобств по кодам"""
    amenities_map = {
        'pool': 'Бассейн',
        'heated_pool': 'Подогреваемый бассейн',
        'spa': 'СПА/Массаж',
        'gym': 'Тренажерный зал',
        'wifi': 'Wi-Fi',
        'bar': 'Бар',
        'kids_club': 'Детский клуб',
        'kids_pool': 'Детский бассейн',
        'aquapark': 'Аквапарк',
    }
    return [amenities_map.get(code, code) for code in amenities_codes]
