from config import UserApplicationManager
import logging

logger = logging.getLogger(__name__)

class UserContextService:
    @staticmethod
    async def save_search_request(user_id: int, state_data: dict, stage: str, action: str = None):
        """Сохранение поискового запроса пользователя"""
        try:
            UserApplicationManager.save_application(user_id, state_data, stage, action)
            logger.info(f"Сохранена заявка пользователя {user_id} на стадии {stage}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении заявки пользователя {user_id}: {e}")
    
    @staticmethod
    async def get_user_context_summary(user_id: int):
        """Получение краткой сводки по истории пользователя"""
        try:
            history = UserApplicationManager.get_user_history(user_id, 3)
            if not history:
                return "У вас пока нет истории поиска туров."
            
            summary = "📋 Ваши последние запросы:\n\n"
            for i, record in enumerate(history, 1):
                summary += f"{i}. {record.get('country', 'Не указано')} "
                summary += f"({record.get('dates', 'даты не указаны')})\n"
                summary += f"   Бюджет: {record.get('budget', 'не указан')}\n"
                if i < len(history):
                    summary += "\n"
            
            return summary
        except Exception as e:
            logger.error(f"Ошибка при получении сводки пользователя {user_id}: {e}")
            return "Не удалось загрузить историю запросов."
    
    @staticmethod
    async def restore_last_search(user_id: int):
        """Восстановление параметров последнего поиска"""
        try:
            context = UserApplicationManager.restore_user_context(user_id)
            if context:
                return {
                    'ai_params': {
                        'country': context.get('country', ''),
                        'dates': context.get('dates', ''),
                        'people_count': context.get('people', ''),
                        'budget': context.get('budget', ''),
                        'preferences': context.get('preferences', '')
                    },
                    'original_input': context.get('original_input', '')
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка при восстановлении поиска пользователя {user_id}: {e}")
            return None