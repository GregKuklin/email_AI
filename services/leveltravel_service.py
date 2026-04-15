"""
Сервис для работы с Leveltravel API.
Реализует полный цикл работы: поиск туров, проверка статуса, получение результатов.

API документация: см. документация.txt
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, List
from datetime import datetime

from config import LEVELTRAVEL_API_KEY
from models.tour_models import SearchParams, HotelCard, dict_to_hotel_card

logger = logging.getLogger(__name__)


class LeveltravelAPIError(Exception):
    """Базовый класс для ошибок Leveltravel API"""
    pass


class LeveltravelTimeoutError(LeveltravelAPIError):
    """Превышено время ожидания результатов поиска"""
    pass


class LeveltravelAuthError(LeveltravelAPIError):
    """Ошибка авторизации (неверный API ключ)"""
    pass


class LeveltravelService:
    """
    Сервис для взаимодействия с Leveltravel API.
    
    Основной flow работы:
    1. enqueue_search() - постановка поиска в очередь
    2. wait_for_results() - ожидание завершения поиска
    3. get_hotels_page() - получение страницы отелей
    4. get_hotel_rooms() - получение деталей номеров отеля
    """
    
    BASE_URL = "https://api.level.travel"
    API_VERSION = "application/vnd.leveltravel.v3.7"
    
    def __init__(self):
        if not LEVELTRAVEL_API_KEY:
            logger.error("LEVELTRAVEL_API_KEY не найден в конфигурации!")
            raise ValueError("LEVELTRAVEL_API_KEY не настроен")
        
        self.api_key = LEVELTRAVEL_API_KEY
        logger.info(f"Инициализация LeveltravelService с ключом: {self.api_key[:10]}...")
    
    def _get_headers(self) -> dict:
        """Получить заголовки для запросов к API"""
        return {
            "Authorization": f'Token token="{self.api_key}"',
            "Accept": self.API_VERSION,
            "Content-Type": "application/json"
        }
    
    async def enqueue_search(self, params: SearchParams) -> str:
        """
        Постановка поиска туров в очередь.
        
        Args:
            params: Параметры поиска (SearchParams)
        
        Returns:
            request_id - идентификатор поискового запроса
        
        Raises:
            LeveltravelAuthError: Ошибка авторизации
            LeveltravelAPIError: Другие ошибки API
        """
        endpoint = f"{self.BASE_URL}/search/enqueue"
        # Используем только базовые параметры без фильтров для enqueue
        api_params = params.to_enqueue_params()

        logger.info(f"Запуск поиска туров с параметрами: {api_params}")
        if params.to_city:
            logger.warning(f"⚠️ Поиск по конкретному городу: {params.to_city}. API может вернуть 0 результатов!")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint,
                    params=api_params,
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    # Логируем статус ответа
                    logger.info(f"Статус ответа от /search/enqueue: {response.status}")
                    
                    if response.status == 401:
                        logger.error("Ошибка авторизации: неверный API ключ")
                        raise LeveltravelAuthError("Неверный API ключ")
                    
                    if response.status == 400:
                        error_data = await response.json()
                        error_msg = error_data.get('error', 'Неизвестная ошибка')
                        logger.error(f"Некорректный запрос: {error_msg}")
                        raise LeveltravelAPIError(f"Ошибка запроса: {error_msg}")
                    
                    if response.status == 403:
                        logger.error("Доступ запрещен")
                        raise LeveltravelAuthError("Доступ запрещен - проверьте API ключ")
                    
                    if response.status != 200:
                        logger.error(f"Неожиданный статус: {response.status}")
                        raise LeveltravelAPIError(f"API вернул статус {response.status}")
                    
                    data = await response.json()
                    
                    if not data.get('success'):
                        error = data.get('error', 'Неизвестная ошибка')
                        logger.error(f"API вернул ошибку: {error}")
                        raise LeveltravelAPIError(f"Ошибка API: {error}")
                    
                    request_id = data.get('request_id')
                    if not request_id:
                        logger.error("API не вернул request_id")
                        raise LeveltravelAPIError("Не получен request_id от API")
                    
                    logger.info(f"Поиск успешно поставлен в очередь, request_id: {request_id}")
                    return request_id
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка соединения с API: {e}")
            raise LeveltravelAPIError(f"Ошибка соединения: {str(e)}")
    
    async def check_status(self, request_id: str, show_size: bool = False) -> dict:
        """
        Проверка статуса выполнения поискового запроса.
        
        Args:
            request_id: ID поискового запроса
            show_size: Показывать ли размер результатов
        
        Returns:
            dict с ключами: status (dict со статусами по операторам), size, success
        
        Статусы:
        - pending: в ожидании
        - performing: выполняется
        - completed: завершено
        - cached: взято из кэша
        - no_results: нет результатов
        - failed: ошибка
        - skipped: пропущено
        - all_filtered: все отфильтровано
        """
        endpoint = f"{self.BASE_URL}/search/status"
        params = {
            "request_id": request_id,
            "show_size": str(show_size).lower()
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint,
                    params=params,
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    
                    if response.status == 401:
                        raise LeveltravelAuthError("Ошибка авторизации")
                    
                    if response.status == 422:
                        error_data = await response.json()
                        error_msg = error_data.get('error_message', 'Неверный request_id')
                        logger.error(f"Ошибка проверки статуса: {error_msg}")
                        raise LeveltravelAPIError(error_msg)
                    
                    if response.status != 200:
                        raise LeveltravelAPIError(f"API вернул статус {response.status}")
                    
                    data = await response.json()
                    return data
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка проверки статуса: {e}")
            raise LeveltravelAPIError(f"Ошибка соединения: {str(e)}")
    
    async def wait_for_results(self, request_id: str, timeout: int = 60, poll_interval: int = 3) -> bool:
        """
        Ожидание завершения поиска с polling.
        
        Args:
            request_id: ID поискового запроса
            timeout: Максимальное время ожидания в секундах
            poll_interval: Интервал проверки в секундах
        
        Returns:
            True если поиск завершен успешно
        
        Raises:
            LeveltravelTimeoutError: Превышено время ожидания
        """
        logger.info(f"Ожидание результатов поиска {request_id}, timeout={timeout}s")
        
        start_time = datetime.now()
        attempts = 0
        
        while True:
            attempts += 1
            elapsed = (datetime.now() - start_time).total_seconds()
            
            if elapsed > timeout:
                logger.error(f"Превышен timeout {timeout}s для request_id={request_id}")
                raise LeveltravelTimeoutError(f"Поиск занял более {timeout} секунд")
            
            try:
                status_data = await self.check_status(request_id, show_size=True)
                statuses = status_data.get('status', {})
                
                # Подсчитываем статусы
                final_statuses = ['completed', 'cached', 'no_results', 'failed', 'skipped', 'all_filtered']
                pending_statuses = ['pending', 'performing']
                
                total = len(statuses)
                completed_count = sum(1 for s in statuses.values() if s in final_statuses)
                
                logger.info(f"Попытка #{attempts}: {completed_count}/{total} операторов завершили поиск")
                
                # Проверяем: все ли операторы завершили работу
                if all(status in final_statuses for status in statuses.values()):
                    logger.info(f"Поиск завершен! Всего результатов: {status_data.get('size', 'N/A')}")
                    return True
                
                # Ждем перед следующей проверкой
                await asyncio.sleep(poll_interval)
                
            except LeveltravelAPIError as e:
                logger.error(f"Ошибка при проверке статуса: {e}")
                # Продолжаем пытаться если не истек timeout
                await asyncio.sleep(poll_interval)
    
    async def get_hotels_page(
        self,
        request_id: str,
        search_params: Optional[SearchParams] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "price"
    ) -> tuple[List[HotelCard], int]:
        """
        Получение страницы отелей из результатов поиска.

        Args:
            request_id: ID поискового запроса
            search_params: Параметры поиска для применения фильтров (опционально)
            page: Номер страницы (начиная с 1)
            limit: Количество отелей на странице
            sort_by: Сортировка (price, rating, relevance)

        Returns:
            tuple[List[HotelCard], int]: (Список HotelCard объектов, Общее количество найденных отелей)
        """
        endpoint = f"{self.BASE_URL}/search/get_grouped_hotels"
        
        params = {
            "request_id": request_id,
            "page_number": page,
            "page_limit": limit,
            "sort_by": sort_by
        }
        
        # Добавляем фильтры из SearchParams если переданы
        if search_params:
            filter_params = search_params.to_filter_params()
            if filter_params:
                params.update(filter_params)
                logger.info(f"Применены фильтры: {list(filter_params.keys())}")
                logger.info(f"Значения фильтров: {filter_params}")

        logger.info(f"Запрос отелей: page={page}, limit={limit}, sort={sort_by}")
        logger.info(f"ВСЕ параметры запроса get_hotels_page: {params}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint,
                    params=params,
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 401:
                        raise LeveltravelAuthError("Ошибка авторизации")
                    
                    if response.status == 422:
                        error_data = await response.json()
                        error_msg = error_data.get('error_message', 'Ошибка запроса')
                        logger.error(f"Ошибка получения отелей: {error_msg}")
                        raise LeveltravelAPIError(error_msg)
                    
                    if response.status != 200:
                        raise LeveltravelAPIError(f"API вернул статус {response.status}")
                    
                    data = await response.json()

                    if not data.get('success'):
                        error = data.get('error', 'Неизвестная ошибка')
                        raise LeveltravelAPIError(f"Ошибка API: {error}")

                    hotels_data = data.get('hotels', [])
                    hotels_count = data.get('hotels_count', 0)

                    logger.info(f"Получено {len(hotels_data)} отелей на странице {page}, всего найдено: {hotels_count}")

                    # ОТЛАДКА: Логируем города отелей если их мало
                    if len(hotels_data) > 0 and len(hotels_data) <= 5:
                        cities = [h.get('hotel', {}).get('city', 'N/A') for h in hotels_data]
                        logger.info(f"Города в результатах: {cities}")

                    # Конвертируем в HotelCard объекты
                    hotel_cards = []
                    for hotel_data in hotels_data:
                        try:
                            card = dict_to_hotel_card(hotel_data)
                            hotel_cards.append(card)
                        except Exception as e:
                            logger.error(f"Ошибка конвертации отеля: {e}")
                            # Пропускаем проблемный отель
                            continue

                    # Клиентская фильтрация по городу ОТКЛЮЧЕНА
                    # Причина: API Level.Travel не поддерживает строгую фильтрацию по городу.
                    # Даже при указании to_city='Dubai', API может вернуть отели из других городов (Дейра, Рас-аль-Хайма).
                    # Строгая клиентская фильтрация приводит к 0 результатам.
                    # Решение: Показываем отели из всех городов региона с указанием города в карточке.

                    if search_params and search_params.to_city:
                        from utils.city_data import get_city_russian_name
                        to_city_russian = get_city_russian_name(
                            search_params.to_country,
                            search_params.to_city
                        )
                        logger.info(
                            f"🏙️ Предпочтительный город: {search_params.to_city} (рус: {to_city_russian}). "
                            f"Показываем отели из всех городов региона (API не поддерживает строгую фильтрацию)."
                        )

                    return hotel_cards, hotels_count
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка получения отелей: {e}")
            raise LeveltravelAPIError(f"Ошибка соединения: {str(e)}")
    
    async def get_hotel_rooms(self, request_id: str, hotel_id: int) -> dict:
        """
        Получение информации о номерах в отеле.
        
        Args:
            request_id: ID поискового запроса
            hotel_id: ID отеля
        
        Returns:
            dict с информацией о номерах и предложениях
        """
        endpoint = f"{self.BASE_URL}/search/hotel_rooms"
        params = {
            "request_id": request_id,
            "hotel_id": hotel_id
        }
        
        logger.info(f"Запрос номеров для отеля {hotel_id}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    endpoint,
                    params=params,
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status != 200:
                        raise LeveltravelAPIError(f"API вернул статус {response.status}")
                    
                    data = await response.json()
                    
                    if not data.get('success'):
                        raise LeveltravelAPIError("Ошибка получения номеров")
                    
                    logger.info(f"Получена информация о номерах отеля {hotel_id}")
                    return data.get('result', [])
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка получения номеров: {e}")
            raise LeveltravelAPIError(f"Ошибка соединения: {str(e)}")
    
    async def get_package_details(self, tour_id: str, request_id: str) -> dict:
        """
        Получить полную информацию о турпакете.
        Возвращает подробные данные: точные даты, трансфер, тип номера,
        чистую цену, условия отмены и другие детали.
        
        Args:
            tour_id: ID тура
            request_id: ID поискового запроса
        
        Returns:
            dict с полной информацией о пакете
        """
        endpoint = f"{self.BASE_URL}/packages/package_details"
        
        body = {
            "tour_id": tour_id,
            "request_id": request_id
        }
        
        logger.info(f"Запрос деталей пакета для тура {tour_id}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=body,
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status != 200:
                        logger.error(f"Ошибка получения деталей пакета: {response.status}")
                        raise LeveltravelAPIError(f"API вернул статус {response.status}")
                    
                    data = await response.json()
                    
                    if not data.get('success'):
                        raise LeveltravelAPIError("Ошибка получения деталей пакета")
                    
                    logger.info(f"Получены детали пакета для тура {tour_id}")
                    return data.get('package', {})
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка получения деталей пакета: {e}")
            raise LeveltravelAPIError(f"Ошибка соединения: {str(e)}")
    
    async def get_booking_link(self, tour_id: str, hotel_id: int, request_id: str) -> str:
        """
        Получить партнерскую ссылку на бронирование тура.
        
        Args:
            tour_id: ID тура
            hotel_id: ID отеля
            request_id: ID поискового запроса
        
        Returns:
            Партнерская URL для бронирования через tp.media
        """
        from urllib.parse import quote
        
        # Формируем URL level.travel
        level_url = f"https://level.travel/package_details/{tour_id}?hotel_id={hotel_id}&request_id={request_id}"
        
        # Кодируем для партнерской ссылки
        encoded_url = quote(level_url, safe='')
        
        # Формируем партнерскую ссылку
        partner_link = (
            f"https://tp.media/r?"
            f"marker=624775&"
            f"trs=409439&"
            f"p=660&"
            f"u={encoded_url}&"
            f"campaign_id=26"
        )
        
        return partner_link
    
    async def test_connection(self) -> bool:
        """
        Тестирование подключения к API.
        Выполняет простой тестовый запрос для проверки работоспособности.
        
        Returns:
            True если подключение успешно
        """
        try:
            # Создаем тестовые параметры поиска
            from datetime import datetime, timedelta
            test_date = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")
            
            test_params = SearchParams(
                from_city="Moscow",
                to_country="TR",
                adults=2,
                start_date=test_date,
                nights="7..7"
            )
            
            request_id = await self.enqueue_search(test_params)
            logger.info(f"Тест подключения успешен! request_id: {request_id}")
            return True
            
        except LeveltravelAuthError:
            logger.error("Тест подключения провален: ошибка авторизации")
            return False
        except Exception as e:
            logger.error(f"Тест подключения провален: {e}")
            return False
