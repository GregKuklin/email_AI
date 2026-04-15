"""
Обработчик бесконечной ленты туров.
Отображает туры с фотографиями и навигацией.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
import logging

from states.tour_states import TourSearchFlow
from models.tour_models import HotelCard, remove_duplicate_hotels, SearchParams
from services.leveltravel_service import LeveltravelService
from services.photo_service import prepare_media_group
from utils.city_data import get_alternative_cities, get_city_russian_name

logger = logging.getLogger(__name__)
router = Router()


async def delete_previous_messages(bot, chat_id: int, message_ids: list):
    """
    Удалить список предыдущих сообщений.

    Args:
        bot: Bot instance
        chat_id: ID чата
        message_ids: Список ID сообщений для удаления
    """
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение {msg_id}: {e}")


async def handle_no_more_tours(callback: CallbackQuery, state: FSMContext, search_params: SearchParams, data: dict):
    """
    Обработка ситуации когда закончились туры.
    Если был указан конкретный город, пробуем переключиться на другие города страны.

    Args:
        callback: CallbackQuery объект
        state: FSMContext
        search_params: Параметры текущего поиска
        data: Данные из state
    """
    # Проверяем, был ли указан конкретный город назначения
    if not search_params or not search_params.to_city:
        # Поиск был по всей стране - больше туров нет
        await callback.answer(
            "Это все доступные туры!\n\n"
            "💡 Вы можете изменить критерии поиска для большего выбора.",
            show_alert=True
        )
        return

    # Получаем список уже проверенных городов
    tried_cities = data.get('tried_cities', [])
    if not tried_cities:
        tried_cities = [search_params.to_city]

    # Получаем альтернативные города
    alternative_cities = get_alternative_cities(
        search_params.to_country,
        search_params.to_city,
        max_alternatives=5  # Получаем больше вариантов
    )

    # Фильтруем только те, которые еще не пробовали
    remaining_alternatives = [
        (eng, rus) for eng, rus in alternative_cities
        if eng not in tried_cities
    ]

    if not remaining_alternatives:
        # Все города в стране уже проверены
        current_city_russian = get_city_russian_name(search_params.to_country, search_params.to_city)
        tried_cities_russian = []
        for city_eng in tried_cities:
            city_rus = get_city_russian_name(search_params.to_country, city_eng)
            if city_rus:
                tried_cities_russian.append(city_rus)

        message = (
            f"🔍 Туры в {current_city_russian} закончились.\n\n"
            f"Мы проверили все основные города:\n"
            f"• {', '.join(tried_cities_russian)}\n\n"
            f"💡 Рекомендации:\n"
            f"• Измените даты поездки\n"
            f"• Увеличьте бюджет\n"
            f"• Попробуйте другую страну\n"
            f"• Уменьшите требования по звездности\n\n"
            f"Используйте кнопку '✏️ Изменить критерии' ниже."
        )
        await callback.answer(message, show_alert=True)
        return

    # Берем первый непроверенный город
    next_city_eng, next_city_rus = remaining_alternatives[0]
    current_city_russian = get_city_russian_name(search_params.to_country, search_params.to_city)

    # Показываем уведомление пользователю
    await callback.message.answer(
        f"📍 Туры в <b>{current_city_russian}</b> закончились.\n\n"
        f"🔄 Начинаю поиск туров в <b>{next_city_rus}</b>...\n\n"
        f"💡 <i>Вы всегда можете изменить критерии поиска с помощью кнопки '✏️ Изменить критерии'</i>",
        parse_mode="HTML"
    )

    logger.info(
        f"Туры в {search_params.to_city} ({current_city_russian}) закончились. "
        f"Переключаемся на {next_city_eng} ({next_city_rus})"
    )

    try:
        # Обновляем параметры поиска с новым городом
        new_params = SearchParams(
            from_city=search_params.from_city,
            to_country=search_params.to_country,
            to_city=next_city_eng,  # НОВЫЙ ГОРОД
            adults=search_params.adults,
            start_date=search_params.start_date,
            nights=search_params.nights,
            kids=search_params.kids,
            kids_ages=search_params.kids_ages,
            min_price=search_params.min_price,
            max_price=search_params.max_price,
            min_stars=search_params.min_stars,
            exact_stars=search_params.exact_stars,
            amenities=search_params.amenities,
            meal_types=search_params.meal_types
        )

        # Запускаем новый поиск
        service = LeveltravelService()
        new_request_id = await service.enqueue_search(new_params)

        # Показываем индикатор загрузки
        loading_msg = await callback.message.answer("⏳ Поиск туров...")

        # Ждем результатов
        await service.wait_for_results(new_request_id)

        # Получаем первую страницу отелей
        new_hotels, total_count = await service.get_hotels_page(
            new_request_id,
            search_params=new_params,
            page=1,
            limit=20
        )

        # Удаляем индикатор загрузки
        await loading_msg.delete()

        if not new_hotels:
            # И в этом городе туров нет - добавляем в список проверенных и пробуем следующий
            tried_cities.append(next_city_eng)
            await state.update_data(
                search_params=new_params,
                tried_cities=tried_cities
            )

            await callback.message.answer(
                f"😔 К сожалению, в <b>{next_city_rus}</b> тоже нет туров под ваши критерии.\n\n"
                f"Попробуем следующий город...",
                parse_mode="HTML"
            )

            # Рекурсивно пробуем следующий город
            await handle_no_more_tours(callback, state, new_params, await state.get_data())
            return

        # Убираем дубликаты
        new_hotels = remove_duplicate_hotels(new_hotels)

        # ========================================
        # MEAL FILTER DISABLED (2025-12-14)
        # ========================================
        # Фильтр по типу питания при переключении городов отключен.
        # Пользователи видят все доступные варианты туров.
        #
        # # Применяем клиентский фильтр по типу питания (если был выбран)
        # selected_meals = data.get('selected_meals', [])
        # if selected_meals and new_hotels:
        #     from models.tour_models import filter_hotels_by_meal
        #     from keyboards.meal_keyboard import expand_meal_types
        #
        #     expanded_meals = expand_meal_types(selected_meals)
        #     if expanded_meals:
        #         hotels_before_filter = len(new_hotels)
        #         new_hotels = filter_hotels_by_meal(new_hotels, expanded_meals)
        #         logger.info(f"Фильтр питания при смене города: {len(new_hotels)} из {hotels_before_filter} туров")
        #
        #         # Если после фильтрации туров не осталось - продолжаем искать в других городах
        #         if not new_hotels:
        #             logger.info(f"После фильтрации питания в {next_city_rus} туров не осталось")
        #             tried_cities.append(next_city_eng)
        #             await state.update_data(
        #                 search_params=new_params,
        #                 tried_cities=tried_cities
        #             )
        #             await callback.message.answer(
        #                 f"😔 В <b>{next_city_rus}</b> нет туров с выбранным типом питания.\n\n"
        #                 f"Попробуем следующий город...",
        #                 parse_mode="HTML"
        #             )
        #             await handle_no_more_tours(callback, state, new_params, await state.get_data())
        #             return

        # Успех! Сохраняем новые данные
        tried_cities.append(next_city_eng)
        await state.update_data(
            hotels=new_hotels,
            total_hotels_count=total_count,
            current_index=0,
            current_page=1,
            request_id=new_request_id,
            search_params=new_params,
            tried_cities=tried_cities
        )

        await callback.message.answer(
            f"✅ Найдено <b>{total_count}</b> туров в <b>{next_city_rus}</b>!\n\n"
            f"Показываю первый тур:",
            parse_mode="HTML"
        )

        # Показываем первый тур из нового города
        await show_tour_card(callback.message, state, new_hotels[0], 0, total_count)

        logger.info(f"Успешно переключились на {next_city_rus}, найдено {total_count} туров")

    except Exception as e:
        logger.error(f"Ошибка при переключении на другой город: {e}", exc_info=True)
        await callback.message.answer(
            f"😔 Произошла ошибка при поиске туров в <b>{next_city_rus}</b>.\n\n"
            f"Попробуйте изменить критерии поиска.",
            parse_mode="HTML"
        )


def generate_booking_url(tour_id: str, hotel_id: int, request_id: str) -> str:
    """
    Генерировать партнерскую ссылку на бронирование.

    Args:
        tour_id: ID тура
        hotel_id: ID отеля
        request_id: ID поискового запроса

    Returns:
        Партнерская URL для бронирования через tp.media
    """
    from urllib.parse import quote

    level_url = f"https://level.travel/package_details/{tour_id}?hotel_id={hotel_id}&request_id={request_id}"
    encoded_url = quote(level_url, safe='')
    booking_url = (
        f"https://tp.media/r?"
        f"marker=624775&"
        f"trs=409439&"
        f"p=660&"
        f"u={encoded_url}&"
        f"campaign_id=26"
    )
    return booking_url


async def show_tour_card(message: Message, state: FSMContext, hotel: HotelCard, index: int, total: int):
    """
    Отобразить карточку тура с фотографиями.

    Args:
        message: Message объект для отправки
        state: FSMContext
        hotel: HotelCard с данными отеля
        index: Текущий индекс тура
        total: Общее количество туров
    """
    try:
        # Получаем данные из state
        data = await state.get_data()
        search_params = data.get('search_params')
        request_id = data.get('request_id')

        # Удаляем предыдущие сообщения карточки тура
        previous_message_ids = data.get('tour_card_message_ids', [])
        if previous_message_ids:
            await delete_previous_messages(message.bot, message.chat.id, previous_message_ids)
        
        # Обновляем дату вылета в hotel card
        if search_params:
            hotel.start_date = search_params.start_date
        
        # === НОВОЕ: Получаем фото отеля + номеров ===
        rooms_cache_key = f"rooms_{hotel.hotel_id}"
        rooms_data = data.get(rooms_cache_key)
        
        # Если данных нет в кэше - запрашиваем
        if not rooms_data and request_id:
            try:
                service = LeveltravelService()
                rooms_data = await service.get_hotel_rooms(request_id, hotel.hotel_id)
                
                # Сохраняем в state для следующих просмотров
                if rooms_data:
                    await state.update_data({rooms_cache_key: rooms_data})
                    logger.info(f"Закэшированы данные о номерах для отеля {hotel.hotel_id}")
            except Exception as e:
                logger.error(f"Ошибка получения данных о номерах: {e}")
                rooms_data = None
        
        # Готовим смешанные фото
        from services.photo_service import get_mixed_photos
        mixed_photos = await get_mixed_photos(hotel, request_id, rooms_data)

        # Список для хранения ID новых сообщений
        new_message_ids = []

        # 1. Отправляем фото (одно отдельно или MediaGroup для 2+)
        if len(mixed_photos) == 1:
            # Telegram MediaGroup требует минимум 2 фото
            # Если только 1 фото - отправляем отдельно
            caption = f"🏨 <b>{hotel.hotel_name}</b> {hotel.format_stars()}\n"
            caption += f"📍 {hotel.city}, {hotel.region}\n"
            caption += f"💰 от {hotel.format_price()}\n"
            caption += f"🍽️ {hotel.meal_description}"

            try:
                sent_msg = await message.answer_photo(
                    photo=mixed_photos[0],
                    caption=caption,
                    parse_mode="HTML"
                )
                new_message_ids.append(sent_msg.message_id)
                logger.info(f"Отправлено 1 фото отдельно для отеля {hotel.hotel_name}")
            except Exception as e:
                logger.error(f"Не удалось отправить фото: {e}. Продолжаем без фото.")
        else:
            # 2+ фото - отправляем MediaGroup
            media = prepare_media_group(hotel, add_caption=True, mixed_photos=mixed_photos)
            try:
                sent_messages = await message.answer_media_group(media=media)
                # MediaGroup возвращает список сообщений
                new_message_ids.extend([msg.message_id for msg in sent_messages])
                logger.info(f"Отправлен MediaGroup из {len(mixed_photos)} фото")
            except Exception as e:
                # Ошибка отправки MediaGroup (WEBPAGE_CURL_FAILED и т.д.)
                logger.error(f"Ошибка отправки MediaGroup: {e}")
                logger.info(f"Попытка отправить фото по одному...")

                # Пробуем отправить фото по одному, пропуская проблемные
                photos_sent = 0
                for i, photo_url in enumerate(mixed_photos):
                    try:
                        if i == 0:
                            # Первое фото с описанием
                            caption = f"🏨 <b>{hotel.hotel_name}</b> {hotel.format_stars()}\n"
                            caption += f"📍 {hotel.city}, {hotel.region}\n"
                            caption += f"💰 от {hotel.format_price()}\n"
                            caption += f"🍽️ {hotel.meal_description}"
                        else:
                            caption = None

                        sent_msg = await message.answer_photo(
                            photo=photo_url,
                            caption=caption,
                            parse_mode="HTML" if caption else None
                        )
                        new_message_ids.append(sent_msg.message_id)
                        photos_sent += 1

                        # Ограничиваем максимум 3 фото при отправке по одному
                        if photos_sent >= 3:
                            break
                    except Exception as photo_error:
                        logger.warning(f"Пропускаем фото {i+1}: {photo_error}")
                        continue

                if photos_sent > 0:
                    logger.info(f"Успешно отправлено {photos_sent} фото по одному")
                else:
                    logger.warning(f"Не удалось отправить ни одного фото для {hotel.hotel_name}")
        
        # 2. Генерируем GPT-описание отеля
        gpt_description = ""
        try:
            from services.openai_service import OpenAIService
            openai_service = OpenAIService()

            # Подготавливаем данные для GPT
            hotel_data = {
                'hotel_name': hotel.hotel_name,
                'stars': hotel.stars,
                'rating': hotel.rating,
                'city': hotel.city,
                'region': hotel.region,
                'features': {
                    'beach_distance': hotel.features.beach_distance if hotel.features else None,
                    'line': hotel.features.line if hotel.features else None,
                    'wi_fi': hotel.features.wi_fi if hotel.features else None
                },
                'meal_description': hotel.meal_description,
                'price': hotel.min_price
            }

            gpt_description = await openai_service.generate_hotel_description(hotel_data)
            logger.info(f"Сгенерировано GPT-описание для {hotel.hotel_name}")
        except Exception as e:
            logger.error(f"Ошибка генерации GPT-описания: {e}", exc_info=True)
            # Продолжаем без GPT-описания (будет использован fallback)

        # 3. Отправляем текстовое описание
        text = await format_tour_description(hotel, index, total, gpt_description)

        # 4. Создаем inline клавиатуру
        keyboard = create_tour_navigation_keyboard(index, total, hotel.tour_id, hotel.hotel_id, request_id)

        # 5. Отправляем сообщение с описанием и кнопками
        sent_text_msg = await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        new_message_ids.append(sent_text_msg.message_id)

        # 6. Сохраняем ID всех отправленных сообщений в state
        await state.update_data(tour_card_message_ids=new_message_ids)

        logger.info(f"Показан тур: {hotel.hotel_name}, сохранено {len(new_message_ids)} ID сообщений")
        
    except Exception as e:
        logger.error(f"Ошибка отображения карточки тура: {e}", exc_info=True)
        await message.answer(
            "😔 Произошла ошибка при загрузке тура. Попробуйте следующий."
        )


async def format_tour_description(hotel: HotelCard, index: int, total: int, gpt_description: str = "") -> str:
    """
    Форматировать описание тура для отображения.

    Args:
        hotel: HotelCard
        index: Текущий индекс (локальный в загруженных турах)
        total: Всего туров (общее количество из API)
        gpt_description: GPT-сгенерированное описание отеля

    Returns:
        Форматированная строка
    """
    # Форматируем позицию с пробелами для читаемости
    def format_number(n: int) -> str:
        """Форматирует число с пробелами: 3622 → 3 622"""
        return f"{n:,}".replace(',', ' ')

    # Унифицированный формат карточки
    text = f"**Тур {index + 1} из {format_number(total)}**\n\n"
    text += f"🏨 **{hotel.hotel_name}** {hotel.format_stars()}\n"
    text += f"📍 {hotel.city}, {hotel.region}\n"
    text += f"📅 {hotel.start_date} • {hotel.nights} ночей\n"
    text += f"💰 от {hotel.format_price()}₽\n"
    text += f"_Цены актуальны на момент подбора и могут меняться_\n\n"

    # GPT-описание (4-5 предложений)
    if gpt_description:
        text += f"{gpt_description}"
    else:
        # Fallback на случай ошибки GPT
        text += f"⭐ Рейтинг: {hotel.rating}/10\n"
        text += f"{hotel.get_meal_emoji()} Питание: {hotel.meal_description}"

    return text


def create_tour_navigation_keyboard(index: int, total: int, tour_id: str, hotel_id: int, request_id: str) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру навигации по турам.

    Args:
        index: Текущий индекс
        total: Всего туров
        tour_id: ID тура
        hotel_id: ID отеля
        request_id: ID поискового запроса

    Returns:
        InlineKeyboardMarkup
    """
    buttons = []

    # Первый ряд: навигация (упрощенная)
    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data="tour_prev"))
    nav_row.append(InlineKeyboardButton(text="➡️", callback_data="tour_next"))
    buttons.append(nav_row)

    # Генерируем партнерскую ссылку
    from urllib.parse import quote
    level_url = f"https://level.travel/package_details/{tour_id}?hotel_id={hotel_id}&request_id={request_id}"
    encoded_url = quote(level_url, safe='')
    booking_url = (
        f"https://tp.media/r?"
        f"marker=624775&"
        f"trs=409439&"
        f"p=660&"
        f"u={encoded_url}&"
        f"campaign_id=26"
    )

    # Каждая кнопка в отдельном ряду
    buttons.append([
        InlineKeyboardButton(text="💬 Спросить больше", callback_data=f"hotel_question_{hotel_id}")
    ])

    buttons.append([
        InlineKeyboardButton(text="🔗 Забронировать", url=booking_url)
    ])

    buttons.append([
        InlineKeyboardButton(text="💾 Сохранить в заметки", callback_data=f"tour_save_{hotel_id}")
    ])

    buttons.append([
        InlineKeyboardButton(text="✏️ Изменить критерии", callback_data="change_criteria")
    ])

    buttons.append([
        InlineKeyboardButton(text="🏠 Вернуться к подборке", callback_data="return_to_start")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "tour_next", TourSearchFlow.browsing_tours)
async def next_tour(callback: CallbackQuery, state: FSMContext):
    """Показать следующий тур"""
    try:
        data = await state.get_data()
        current_index = data.get('current_index', 0)
        hotels = data.get('hotels', [])
        request_id = data.get('request_id')
        current_page = data.get('current_page', 1)
        
        # Переходим к следующему туру
        current_index += 1
        
        # Проверяем: нужно ли загрузить следующую страницу?
        if current_index >= len(hotels):
            # Показываем индикатор
            await callback.answer("⏳ Загружаем еще туры...", show_alert=False)
            
            # Загружаем следующую страницу
            service = LeveltravelService()
            search_params = data.get('search_params')  # Получаем SearchParams из state
            new_hotels, _ = await service.get_hotels_page(  # _ игнорируем, т.к. total уже сохранен
                request_id,
                search_params=search_params,  # Применяем те же фильтры
                page=current_page + 1,
                limit=20
            )

            # Убираем дубликаты в новой странице
            new_hotels = remove_duplicate_hotels(new_hotels)

            # ========================================
            # MEAL FILTER DISABLED (2025-12-14)
            # ========================================
            # Фильтр по типу питания при пагинации отключен.
            # Пользователи видят все доступные варианты туров.
            #
            # # Применяем клиентский фильтр по типу питания (если был выбран)
            # selected_meals = data.get('selected_meals', [])
            # if selected_meals and new_hotels:
            #     from models.tour_models import filter_hotels_by_meal
            #     from keyboards.meal_keyboard import expand_meal_types
            #
            #     expanded_meals = expand_meal_types(selected_meals)
            #     if expanded_meals:
            #         hotels_before_filter = len(new_hotels)
            #         new_hotels = filter_hotels_by_meal(new_hotels, expanded_meals)
            #         logger.info(f"Фильтр питания при пагинации: {len(new_hotels)} из {hotels_before_filter} туров соответствуют")

            # Убираем отели которые уже есть в ленте
            existing_ids = {h.hotel_id for h in hotels}
            new_hotels = [h for h in new_hotels if h.hotel_id not in existing_ids]

            logger.info(f"Загружено {len(new_hotels)} новых уникальных отелей")

            if new_hotels:
                # Добавляем новые туры
                hotels.extend(new_hotels)
                await state.update_data(
                    current_page=current_page + 1,
                    hotels=hotels
                )
                logger.info(f"Загружена страница {current_page + 1}, всего туров: {len(hotels)}")
            else:
                # Больше туров нет - проверяем, можно ли переключиться на другие города
                await handle_no_more_tours(callback, state, search_params, data)
                return
        
        # Сохраняем новый индекс
        await state.update_data(current_index=current_index)

        # Показываем тур
        hotel = hotels[current_index]
        total_hotels_count = data.get('total_hotels_count', len(hotels))
        await show_tour_card(callback.message, state, hotel, current_index, total_hotels_count)
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при переходе к следующему туру: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "tour_prev", TourSearchFlow.browsing_tours)
async def prev_tour(callback: CallbackQuery, state: FSMContext):
    """Показать предыдущий тур"""
    try:
        data = await state.get_data()
        current_index = data.get('current_index', 0)
        hotels = data.get('hotels', [])
        
        if current_index > 0:
            current_index -= 1
            await state.update_data(current_index=current_index)

            hotel = hotels[current_index]
            total_hotels_count = data.get('total_hotels_count', len(hotels))
            await show_tour_card(callback.message, state, hotel, current_index, total_hotels_count)
        else:
            await callback.answer("Это первый тур!", show_alert=False)
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при переходе к предыдущему туру: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "tour_info", TourSearchFlow.browsing_tours)
async def tour_info(callback: CallbackQuery, state: FSMContext):
    """Показать информацию о текущей позиции"""
    data = await state.get_data()
    current_index = data.get('current_index', 0)
    total_hotels_count = data.get('total_hotels_count', 0)

    # Форматируем число с пробелами
    def format_number(n: int) -> str:
        return f"{n:,}".replace(',', ' ')

    await callback.answer(
        f"Вы просматриваете тур {current_index + 1} из {format_number(total_hotels_count)}",
        show_alert=False
    )


