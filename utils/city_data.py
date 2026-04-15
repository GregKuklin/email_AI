"""
Модуль для работы с городами назначения.
Содержит словарь популярных городов/курортов для каждой страны.
"""

# Словарь: ISO код страны -> список городов (английские названия для API)
COUNTRY_CITIES = {
    # Турция (TR)
    "TR": {
        "display_order": ["Анталия", "Кемер", "Аланья", "Сиде", "Белек", "Бодрум", "Мармарис", "Фетхие", "Стамбул"],
        "cities": {
            "Анталия": "Antalya",
            "Кемер": "Kemer",
            "Аланья": "Alanya",
            "Сиде": "Side",
            "Белек": "Belek",
            "Бодрум": "Bodrum",
            "Мармарис": "Marmaris",
            "Фетхие": "Fethiye",
            "Стамбул": "Istanbul",
        }
    },

    # Египет (EG)
    "EG": {
        "display_order": ["Шарм-эль-Шейх", "Хургада", "Марса Алам", "Таба", "Дахаб", "Эль-Гуна"],
        "cities": {
            "Шарм-эль-Шейх": "Sharm el-Sheikh",
            "Хургада": "Hurghada",
            "Марса Алам": "Marsa Alam",
            "Таба": "Taba",
            "Дахаб": "Dahab",
            "Эль-Гуна": "El Gouna",
        }
    },

    # ОАЭ (AE)
    "AE": {
        "display_order": ["Дубай", "Абу-Даби", "Шарджа", "Рас-аль-Хайма", "Фуджейра", "Аджман"],
        "cities": {
            "Дубай": "Dubai",
            "Абу-Даби": "Abu Dhabi",
            "Шарджа": "Sharjah",
            "Рас-аль-Хайма": "Ras Al Khaimah",
            "Фуджейра": "Fujairah",
            "Аджман": "Ajman",
        }
    },

    # Таиланд (TH)
    "TH": {
        "display_order": ["Пхукет", "Паттайя", "Самуи", "Краби", "Бангкок", "Хуа Хин", "Ча-Ам"],
        "cities": {
            "Пхукет": "Phuket",
            "Паттайя": "Pattaya",
            "Самуи": "Koh Samui",
            "Краби": "Krabi",
            "Бангкок": "Bangkok",
            "Хуа Хин": "Hua Hin",
            "Ча-Ам": "Cha-am",
        }
    },

    # Греция (GR)
    "GR": {
        "display_order": ["Афины", "Крит", "Родос", "Корфу", "Халкидики", "Санторини", "Закинф", "Кос"],
        "cities": {
            "Афины": "Athens",
            "Крит": "Crete",
            "Родос": "Rhodes",
            "Корфу": "Corfu",
            "Халкидики": "Chalkidiki",
            "Санторини": "Santorini",
            "Закинф": "Zakynthos",
            "Кос": "Kos",
        }
    },

    # Испания (ES)
    "ES": {
        "display_order": ["Барселона", "Мадрид", "Тенерифе", "Майорка", "Коста-Дорада", "Коста-Брава", "Ибица"],
        "cities": {
            "Барселона": "Barcelona",
            "Мадрид": "Madrid",
            "Тенерифе": "Tenerife",
            "Майорка": "Mallorca",
            "Коста-Дорада": "Costa Dorada",
            "Коста-Брава": "Costa Brava",
            "Ибица": "Ibiza",
        }
    },

    # Вьетнам (VN)
    "VN": {
        "display_order": ["Нячанг", "Фукуок", "Фантьет", "Дананг", "Ханой", "Хошимин"],
        "cities": {
            "Нячанг": "Nha Trang",
            "Фукуок": "Phu Quoc",
            "Фантьет": "Phan Thiet",
            "Дананг": "Da Nang",
            "Ханой": "Hanoi",
            "Хошимин": "Ho Chi Minh City",
        }
    },

    # Мальдивы (MV)
    "MV": {
        "display_order": ["Мале", "Северный Мале Атолл", "Южный Мале Атолл", "Ари Атолл"],
        "cities": {
            "Мале": "Male",
            "Северный Мале Атолл": "North Male Atoll",
            "Южный Мале Атолл": "South Male Atoll",
            "Ари Атолл": "Ari Atoll",
        }
    },

    # Кипр (CY)
    "CY": {
        "display_order": ["Айя-Напа", "Протарас", "Лимассол", "Пафос", "Ларнака"],
        "cities": {
            "Айя-Напа": "Ayia Napa",
            "Протарас": "Protaras",
            "Лимассол": "Limassol",
            "Пафос": "Paphos",
            "Ларнака": "Larnaca",
        }
    },

    # Италия (IT)
    "IT": {
        "display_order": ["Рим", "Милан", "Венеция", "Флоренция", "Римини", "Неаполь", "Сицилия"],
        "cities": {
            "Рим": "Rome",
            "Милан": "Milan",
            "Венеция": "Venice",
            "Флоренция": "Florence",
            "Римини": "Rimini",
            "Неаполь": "Naples",
            "Сицилия": "Sicily",
        }
    },
}


