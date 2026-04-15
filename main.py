import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from handlers import (
    start_handler,
    find_tour_handler,
    params_handler,
    improved_tour_handler,
    amenities_handler,
    tour_feed_handler,
    edit_params_handler,
    inspiring_handler,
    description_handler,
    chat_handler,
    favorites_handler
)
from config import BOT_TOKEN, setup_logging
from database.models import async_main

# Настройка логирования с дублированием в файл и Google Sheets
logger = setup_logging()

async def main():
    try:
        logger.info("Запуск бота...")
        
        bot = Bot(token=BOT_TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Регистрируем роутеры (порядок важен!)
        dp.include_router(start_handler.router)           # /start и главное меню
        dp.include_router(favorites_handler.router)       # Заметки
        dp.include_router(edit_params_handler.router)     # Выборочное редактирование параметров
        dp.include_router(params_handler.router)          # Ручной ввод параметров
        dp.include_router(improved_tour_handler.router)   # Свободный текст через AI
        dp.include_router(amenities_handler.router)       # Выбор удобств
        dp.include_router(tour_feed_handler.router)       # Просмотр туров
        dp.include_router(find_tour_handler.router)       # Кнопка "Подобрать тур"
        dp.include_router(inspiring_handler.router)       # "Получить вдохновение"
        dp.include_router(description_handler.router)     # Описание бота
        dp.include_router(chat_handler.router)            # Чат с Navia (в конец)
        await async_main()
        
        logger.info("Роутеры зарегистрированы, начинаем polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        raise
    finally:
        logger.info("Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
        sys.exit(1)