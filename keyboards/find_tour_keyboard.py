"""
Клавиатуры для сценария подбора туров.
Унифицированные клавиатуры для всех handlers.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.country_data import COUNTRY_TO_ISO
from utils.city_data import get_cities_for_country
import math

# Определяем популярные страны и остальные
POPULAR_COUNTRIES = ['турция', 'египет', 'оаэ', 'таиланд', 'россия', 'абхазия', 'мальдивы']

# Специальные правила капитализации для аббревиатур
CAPITALIZATION_RULES = {
    'оаэ': 'ОАЭ',
    'юар': 'ЮАР',
    'сша': 'США'
}

def format_country_name(country_name: str) -> str:
    """Форматирует название страны с учетом специальных правил."""
    if country_name in CAPITALIZATION_RULES:
        return CAPITALIZATION_RULES[country_name]
    return country_name.capitalize()

# Формируем полный список стран в нужном порядке
ordered_countries = []
popular_set = set()

# Сначала популярные
for country_name in POPULAR_COUNTRIES:
    if country_name in COUNTRY_TO_ISO:
        ordered_countries.append((format_country_name(country_name), COUNTRY_TO_ISO[country_name]))
        popular_set.add(country_name)

# Затем остальные по алфавиту
other_countries = []
for name, code in COUNTRY_TO_ISO.items():
    if name not in popular_set:
        other_countries.append((format_country_name(name), code))

ordered_countries.extend(sorted(other_countries, key=lambda x: x[0]))


def create_country_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора страны с пагинацией."""
    builder = InlineKeyboardBuilder()
    items_per_page = 8
    
    start_offset = page * items_per_page
    end_offset = start_offset + items_per_page
    
    # Добавляем кнопки стран для текущей страницы
    for name, code in ordered_countries[start_offset:end_offset]:
        builder.button(text=name, callback_data=f"country_{code}")
    
    # Рассчитываем общее количество страниц
    total_pages = math.ceil(len(ordered_countries) / items_per_page)
    
    # Создаем навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"country_page_{page - 1}"))
    
    if end_offset < len(ordered_countries):
        nav_buttons.append(InlineKeyboardButton(text="▶️ Вперёд", callback_data=f"country_page_{page + 1}"))

    # Выстраиваем кнопки стран в 2 колонки
    builder.adjust(2)
    
    # Добавляем ряд с навигацией
    if nav_buttons:
        builder.row(*nav_buttons)
        
    return builder.as_markup()


# ============================================
# Главное меню выбора сценария
# ============================================

inspiring_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Ввести параметры", callback_data="enter_params")]
    ]
)


# ============================================
# REPLY-КЛАВИАТУРЫ (исчезающие после выбора)
# ============================================