def get_cities_for_country(country_code: str) -> dict | None:
    """
    Возвращает словарь городов для указанной страны.

    Args:
        country_code: ISO код страны (например, "TR", "EG")

    Returns:
        Словарь с ключами display_order и cities, или None если страна не найдена
    """
    return COUNTRY_CITIES.get(country_code)


def get_city_english_name(country_code: str, russian_name: str) -> str | None:
    """
    Возвращает английское название города по русскому.

    Args:
        country_code: ISO код страны
        russian_name: Русское название города

    Returns:
        Английское название города или None
    """
    country_data = COUNTRY_CITIES.get(country_code)
    if not country_data:
        return None

    return country_data["cities"].get(russian_name)


def normalize_city_name(city_input: str, country_code: str) -> str | None:
    """
    Нормализует пользовательский ввод города и возвращает английское название.

    Args:
        city_input: Ввод пользователя (например, "кемер", "Кемер", "КЕМЕР")
        country_code: ISO код страны

    Returns:
        Английское название города или None
    """
    country_data = COUNTRY_CITIES.get(country_code)
    if not country_data:
        return None

    # Нормализуем ввод пользователя
    normalized_input = city_input.strip().lower()

    # Ищем совпадение по русскому названию (без учета регистра)
    for russian_name, english_name in country_data["cities"].items():
        if russian_name.lower() == normalized_input:
            return english_name

    return None


def get_city_russian_name(country_code: str, english_name: str) -> str | None:
    """
    Возвращает русское название города по английскому.

    ВАЖНО: API Level.Travel возвращает города на РУССКОМ языке!
    Эта функция используется для фильтрации результатов.

    Args:
        country_code: ISO код страны (например, "TH")
        english_name: Английское название города (например, "Phuket")

    Returns:
        Русское название города (например, "Пхукет") или None

    Example:
        >>> get_city_russian_name("TH", "Phuket")
        "Пхукет"
        >>> get_city_russian_name("TH", "Pattaya")
        "Паттайя"
    """
    country_data = COUNTRY_CITIES.get(country_code)
    if not country_data:
        return None

    # Создаём обратный маппинг: английский -> русский
    for russian_name, eng_name in country_data["cities"].items():
        if eng_name.lower() == english_name.lower():
            return russian_name

    return None


def get_alternative_cities(country_code: str, current_city: str, max_alternatives: int = 3) -> list[tuple[str, str]]:
    """
    Возвращает список альтернативных городов в той же стране.

    Используется когда туры в конкретный город закончились,
    чтобы предложить пользователю туры в другие города страны.

    Args:
        country_code: ISO код страны (например, "AE" для ОАЭ)
        current_city: Текущий город (английское название, например "Dubai")
        max_alternatives: Максимальное количество альтернатив

    Returns:
        Список кортежей (английское_название, русское_название) альтернативных городов
        Возвращает пустой список если страна не найдена или нет альтернатив

    Example:
        >>> get_alternative_cities("AE", "Dubai", 3)
        [("Abu Dhabi", "Абу-Даби"), ("Sharjah", "Шарджа"), ("Ras Al Khaimah", "Рас-аль-Хайма")]

        >>> get_alternative_cities("TR", "Antalya", 2)
        [("Kemer", "Кемер"), ("Alanya", "Аланья")]
    """
    country_data = COUNTRY_CITIES.get(country_code)
    if not country_data:
        return []

    cities = country_data["cities"]
    display_order = country_data["display_order"]

    # Нормализуем текущий город для сравнения
    current_city_lower = current_city.lower()

    # Собираем альтернативы в порядке display_order
    alternatives = []
    for russian_name in display_order:
        english_name = cities.get(russian_name)
        if english_name and english_name.lower() != current_city_lower:
            alternatives.append((english_name, russian_name))

            # Ограничиваем количество
            if len(alternatives) >= max_alternatives:
                break

    return alternatives
