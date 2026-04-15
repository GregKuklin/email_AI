"""
Клавиатуры для выбора типов питания.
Используется для клиентской фильтрации туров по типу питания.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Список доступных типов питания (упрощенный)
MEAL_TYPES_LIST = [
    ('WITH_MEAL', '🍽️ С питанием'),
    ('WITHOUT_MEAL', '🚫 Без питания'),
]

# Маппинг упрощенных типов на реальные коды API
MEAL_TYPE_MAPPING = {
    'WITH_MEAL': ['AI', 'UAI', 'BB', 'HB', 'FB', 'HBD', 'AI24', 'DNR', 'AIL', 'FB+', 'HB+', 'HBL'],
    'WITHOUT_MEAL': ['RO']
}


def expand_meal_types(selected_meals: list) -> list:
    """
    Разворачивает упрощенные коды типов питания в полные списки API кодов.

    Args:
        selected_meals: Список упрощенных кодов (['WITH_MEAL'], ['WITHOUT_MEAL'], или оба)

    Returns:
        Список реальных кодов API для фильтрации

    Examples:
        ['WITH_MEAL'] → ['AI', 'UAI', 'BB', 'HB', 'FB', ...]
        ['WITHOUT_MEAL'] → ['RO']
        ['WITH_MEAL', 'WITHOUT_MEAL'] → [] (все типы)
        [] → [] (все типы)
    """
    if not selected_meals:
        return []  # Пустой список = показать все

    # Если выбраны оба варианта - показать все
    if len(selected_meals) == 2:
        return []

    # Разворачиваем выбранный тип
    expanded = []
    for meal_code in selected_meals:
        expanded.extend(MEAL_TYPE_MAPPING.get(meal_code, []))

    return expanded


def create_meal_types_keyboard(selected_meals: list = None) -> InlineKeyboardMarkup:
    """
    Создать клавиатуру для выбора типов питания (упрощенную).

    Args:
        selected_meals: Список уже выбранных типов питания (упрощенные коды)

    Returns:
        InlineKeyboardMarkup с кнопками типов питания

    Note:
        Клиентская фильтрация - туры фильтруются после получения от API.
        Теперь только 2 опции: "С питанием" и "Без питания"
    """
    if selected_meals is None:
        selected_meals = []

    buttons = []

    # Создаем ряд с двумя кнопками
    row = []
    for meal_code, meal_name in MEAL_TYPES_LIST:
        # Добавляем галочку если тип выбран
        if meal_code in selected_meals:
            button_text = f"✅ {meal_name}"
        else:
            button_text = meal_name

        button = InlineKeyboardButton(
            text=button_text,
            callback_data=f"meal_toggle_{meal_code}"
        )
        row.append(button)

    buttons.append(row)

    # Добавляем кнопку "Продолжить"
    continue_text = "✅ Продолжить"
    if not selected_meals:
        continue_text = "✅ Продолжить (все типы)"
    elif len(selected_meals) == 2:
        continue_text = "✅ Продолжить (все типы)"

    buttons.append([
        InlineKeyboardButton(
            text=continue_text,
            callback_data="meal_done"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_selected_meals(selected_meals: list) -> str:
    """
    Форматировать список выбранных типов питания для отображения.

    Args:
        selected_meals: Список упрощенных кодов выбранных типов питания

    Returns:
        Форматированная строка с выбранными типами питания
    """
    if not selected_meals:
        return "Любое питание"

    # Если выбраны оба варианта
    if len(selected_meals) == 2:
        return "Любое питание"

    # Создаем словарь для быстрого поиска
    meals_dict = {code: name for code, name in MEAL_TYPES_LIST}

    # Форматируем список
    meals_names = [
        meals_dict.get(code, code)
        for code in selected_meals
    ]

    return ", ".join(meals_names)
