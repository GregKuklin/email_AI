"""
Утилита для автоматического удаления предыдущих сообщений бота.
Помогает поддерживать чат чистым и читаемым.

Подход: каждое новое сообщение удаляет предыдущее.
"""

import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


async def send_and_delete_previous(
    message: Message,
    text: str,
    state: FSMContext,
    reply_markup=None,
    parse_mode: str = "Markdown",
    state_key: str = "last_bot_message_id"
) -> Message:
    """
    Отправить новое сообщение и удалить предыдущее.

    Это основная функция для чистого чата - она:
    1. Удаляет предыдущее сообщение бота (если есть)
    2. Отправляет новое сообщение
    3. Сохраняет ID нового сообщения в state

    Args:
        message: Message объект (от пользователя)
        text: Текст нового сообщения
        state: FSMContext для хранения ID
        reply_markup: Клавиатура (опционально)
        parse_mode: Режим парсинга (Markdown/HTML)
        state_key: Ключ в state для хранения ID

    Returns:
        Message: Отправленное сообщение
    """
    # Получаем ID предыдущего сообщения бота
    data = await state.get_data()
    previous_msg_id = data.get(state_key)

    # Удаляем предыдущее сообщение если оно есть
    if previous_msg_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=previous_msg_id
            )
            logger.debug(f"✅ Удалено предыдущее сообщение {previous_msg_id}")
        except Exception as e:
            logger.debug(f"Не удалось удалить сообщение {previous_msg_id}: {e}")

    # Отправляем новое сообщение
    sent_message = await message.answer(
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )

    # Сохраняем ID нового сообщения
    await state.update_data({state_key: sent_message.message_id})
    logger.debug(f"📝 Сохранен ID нового сообщения: {sent_message.message_id}")

    return sent_message


async def delete_last_bot_message(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    state_key: str = "last_bot_message_id"
) -> bool:
    """
    Удалить последнее сообщение бота из state.

    Используется когда нужно просто удалить последнее сообщение
    без отправки нового (например, перед показом туров).

    Args:
        bot: Bot instance
        chat_id: ID чата
        state: FSMContext
        state_key: Ключ в state

    Returns:
        bool: True если сообщение было удалено
    """
    data = await state.get_data()
    message_id = data.get(state_key)

    if not message_id:
        logger.debug("Нет сообщения для удаления в state")
        return False

    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        await state.update_data({state_key: None})
        logger.info(f"✅ Удалено последнее сообщение бота: {message_id}")
        return True
    except Exception as e:
        logger.warning(f"❌ Ошибка удаления сообщения {message_id}: {e}")
        return False


async def clear_all_bot_messages(state: FSMContext):
    """
    Очистить все сохраненные ID сообщений из state.

    Используется при сбросе состояния или начале нового процесса.
    """
    await state.update_data(last_bot_message_id=None)
    logger.debug("🧹 Очищены все ID сообщений из state")