@router.callback_query(F.data.startswith("tour_pdf_"), TourSearchFlow.browsing_tours)
async def generate_tour_pdf(callback: CallbackQuery, state: FSMContext):
    """Сгенерировать подробный PDF с информацией о туре"""
    await callback.answer("📄 Собираю информацию о туре...", show_alert=False)
    
    try:
        data = await state.get_data()
        current_index = data.get('current_index', 0)
        hotels = data.get('hotels', [])
        request_id = data.get('request_id')
        
        if current_index < len(hotels):
            hotel = hotels[current_index]
            
            # Запрашиваем подробности о номерах
            service = LeveltravelService()
            
            try:
                rooms_data = await service.get_hotel_rooms(request_id, hotel.hotel_id)
                logger.info(f"Получены данные о {len(rooms_data) if isinstance(rooms_data, list) else 0} типах номеров")
            except Exception as e:
                logger.error(f"Ошибка получения данных о номерах: {e}")
                rooms_data = []
            
            # Генерируем PDF
            from services.pdf_generator import PDFGenerator
            generator = PDFGenerator()
            pdf_buffer = await generator.generate_detailed_tour_pdf(
                hotel,
                rooms_data,
                request_id
            )
            
            # Отправляем пользователю
            filename = f"tour_{hotel.hotel_name.replace(' ', '_')[:30]}.pdf"
            await callback.message.answer_document(
                BufferedInputFile(
                    pdf_buffer.read(),
                    filename=filename
                ),
                caption=f"📄 Подробная информация о туре в {hotel.hotel_name}",
                parse_mode="Markdown"
            )
            
            logger.info(f"PDF успешно сгенерирован и отправлен для {hotel.hotel_name}")
        
    except Exception as e:
        logger.error(f"Ошибка генерации PDF: {e}", exc_info=True)
        await callback.message.answer("😔 Произошла ошибка при генерации PDF. Попробуйте позже.")


