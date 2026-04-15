"""
Модели данных для работы с турами и отелями.
Используются для типизации и структурирования данных из Leveltravel API.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class SearchParams:
    """Параметры поиска туров для Leveltravel API"""
    
    # Обязательные параметры
    from_city: str              # "Moscow", "Saint Petersburg"
    to_country: str             # ISO2 код: "TR", "EG", "AE", "TH", etc.
    adults: int                 # Количество взрослых (минимум 1)
    start_date: str             # Дата вылета "DD.MM.YYYY"
    nights: str                 # Интервал ночей "7..9", "10..14"
    
    # Опциональные параметры
    kids: int = 0                           # Количество детей
    kids_ages: list[int] = field(default_factory=list)  # Возраста детей
    
    # Фильтры
    min_price: Optional[int] = None         # Минимальная цена
    max_price: Optional[int] = None         # Максимальная цена
    min_stars: Optional[int] = None         # Минимум звезд (1-5) - устаревшее, использовать exact_stars
    exact_stars: Optional[int] = None       # Конкретная звездность (3, 4, или 5)
    
    # Удобства (amenities)
    amenities: list[str] = field(default_factory=list)  # ["pool", "spa", "wifi"]

    # Клиентские фильтры (применяются после получения от API)
    meal_types: list[str] = field(default_factory=list)  # ["AI", "UAI", "BB", "HB", "FB", "RO"]

    # Дополнительные параметры
    to_city: Optional[str] = None           # Конкретный город назначения
    hotel_ids: list[int] = field(default_factory=list)  # Конкретные отели
    
    def to_enqueue_params(self) -> dict:
        """
        Конвертация в параметры для search/enqueue.
        Только базовые параметры поиска без фильтров.
        """
        params = {
            "from_city": self.from_city,
            "to_country": self.to_country,
            "adults": self.adults,
            "start_date": self.start_date,
            "nights": self.nights,
        }
        
        # Добавляем опциональные параметры
        if self.kids is not None and self.kids > 0:
            params["kids"] = self.kids
            params["kids_ages"] = self.kids_ages
            
        if self.to_city:
            params["to_city"] = self.to_city
            
        if self.hotel_ids:
            params["hotel_ids"] = self.hotel_ids
        
        return params
    
    def to_filter_params(self) -> dict:
        """
        Конвертация в параметры фильтрации для search/get_grouped_hotels.
        Только фильтры, без базовых параметров поиска.
        """
        filters = {}
        
        # Фильтры по цене
        if self.min_price is not None and self.min_price > 0:
            filters["filter_price_min"] = self.min_price
        if self.max_price is not None and self.max_price > 0:
            filters["filter_price_max"] = self.max_price
            
        # Фильтр по звездности
        # Приоритет: exact_stars (конкретная звездность) > min_stars (устаревшее)
        if self.exact_stars is not None and self.exact_stars > 0:
            # Конкретная звездность - только указанное значение
            filters["filter_stars"] = str(self.exact_stars)
        elif self.min_stars is not None and self.min_stars > 0:
            # Старая логика "от X звезд" для обратной совместимости
            filters["filter_stars"] = ",".join([str(i) for i in range(5, self.min_stars - 1, -1)])
            
        # Маппинг удобств на API фильтры
        amenity_filters = self._map_amenities_to_filters()
        filters.update(amenity_filters)
        
        return filters
    
    def _map_amenities_to_filters(self) -> dict:
        """
        Маппинг удобств на фильтры API.
        Используется только в to_filter_params() для search/get_grouped_hotels.
        
        ВАЖНО: Boolean значения конвертируются в строки 'true'/'false',
        т.к. aiohttp не принимает boolean в query параметрах.
        """
        filters = {}
        
        amenity_mapping = {
            'pool': {'filter_pool': 'true'},
            'heated_pool': {'filter_heated_pool': 'true'},
            'spa': {'filter_massage': 'true', 'filter_thermal_fun': 'true'},
            'wifi': {'filter_wifi': 'FREE'},  # FREE или PAID
            'bar': {'filter_bar': 'true'},
            'kids_club': {'filter_kids_club': 'true'},
            'kids_pool': {'filter_kids_pool': 'true'},
            'kids_menu': {'filter_kids_menu': 'true'},
            'nanny': {'filter_nanny': 'true'},
            'parking': {'filter_parking': 'true'},
            'aquapark': {'filter_aquapark': 'true'},
            'beach_line': {'filter_line': 1},  # Первая линия пляжа
        }
        
        for amenity in self.amenities:
            if amenity in amenity_mapping:
                filters.update(amenity_mapping[amenity])

        return filters

    def has_meal_filter(self) -> bool:
        """Проверка наличия фильтра по типу питания"""
        return bool(self.meal_types)


@dataclass
class HotelFeatures:
    """Особенности отеля"""
    airport_distance: Optional[int] = None  # Расстояние до аэропорта (метры)
    beach_distance: Optional[int] = None    # Расстояние до пляжа (метры)
    beach_type: Optional[str] = None        # Тип пляжа
    beach_surface: Optional[str] = None     # Поверхность пляжа
    line: Optional[int] = None              # Линия пляжа
    wi_fi: Optional[str] = None             # Тип Wi-Fi


@dataclass
class HotelImage:
    """Изображение отеля"""
    x500: Optional[str] = None
    x900: Optional[str] = None
    webp_x620: Optional[str] = None
    
    def get_best_url(self) -> Optional[str]:
        """Получить лучшее доступное качество"""
        return self.x900 or self.webp_x620 or self.x500


@dataclass
class Hotel:
    """Информация об отеле"""
    id: int
    name: str
    rating: float
    stars: int
    city: str
    region_name: str
    lat: float
    long: float
    link: str
    images: list[HotelImage]
    features: HotelFeatures
    
    def get_photo_urls(self, limit: int = 10) -> list[str]:
        """Получить список URL фотографий"""
        urls = []
        for img in self.images:
            url = img.get_best_url()
            if url:
                urls.append(url)
            if len(urls) >= limit:
                break
        return urls


@dataclass
class MealType:
    """Тип питания"""
    id: str                 # "AI", "UAI", "BB", etc.
    min_price: int          # Минимальная цена для этого типа питания
    description: str        # "Всё включено", "Завтрак", etc.


@dataclass
class RoomDetails:
    """Детали номера"""
    id: int
    name_ru: str
    name_en: str
    accommodation: str      # "3 чел (2 взрослых + 1 ребенок)"
    area: Optional[int]     # Площадь в м²
    description: str
    view: str
    facilities: list[dict]  # Список удобств номера
    images: list[HotelImage]


@dataclass
class TourOffer:
    """Предложение тура"""
    id: str                         # ID предложения
    nights_count: int               # Количество ночей
    price: int                      # Цена в рублях
    operator_id: int                # ID туроператора
    operator_name: str              # Название туроператора
    start_date: str                 # Дата вылета
    link: str                       # Ссылка на детали
    meal_type: str                  # Тип питания
    instant_confirm: bool           # Мгновенное подтверждение
    availability: dict              # Доступность (flight, hotel)


@dataclass
class HotelCard:
    """
    Карточка отеля для отображения в ленте.
    Основная структура данных для показа пользователю.
    """
    hotel_id: int
    hotel_name: str
    stars: int
    rating: float
    region: str
    city: str
    min_price: int
    nights: int
    operator_name: str
    meal_type: str              # "AI", "UAI", "BB"
    meal_description: str       # "Всё включено", "Завтрак"
    images: list[str]           # URL фотографий (минимум 5)
    tour_id: str
    tour_link: str
    description: str
    features: HotelFeatures
    instant_confirm: bool
    availability: str           # Текстовое описание доступности
    
    # Дополнительная информация
    start_date: str
    surcharge: int = 0
    bonus_count: int = 0
    
    def format_price(self) -> str:
        """Форматированная цена"""
        return f"{self.min_price:,}".replace(",", " ")
    
    def format_stars(self) -> str:
        """Звезды в текстовом формате"""
        if self.stars == 0:
            return "Без звезд"
        elif self.stars == 1:
            return "1 звезда"
        elif self.stars in [2, 3, 4]:
            return f"{self.stars} звезды"
        else:
            return f"{self.stars} звезд"
    
    def get_meal_emoji(self) -> str:
        """Эмодзи для типа питания"""
        meal_emojis = {
            "AI": "🍽️",
            "UAI": "🍽️✨",
            "FB": "🍽️",
            "HB": "🥐",
            "BB": "☕",
            "RO": "🚫"
        }
        return meal_emojis.get(self.meal_type, "🍽️")


def dict_to_hotel_card(api_data: dict) -> HotelCard:
    """
    Конвертация ответа API в HotelCard.
    
    Args:
        api_data: Данные из Leveltravel API (один элемент массива hotels)
    
    Returns:
        HotelCard объект
    """
    hotel_data = api_data.get("hotel", {})
    
    # Извлекаем фотографии
    images_data = hotel_data.get("images", [])
    image_urls = []
    for img in images_data:
        url = img.get("x900") or img.get("webp_x620") or img.get("x500")
        if url:
            image_urls.append(url)
    
    # НЕ дозаполняем повторами - используем сколько есть (1, 2, 3, 4 или 5+)
    
    # Извлекаем features
    features_data = hotel_data.get("features", {})
    features = HotelFeatures(
        airport_distance=features_data.get("airport_distance"),
        beach_distance=features_data.get("beach_distance"),
        beach_type=features_data.get("beach_type"),
        beach_surface=features_data.get("beach_surface"),
        line=features_data.get("line"),
        wi_fi=features_data.get("wi_fi")
    )
    
    # Определяем тип питания и описание
    meal_type = api_data.get("meal_type", "RO")
    meal_descriptions = {
        "BB": "Завтрак",
        "RO": "Без питания",
        "AI": "Всё включено",
        "UAI": "Ультра всё включено",
        "HB": "Завтрак и ужин",
        "FB": "Завтрак, обед, ужин",
        "HBD": "Завтрак и ужин (или обед)",
        "AI24": "Всё включено 24 часа",
        "DNR": "Ужин",
        "AIL": "Всё включено с ограничениями",
        "FB+": "Завтрак, обед, ужин +",
        "HB+": "Завтрак и ужин +",
        "HBL": "Завтрак и обед"
    }
    meal_description = meal_descriptions.get(meal_type, "Не указано")
    
    # Извлекаем extras
    extras = api_data.get("extras", {})
    
    # Availability
    availability_data = api_data.get("availability", {})
    flight = availability_data.get("flight", "n/a")
    hotel = availability_data.get("hotel", "n/a")
    availability_tooltip = availability_data.get("tooltip", "")
    
    return HotelCard(
        hotel_id=hotel_data.get("id"),
        hotel_name=hotel_data.get("name", "Неизвестный отель"),
        stars=hotel_data.get("stars", 0),
        rating=hotel_data.get("rating", 0.0),
        region=hotel_data.get("region_name", ""),
        city=hotel_data.get("city", ""),
        min_price=api_data.get("min_price", 0),
        nights=api_data.get("min_price_nights", 7),
        operator_name="Различные операторы",  # Будет определено из offers
        meal_type=meal_type,
        meal_description=meal_description,
        images=image_urls[:10],  # Максимум 10 для Telegram
        tour_id=api_data.get("tour_id", ""),
        tour_link=f"https://level.travel{hotel_data.get('link', '')}",
        description=hotel_data.get("description", ""),
        features=features,
        instant_confirm=extras.get("instant_confirm", False),
        availability=availability_tooltip,
        start_date="",  # Будет заполнено из search params
        surcharge=api_data.get("surcharge", 0),
        bonus_count=api_data.get("bonus_count", 0)
    )


def remove_duplicate_hotels(hotels: list[HotelCard]) -> list[HotelCard]:
    """
    Убирает дубликаты отелей, оставляя лучшее предложение для каждого.
    
    API Level.Travel возвращает несколько туров для одного отеля (разные операторы,
    типы питания). Эта функция группирует по hotel_id и выбирает вариант с лучшей ценой.
    
    Args:
        hotels: Список всех туров из API
    
    Returns:
        Список уникальных отелей (по hotel_id) с лучшими ценами
    """
    if not hotels:
        return []
    
    # Группируем по hotel_id
    hotels_dict = {}
    
    for hotel in hotels:
        if hotel.hotel_id not in hotels_dict:
            # Первая встреча этого отеля
            hotels_dict[hotel.hotel_id] = hotel
        else:
            # Если цена лучше - заменяем
            if hotel.min_price < hotels_dict[hotel.hotel_id].min_price:
                hotels_dict[hotel.hotel_id] = hotel
    
    # Возвращаем только уникальные отели, отсортированные по цене
    unique_hotels = list(hotels_dict.values())
    unique_hotels.sort(key=lambda h: h.min_price)
    
    return unique_hotels


def format_search_summary(params: SearchParams) -> str:
    """
    Форматирование параметров поиска для показа пользователю.
    
    Args:
        params: Параметры поиска
    
    Returns:
        Форматированная строка с параметрами
    """
    # Форматируем направление
    destination = params.to_country
    if params.to_city:
        destination = f"{params.to_city}, {params.to_country}"

    summary = f"""📋 **Параметры поиска:**

