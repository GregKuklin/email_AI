"""
Сервис для работы с фотографиями отелей.
Подготовка MediaGroup для отправки в Telegram.
"""

import logging
from typing import List
from aiogram.types import InputMediaPhoto
from models.tour_models import HotelCard

logger = logging.getLogger(__name__)

# Placeholder изображение (если фото недоступны)
PLACEHOLDER_IMAGE = "https://via.placeholder.com/800x600?text=No+Image"


async def get_mixed_photos(
    hotel: HotelCard,
    request_id: str,
    cached_rooms_data: list = None
) -> list:
    """
    Получить смешанные фото отеля и номеров.
    
    Args:
        hotel: HotelCard с данными отеля
        request_id: ID поискового запроса
        cached_rooms_data: Кэшированные данные hotel_rooms
    
    Returns:
        Список URL фотографий (минимум 5, максимум 10)
    """
    all_photos = []
    room_photos = []
    
    # 1. Фото отеля (берем только ПЕРВОЕ)
    hotel_photos = hotel.images[:1]  # Только 1 фото отеля
    all_photos.extend(hotel_photos)
    
    # 2. Собираем ВСЕ фото номеров (из кэша)
    if cached_rooms_data:
        for room_data in cached_rooms_data:
            room = room_data.get('room') or {}
            images = room.get('images') or []
            
            for img in images:
                if not img:
                    continue
                photo_url = img.get('x900') or img.get('x900x380')
                # Проверяем уникальность среди всех фото
                if photo_url and photo_url not in all_photos and photo_url not in room_photos:
                    room_photos.append(photo_url)
                    
                # Останавливаемся когда собрали достаточно
                if len(room_photos) >= 9:  # Максимум 9 фото номеров (1 отель + 9 = 10 лимит)
                    break
            
            if len(room_photos) >= 9:
                break
    
    # 3. Формируем финальный список: 1 отель + до 4 номеров
    if room_photos:
        # Берем первые 4 фото номеров
        all_photos.extend(room_photos[:4])  # Ровно 4 фото номеров
        logger.info(f"Отель {hotel.hotel_name}: 1 фото отеля + {len(room_photos[:4])} фото номеров")
    else:
        # Fallback: если фото номеров нет - используем фото отеля
        logger.warning(f"Отель {hotel.hotel_name}: нет фото номеров, используем только фото отеля")
        if len(hotel.images) >= 5:
            all_photos = hotel.images[:5]
        else:
            all_photos = hotel.images  # Оставляем как есть
    
    # 4. Если совсем нет фото - placeholder (минимум 2 для Telegram MediaGroup)
    if len(all_photos) == 0:
        logger.warning(f"Отель {hotel.hotel_name} не имеет фото")
        all_photos = [PLACEHOLDER_IMAGE] * 2
    
    return all_photos[:10]  # Максимум 10 для Telegram


def prepare_media_group(
    hotel: HotelCard,
    add_caption: bool = True,
    mixed_photos: list = None
) -> List[InputMediaPhoto]:
    """
    Подготовить MediaGroup с фотографиями отеля для Telegram.
    
    Args:
        hotel: HotelCard с информацией об отеле
        add_caption: Добавить ли подпись к первому фото
        mixed_photos: Предподготовленный список фото (отель+номера)
    
    Returns:
        Список InputMediaPhoto для отправки через send_media_group
    """
    # Используем mixed_photos если есть, иначе только фото отеля
    if mixed_photos:
        photos = mixed_photos
        logger.info(f"Используем {len(photos)} смешанных фото (отель + номера)")
    else:
        photos = hotel.images[:10]  # Telegram лимит: 10 фото в MediaGroup
        
        # Без дозаполнения повторами
        if 0 < len(photos) < 2:
            logger.warning(f"Отель {hotel.hotel_name} имеет только {len(photos)} фото")
            # Добавляем placeholder до минимума 2 для MediaGroup
            while len(photos) < 2:
                photos.append(PLACEHOLDER_IMAGE)
        elif len(photos) == 0:
            # Если совсем нет фото - добавляем 2 placeholder
            logger.warning(f"Отель {hotel.hotel_name} не имеет фото, используем placeholder")
            photos = [PLACEHOLDER_IMAGE, PLACEHOLDER_IMAGE]
    
    media = []
    
    for i, photo_url in enumerate(photos):
        try:
            if i == 0 and add_caption:
                # Первое фото с подписью
                caption = f"{hotel.format_stars()} {hotel.hotel_name}"
                media.append(InputMediaPhoto(
                    media=photo_url,
                    caption=caption
                ))
            else:
                media.append(InputMediaPhoto(media=photo_url))
                
        except Exception as e:
            logger.error(f"Ошибка добавления фото {photo_url}: {e}")
            # Пропускаем проблемное фото
            continue
    
    return media


def validate_photo_url(url: str) -> bool:
    """
    Проверить валидность URL фотографии.
    
    Args:
        url: URL для проверки
    
    Returns:
        True если URL валиден
    """
    if not url:
        return False
    
    # Проверяем что это HTTP(S) ссылка
    if not url.startswith(('http://', 'https://')):
        return False
    
    # Проверяем что это изображение (по расширению)
    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
    if not any(url.lower().endswith(ext) for ext in valid_extensions):
        # Если нет расширения, но есть домен level.travel или cdn - считаем валидным
        if 'level.travel' in url or 'cdn' in url:
            return True
        return False
    
    return True


def format_photo_urls(urls: List[str]) -> List[str]:
    """
    Отфильтровать и отформатировать список URL фотографий.
    
    Args:
        urls: Список URL
    
    Returns:
        Отфильтрованный список валидных URL
    """
    valid_urls = []
    
    for url in urls:
        if validate_photo_url(url):
            valid_urls.append(url)
        else:
            logger.warning(f"Невалидный URL фото: {url}")
    
    # Если нет валидных URL, добавляем placeholder
    if not valid_urls:
        valid_urls.append(PLACEHOLDER_IMAGE)
    
    return valid_urls
