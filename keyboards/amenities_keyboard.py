"""
Клавиатуры для выбора удобств отеля.
Используется в процессе подбора туров для фильтрации по удобствам.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Список доступных удобств с русскими названиями
AMENITIES_LIST = [
    ('pool', 'Бассейн'),
    ('heated_pool', 'Подогрев бассейна'),
    ('spa', 'СПА/Массаж'),
    ('gym', 'Фитнес-зал'),
    ('wifi', 'Wi-Fi бесплатно'),
    ('bar', 'Бар'),
    ('kids_club', 'Детский клуб'),
    ('kids_pool', 'Детский бассейн'),
    ('kids_menu', 'Детское меню'),
    ('nanny', 'Услуги няни'),
    ('parking', 'Парковка'),
    ('aquapark', 'Аквапарк'),
    ('beach_line', '1-я линия пляжа'),
]


def create_amenities_keyboard(selected_amenities: list = None) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора удобств отеля.
    
    Args:
        selected_amenities: Список уже выбранных удобств (их коды)
    
    Returns:
        InlineKeyboardMarkup с кнопками удобств
    """
    if selected_amenities is None:
        selected_amenities = []
    
    buttons = []
    
    # Создаем кнопки для каждого удобства
    for amenity_code, amenity_name in AMENITIES_LIST:
        # Добавляем галочку если удобство выбрано
        if amenity_code in selected_amenities:
            button_text = f"✅ {amenity_name}"
        else:
            button_text = amenity_name
        
        button = InlineKeyboardButton(
            text=button_text,
            callback_data=f"amenity_toggle_{amenity_code}"
        )
        buttons.append([button])
    
    # Добавляем кнопку "Продолжить без фильтров"
    buttons.append([
        InlineKeyboardButton(
            text="✅ Продолжить без фильтров" if not selected_amenities else "✅ Продолжить",
            callback_data="amenities_done"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_amenities_summary_keyboard() -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для подтверждения выбранных удобств.
    
    Returns:
        InlineKeyboardMarkup с кнопками подтверждения
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Всё верно", callback_data="amenities_confirm"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="amenities_edit")
        ]
    ])


def format_selected_amenities(selected_amenities: list) -> str:
    """
    Форматировать список выбранных удобств для отображения.
    
    Args:
        selected_amenities: Список кодов выбранных удобств
    
    Returns:
        Форматированная строка с выбранными удобствами
    """
    if not selected_amenities:
        return "Не выбраны"
    
    # Создаем словарь для быстрого поиска
    amenities_dict = dict(AMENITIES_LIST)
    
    # Форматируем список
    amenities_names = [
        amenities_dict.get(code, code) 
        for code in selected_amenities
    ]
    
    return ", ".join(amenities_names)