📍 **Откуда:** {params.from_city}
🌍 **Куда:** {destination}
📅 **Дата вылета:** {params.start_date}
🌙 **Ночей:** {params.nights}
👥 **Туристы:** {params.adults} взр."""
    
    if params.kids > 0:
        ages_str = ", ".join([str(age) for age in params.kids_ages])
        summary += f", {params.kids} дет. ({ages_str} лет)"
    
    if params.min_price or params.max_price:
        budget_str = ""
        if params.min_price and params.max_price:
            budget_str = f"{params.min_price:,} - {params.max_price:,}₽"
        elif params.min_price:
            budget_str = f"от {params.min_price:,}₽"
        elif params.max_price:
            budget_str = f"до {params.max_price:,}₽"
        summary += f"\n💰 **Бюджет:** {budget_str}"
    
    # Отображаем звездность (приоритет exact_stars)
    if params.exact_stars:
        summary += f"\n⭐ **Звезды:** {params.exact_stars}"
    elif params.min_stars:
        summary += f"\n⭐ **Звезды:** от {params.min_stars}"
    
    if params.amenities:
        amenity_names = {
            'pool': 'Бассейн',
            'heated_pool': 'Подогреваемый бассейн',
            'spa': 'СПА/Массаж',
            'gym': 'Тренажерный зал',
            'wifi': 'Wi-Fi',
            'bar': 'Бар',
            'kids_club': 'Детский клуб',
            'kids_pool': 'Детский бассейн',
            'kids_menu': 'Детское меню',
            'nanny': 'Няня',
            'parking': 'Парковка',
            'aquapark': 'Аквапарк',
            'beach_line': '1-я линия пляжа',
        }
        amenities_str = ", ".join([amenity_names.get(a, a) for a in params.amenities])
        summary += f"\n🏊 **Удобства:** {amenities_str}"

    # ========================================
    # MEAL FILTER DISABLED (2025-12-14)
    # ========================================
    # Фильтр по типу питания отключен для показа всех доступных вариантов пользователям.
    # Оставлен закомментированным для возможности быстрого восстановления функционала.
    #
    # # Питание
    # if params.meal_types:
    #     from keyboards.meal_keyboard import format_selected_meals
    #     meals_str = format_selected_meals(params.meal_types)
    #     summary += f"\n🍽️ **Питание:** {meals_str}"

    return summary


# ========================================
# MEAL FILTER DISABLED (2025-12-14)
# ========================================
# Фильтрация по типу питания отключена. Пользователи видят все варианты туров
# независимо от типа питания. Функция оставлена для возможности быстрого восстановления.
#
# def filter_hotels_by_meal(hotels: list['HotelCard'], meal_types: list[str]) -> list['HotelCard']:
#     """
#     Клиентская фильтрация отелей по типу питания.
#
#     Args:
#         hotels: Список отелей для фильтрации
#         meal_types: Допустимые типы питания (["AI", "UAI", "BB"])
#
#     Returns:
#         Отфильтрованный список отелей
#
#     Note:
#         Эта функция применяется на клиенте, т.к. API Level.Travel
#         не поддерживает filter_meals в параметрах запроса.
#     """
#     if not meal_types:
#         return hotels
#
#     return [hotel for hotel in hotels if hotel.meal_type in meal_types]
