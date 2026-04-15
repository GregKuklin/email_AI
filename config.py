import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
import json

# Загружаем переменные окружения
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')

# API ключ Travelata
TRAVELATA_API_KEY = os.getenv('TRAVELATA_API_KEY')

# API ключ Level.Travel
LEVELTRAVEL_API_KEY = os.getenv('LEVELTRAVEL_API_KEY')

# OpenAI API ключ
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials/tourbot-462221-a9249ad037bc.json', scope)
client = gspread.authorize(creds)
sheet = client.open('Tourbot').sheet1
logs_sheet = client.open('Tourbot').worksheet('Bot_logs')
application_sheet = client.open('Tourbot').worksheet('Users_Applications')

# Кастомный обработчик для логирования в Google Sheets
class GoogleSheetsHandler(logging.Handler):
    def __init__(self, sheet):
        super().__init__()
        self.sheet = sheet
        
    def emit(self, record):
        try:
            # Форматируем запись лога
            log_entry = self.format(record)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Добавляем строку в Google Sheets
            self.sheet.append_row([
                timestamp,
                record.levelname,
                record.name,
                record.getMessage()
            ])
        except Exception as e:
            # Если не удалось записать в Google Sheets, игнорируем ошибку
            # чтобы не нарушить работу основного приложения
            pass

# Функция для настройки логирования
def setup_logging():
    # Создаем форматтер
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Создаем обработчик для файла
    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Создаем обработчик для Google Sheets
    sheets_handler = GoogleSheetsHandler(logs_sheet)
    sheets_handler.setFormatter(formatter)
    
    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(sheets_handler)
    
    return root_logger

# Функции для работы с заявками пользователей
class UserApplicationManager:
    @staticmethod
    def save_application(user_id: int, user_data: dict, stage: str, action: str = None):
        """Сохранение заявки пользователя в Google Sheets"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Извлекаем данные из user_data
            country = user_data.get('country', 'не указано')
            departure_city = user_data.get('departure_city', 'не указано')
            dates = f"{user_data.get('user_departure_date', 'не указано')} - {user_data.get('user_return_date', 'не указано')}"
            adults = user_data.get('adults', 'не указано')
            kids = user_data.get('kids', 'не указано')
            budget = user_data.get('ai_params', {}).get('budget', 'не указано')
            preferences = user_data.get('ai_params', {}).get('preferences', 'не указано')
            original_input = user_data.get('original_input', 'не указано')
            
            # Подсчитываем стоимость найденных туров
            tours = user_data.get('tours', [])
            min_price = 'не найдено'
            max_price = 'не найдено'
            tours_count = len(tours)
            
            if tours:
                prices = []
                for tour in tours:
                    if 'price' in tour and tour['price']:
                        try:
                            price = float(tour['price'])
                            prices.append(price)
                        except:
                            pass
                
                if prices:
                    min_price = min(prices)
                    max_price = max(prices)
            
            # Сохраняем в Google Sheets
            application_sheet.append_row([
                timestamp,
                user_id,
                country,
                departure_city,
                dates,
                f"{adults} взр., {kids} дет.",
                budget,
                preferences,
                stage,
                action or 'просмотр',
                tours_count,
                min_price,
                max_price,
                original_input
            ])
            
        except Exception as e:
            logging.error(f"Ошибка при сохранении заявки: {e}")
    
    @staticmethod
    def get_user_history(user_id: int, limit: int = 5):
        """Получение истории заявок пользователя"""
        try:
            # Получаем все записи
            records = application_sheet.get_all_records()
            
            # Фильтруем по user_id и берем последние записи
            user_records = [r for r in records if str(r.get('user_id', '')) == str(user_id)]
            user_records = sorted(user_records, key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return user_records[:limit]
            
        except Exception as e:
            logging.error(f"Ошибка при получении истории пользователя: {e}")
            return []
    
    @staticmethod
    def restore_user_context(user_id: int):
        """Восстановление контекста последней заявки пользователя"""
        try:
            history = UserApplicationManager.get_user_history(user_id, 1)
            if history:
                last_record = history[0]
                return {
                    'country': last_record.get('country', ''),
                    'departure_city': last_record.get('departure_city', ''),
                    'dates': last_record.get('dates', ''),
                    'people': last_record.get('people_count', ''),
                    'budget': last_record.get('budget', ''),
                    'preferences': last_record.get('preferences', ''),
                    'original_input': last_record.get('original_input', '')
                }
            return None
        except Exception as e:
            logging.error(f"Ошибка при восстановлении контекста: {e}")