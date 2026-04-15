"""
Обработчик ручного ввода параметров для подбора туров.
Реализует полный flow от выбора города вылета до запуска поиска.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import logging

from states.tour_states import TourSearchFlow
from models.tour_models import SearchParams, format_search_summary, remove_duplicate_hotels
from services.leveltravel_service import LeveltravelService, LeveltravelAPIError
from handlers.amenities_handler import ask_for_amenities
from utils.city_data import get_cities_for_country, normalize_city_name
from utils.message_cleanup import send_and_delete_previous, delete_last_bot_message, clear_all_bot_messages
from keyboards.find_tour_keyboard import (
    departure_city_keyboard,
    nights_keyboard,
    adults_keyboard,
    kids_keyboard,
    budget_keyboard,
    stars_keyboard,
    confirmation_keyboard,
    create_country_keyboard,
    popular_countries_keyboard,
    create_destination_city_keyboard
)

logger = logging.getLogger(__name__)
router = Router()


# ============================================
# Словарь городов России (русский → английский)
# ============================================

RUSSIAN_CITIES = {
    "москва": "Moscow",
    "санкт-петербург": "Saint Petersburg",
    "спб": "Saint Petersburg",
    "питер": "Saint Petersburg",
    "казань": "Kazan",
    "новосибирск": "Novosibirsk",
    "екатеринбург": "Ekaterinburg",
    "нижний новгород": "Nizhny Novgorod",
    "самара": "Samara",
    "омск": "Omsk",
    "челябинск": "Chelyabinsk",
    "ростов-на-дону": "Rostov-on-Don",
    "уфа": "Ufa",
    "красноярск": "Krasnoyarsk",
    "пермь": "Perm",
    "воронеж": "Voronezh",
    "волгоград": "Volgograd",
    "краснодар": "Krasnodar",
    "саратов": "Saratov",
    "тюмень": "Tyumen",
    "ижевск": "Izhevsk",
    "барнаул": "Barnaul",
    "иркутск": "Irkutsk",
    "ульяновск": "Ulyanovsk",
    "хабаровск": "Khabarovsk",
    "ярославль": "Yaroslavl",
    "владивосток": "Vladivostok",
    "махачкала": "Makhachkala",
    "томск": "Tomsk",
    "оренбург": "Orenburg",
    "кемерово": "Kemerovo",
    "новокузнецк": "Novokuznetsk",
    "рязань": "Ryazan",
    "астрахань": "Astrakhan",
    "пенза": "Penza",
    "киров": "Kirov",
    "липецк": "Lipetsk",
    "чебоксары": "Cheboksary",
    "калининград": "Kaliningrad",
    "тула": "Tula",
    "сочи": "Sochi"
}


# ============================================
# Шаг 1: Выбор города вылета
# ============================================

@router.callback_query(F.data == "enter_params")
async def start_params_flow(callback: CallbackQuery, state: FSMContext):
    """Начало сценария ручного ввода параметров"""
    # Очищаем state и начинаем новый flow
    await state.clear()
    await state.set_state(TourSearchFlow.waiting_departure_city)

    # Отправляем первый вопрос и сохраняем его ID
    sent_msg = await callback.message.answer(
        "📍 **Из какого города вылетаете?**\n\n"
        "Выберите из списка ниже или нажмите 'Другой город' для ручного ввода:",
        reply_markup=departure_city_keyboard,
        parse_mode="Markdown"
    )

    # Сохраняем ID первого вопроса
    await state.update_data(last_bot_message_id=sent_msg.message_id)
    await callback.answer()


# Callback-обработчики для inline-кнопок
@router.callback_query(F.data == "departure_skip", TourSearchFlow.waiting_departure_city)
async def departure_skip_city(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Пропустить' - выбор Москвы по умолчанию"""

    # Молча выбираем Москву
    await state.update_data(from_city="Moscow")
    logger.info("Город вылета пропущен, выбрана Москва по умолчанию")

    # Переходим к выбору страны
    await ask_for_country(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "departure_other", TourSearchFlow.waiting_departure_city)