@router.callback_query(F.data.startswith("hotel_question_"), TourSearchFlow.browsing_tours)
async def start_hotel_question(callback: CallbackQuery, state: FSMContext):
    hotel_id_str = callback.data.replace("hotel_question_", "")
    hotel_id = int(hotel_id_str)
    
    # Сохраняем hotel_id в state для последующего использования
    await state.update_data(question_hotel_id=hotel_id)
    await state.set_state(TourSearchFlow.asking_hotel_question)
    
    await callback.message.answer(
        "❓ Задайте ваш вопрос об этом отеле.\n\n"
        "Я запрошу информацию из базы данных Level.Travel и отвечу на ваш вопрос.\n\n"
        "Например:\n"
        "• Какие номера доступны?\n"
        "• Есть ли в номерах кондиционер?\n"
        "• Какое питание включено?\n"
        "• Сколько стоит тур с завтраком?\n\n"
        "Или нажмите /cancel для отмены."
    )
    
    await callback.answer()
    
    logger.info(f"Пользователь начал задавать вопрос по отелю {hotel_id}")


def format_hotel_context(hotel: HotelCard, hotel_rooms: list) -> str:
    context = f"""
🏨 ОТЕЛЬ: {hotel.hotel_name}
⭐ Категория: {hotel.stars} звезд
"""

    if hotel.rating and hotel.rating > 0:
        context += f"📊 Рейтинг: {hotel.rating}/10\n"

    context += f"""📍 Местоположение: {hotel.city}, {hotel.region}
💰 Цена: от {hotel.format_price()}₽ за {hotel.nights} ночей
🍽️ Питание в базовой цене: {hotel.meal_description}
"""
    if hotel.start_date:
        context += f"📅 Дата заезда: {hotel.start_date}\n"
    if hotel.operator_name:
        context += f"🏢 Туроператор: {hotel.operator_name}\n"
    if hotel.instant_confirm:
        context += "✅ Доступно мгновенное подтверждение бронирования\n"

    if hotel.description and hotel.description.strip():
        context += f"\n📝 ОПИСАНИЕ ОТЕЛЯ:\n{hotel.description.strip()}\n"

    context += "\n🎯 ОСОБЕННОСТИ И РАСПОЛОЖЕНИЕ:\n"
    if hotel.features:
        if hotel.features.beach_distance is not None:
            context += f"- Расстояние до пляжа: {hotel.features.beach_distance}м\n"
        if hotel.features.line:
            context += f"- Линия пляжа: {hotel.features.line}-я\n"
        if hotel.features.beach_type:
            context += f"- Тип пляжа: {hotel.features.beach_type}\n"
        if hotel.features.beach_surface:
            context += f"- Покрытие пляжа: {hotel.features.beach_surface}\n"
        if hotel.features.airport_distance is not None:
            context += f"- Расстояние до аэропорта: {hotel.features.airport_distance}м\n"
        if hotel.features.wi_fi:
            context += f"- Wi-Fi: {hotel.features.wi_fi}\n"

    if hotel_rooms and isinstance(hotel_rooms, list):
        context += "\n\nДоступные типы номеров:\n"

        for i, room in enumerate(hotel_rooms[:5], 1):
            room_info = room.get('room', {})
            meal_types = room.get('meal_types', [])

            context += f"\n{i}. {room_info.get('name_ru', 'Стандартный номер')}"

            if room_info.get('area'):
                context += f" ({room_info['area']}м²)"
            if room_info.get('accommodation'):
                context += f" - {room_info['accommodation']}"

            facilities = room_info.get('facilities', [])
            if facilities:
                fac_names = [f['name'] for f in facilities[:5]]
                context += f"\n   Удобства: {', '.join(fac_names)}"

            if meal_types:
                context += "\n   Варианты питания:"
                for meal in meal_types[:3]:
                    meal_id = meal.get('id', '')
                    meal_desc = meal.get('description', '')
                    meal_price = meal.get('min_price', 0)
                    context += f"\n     • {meal_id} ({meal_desc}): от {meal_price:,}₽".replace(',', ' ')

    return context


