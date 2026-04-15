from database.models import async_session, Hotel, Favorite
from sqlalchemy import select, update, func, delete
from typing import Optional, List
import json


async def set_hotel(id, hotelName, hotelDescription):
    async with async_session() as session:
        hotel = await session.scalar(select(Hotel).where(Hotel.id== id))
        if not hotel:
            new_hotel = Hotel(
                id=id,
                hotelName=hotelName,
                hotelDescription=hotelDescription
            )
            session.add(new_hotel)
            await session.commit()


async def hotel_exists(hotel_name: str) -> bool:
    """Проверяет существование отеля в базе данных по названию"""
    if not hotel_name or not hotel_name.strip():
        return False
    
    async with async_session() as session:
        hotel = await session.scalar(select(Hotel).where(Hotel.hotelName == hotel_name.strip()))
        return hotel is not None


async def get_hotel_info(hotel_name: str) -> Optional[dict]:
    """Получает информацию об отеле из базы данных по названию"""
    if not hotel_name or not hotel_name.strip():
        return None
    
    async with async_session() as session:
        hotel = await session.scalar(select(Hotel).where(Hotel.hotelName == hotel_name.strip()))
        if hotel:
            return {
                'id': hotel.id,
                'hotelName': hotel.hotelName,
                'hotelDescription': hotel.hotelDescription
            }
        return None


async def save_hotel_info(hotel_name: str, hotel_description: str) -> None:
    """Сохраняет информацию об отеле в базу данных"""
    if not hotel_name or not hotel_name.strip() or not hotel_description:
        return
    
    async with async_session() as session:
        # Проверяем, существует ли уже отель с таким названием
        existing_hotel = await session.scalar(select(Hotel).where(Hotel.hotelName == hotel_name.strip()))
        if not existing_hotel:
            new_hotel = Hotel(
                hotelName=hotel_name.strip(),
                hotelDescription=hotel_description
            )
            session.add(new_hotel)
            await session.commit()


async def get_hotel_by_url(tour_url: str) -> Optional[dict]:
    """Получает информацию об отеле по URL тура (если отель был сохранен ранее для этого URL)"""
    if not tour_url:
        return None

    # Пока что используем простую логику - ищем отель по названию из URL
    # В будущем можно добавить отдельную таблицу для связи URL и отелей
    return None


# ============================================
# Функции для работы с избранным
# ============================================

async def add_to_favorites(
    user_id: int,
    hotel_id: int,
    hotel_name: str,
    country: str,
    city: str,
    price: int,
    nights: int,
    start_date: str,
    tour_id: str,
    request_id: str,
    tour_data: dict
) -> bool:
    """
    Добавить тур в избранное.

    Args:
        user_id: ID пользователя Telegram
        hotel_id: ID отеля
        hotel_name: Название отеля
        country: Страна
        city: Город
        price: Цена тура
        nights: Количество ночей
        start_date: Дата вылета
        tour_id: ID тура
        request_id: ID запроса поиска
        tour_data: Полные данные тура в формате dict (будут сохранены как JSON)

    Returns:
        True если тур добавлен, False если уже был в избранном
    """
    async with async_session() as session:
        # Проверяем, есть ли уже этот тур в избранном
        existing = await session.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.hotel_id == hotel_id
            )
        )

        if existing:
            return False  # Уже в избранном

        # Добавляем новый тур
        favorite = Favorite(
            user_id=user_id,
            hotel_id=hotel_id,
            hotel_name=hotel_name,
            country=country,
            city=city,
            price=price,
            nights=nights,
            start_date=start_date,
            tour_id=tour_id,
            request_id=request_id,
            tour_data=json.dumps(tour_data, ensure_ascii=False)
        )

        session.add(favorite)
        await session.commit()
        return True


async def remove_from_favorites(user_id: int, favorite_id: int) -> bool:
    """
    Удалить тур из избранного по ID записи.

    Args:
        user_id: ID пользователя
        favorite_id: ID записи в таблице favorites

    Returns:
        True если удалено, False если запись не найдена
    """
    async with async_session() as session:
        result = await session.execute(
            delete(Favorite).where(
                Favorite.id == favorite_id,
                Favorite.user_id == user_id
            )
        )
        await session.commit()
        return result.rowcount > 0


async def get_user_favorites(user_id: int) -> List[dict]:
    """
    Получить все избранные туры пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        Список словарей с данными избранных туров
    """
    async with async_session() as session:
        result = await session.execute(
            select(Favorite)
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
        )
        favorites = result.scalars().all()

        return [
            {
                'id': fav.id,
                'hotel_id': fav.hotel_id,
                'hotel_name': fav.hotel_name,
                'country': fav.country,
                'city': fav.city,
                'price': fav.price,
                'nights': fav.nights,
                'start_date': fav.start_date,
                'tour_id': fav.tour_id,
                'request_id': fav.request_id,
                'tour_data': json.loads(fav.tour_data) if fav.tour_data else {},
                'created_at': fav.created_at
            }
            for fav in favorites
        ]


async def clear_user_favorites(user_id: int) -> int:
    """
    Удалить все избранные туры пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        Количество удаленных записей
    """
    async with async_session() as session:
        result = await session.execute(
            delete(Favorite).where(Favorite.user_id == user_id)
        )
        await session.commit()
        return result.rowcount


async def is_in_favorites(user_id: int, hotel_id: int) -> bool:
    """
    Проверить, находится ли тур в избранном.

    Args:
        user_id: ID пользователя
        hotel_id: ID отеля

    Returns:
        True если тур в избранном, False иначе
    """
    async with async_session() as session:
        result = await session.scalar(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.hotel_id == hotel_id
            )
        )
        return result is not None


async def get_favorites_count(user_id: int) -> int:
    """
    Получить количество избранных туров пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        Количество туров в избранном
    """
    async with async_session() as session:
        result = await session.scalar(
            select(func.count(Favorite.id)).where(Favorite.user_id == user_id)
        )
        return result or 0