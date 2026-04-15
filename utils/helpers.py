"""
Вспомогательные функции для проекта
"""

from datetime import datetime, timedelta


def get_or_default(value, default):
    """
    Вернуть default если value is None.
    
    В отличие от dict.get(key, default), эта функция проверяет само значение,
    а не наличие ключа в словаре.
    
    Args:
        value: Значение для проверки
        default: Значение по умолчанию если value is None
    
    Returns:
        default если value is None, иначе value
    
    Examples:
        >>> get_or_default(None, 0)
        0
        >>> get_or_default(5, 0)
        5
        >>> data = {"kids": None}
        >>> get_or_default(data.get("kids"), 0)
        0
    """
    return default if value is None else value


def get_min_date() -> datetime:
    """
    Получить минимальную допустимую дату вылета (завтра).
    
    Returns:
        datetime объект с датой завтра (00:00:00)
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today + timedelta(days=1)


def get_max_date() -> datetime:
    """
    Получить максимальную допустимую дату вылета (через 365 дней).
    
    Returns:
        datetime объект с датой через год
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today + timedelta(days=365)


def validate_date(date_str: str) -> tuple[bool, str]:
    """
    Валидация даты вылета.
    
    Args:
        date_str: Дата в формате DD.MM.YYYY
    
    Returns:
        Tuple (валидна ли дата, сообщение об ошибке)
    """
    try:
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        min_date = get_min_date()
        max_date = get_max_date()
        
        if date_obj < min_date:
            min_date_str = min_date.strftime("%d.%m.%Y")
            return False, f"Дата вылета не может быть в прошлом или сегодня. Минимальная дата: {min_date_str} (завтра)"
        
        if date_obj > max_date:
            max_date_str = max_date.strftime("%d.%m.%Y")
            return False, f"Дата вылета слишком далеко в будущем. Максимальная дата: {max_date_str}"
        
        return True, ""
    
    except ValueError:
        return False, "Неверный формат даты. Используйте DD.MM.YYYY"


def analyze_zero_results(data: dict) -> tuple[str, str]:
    """
    Анализ причины отсутствия результатов поиска.
    
    Args:
        data: Данные из state с параметрами поиска
    
    Returns:
        Tuple (причина, рекомендация)
    """
    start_date = data.get('start_date')
    from_city = data.get('from_city')
    
    # Список редких городов с ограниченным количеством направлений
    rare_cities = [
        "Ekaterinburg", "Novosibirsk", "Krasnoyarsk", "Irkutsk",
        "Vladivostok", "Khabarovsk", "Ufa", "Perm", "Chelyabinsk",
        "Omsk", "Samara", "Rostov-on-Don", "Volgograd", "Voronezh",
        "Barnaul", "Izhevsk", "Ulyanovsk", "Yaroslavl", "Tomsk",
        "Orenburg", "Kemerovo", "Novokuznetsk", "Ryazan", "Astrakhan",
        "Penza", "Kirov", "Lipetsk", "Cheboksary", "Kaliningrad", "Tula"
    ]
    
    # Проверка 1: Редкий город вылета
    if from_city and from_city in rare_cities:
        return (
            f"⚠️ Не найдено туров из города {from_city}.",
            f"**Возможные причины:**\n"
            f"• Ограниченное количество направлений из этого города\n"
            f"• На выбранные даты ({start_date}) нет рейсов\n"
            f"• Слишком специфичная комбинация параметров\n\n"
            f"**💡 Рекомендации:**\n"
            f"• Попробуйте Москву или Санкт-Петербург (больше направлений)\n"
            f"• Измените даты на ±3-7 дней\n"
            f"• Уменьшите количество ночей\n"
            f"• Попробуйте популярные направления (Турция, ОАЭ, Египет)"
        )
    
    # Проверка 2: Дата
    if start_date:
        try:
            date_obj = datetime.strptime(start_date, "%d.%m.%Y")
            days_until = (date_obj - datetime.now()).days
            
            if days_until <= 0:
                return (
                    "⚠️ Дата вылета уже прошла или сегодня.",
                    "Выберите дату не ранее завтрашнего дня."
                )
            
            if days_until > 365:
                return (
                    "⚠️ Дата вылета слишком далеко в будущем.",
                    "Выберите дату в ближайший год."
                )
        except:
            pass
    
    # Общая причина
    return (
        "⚠️ По вашим критериям туров не найдено.",
        "Попробуйте:\n"
        "• Расширить диапазон дат\n"
        "• Изменить количество ночей (например, 7-10)\n"
        "• Увеличить бюджет\n"
        "• Снизить требования к звездности (попробуйте 4★)"
    )