def generate_fallback_answer(question: str, hotel: HotelCard, hotel_rooms: list) -> str:
    answer = f"📋 <b>Информация об отеле {hotel.hotel_name}</b>\n\n"
    answer += f"⭐ Категория: {hotel.stars} звезд\n"
    if hotel.rating and hotel.rating > 0:
        answer += f"📊 Рейтинг: {hotel.rating}/10\n"

    answer += f"📍 Местоположение: {hotel.city}, {hotel.region}\n"
    answer += f"💰 Цена от: {hotel.format_price()}₽ за {hotel.nights} ночей\n"
    answer += f"🍽️ Питание: {hotel.meal_description}\n\n"
    if hotel.features:
        features_list = []
        if hotel.features.beach_distance:
            features_list.append(f"🏖️ До пляжа: {hotel.features.beach_distance}м")
        if hotel.features.line:
            features_list.append(f"🌊 {hotel.features.line}-я линия")
        if hotel.features.beach_type:
            features_list.append(f"🏝️ Пляж: {hotel.features.beach_type}")
        if hotel.features.wi_fi:
            features_list.append(f"📶 Wi-Fi: {hotel.features.wi_fi}")

        if features_list:
            answer += "<b>Особенности:</b>\n" + "\n".join(features_list) + "\n\n"

    if hotel_rooms and isinstance(hotel_rooms, list) and len(hotel_rooms) > 0:
        answer += f"<b>🛏️ Доступно типов номеров: {len(hotel_rooms)}</b>\n\n"

        for i, room in enumerate(hotel_rooms[:2], 1):
            room_info = room.get('room', {})
            meal_types = room.get('meal_types', [])

            room_name = room_info.get('name_ru', 'Стандартный номер')
            answer += f"{i}. <b>{room_name}</b>\n"

            if room_info.get('area'):
                answer += f"   📐 Площадь: {room_info['area']}м²\n"
            if room_info.get('accommodation'):
                answer += f"   👥 {room_info['accommodation']}\n"
            facilities = room_info.get('facilities', [])
            if facilities and len(facilities) > 0:
                fac_names = [f.get('name', '') for f in facilities[:4] if f and f.get('name')]
                if fac_names:
                    answer += f"   ✨ {', '.join(fac_names)}\n"

            if meal_types and len(meal_types) > 0:
                meal = meal_types[0]
                meal_id = meal.get('id', '')
                meal_desc = meal.get('description', '')
                meal_price = meal.get('min_price', 0)
                if meal_id and meal_price:
                    answer += f"   🍽️ {meal_id} ({meal_desc}): от {meal_price:,}₽\n".replace(',', ' ')

            answer += "\n"

        if len(hotel_rooms) > 2:
            answer += f"<i>... и еще {len(hotel_rooms) - 2} типов номеров</i>\n\n"

    answer += "ℹ️ <i>Для получения более детальной консультации по вашему вопросу, пожалуйста, нажмите кнопку 'Забронировать' для связи с туроператором.</i>"

    return answer


