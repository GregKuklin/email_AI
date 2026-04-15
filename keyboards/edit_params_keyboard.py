"""
Клавиатура для выборочного редактирования параметров тура.
Позволяет изменять отдельные параметры без повторного ввода всех данных.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional


def create_edit_params_keyboard(
    from_city: str = None,
    to_country: str = None,
    to_city: str = None,
    start_date: str = None,
    nights: str = None,
    adults: int = None,
    kids: int = None,
    kids_ages: list = None,
    min_price: int = None,
    max_price: int = None,
    min_stars: int = None,
    amenities: list = None
) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выборочного редактирования параметров.
    
    Args:
        Все параметры поиска тура
        
    Returns:
        InlineKeyboardMarkup с кнопками редактирования для каждого параметра
    """
    
    # Маппинг кодов стран
    countries = {
        'TR': 'Турция',
        'EG': 'Египет',
        'AE': 'ОАЭ',
        'TH': 'Таиланд',
        'GR': 'Греция',
        'ES': 'Испания',
    }
    
    # Маппинг городов
    cities = {
        'Moscow': 'Москва',
        'Saint Petersburg': 'СПб',
        'Kazan': 'Казань',
    }
    
    # Маппинг удобств
    amenities_map = {
        'pool': 'Бассейн',
        'heated_pool': 'Подогрев бассейна',
        'spa': 'СПА',
        'gym': 'Фитнес-зал',
        'wifi': 'Wi-Fi',
        'bar': 'Бар',
        'kids_club': 'Детский клуб',
        'kids_pool': 'Детский бассейн',
        'kids_menu': 'Детское меню',
        'nanny': 'Няня',
        'parking': 'Парковка',
        'aquapark': 'Аквапарк',
        'beach_line': '1-я линия',
    }
    
    buttons = []
    
    # Откуда
    if from_city:
        city_display = cities.get(from_city, from_city)
        buttons.append([
            InlineKeyboardButton(
                text=f"Откуда: {city_display}",
                callback_data="param_display"
            ),
            InlineKeyboardButton(
                text="Изменить",
                callback_data="edit_param_from_city"
            )
        ])
    
    # Куда
    if to_country:
        country_display = countries.get(to_country, to_country)
        # Добавляем город, если указан
        if to_city:
            destination_display = f"{to_city}, {country_display}"
        else:
            destination_display = country_display

        buttons.append([
            InlineKeyboardButton(
                text=f"Куда: {destination_display}",
                callback_data="param_display"
            ),
            InlineKeyboardButton(
                text="Изменить",
                callback_data="edit_param_country"
            )
        ])
    
    # Даты
    if start_date:
        buttons.append([
            InlineKeyboardButton(
                text=f"Дата: {start_date}",
                callback_data="param_display"
            ),
            InlineKeyboardButton(
                text="Изменить",
                callback_data="edit_param_dates"
            )
        ])
    
    # Ночей
    if nights:
        buttons.append([
            InlineKeyboardButton(
                text=f"Ночей: {nights}",
                callback_data="param_display"
            ),
            InlineKeyboardButton(
                text="Изменить",
                callback_data="edit_param_nights"
            )
        ])
    
    # Взрослые
    if adults:
        buttons.append([
            InlineKeyboardButton(
                text=f"Взрослых: {adults}",
                callback_data="param_display"
            ),
            InlineKeyboardButton(
                text="Изменить",
                callback_data="edit_param_adults"
            )
        ])
    
    # Дети
    kids_text = f"Детей: {kids or 0}"
    if kids and kids > 0 and kids_ages:
        ages_str = ', '.join(str(age) for age in kids_ages)
        kids_text += f" ({ages_str} лет)"

    buttons.append([
        InlineKeyboardButton(
            text=kids_text,
            callback_data="param_display"
        ),
        InlineKeyboardButton(
            text="Изменить",
            callback_data="edit_param_kids"
        )
    ])
    
    # Бюджет
    if min_price or max_price:
        if min_price and max_price:
            budget_text = f"Бюджет: {min_price:,} - {max_price:,}₽".replace(',', ' ')
        elif max_price:
            budget_text = f"Бюджет: до {max_price:,}₽".replace(',', ' ')
        elif min_price:
            budget_text = f"Бюджет: от {min_price:,}₽".replace(',', ' ')

        buttons.append([
            InlineKeyboardButton(
                text=budget_text,
                callback_data="param_display"
            ),
            InlineKeyboardButton(
                text="Изменить",
                callback_data="edit_param_budget"
            )
        ])
    
    # Звезды
    if min_stars:
        buttons.append([
            InlineKeyboardButton(
                text=f"Звезды: от {min_stars}",
                callback_data="param_display"
            ),
            InlineKeyboardButton(
                text="Изменить",
                callback_data="edit_param_stars"
            )
        ])
    
    # Удобства
    if amenities and len(amenities) > 0:
        amenities_display = ', '.join([amenities_map.get(a, a) for a in amenities[:2]])
        if len(amenities) > 2:
            amenities_display += f" +{len(amenities) - 2}"

        buttons.append([
            InlineKeyboardButton(
                text=f"Удобства: {amenities_display}",
                callback_data="param_display"
            ),
            InlineKeyboardButton(
                text="Изменить",
                callback_data="edit_param_amenities"
            )
        ])
    
    # Разделитель
    buttons.append([
        InlineKeyboardButton(
            text="─" * 25,
            callback_data="separator"
        )
    ])
    
    # Кнопки действий
    buttons.append([
        InlineKeyboardButton(
            text="✅ Искать туры",
            callback_data="confirm_edited_params"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="🔄 Сначала",
            callback_data="enter_params"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_params_summary(params: dict) -> str:
    """
    Форматировать краткую сводку по параметрам.
    
    Args:
        params: Словарь с параметрами
        
    Returns:
        Отформатированная строка
    """
    
    countries = {
        'TR': 'Турция',
        'EG': 'Египет',
        'AE': 'ОАЭ',
        'TH': 'Таиланд',
        'GR': 'Греция',
        'ES': 'Испания',
    }

    cities = {
        'Moscow': 'Москва',
        'Saint Petersburg': 'СПб',
        'Kazan': 'Казань',
    }

    text = "**Текущие параметры поиска:**\n\n"

    if params.get('from_city'):
        city = cities.get(params['from_city'], params['from_city'])
        text += f"Откуда: {city}\n"

    if params.get('to_country'):
        country = countries.get(params['to_country'], params['to_country'])
        # Добавляем город, если указан
        if params.get('to_city'):
            text += f"Куда: {params['to_city']}, {country}\n"
        else:
            text += f"Куда: {country}\n"

    if params.get('start_date'):
        text += f"Дата: {params['start_date']}\n"

    if params.get('nights'):
        text += f"Ночей: {params['nights']}\n"

    if params.get('adults'):
        text += f"Взрослых: {params['adults']}\n"

    kids = params.get('kids', 0)
    if kids > 0:
        kids_ages = params.get('kids_ages', [])
        ages_str = ', '.join(str(age) for age in kids_ages) if kids_ages else ''
        text += f"Детей: {kids}" + (f" ({ages_str} лет)" if ages_str else "") + "\n"

    if params.get('max_price'):
        text += f"Бюджет: до {params['max_price']:,}₽\n".replace(',', ' ')

    if params.get('min_stars'):
        text += f"Звезды: от {params['min_stars']}\n"

    amenities = params.get('amenities', [])
    if amenities:
        amenities_map = {
            'pool': 'Бассейн',
            'spa': 'СПА',
            'wifi': 'Wi-Fi',
            'bar': 'Бар',
            'kids_club': 'Детский клуб',
        }
        amenities_display = ', '.join([amenities_map.get(a, a) for a in amenities])
        text += f"Удобства: {amenities_display}\n"

    text += "\n**Нажмите 'Изменить' чтобы изменить параметр**"
    
    return text