# Клавиатура для выбора города вылета (REPLY)
departure_city_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Москва")],
        [KeyboardButton(text="СПб")],
        [KeyboardButton(text="Другой город")],
        [KeyboardButton(text="Пропустить")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Клавиатура для выбора популярной страны (REPLY)
popular_countries_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Турция"), KeyboardButton(text="Египет")],
        [KeyboardButton(text="ОАЭ"), KeyboardButton(text="Таиланд")],
        [KeyboardButton(text="Вьетнам"), KeyboardButton(text="Грузия")],
        [KeyboardButton(text="Другая")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Клавиатура для выбора количества ночей (REPLY)
nights_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="2-4 ночи"), KeyboardButton(text="5-7 ночей")],
        [KeyboardButton(text="8-14 ночей"), KeyboardButton(text="14+ ночей")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Клавиатура для выбора количества взрослых (REPLY)
adults_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="1"), KeyboardButton(text="2")],
        [KeyboardButton(text="3"), KeyboardButton(text="4+")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Клавиатура для выбора количества детей (REPLY)
kids_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="0"), KeyboardButton(text="1")],
        [KeyboardButton(text="2"), KeyboardButton(text="3+")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Клавиатура для выбора бюджета (REPLY)
budget_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="до 100к")],
        [KeyboardButton(text="100-200к")],
        [KeyboardButton(text="200-300к")],
        [KeyboardButton(text="400-500к")],
        [KeyboardButton(text="500к+")],
        [KeyboardButton(text="Пропустить")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Клавиатура для выбора звездности (REPLY)
stars_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="5 звезд")],
        [KeyboardButton(text="4 звезды")],
        [KeyboardButton(text="3 звезды")],
        [KeyboardButton(text="Любые")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Удаление клавиатуры
remove_keyboard = ReplyKeyboardRemove()


def create_destination_city_keyboard(country_code: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора города назначения в выбранной стране.

    Args:
        country_code: ISO код страны (например, "TR", "EG")

    Returns:
        InlineKeyboardMarkup с кнопками городов или None если города не найдены
    """
    country_data = get_cities_for_country(country_code)

    if not country_data:
        # Если для страны нет предзаданных городов, предлагаем сразу искать по всей стране
        builder = InlineKeyboardBuilder()
        builder.button(text="Вся страна", callback_data="destination_all")
        builder.button(text="Указать город вручную", callback_data="destination_custom")
        builder.adjust(1)
        return builder.as_markup()

    builder = InlineKeyboardBuilder()

    # Добавляем кнопку "Вся страна" первой
    builder.button(text="🌍 Вся страна", callback_data="destination_all")

    # Добавляем города в порядке из display_order
    for city_russian in country_data["display_order"]:
        city_english = country_data["cities"][city_russian]
        builder.button(
            text=city_russian,
            callback_data=f"destination_{city_english}"
        )

    # Добавляем кнопку для ручного ввода
    builder.button(text="✏️ Другой город", callback_data="destination_custom")

    # Размещаем кнопки: "Вся страна" отдельно, остальные по 2 в ряд
    builder.adjust(1, 2, 2, 2, 2, 2, 1)

    return builder.as_markup()


# ============================================
# INLINE-КЛАВИАТУРЫ (старые, для совместимости)
# ============================================

# Клавиатура для выбора города вылета
departure_city_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Москва", callback_data="departure_Moscow")],
        [InlineKeyboardButton(text="СПб", callback_data="departure_Saint Petersburg")],
        [InlineKeyboardButton(text="Другой город", callback_data="departure_other")],
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="departure_skip")]
    ]
)


# Клавиатура для выбора популярной страны
popular_countries_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Турция", callback_data="country_TR")],
        [InlineKeyboardButton(text="Египет", callback_data="country_EG")],
        [InlineKeyboardButton(text="ОАЭ", callback_data="country_AE")],
        [InlineKeyboardButton(text="Таиланд", callback_data="country_TH")],
        [InlineKeyboardButton(text="Вьетнам", callback_data="country_VN")],
        [InlineKeyboardButton(text="Грузия", callback_data="country_GE")],
        [InlineKeyboardButton(text="Другая страна", callback_data="country_other")]
    ]
)





# Клавиатура для выбора количества ночей
nights_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="2-4 ночи", callback_data="nights_2..4")],
        [InlineKeyboardButton(text="5-7 ночей", callback_data="nights_5..7")],
        [InlineKeyboardButton(text="8-14 ночей", callback_data="nights_8..14")],
        [InlineKeyboardButton(text="14+ ночей", callback_data="nights_14..21")],
    ]
)


# Клавиатура для выбора количества взрослых
adults_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="1", callback_data="adults_1"),
            InlineKeyboardButton(text="2", callback_data="adults_2"),
        ],
        [
            InlineKeyboardButton(text="3", callback_data="adults_3"),
            InlineKeyboardButton(text="4+", callback_data="adults_4"),
        ]
    ]
)


# Клавиатура для выбора количества детей
kids_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="0", callback_data="kids_0"),
            InlineKeyboardButton(text="1", callback_data="kids_1"),
        ],
        [
            InlineKeyboardButton(text="2", callback_data="kids_2"),
            InlineKeyboardButton(text="3+", callback_data="kids_3"),
        ]
    ]
)


# Клавиатура для выбора бюджета
budget_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="до 100к", callback_data="budget_0_100000")],
        [InlineKeyboardButton(text="100-200к", callback_data="budget_100000_200000")],
        [InlineKeyboardButton(text="200-300к", callback_data="budget_200000_300000")],
        [InlineKeyboardButton(text="400-500к", callback_data="budget_400000_500000")],
        [InlineKeyboardButton(text="500к+", callback_data="budget_500000_999999")],
        [InlineKeyboardButton(text="Пропустить", callback_data="budget_skip")],
    ]
)


# Клавиатура для выбора звездности
stars_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="5 звезд", callback_data="stars_5")],
        [InlineKeyboardButton(text="4 звезды", callback_data="stars_4")],
        [InlineKeyboardButton(text="3 звезды", callback_data="stars_3")],
        [InlineKeyboardButton(text="2 звезды", callback_data="stars_2")],
        [InlineKeyboardButton(text="1 звезда", callback_data="stars_1")],
        [InlineKeyboardButton(text="Любые", callback_data="stars_skip")],
    ]
)


# Клавиатура для подтверждения параметров
confirmation_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅ Искать туры", callback_data="confirm_search")],
        [InlineKeyboardButton(text="✏️ Изменить", callback_data="edit_params")],
    ]
)