@router.message(TourSearchFlow.asking_hotel_question)
async def handle_hotel_question(message: Message, state: FSMContext):
    user_question = message.text

    if user_question.strip().lower() == '/done':
        await state.set_state(TourSearchFlow.browsing_tours)

        data = await state.get_data()
        hotels = data.get('hotels', [])
        current_index = data.get('current_index', 0)

        if hotels and current_index < len(hotels):
            hotel = hotels[current_index]
            total = len(hotels)

            await show_tour_card(message, state, hotel, current_index, total)
            logger.info("Пользователь завершил режим вопросов об отеле")
        else:
            await message.answer("✅ Режим вопросов завершен.")

        return

    if user_question.strip().lower() in ['/cancel', 'отмена']:
        await state.set_state(TourSearchFlow.browsing_tours)

        data = await state.get_data()
        hotels = data.get('hotels', [])
        current_index = data.get('current_index', 0)

        if hotels and current_index < len(hotels):
            hotel = hotels[current_index]
            total = len(hotels)
            await show_tour_card(message, state, hotel, current_index, total)
            logger.info("Пользователь отменил режим вопросов об отеле")
        else:
            await message.answer("❌ Вопрос отменен. Продолжайте просмотр туров.")

        return

    loading_msg = await message.answer("🔍 Запрашиваю информацию об отеле...")

    try:
        data = await state.get_data()
        hotel_id = data.get('question_hotel_id')
        request_id = data.get('request_id')
        hotels = data.get('hotels', [])
        current_index = data.get('current_index', 0)
        search_params = data.get('search_params')
        hotel = hotels[current_index] if current_index < len(hotels) else None
        if not hotel or not request_id:
            await loading_msg.edit_text("😔 Не могу найти информацию об отеле. Попробуйте снова.")
            await state.set_state(TourSearchFlow.browsing_tours)
            return

        service = LeveltravelService()
        hotel_rooms = await service.get_hotel_rooms(request_id, hotel_id)

        logger.info(f"Получены детали отеля {hotel_id}: {len(hotel_rooms) if isinstance(hotel_rooms, list) else 0} типов номеров")
        context = format_hotel_context(hotel, hotel_rooms)

        amenities_info = ""
        if search_params and hasattr(search_params, 'amenities') and search_params.amenities:
            amenity_names = {
                'pool': 'бассейн',
                'heated_pool': 'подогреваемый бассейн',
                'spa': 'спа и массаж',
                'wifi': 'бесплатный Wi-Fi',
                'bar': 'бар',
                'kids_club': 'детский клуб',
                'kids_pool': 'детский бассейн',
                'kids_menu': 'детское меню',
                'nanny': 'услуги няни',
                'parking': 'парковка',
                'aquapark': 'аквапарк',
                'beach_line': 'первая линия пляжа'
            }

            amenities_list = [amenity_names.get(a, a) for a in search_params.amenities if a in amenity_names]

            if amenities_list:
                amenities_info = f"\n\n✅ ГАРАНТИРОВАННЫЕ УДОБСТВА (использованы при поиске):\n"
                amenities_info += "\n".join([f"• Отель ИМЕЕТ: {amenity}" for amenity in amenities_list])
                amenities_info += "\n\nВсе показанные отели были отфильтрованы по этим критериям, поэтому наличие этих удобств гарантировано."

        context_with_amenities = context + amenities_info

        answer = None
        try:
            await loading_msg.edit_text("🤖 Анализирую информацию и готовлю ответ...")

            from services.openai_service import OpenAIService
            openai_service = OpenAIService()

            prompt = f"""
Ты - эксперт по туризму и консультант по отелям.
Пользователь просматривает туры и задал вопрос о конкретном отеле.

📋 ИНФОРМАЦИЯ ОБ ОТЕЛЕ:
{context_with_amenities}

❓ ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{user_question}

📝 СТРОГИЕ ИНСТРУКЦИИ:
1. **КРИТИЧНО**: Отвечай ТОЛЬКО на основе предоставленной информации выше
2. **Гарантированные удобства**: Если в разделе "ГАРАНТИРОВАННЫЕ УДОБСТВА" указано, что отель ИМЕЕТ какое-то удобство (например, бассейн), то отвечай уверенно "Да, в отеле есть..."
3. **Удобства номеров**: Информация о facilities номеров (кондиционер, балкон, сейф) находится в разделе о типах номеров - используй её для ответов
4. **Отсутствие данных**: Если конкретная информация НЕ указана в контексте:
   - НЕ придумывай факты
   - НЕ делай предположений на основе "опыта"
   - НЕ давай "общие советы о туризме"
   - Честно скажи: "Эту информацию лучше уточнить при бронировании"
5. **Формат ответа**:
   - Максимум 800 символов (строгий лимит!)
   - Разделяй текст на абзацы (двойной перенос строки)
   - Используй списки (•) для перечислений
   - Будь дружелюбным и профессиональным

Отвечай на русском языке.
"""

            answer = await openai_service.get_completion(prompt, temperature=0.6)
            logger.info(f"Получен ответ от GPT для вопроса об отеле {hotel_id}")

        except Exception as gpt_error:
            logger.warning(f"GPT недоступен, используем fallback: {gpt_error}")
            answer = generate_fallback_answer(user_question, hotel, hotel_rooms)

        full_message = (
            f"❓ <b>Ваш вопрос:</b>\n{user_question}\n\n"
            f"💡 <b>Ответ:</b>\n{answer}\n\n"
            f"Если у вас есть еще вопросы - просто напишите их, или нажмите /done для возврата к просмотру туров."
        )

        TELEGRAM_MAX_LENGTH = 4096
        if len(full_message) > TELEGRAM_MAX_LENGTH:
            question_part = f"❓ <b>Ваш вопрос:</b>\n{user_question}\n\n💡 <b>Ответ:</b>\n"
            footer = "\n\n...(ответ обрезан)\n\nЕсли у вас есть еще вопросы - просто напишите их, или нажмите /done для возврата к просмотру туров."

            max_answer_length = TELEGRAM_MAX_LENGTH - len(question_part) - len(footer)
            truncated_answer = answer[:max_answer_length]

            full_message = question_part + truncated_answer + footer

            logger.warning(
                f"Ответ обрезан из-за лимита Telegram: {len(answer)} → {max_answer_length} символов"
            )

        await loading_msg.edit_text(
            full_message,
            parse_mode="HTML"
        )

        logger.info(f"Ответ на вопрос по отелю {hotel_id} отправлен (длина: {len(full_message)} символов)")

    except Exception as e:
        logger.error(f"Ошибка при обработке вопроса об отеле: {e}", exc_info=True)
        await loading_msg.edit_text(
            "😔 Произошла ошибка при получении информации об отеле.\n\n"
            "Попробуйте задать вопрос позже или вернитесь к просмотру туров командой /done"
        )