async def departure_other_city(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора 'Другой город'"""

    await state.set_state(TourSearchFlow.waiting_custom_city)

    await callback.message.answer(
        "📝 **Введите название города на русском языке:**\n\n"
        "Например: Казань, Новосибирск, Екатеринбург\n\n"
        "ℹ️ Доступны крупные города России\n\n"
        "Напишите /cancel для отмены",
        parse_mode="Markdown"
    )

    await callback.answer()


@router.callback_query(F.data.startswith("departure_"), TourSearchFlow.waiting_departure_city)
async def select_departure_city(callback: CallbackQuery, state: FSMContext):
    """Выбор города вылета"""
    city_en = callback.data.replace("departure_", "")

    # Сохраняем город
    await state.update_data(from_city=city_en)
    logger.info(f"Выбран город вылета: {city_en}")

    # Переходим к выбору страны
    await ask_for_country(callback.message, state)
    await callback.answer()


@router.message(Command("cancel"), TourSearchFlow.waiting_custom_city)
async def cancel_custom_city(message: Message, state: FSMContext):
    """Отмена ввода города"""
    await state.set_state(TourSearchFlow.waiting_departure_city)
    await message.answer(
        "❌ Ввод отменен.\n\n"
        "📍 **Выберите город из списка:**",
        reply_markup=departure_city_keyboard,
        parse_mode="Markdown"
    )


@router.message(TourSearchFlow.waiting_custom_city)
async def handle_custom_city(message: Message, state: FSMContext):
    """Обработка ввода города на русском"""
    
    city_russian = message.text.strip().lower()
    
    # Проверяем в словаре
    if city_russian in RUSSIAN_CITIES:
        city_en = RUSSIAN_CITIES[city_russian]
        
        await state.update_data(from_city=city_en)
        logger.info(f"Выбран город вылета: {city_russian} -> {city_en}")
        
        await message.answer(
            f"Город вылета: **{message.text.capitalize()}**",
            parse_mode="Markdown"
        )
        
        # Переходим к выбору страны
        await ask_for_country(message, state)
    else:
        # Город не найден - предлагаем варианты
        await message.answer(
            f"❌ Город '{message.text}' не найден.\n\n"
            "Попробуйте один из доступных городов:\n\n"
            "• Москва\n• Санкт-Петербург\n• Казань\n• Новосибирск\n"
            "• Екатеринбург\n• Нижний Новгород\n• Самара\n• Омск\n"
            "• Краснодар\n• Сочи\n• Ростов-на-Дону\n\n"
            "Или напишите /cancel для отмены",
            parse_mode="Markdown"
        )


# ============================================
# Шаг 2: Выбор страны назначения
# ============================================

async def ask_for_country(message: Message, state: FSMContext):
    """Запросить выбор страны - показываем inline-кнопки с популярными странами."""
    await state.set_state(TourSearchFlow.waiting_country)

    # Удаляем предыдущий вопрос, отправляем новый
    await send_and_delete_previous(
        message=message,
        text="🌍 **Куда хотите поехать?**\n\n"
             "Выберите популярную страну или нажмите 'Другая страна' для полного списка:",
        state=state,
        reply_markup=popular_countries_keyboard,
        parse_mode="Markdown"
    )


# Callback-обработчики для inline-кнопок стран
@router.callback_query(F.data == "country_other", TourSearchFlow.waiting_country)
async def select_other_country(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора 'Другая страна' - запрос ручного ввода."""
    await state.set_state(TourSearchFlow.waiting_custom_country)

    await callback.message.answer(
        "📝 **Введите название страны на русском языке:**\n\n"
        "Например: Испания, Италия, Греция, Кипр, Мальдивы\n\n"
        "Напишите /cancel для возврата",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(Command("cancel"), TourSearchFlow.waiting_custom_country)
async def cancel_custom_country(message: Message, state: FSMContext):
    """Отмена ввода страны"""
    await state.set_state(TourSearchFlow.waiting_country)
    await message.answer(
        "❌ Ввод отменен.\n\n"
        "🌍 **Выберите страну из списка:**",
        reply_markup=popular_countries_keyboard,
        parse_mode="Markdown"
    )


@router.message(TourSearchFlow.waiting_custom_country)
async def handle_custom_country(message: Message, state: FSMContext):
    """Обработка ручного ввода названия страны"""
    from utils.country_data import COUNTRY_TO_ISO

    country_russian = message.text.strip().lower()

    # Проверяем в словаре
    if country_russian in COUNTRY_TO_ISO:
        country_code = COUNTRY_TO_ISO[country_russian]

        await state.update_data(to_country=country_code)
        logger.info(f"Выбрана страна: {country_russian} -> {country_code}")

        await message.answer(
            f"Страна: {message.text.capitalize()}"
        )

        # Переходим к выбору города назначения
        await ask_for_destination_city(message, state, country_code)
    else:
        # Страна не найдена - показываем ошибку с примерами
        await message.answer(
            f"❌ Страна **'{message.text}'** не найдена в базе.\n\n"
            "**Популярные направления:**\n"
            "• Турция, Египет, ОАЭ\n"
            "• Таиланд, Вьетнам, Грузия\n"
            "• Испания, Италия, Греция\n"
            "• Кипр, Мальдивы, Мексика\n"
            "• Франция, Португалия, Черногория\n\n"
            "Введите название ещё раз или напишите /cancel для возврата",
            parse_mode="Markdown"
        )


@router.callback_query(F.data.startswith("country_page_"), TourSearchFlow.waiting_country)
async def handle_country_page(callback: CallbackQuery, state: FSMContext):
    """Обработка навигации по страницам стран."""
    page = int(callback.data.split('_')[-1])
    await callback.message.edit_reply_markup(
        reply_markup=create_country_keyboard(page=page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("country_"), TourSearchFlow.waiting_country)
async def select_country(callback: CallbackQuery, state: FSMContext):
    """Выбор страны назначения."""
    country_code = callback.data.replace("country_", "")

    # Пропускаем служебные callback'и
    if country_code in ["other"] or country_code.startswith("page_"):
        return

    await state.update_data(to_country=country_code)
    logger.info(f"Выбрана страна: {country_code}")

    # Переходим к выбору города назначения
    await ask_for_destination_city(callback.message, state, country_code)
    await callback.answer()


# ============================================
# Шаг 2.5: Выбор города назначения
# ============================================

async def ask_for_destination_city(message: Message, state: FSMContext, country_code: str):
    """Запросить выбор города назначения в выбранной стране."""
    await state.set_state(TourSearchFlow.waiting_destination_city)

    # Проверяем, есть ли города для этой страны
    country_data = get_cities_for_country(country_code)

    if country_data:
        # Удаляем предыдущий вопрос, отправляем новый
        await send_and_delete_previous(
            message=message,
            text="🏙️ **Какой город или курорт вас интересует?**\n\n"
                 "Выберите конкретный город или 'Вся страна' для поиска по всей стране:",
            state=state,
            reply_markup=create_destination_city_keyboard(country_code),
            parse_mode="Markdown"
        )
    else:
        # Если городов нет в словаре, сразу переходим к датам
        logger.info(f"Нет предзаданных городов для {country_code}, пропускаем выбор города")
        await ask_for_dates(message, state)


@router.callback_query(F.data == "destination_all", TourSearchFlow.waiting_destination_city)
async def select_all_country(callback: CallbackQuery, state: FSMContext):
    """Выбор 'Вся страна' - не указываем конкретный город."""
    # to_city остается None - поиск по всей стране
    await state.update_data(to_city=None)
    logger.info("Выбран поиск по всей стране (to_city=None)")

    await callback.message.answer("🌍 Выбрано: **Вся страна**", parse_mode="Markdown")

    # Переходим к выбору дат
    await ask_for_dates(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "destination_custom", TourSearchFlow.waiting_destination_city)
async def select_custom_destination(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора 'Другой город' - запрос ручного ввода."""
    await state.set_state(TourSearchFlow.waiting_custom_destination)

    await callback.message.answer(
        "📝 **Введите название города на английском языке:**\n\n"
        "Например: Antalya, Kemer, Side, Hurghada\n\n"
        "Напишите /cancel для возврата",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(Command("cancel"), TourSearchFlow.waiting_custom_destination)
async def cancel_custom_destination(message: Message, state: FSMContext):
    """Отмена ручного ввода города назначения."""
    user_data = await state.get_data()
    country_code = user_data.get("to_country")

    await state.set_state(TourSearchFlow.waiting_destination_city)
    await message.answer(
        "❌ Ввод отменен.\n\n"
        "🏙️ **Выберите город из списка:**",
        reply_markup=create_destination_city_keyboard(country_code) if country_code else None,
        parse_mode="Markdown"
    )


@router.message(TourSearchFlow.waiting_custom_destination)
async def handle_custom_destination(message: Message, state: FSMContext):
    """Обработка ручного ввода города назначения."""
    city_input = message.text.strip()

    # Сохраняем как есть (предполагаем, что пользователь ввел на английском)
    await state.update_data(to_city=city_input)
    logger.info(f"Выбран город назначения (ручной ввод): {city_input}")

    await message.answer(
        f"Город назначения: **{city_input}**",
        parse_mode="Markdown"
    )

    # Переходим к выбору дат
    await ask_for_dates(message, state)


@router.callback_query(F.data.startswith("destination_"), TourSearchFlow.waiting_destination_city)
async def select_destination_city(callback: CallbackQuery, state: FSMContext):
    """Выбор конкретного города назначения."""
    city_english = callback.data.replace("destination_", "")

    # Пропускаем служебные callback'и
    if city_english in ["all", "custom"]:
        return

    await state.update_data(to_city=city_english)
    logger.info(f"Выбран город назначения: {city_english}")

    # Находим русское название для отображения
    user_data = await state.get_data()
    country_code = user_data.get("to_country")
    country_data = get_cities_for_country(country_code)

    city_russian = city_english
    if country_data:
        for rus_name, eng_name in country_data["cities"].items():
            if eng_name == city_english:
                city_russian = rus_name
                break

    await callback.message.answer(
        f"🏙️ Город: **{city_russian}**",
        parse_mode="Markdown"
    )

    # Переходим к выбору дат
    await ask_for_dates(callback.message, state)
    await callback.answer()


# ============================================
# Шаг 3: Выбор дат
# ============================================

async def ask_for_dates(message: Message, state: FSMContext):
    """Запросить даты поездки"""
    await state.set_state(TourSearchFlow.waiting_dates)

    # Удаляем предыдущий вопрос, отправляем новый
    await send_and_delete_previous(
        message=message,
        text="📅 **Когда планируете поездку?**\n\n"
             "Введите дату вылета в формате **ДД.ММ.ГГГГ**\n"
             "Например: 17.10.2025",
        state=state,
        parse_mode="Markdown"
    )
@router.message(TourSearchFlow.waiting_dates)
async def handle_dates(message: Message, state: FSMContext):
    """Обработка ввода дат"""
    date_text = message.text.strip()
    
    # Валидация даты с помощью helpers
    from utils.helpers import validate_date
    is_valid, error_message = validate_date(date_text)
    
    if not is_valid:
        await message.answer(
            f"❌ {error_message}\n\n"
            "Введите дату в формате **ДД.ММ.ГГГГ**\n"
            "Например: 15.10.2025",
            parse_mode="Markdown"
        )
        return
    
    # Сохраняем дату
    await state.update_data(start_date=date_text)
    logger.info(f"Выбрана дата вылета: {date_text}")
    
    # Переходим к выбору количества ночей
    await ask_for_nights(message, state)


# ============================================
# Шаг 4: Выбор количества ночей
# ============================================

async def ask_for_nights(message: Message, state: FSMContext):
    """Запросить количество ночей"""
    await state.set_state(TourSearchFlow.waiting_nights)

    # Удаляем предыдущий вопрос, отправляем новый
    await send_and_delete_previous(
        message=message,
        text="🌙 **Сколько ночей планируете пробыть?**",
        state=state,
        reply_markup=nights_keyboard,
        parse_mode="Markdown"
    )
@router.callback_query(F.data.startswith("nights_"))
async def select_nights(callback: CallbackQuery, state: FSMContext):
    """Выбор количества ночей"""
    nights = callback.data.replace("nights_", "")

    await state.update_data(nights=nights)
    logger.info(f"Выбрано ночей: {nights}")

    # Переходим к выбору количества взрослых
    await ask_for_adults(callback.message, state)
    await callback.answer()


# ============================================
# Шаг 5: Выбор количества взрослых
# ============================================

async def ask_for_adults(message: Message, state: FSMContext):
    """Запросить количество взрослых"""
    await state.set_state(TourSearchFlow.waiting_adults)

    # Удаляем предыдущий вопрос, отправляем новый
    await send_and_delete_previous(
        message=message,
        text="👥 **Сколько взрослых?**",
        state=state,
        reply_markup=adults_keyboard,
        parse_mode="Markdown"
    )
@router.callback_query(F.data.startswith("adults_"))
async def select_adults(callback: CallbackQuery, state: FSMContext):
    """Выбор количества взрослых"""
    adults = int(callback.data.replace("adults_", ""))

    await state.update_data(adults=adults)
    logger.info(f"Выбрано взрослых: {adults}")

    # Переходим к выбору количества детей
    await ask_for_kids(callback.message, state)
    await callback.answer()


# ============================================
# Шаг 6: Выбор количества детей
# ============================================

async def ask_for_kids(message: Message, state: FSMContext):
    """Запросить количество детей"""
    await state.set_state(TourSearchFlow.waiting_kids)

    # Удаляем предыдущий вопрос, отправляем новый
    await send_and_delete_previous(
        message=message,
        text="👶 **Сколько детей?**",
        state=state,
        reply_markup=kids_keyboard,
        parse_mode="Markdown"
    )
@router.callback_query(F.data.startswith("kids_"))
async def select_kids(callback: CallbackQuery, state: FSMContext):
    """Выбор количества детей"""
    kids = int(callback.data.replace("kids_", ""))

    await state.update_data(kids=kids)
    logger.info(f"Выбрано детей: {kids}")

    if kids > 0:
        # Если есть дети - запрашиваем возраста
        await ask_for_kids_ages(callback.message, state, kids)
    else:
        # Если детей нет - переходим к выбору бюджета
        await state.update_data(kids_ages=[])
        await ask_for_budget(callback.message, state)

    await callback.answer()


# ============================================
# Шаг 7: Ввод возрастов детей
# ============================================

async def ask_for_kids_ages(message: Message, state: FSMContext, kids_count: int):
    """Запросить возраста детей"""
    await state.set_state(TourSearchFlow.waiting_kids_ages)

    # Удаляем предыдущий вопрос, отправляем новый
    await send_and_delete_previous(
        message=message,
        text=f"👶 **Укажите возраст каждого ребенка (через запятую)**\n\n"
             f"Например: 5, 8, 12\n"
             f"Всего детей: {kids_count}",
        state=state,
        parse_mode="Markdown"
    )
@router.message(TourSearchFlow.waiting_kids_ages)
async def handle_kids_ages(message: Message, state: FSMContext):
    """Обработка ввода возрастов детей"""
    ages_text = message.text.strip()
    
    try:
        # Парсим возраста
        ages = [int(age.strip()) for age in ages_text.split(',')]
        
        # Валидация
        data = await state.get_data()
        kids_count = data.get('kids', 0)
        
        if len(ages) != kids_count:
            await message.answer(
                f"❌ Вы указали {len(ages)} возраст(а), а должно быть {kids_count}.\n"
                f"Попробуйте еще раз:"
            )
            return
        
        if any(age < 0 or age > 17 for age in ages):
            await message.answer(
                "❌ Возраст детей должен быть от 0 до 17 лет. Попробуйте еще раз:"
            )
            return
        
        # Сохраняем возраста
        await state.update_data(kids_ages=ages)
        logger.info(f"Указаны возраста детей: {ages}")
        
        # Переходим к выбору бюджета
        await ask_for_budget(message, state)
        
    except ValueError:
        await message.answer(
            "❌ Некорректный формат. Введите возраста через запятую.\n"
            "Например: 5, 8, 12"
        )


# ============================================
# Шаг 8: Выбор бюджета (опционально)
# ============================================

async def ask_for_budget(message: Message, state: FSMContext):
    """Запросить бюджет"""
    await state.set_state(TourSearchFlow.waiting_budget)

    # Удаляем предыдущий вопрос, отправляем новый
    await send_and_delete_previous(
        message=message,
        text="💰 **Какой бюджет на тур?**\n\n"
             "Можно пропустить этот шаг.",
        state=state,
        reply_markup=budget_keyboard,
        parse_mode="Markdown"
    )
@router.callback_query(F.data.startswith("budget_"))
async def select_budget(callback: CallbackQuery, state: FSMContext):
    """Выбор бюджета"""
    budget_data = callback.data.replace("budget_", "")

    if budget_data == "skip":
        await state.update_data(min_price=None, max_price=None)
        logger.info("Бюджет пропущен")
    else:
        min_price, max_price = map(int, budget_data.split("_"))
        await state.update_data(min_price=min_price, max_price=max_price)
        logger.info(f"Выбран бюджет: {min_price}-{max_price}")

    # Переходим к выбору звездности
    await ask_for_stars(callback.message, state)
    await callback.answer()


# ============================================
# Шаг 9: Выбор звездности (опционально)
# ============================================

async def ask_for_stars(message: Message, state: FSMContext):
    """Запросить минимальную звездность"""
    await state.set_state(TourSearchFlow.waiting_stars)

    # Удаляем предыдущий вопрос, отправляем новый
    await send_and_delete_previous(
        message=message,
        text="⭐ **Минимальная звездность отеля?**",
        state=state,
        reply_markup=stars_keyboard,
        parse_mode="Markdown"
    )
@router.callback_query(F.data.startswith("stars_"))
async def select_stars(callback: CallbackQuery, state: FSMContext):
    """Выбор звездности"""
    stars_data = callback.data.replace("stars_", "")

    if stars_data == "skip":
        await state.update_data(exact_stars=None, min_stars=None)
        logger.info("Звездность пропущена")
    else:
        exact_stars = int(stars_data)
        await state.update_data(exact_stars=exact_stars, min_stars=None)
        logger.info(f"Выбрана конкретная звездность: {exact_stars}")

    # Переходим к выбору удобств
    await ask_for_amenities(callback.message, state)
    await callback.answer()


# ============================================
# Шаг 10: Подтверждение параметров
# ============================================

async def show_params_confirmation(message: Message, state: FSMContext):
    """Показать все параметры для подтверждения"""
    data = await state.get_data()

    # Создаем SearchParams для форматирования
    try:
        params = SearchParams(
            from_city=data.get('from_city', 'Moscow'),
            to_country=data.get('to_country', 'TR'),
            to_city=data.get('to_city'),  # ИСПРАВЛЕНО: добавлен город назначения
            adults=data.get('adults', 2),
            start_date=data.get('start_date', '01.08.2024'),
            nights=data.get('nights', '7..9'),
            kids=data.get('kids', 0),
            kids_ages=data.get('kids_ages', []),
            min_price=data.get('min_price'),
            max_price=data.get('max_price'),
            exact_stars=data.get('exact_stars'),
            min_stars=data.get('min_stars'),
            amenities=data.get('selected_amenities', []),
            meal_types=data.get('selected_meals', [])
        )

        summary = format_search_summary(params)

        # Удаляем предыдущий вопрос, отправляем подтверждение
        await send_and_delete_previous(
            message=message,
            text=f"{summary}\n\n"
                 "**Всё верно?**",
            state=state,
            reply_markup=confirmation_keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка создания summary: {e}")
        await message.answer("Произошла ошибка. Попробуйте начать сначала.")


@router.callback_query(F.data == "confirm_search")
async def confirm_and_search(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и запуск поиска"""
    await callback.answer()
    await state.set_state(TourSearchFlow.searching_tours)

    # Удаляем последний вопрос бота (подтверждение)
    await delete_last_bot_message(callback.bot, callback.message.chat.id, state)

    # Показываем индикатор загрузки
    loading_msg = await callback.message.answer("🔍 Ищем туры...")

    try:
        # Получаем данные
        data = await state.get_data()
        
        # Создаем SearchParams
        params = SearchParams(
            from_city=data.get('from_city', 'Moscow'),
            to_country=data.get('to_country', 'TR'),
            to_city=data.get('to_city'),  # ИСПРАВЛЕНО: добавлен город назначения
            adults=data.get('adults', 2),
            start_date=data.get('start_date', '01.08.2024'),
            nights=data.get('nights', '7..9'),
            kids=data.get('kids', 0),
            kids_ages=data.get('kids_ages', []),
            min_price=data.get('min_price'),
            max_price=data.get('max_price'),
            exact_stars=data.get('exact_stars'),
            min_stars=data.get('min_stars'),
            amenities=data.get('selected_amenities', []),
            meal_types=data.get('selected_meals', [])
        )

        # Запускаем поиск
        service = LeveltravelService()
        request_id = await service.enqueue_search(params)
        
        logger.info(f"Поиск запущен, request_id: {request_id}")
        
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

        # Убираем дубликаты отелей (один отель может быть у нескольких операторов)
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
                [InlineKeyboardButton(text="Изменить параметры", callback_data="enter_params")],
                [InlineKeyboardButton(text="Главное меню", callback_data="start")]
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


@router.callback_query(F.data == "edit_params")
async def edit_params(callback: CallbackQuery, state: FSMContext):
    """Изменить параметры - показать меню редактирования"""
    from handlers.edit_params_handler import show_edit_params_menu
    await show_edit_params_menu(callback, state)
