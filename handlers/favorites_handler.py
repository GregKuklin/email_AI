"""
Обработчик для работы с избранными турами.
Просмотр, удаление, очистка избранного.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from database.requests import (
    get_user_favorites,
    remove_from_favorites,
    clear_user_favorites,
    get_favorites_count
)
from keyboards.favorites_keyboard import create_favorites_list_keyboard, confirm_clear_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "Мои заметки")
@router.message(Command("favorites"))
async def show_favorites(message: Message, state: FSMContext, user_id: int = None):
    """Показать список избранных туров"""
    await state.clear()

    # Если user_id не передан, берём из message
    if user_id is None:
        user_id = message.from_user.id

    try:
        favorites = await get_user_favorites(user_id)

        if not favorites:
            await message.answer(
                "📭 **Ваши заметки пусты**\n\n"
                "Добавляйте понравившиеся туры в заметки, "
                "чтобы не потерять их!",
                parse_mode="Markdown"
            )
            return

        # Формируем список
        text = f"💾 **Ваши сохраненные туры ({len(favorites)}):**\n\n"

        for i, fav in enumerate(favorites, 1):
            text += f"{i}. **{fav['hotel_name']}**\n"
            text += f"   📍 {fav['city']}, {fav['country']}\n"
            text += f"   💰 от {fav['price']:,} ₽\n"
            text += f"   📅 {fav['start_date']} ({fav['nights']} ночей)\n\n"

        text += "\n_Выберите тур для просмотра или удаления:_"

        # Создаем клавиатуру со списком
        keyboard = create_favorites_list_keyboard(favorites)

        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

        logger.info(f"Пользователь {user_id} просмотрел {len(favorites)} избранных")

    except Exception as e:
        logger.error(f"Ошибка отображения избранного: {e}", exc_info=True)
        await message.answer("😔 Произошла ошибка при загрузке заметок")


@router.callback_query(F.data.startswith("view_favorite_"))
async def view_favorite_tour(callback: CallbackQuery, state: FSMContext):
    """Просмотреть детали избранного тура"""
    favorite_id_str = callback.data.replace("view_favorite_", "")
    favorite_id = int(favorite_id_str)

    await callback.answer("⏳ Загружаю информацию...")

    try:
        favorites = await get_user_favorites(callback.from_user.id)

        # Находим нужный тур
        tour = None
        for fav in favorites:
            if fav['id'] == favorite_id:
                tour = fav
                break

        if not tour:
            await callback.message.answer("❌ Тур не найден")
            return

        # Парсим JSON-строку в словарь
        import json
        tour_data = json.loads(tour['tour_data']) if isinstance(tour['tour_data'], str) else tour['tour_data']

        # Формируем подробное описание
        text = f"🏨 **{tour['hotel_name']}**\n\n"
        text += f"⭐ Звезд: {tour_data.get('stars', 'N/A')}\n"
        text += f"📊 Рейтинг: {tour_data.get('rating', 'N/A')}/10\n"
        text += f"📍 {tour['city']}, {tour['country']}\n"
        text += f"💰 Цена: от {tour['price']:,} ₽\n"
        text += f"_Цены актуальны на момент подбора и могут меняться_\n"
        text += f"🌙 Ночей: {tour['nights']}\n"
        text += f"📅 Дата: {tour['start_date']}\n"
        text += f"🍽️ Питание: {tour_data.get('meal_description', 'N/A')}\n"

        if tour_data.get('description'):
            text += f"\n📝 {tour_data['description'][:300]}..."

        # Кнопки действий
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from urllib.parse import quote

        # Генерируем ссылку для бронирования
        level_url = f"https://level.travel/package_details/{tour['tour_id']}?hotel_id={tour['hotel_id']}&request_id={tour['request_id']}"
        encoded_url = quote(level_url, safe='')
        booking_url = (
            f"https://tp.media/r?"
            f"marker=624775&trs=409439&p=660&"
            f"u={encoded_url}&campaign_id=26"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Перейти на сайт", url=booking_url)],
            [InlineKeyboardButton(text="🗑️ Удалить из заметок", callback_data=f"delete_favorite_{favorite_id}")],
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_favorites")]
        ])

        await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка просмотра избранного тура: {e}", exc_info=True)
        await callback.message.answer("😔 Ошибка загрузки информации")


@router.callback_query(F.data.startswith("delete_favorite_"))
async def delete_favorite_tour(callback: CallbackQuery, state: FSMContext):
    """Удалить тур из избранного"""
    favorite_id_str = callback.data.replace("delete_favorite_", "")
    favorite_id = int(favorite_id_str)

    try:
        success = await remove_from_favorites(callback.from_user.id, favorite_id)

        if success:
            await callback.answer("✅ Тур удален из заметок", show_alert=True)
            # Возвращаемся к списку
            await show_favorites(callback.message, state, user_id=callback.from_user.id)
        else:
            await callback.answer("❌ Не удалось удалить", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка удаления из избранного: {e}", exc_info=True)
        await callback.answer("❌ Ошибка удаления", show_alert=True)


@router.callback_query(F.data == "back_to_favorites")
async def back_to_favorites_list(callback: CallbackQuery, state: FSMContext):
    """Вернуться к списку избранного"""
    await show_favorites(callback.message, state, user_id=callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "clear_all_favorites")
async def confirm_clear_favorites(callback: CallbackQuery):
    """Подтверждение очистки всех заметок"""
    count = await get_favorites_count(callback.from_user.id)

    if count == 0:
        await callback.answer("У вас нет сохраненных туров", show_alert=True)
        return

    text = f"⚠️ **Подтверждение**\n\nВы уверены, что хотите удалить все {count} туров из заметок?"
    keyboard = confirm_clear_keyboard()

    await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "confirm_clear_yes")
async def clear_all_favorites_confirmed(callback: CallbackQuery, state: FSMContext):
    """Очистить все избранное (подтверждено)"""
    try:
        count = await clear_user_favorites(callback.from_user.id)

        await callback.answer(f"✅ Удалено {count} туров", show_alert=True)
        await show_favorites(callback.message, state, user_id=callback.from_user.id)

        logger.info(f"Пользователь {callback.from_user.id} очистил {count} избранных")

    except Exception as e:
        logger.error(f"Ошибка очистки избранного: {e}", exc_info=True)
        await callback.answer("❌ Ошибка очистки", show_alert=True)


@router.callback_query(F.data == "confirm_clear_no")
async def cancel_clear_favorites(callback: CallbackQuery, state: FSMContext):
    """Отменить очистку"""
    await callback.answer("❌ Отменено")
    await show_favorites(callback.message, state, user_id=callback.from_user.id)