@router.message(Command("done"), TourSearchFlow.asking_hotel_question)
async def finish_hotel_questions(message: Message, state: FSMContext):
    await state.set_state(TourSearchFlow.browsing_tours)
    await message.answer(
        "✅ Режим вопросов завершен. Продолжайте просмотр туров.\n\n"
        "Используйте кнопки навигации для перехода между турами."
    )
    
    logger.info("Пользователь завершил режим вопросов об отеле")


def categorize_hotel_facilities(facilities: list) -> dict:
    """
    Группировка удобств отеля по категориям.
    
    Args:
        facilities: Список названий удобств
    
    Returns:
        Словарь {категория: [удобства]}
    """
    categories = {
        "🏊 Бассейны и водные развлечения": [],
        "🏋️ Спорт и фитнес": [],
        "🍽️ Питание и бары": [],
        "👶 Для детей": [],
        "💆 СПА и релакс": [],
        "🅿️ Транспорт и парковка": [],
        "📶 Связь и технологии": [],
        "🛏️ В номере": []
    }
    
    keywords = {
        "🏊 Бассейны и водные развлечения": ["бассейн", "аквапарк", "водная горка", "джакузи"],
        "🏋️ Спорт и фитнес": ["фитнес", "тренажерный зал", "спортзал", "теннис", "волейбол", "йога"],
        "🍽️ Питание и бары": ["ресторан", "бар", "кафе", "буфет", "кухня", "мини-бар"],
        "👶 Для детей": ["детск", "игровая", "няня", "анимация"],
        "💆 СПА и релакс": ["спа", "сауна", "баня", "хамам", "массаж", "джакузи"],
        "🅿️ Транспорт и парковка": ["парковка", "трансфер", "прокат"],
        "📶 Связь и технологии": ["wi-fi", "интернет", "телевизор", "кондиционер"],
        "🛏️ В номере": ["сейф", "фен", "халат", "тапочки", "полотенце", "балкон"]
    }
    
    for facility in facilities:
        facility_lower = facility.lower()
        categorized = False
        
        for category, keys in keywords.items():
            if any(key in facility_lower for key in keys):
                categories[category].append(facility)
                categorized = True
                break
        
        if not categorized:
            categories["🛏️ В номере"].append(facility)
    
    # Удаляем пустые категории
    return {k: v for k, v in categories.items() if v}


@router.callback_query(F.data.startswith("hotel_details_"), TourSearchFlow.browsing_tours)
async def show_hotel_details(callback: CallbackQuery, state: FSMContext):
    """Показать подробную информацию об отеле"""
    hotel_id = int(callback.data.replace("hotel_details_", ""))
    
    await callback.answer("⏳ Загружаю информацию об отеле...")
    
    try:
        # Получаем данные из state
        data = await state.get_data()
        request_id = data.get('request_id')
        hotels = data.get('hotels', [])
        current_index = data.get('current_index', 0)
        
        # Находим текущий отель
        hotel = hotels[current_index] if current_index < len(hotels) else None
        
        if not hotel:
            await callback.message.answer("😔 Отель не найден")
            return
        
        # Запрашиваем детали отеля через API hotel_rooms
        service = LeveltravelService()
        hotel_rooms_data = await service.get_hotel_rooms(request_id, hotel_id)
        
        if not hotel_rooms_data:
            await callback.message.answer("😔 Информация об отеле временно недоступна")
            return
        
        # Собираем все уникальные удобства из всех номеров
        all_facilities = {}
        for room_data in hotel_rooms_data:
            room = room_data.get('room') or {}  # Защита от None
            facilities = room.get('facilities') or []  # Защита от None
            for facility in facilities:
                if not facility:  # Проверка на None/пустой объект
                    continue
                facility_id = facility.get('id')
                facility_name = facility.get('name')
                if facility_id and facility_name and facility_id not in all_facilities:
                    all_facilities[facility_id] = facility_name
        
        # Если удобств нет - показываем только информацию о расположении
        if not all_facilities:
            text = f"📋 <b>Информация об отеле</b>\n\n"
            text += f"<b>{hotel.hotel_name}</b> {hotel.format_stars()}\n"
            text += f"📍 {hotel.region}, {hotel.city}\n\n"
            
            if hotel.features:
                text += "<b>📍 Расположение:</b>\n"
                if hotel.features.beach_distance:
                    text += f"  • До пляжа: {hotel.features.beach_distance}м\n"
                if hotel.features.line:
                    text += f"  • Линия: {hotel.features.line}-я\n"
                if hotel.features.airport_distance:
                    text += f"  • До аэропорта: {hotel.features.airport_distance/1000:.1f}км\n"
            else:
                text += "ℹ️ Детальная информация об удобствах недоступна.\n"
                text += "Используйте кнопку 'Забронировать' для получения полной информации."
            
            await callback.message.answer(text, parse_mode="HTML")
            
            # === Кнопки навигации для случая без удобств ===
            booking_url = generate_booking_url(hotel.tour_id, hotel.hotel_id, request_id)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="◀️ Вернуться к просмотру",
                        callback_data="return_to_browsing"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔗 Забронировать тур",
                        url=booking_url
                    )
                ]
            ])
            
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=keyboard
            )
            
            logger.info(f"Показана базовая информация об отеле {hotel_id} (удобства недоступны)")
            return
        
        # Группируем удобства по категориям
        categorized = categorize_hotel_facilities(list(all_facilities.values()))
        
        # Формируем сообщение
        text = f"📋 <b>Подробная информация об отеле</b>\n\n"
        text += f"<b>{hotel.hotel_name}</b> {hotel.format_stars()}\n"
        text += f"📍 {hotel.region}, {hotel.city}\n\n"
        
        # Добавляем категории удобств
        for category, items in categorized.items():
            if items:
                text += f"<b>{category}:</b>\n"
                for item in items[:8]:  # Ограничиваем до 8 на категорию
                    text += f"  ✓ {item}\n"
                text += "\n"
        
        # Добавляем информацию о расположении из hotel.features
        if hotel.features:
            text += "<b>📍 Расположение:</b>\n"
            if hotel.features.beach_distance:
                text += f"  • До пляжа: {hotel.features.beach_distance}м\n"
            if hotel.features.line:
                text += f"  • Линия: {hotel.features.line}-я\n"
            if hotel.features.airport_distance:
                text += f"  • До аэропорта: {hotel.features.airport_distance/1000:.1f}км\n"
        
        await callback.message.answer(text, parse_mode="HTML")

        # === НОВОЕ: Добавляем кнопки навигации ===
        booking_url = generate_booking_url(hotel.tour_id, hotel.hotel_id, request_id)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Вернуться к просмотру",
                    callback_data="return_to_browsing"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Забронировать тур",
                    url=booking_url
                )
            ]
        ])

        await callback.message.answer(
            "Выберите действие:",
            reply_markup=keyboard
        )

        logger.info(f"Показана детальная информация об отеле {hotel_id}")
        
    except Exception as e:
        logger.error(f"Ошибка загрузки деталей отеля: {e}", exc_info=True)
        await callback.message.answer("😔 Не удалось загрузить информацию об отеле")


@router.callback_query(F.data.startswith("hotel_rooms_"), TourSearchFlow.browsing_tours)
async def show_hotel_rooms(callback: CallbackQuery, state: FSMContext):
    """Показать подробную информацию о номерах"""
    hotel_id = int(callback.data.replace("hotel_rooms_", ""))
    
    await callback.answer("⏳ Загружаю информацию о номерах...")
    
    try:
        # Получаем данные из state
        data = await state.get_data()
        request_id = data.get('request_id')
        hotels = data.get('hotels', [])
        current_index = data.get('current_index', 0)
        
        hotel = hotels[current_index] if current_index < len(hotels) else None
        
        if not hotel:
            await callback.message.answer("😔 Отель не найден")
            return
        
        # Запрашиваем детали номеров
        service = LeveltravelService()
        hotel_rooms_data = await service.get_hotel_rooms(request_id, hotel_id)
        
        if not hotel_rooms_data:
            await callback.message.answer("😔 Информация о номерах недоступна")
            return
        
        # Ограничиваем до 3 типов номеров (чтобы не перегружать)
        rooms_to_show = hotel_rooms_data[:3]
        
        rooms_sent = 0  # Счетчик успешно отправленных номеров
        
        for i, room_data in enumerate(rooms_to_show, 1):
            room = room_data.get('room') or {}  # Защита от None
            if not room:  # Пропускаем пустые номера
                continue
                
            meal_types = room_data.get('meal_types') or []  # Защита от None
            
            # Отправляем фото номера (максимум 5)
            images = (room.get('images') or [])[:5]  # Защита от None
            if images:
                from aiogram.types import InputMediaPhoto
                media = []
                for img in images:
                    if not img:  # Проверка на None
                        continue
                    photo_url = img.get('x900') or img.get('x900x380')
                    if photo_url:
                        media.append(InputMediaPhoto(media=photo_url))
                
                if media:
                    # Первому фото добавляем caption с названием номера
                    room_name = room.get('name_ru') or 'Номер'
                    media[0].caption = f"🛏️ {room_name}"
                    try:
                        await callback.message.answer_media_group(media=media)
                    except Exception as e:
                        logger.error(f"Ошибка отправки фото номера: {e}")
                        # Продолжаем без фото
            
            # Формируем описание номера
            room_name = room.get('name_ru') or 'Стандартный номер'
            text = f"<b>🛏️ {room_name}</b>\n\n"
            
            area = room.get('area')
            if area:
                text += f"📐 Площадь: {area} м²\n"
            
            accommodation = room.get('accommodation')
            if accommodation:
                text += f"👥 Вместимость: {accommodation}\n"
            
            # Описание номера
            description = room.get('description')
            if description:
                desc = description[:300]  # Ограничиваем длину
                text += f"\n📝 {desc}{'...' if len(description) > 300 else ''}\n"
            
            # Удобства в номере
            facilities = room.get('facilities') or []  # Защита от None
            if facilities:
                text += "\n<b>✨ Удобства:</b>\n"
                # Показываем первые 8 удобств
                facility_count = 0
                for facility in facilities[:10]:  # Берем чуть больше на случай невалидных
                    if not facility:  # Проверка на None
                        continue
                    facility_name = facility.get('name')
                    if facility_name:
                        text += f"  • {facility_name}\n"
                        facility_count += 1
                        if facility_count >= 8:
                            break
                
                if len(facilities) > 8:
                    text += f"  • ... и ещё {len(facilities) - 8}\n"
            
            # Варианты питания и цены
            if meal_types:
                text += "\n<b>🍽️ Варианты питания:</b>\n"
                meal_count = 0
                for meal in meal_types[:5]:  # Берем чуть больше
                    if not meal:  # Проверка на None
                        continue
                    meal_id = meal.get('id', '')
                    meal_desc = meal.get('description', '')
                    meal_price = meal.get('min_price', 0)
                    if meal_id or meal_desc:
                        text += f"  • {meal_id} ({meal_desc}): от {meal_price:,}₽\n".replace(',', ' ')
                        meal_count += 1
                        if meal_count >= 3:
                            break
            
            try:
                await callback.message.answer(text, parse_mode="HTML")
                rooms_sent += 1
            except Exception as e:
                logger.error(f"Ошибка отправки описания номера: {e}")
                # Продолжаем со следующим номером
        
        # Если номеров больше 3 и мы успешно отправили хотя бы 1
        if rooms_sent > 0 and len(hotel_rooms_data) > 3:
            await callback.message.answer(
                f"ℹ️ Показано {rooms_sent} из {len(hotel_rooms_data)} доступных типов номеров.\n"
                f"Для полной информации нажмите 'Забронировать'."
            )
        elif rooms_sent == 0:
            await callback.message.answer(
                "😔 Не удалось загрузить информацию о номерах.\n"
                "Используйте кнопку 'Забронировать' для получения деталей."
            )
        
        logger.info(f"Показана информация о {rooms_sent} номерах отеля {hotel_id}")

        # === НОВОЕ: Добавляем кнопки навигации ===
        booking_url = generate_booking_url(hotel.tour_id, hotel.hotel_id, request_id)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Вернуться к просмотру",
                    callback_data="return_to_browsing"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Забронировать тур",
                    url=booking_url
                )
            ]
        ])

        await callback.message.answer(
            "Выберите действие:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки номеров: {e}", exc_info=True)
        await callback.message.answer("😔 Не удалось загрузить информацию о номерах")


@router.callback_query(F.data == "return_to_browsing", TourSearchFlow.browsing_tours)
async def return_to_browsing(callback: CallbackQuery, state: FSMContext):
    """Вернуться к просмотру текущего тура"""
    try:
        data = await state.get_data()
        current_index = data.get('current_index', 0)
        hotels = data.get('hotels', [])
        
        if current_index < len(hotels):
            hotel = hotels[current_index]
            
            # Показываем текущую карточку тура заново
            await show_tour_card(callback.message, state, hotel, current_index, len(hotels))
            
            await callback.answer("✅ Вернулись к просмотру туров")
        else:
            await callback.answer("Ошибка: тур не найден", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка возврата к просмотру: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "change_criteria")
async def change_search_criteria(callback: CallbackQuery, state: FSMContext):
    """Изменить критерии поиска"""
    data = await state.get_data()

    # Проверяем есть ли сохраненные параметры
    if data.get('search_params') or data.get('ai_parsed_params'):
        # Показываем меню редактирования
        from handlers.edit_params_handler import show_edit_params_menu
        await show_edit_params_menu(callback, state)
    else:
        # Параметров нет - предлагаем начать заново
        await state.clear()
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Ввести параметры", callback_data="enter_params")],
            [InlineKeyboardButton(text="Свободный ввод", callback_data="improved_questions")],
            [InlineKeyboardButton(text="Главное меню", callback_data="start")]
        ])
        await callback.message.answer("🔄 Начнем новый поиск?", reply_markup=keyboard)

    await callback.answer()


@router.callback_query(F.data.startswith("tour_save_"), TourSearchFlow.browsing_tours)
async def save_to_favorites(callback: CallbackQuery, state: FSMContext):
    """Сохранить тур в избранное (заметки)"""
    try:
        hotel_id = int(callback.data.replace("tour_save_", ""))

        # Получаем данные из state
        data = await state.get_data()
        hotels = data.get('hotels', [])
        current_index = data.get('current_index', 0)
        request_id = data.get('request_id')

        # Находим текущий отель
        hotel = hotels[current_index] if current_index < len(hotels) else None

        if not hotel:
            await callback.answer("Ошибка: тур не найден", show_alert=True)
            return

        # Сохраняем в базу данных
        from database.requests import add_to_favorites
        import json

        # Подготавливаем данные тура в JSON
        tour_data = {
            'tour_id': hotel.tour_id,
            'request_id': request_id,
            'stars': hotel.stars,
            'rating': hotel.rating,
            'region': hotel.region,
            'meal_description': hotel.meal_description,
            'operator_name': hotel.operator_name,
            'availability': hotel.availability,
            'instant_confirm': hotel.instant_confirm
        }

        success = await add_to_favorites(
            user_id=callback.from_user.id,
            hotel_id=hotel.hotel_id,
            hotel_name=hotel.hotel_name,
            country=hotel.region,
            city=hotel.city,
            price=hotel.min_price,
            nights=hotel.nights,
            start_date=hotel.start_date,
            tour_id=hotel.tour_id,
            request_id=request_id,
            tour_data=json.dumps(tour_data, ensure_ascii=False)
        )

        if success:
            await callback.answer("✅ Тур сохранён в заметки!", show_alert=True)
            logger.info(f"Пользователь {callback.from_user.id} сохранил тур {hotel.hotel_name} в избранное")
        else:
            await callback.answer("ℹ️ Этот тур уже в ваших заметках", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка сохранения тура в избранное: {e}", exc_info=True)
        await callback.answer("😔 Ошибка при сохранении тура", show_alert=True)


@router.callback_query(F.data == "return_to_start")
async def return_to_start(callback: CallbackQuery, state: FSMContext):
    """Вернуться к началу (главное меню)"""
    await state.clear()

    from keyboards.main_keyboard import main_menu
    from config import sheet

    text = sheet.cell(2, 1).value if sheet.cell(2, 1).value else (
        "👋 Главное меню\n\n"
        "Выберите действие:"
    )

    await callback.message.answer(text, reply_markup=main_menu)
    await callback.answer("✅ Вернулись в главное меню")

    logger.info(f"Пользователь {callback.from_user.id} вернулся в главное меню из просмотра туров")
