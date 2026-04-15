import openai
from config import OPENAI_API_KEY
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY не найден в переменных окружения")
            raise ValueError("OPENAI_API_KEY не настроен")
        
        logger.info(f"Инициализация OpenAI клиента с ключом: {OPENAI_API_KEY[:10]}...")
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    async def get_travel_inspiration(self, category: str) -> str:
        """Получить рекомендации по путешествиям от ChatGPT-4"""
        
        prompts = {
            "sea": "Порекомендуй 5 лучших морских курортов и направлений для пляжного отдыха. Включи страны, города и краткое описание каждого места. Ответ должен быть на русском языке и не более 500 символов.",
            "city": "Порекомендуй 5 лучших городов мира для городского туризма и прогулок. Включи страны, города и краткое описание достопримечательностей. Ответ должен быть на русском языке и не более 500 символов.",
            "nature": "Порекомендуй 5 лучших направлений для активного отдыха на природе и в горах. Включи страны, регионы и виды активностей. Ответ должен быть на русском языке и не более 500 символов.",
            "beauty": "Порекомендуй 5 самых красивых и роскошных курортов мира для элитного отдыха. Включи страны, отели и особенности. Ответ должен быть на русском языке и не более 500 символов.",
            "calm": "Порекомендуй 5 лучших мест для спокойного отдыха и релаксации. Включи страны, курорты и виды отдыха для восстановления сил. Ответ должен быть на русском языке и не более 500 символов."
        }
        
        try:
            prompt = prompts.get(category, prompts["sea"])
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты эксперт по туризму и путешествиям. Давай краткие, но информативные рекомендации."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при обращении к OpenAI: {e}")
            return self._get_fallback_recommendation(category)
    
    def _get_fallback_recommendation(self, category: str) -> str:
        """Резервные рекомендации на случай ошибки API"""
        fallbacks = {
            "sea": "🏖️ Рекомендуемые морские направления:\n\n🇹🇷 Турция - Анталья, Кемер\n🇪🇬 Египет - Хургада, Шарм-эль-Шейх\n🇬🇷 Греция - Крит, Родос\n🇪🇸 Испания - Коста-дель-Соль\n🇹🇭 Таиланд - Пхукет, Паттайя",
            "city": "🏛️ Лучшие города для путешествий:\n\n🇮🇹 Рим - Колизей, Ватикан\n🇫🇷 Париж - Эйфелева башня, Лувр\n🇬🇧 Лондон - Биг-Бен, Тауэр\n🇪🇸 Барселона - Саграда Фамилия\n🇨🇿 Прага - Карлов мост",
            "nature": "🏔️ Активный отдых на природе:\n\n🇦🇹 Австрия - Альпы, горнолыжные курорты\n🇨🇭 Швейцария - треккинг, альпинизм\n🇳🇴 Норвегия - фьорды, северное сияние\n🇳🇿 Новая Зеландия - экстремальный спорт\n🇨🇦 Канада - национальные парки",
            "beauty": "✨ Роскошные курорты:\n\n🇲🇻 Мальдивы - водные виллы\n🇸🇨 Сейшелы - эксклюзивные отели\n🇫🇷 Французская Ривьера - Канны, Ницца\n🇮🇹 Амальфитанское побережье\n🇬🇷 Санторини - романтические закаты",
            "calm": "🧘 Места для релаксации:\n\n🇮🇩 Бали - спа-курорты, йога\n🇱🇰 Шри-Ланка - аюрведа\n🇮🇳 Гоа - медитация на пляже\n🇯🇵 Япония - онсэны (горячие источники)\n🇮🇸 Исландия - геотермальные источники"
        }
        return fallbacks.get(category, fallbacks["sea"])
    
    async def analyze_tour_params(self, user_input: str) -> dict:
        """
        Анализ параметров тура через ChatGPT-4.
        Извлекает: страну, город назначения, даты, количество человек, бюджет, удобства.

        Returns:
            dict с ключами: country, to_city, from_city, start_date, nights, adults, kids,
                           kids_ages, min_budget, max_budget, amenities
        """
        
        # Определяем текущую дату и разумную дату вылета
        from datetime import datetime, timedelta
        today = datetime.now()
        future_date = today + timedelta(days=30)  # через месяц по умолчанию
        current_year = today.year
        next_year = current_year + 1 if today.month >= 10 else current_year
        
        prompt = f"""
Ты помощник по анализу туристических запросов. Проанализируй запрос и извлеки параметры.

ВАЖНО: Сегодня {today.strftime('%d.%m.%Y')}. ВСЕ ДАТЫ ДОЛЖНЫ БЫТЬ В БУДУЩЕМ!

Запрос: "{user_input}"

Извлеки максимум информации:
1. Страна/направление (ISO2 код если можешь: TR-Турция, EG-Египет, AE-ОАЭ, TH-Таиланд, GR-Греция, ES-Испания)
2. Город назначения (если указан конкретный город/курорт, на английском):
   - Турция: Antalya, Kemer, Alanya, Side, Belek, Bodrum, Marmaris, Istanbul
   - Египет: Sharm el-Sheikh, Hurghada, Marsa Alam, Taba
   - ОАЭ: Dubai, Abu Dhabi, Sharjah, Ras Al Khaimah
   - Таиланд: Phuket, Pattaya, Koh Samui, Krabi, Bangkok
   - Греция: Athens, Crete, Rhodes, Corfu
3. Город вылета (если указан, на английском: Moscow, Saint Petersburg, Kazan, и т.д.)
4. Дату вылета в формате ДД.ММ.ГГГГ (ОБЯЗАТЕЛЬНО В БУДУЩЕМ! Если не указана явно - используй {future_date.strftime('%d.%m.%Y')})
5. Количество ночей (число или диапазон типа "7..9", если не указано - используй 7)
6. Количество взрослых (число, если не указано - используй 2)
7. Количество детей (число, если не указано - 0)
8. Возраста детей (массив чисел)
9. Минимальный бюджет (число)
10. Максимальный бюджет (число)
11. Удобства отеля: бассейн→pool, спа→spa, wifi→wifi, бар→bar, детский клуб→kids_club, аквапарк→aquapark

ВАЖНЫЕ ПРАВИЛА:
- Если дата не указана явно - используй {future_date.strftime('%d.%m.%Y')}
- Если указан только месяц (например "август") - используй год {next_year}
- Если дата в прошлом - сдвинь на год вперед
- Если параметр не найден - возвращай разумное значение по умолчанию (adults=2, kids=0, nights=7)
- Если указан город назначения - обязательно укажи его на АНГЛИЙСКОМ языке

Примеры извлечения города:
- "Хочу в Кемер" → to_city="Kemer"
- "Турция, Анталия" → country="TR", to_city="Antalya"
- "Поездка в Шарм" → country="EG", to_city="Sharm el-Sheikh"
- "Турция в августе" → country="TR", to_city=null (город не указан)

Ответь СТРОГО в JSON формате (без комментариев):
{{
    "country": "TR" или null,
    "to_city": "Kemer" или null,
    "from_city": "Moscow" или null,
    "start_date": "{future_date.strftime('%d.%m.%Y')}",
    "nights": 7,
    "adults": 2,
    "kids": 0,
    "kids_ages": [],
    "min_budget": число или null,
    "max_budget": число или null,
    "amenities": []
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты эксперт по анализу туристических запросов. Отвечай ТОЛЬКО JSON без дополнительного текста."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.2
            )
            
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"AI ответ: {ai_response[:200]}...")
            
            # Парсим JSON
            import json
            # Убираем возможные markdown блоки
            if ai_response.startswith('```'):
                ai_response = ai_response.split('```')[1]
                if ai_response.startswith('json'):
                    ai_response = ai_response[4:]
            
            result = json.loads(ai_response)
            
            # Валидация и исправление даты с помощью helpers
            from datetime import datetime, timedelta
            from utils.helpers import get_min_date, get_max_date
            
            min_date = get_min_date()
            max_date = get_max_date()
            default_date = datetime.now() + timedelta(days=30)
            
            if result.get('start_date'):
                try:
                    date_obj = datetime.strptime(result['start_date'], '%d.%m.%Y')
                    
                    # Дата в прошлом или сегодня
                    if date_obj < min_date:
                        # Пытаемся исправить год (возможно ChatGPT ошибся с годом)
                        if date_obj.month >= datetime.now().month:
                            date_obj = date_obj.replace(year=datetime.now().year)
                        else:
                            date_obj = date_obj.replace(year=datetime.now().year + 1)
                        
                        # Проверяем снова
                        if date_obj < min_date:
                            date_obj = default_date
                        
                        result['start_date'] = date_obj.strftime('%d.%m.%Y')
                        logger.warning(f"ChatGPT вернул дату в прошлом, исправлено на: {result['start_date']}")
                    
                    # Дата слишком далеко в будущем
                    elif date_obj > max_date:
                        date_obj = default_date
                        result['start_date'] = date_obj.strftime('%d.%m.%Y')
                        logger.warning(f"ChatGPT вернул слишком далекую дату, исправлено на: {result['start_date']}")
                    
                except ValueError:
                    logger.error(f"Некорректный формат даты от ChatGPT: {result['start_date']}")
                    result['start_date'] = default_date.strftime('%d.%m.%Y')
            else:
                # Если даты нет - ставим через месяц
                result['start_date'] = default_date.strftime('%d.%m.%Y')
                logger.info(f"ChatGPT не вернул дату, установлена по умолчанию: {result['start_date']}")
            
            # Проверяем обязательные числовые поля
            if result.get('adults') is None or result.get('adults') < 1:
                result['adults'] = 2
            if result.get('kids') is None:
                result['kids'] = 0
            if result.get('nights') is None:
                result['nights'] = 7
            
            logger.info(f"Распознанные параметры: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от AI: {e}, ответ: {ai_response}")
            return self._fallback_parse(user_input)
        except Exception as e:
            logger.error(f"Ошибка при анализе параметров через OpenAI: {e}", exc_info=True)
            return self._fallback_parse(user_input)
    
    def _parse_ai_response(self, ai_response: str, original_input: str) -> dict:
        """Парсинг ответа от AI"""
        try:
            lines = ai_response.split('\n')
            params = {}
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if 'страна' in key:
                        params['country'] = value if value != "не указано" else None
                    elif 'дат' in key:
                        params['dates'] = value if value != "не указано" else None
                    elif 'люд' in key or 'человек' in key:
                        params['people_count'] = value if value != "не указано" else None
                    elif 'бюджет' in key:
                        params['budget'] = value if value != "не указано" else None
                    elif 'рейтинг' in key:
                        params['rating'] = value if value != "не указано" else None
                    elif 'пожелан' in key:
                        params['preferences'] = value if value != "не указано" else original_input
            
            # Если пожелания не извлечены, используем весь исходный текст
            if 'preferences' not in params:
                params['preferences'] = original_input
                
            return params
            
        except Exception as e:
            logger.error(f"Ошибка парсинга ответа AI: {e}")
            return self._fallback_parse(original_input)
    
    def _fallback_parse(self, user_input: str) -> dict:
        """Резервный парсинг без AI"""
        return {
            'country': None,
            'dates': None,
            'people_count': None,
            'budget': None,
            'rating': None,
            'preferences': user_input
        }

    async def get_navia_response_with_context(self, user_message: str, chat_history: list) -> str:
        """Получить ответ от Navia с учетом контекста диалога"""
        
        # Обновленный промпт для Navia
        navia_prompt = (
            "Ты — доброжелательный тревел-ассистент по имени Navia. "
            "Ты общаешься так, будто ты настоящий человек — тепло, с эмпатией и профессионализмом. "
            "Ты отвечаешь только по теме путешествий и отдыха. "
            "Если пользователь пишет что-то не по теме, мягко перенаправь его на тревел-запросы. "
            "Ты умеешь анализировать сообщения и понимать, какие данные (даты, количество, бюджет и т.п.) уже есть, и какие ещё нужно уточнить. "
            "❗️Очень важно: пиши структурированно, дели текст на абзацы по смыслу, используй эмодзи там, где это естественно. "
            "Не пиши сплошным блоком. Сделай так, чтобы пользователю было удобно читать, как будто с ним общается живой тревел-эксперт.\n\n"
            "Также учитывай контекст из функции 'Получить вдохновение' - ты можешь рекомендовать направления по категориям: "
            "морской отдых, городской туризм, природа и активности, красивые места, спокойный отдых.\n\n"
            "🎯 ВАЖНО: Если пользователь хочет перейти непосредственно к подбору тура или просит найти конкретные туры, "
            "обязательно напомни ему, что для этого нужно нажать на кнопку 'Найти тур' в меню. "
            "Объясни, что там он сможет указать все параметры и получить актуальные предложения.\n\n"
            "📋 КОНТЕКСТ ТУРА:\n"
            "Если в сообщении присутствует ДЕТАЛЬНАЯ информация об отеле "
            "(название, категория, описание, расположение, типы номеров с удобствами, "
            "площадь, вместимость, варианты питания с ценами), используй её для точных ответов.\n\n"
            "Ты можешь отвечать на вопросы:\n"
            "• Об удобствах номеров (кондиционер, балкон, сейф, ванна, площадь, вид из окна)\n"
            "• О расположении отеля (расстояние до пляжа/аэропорта, линия пляжа, тип пляжа)\n"
            "• О питании (какие типы доступны, что включено в цену, доплата за улучшение)\n"
            "• О соотношении цена/качество на основе характеристик\n"
            "• О подходящих типах номеров для разного состава туристов\n"
            "• О мгновенном подтверждении бронирования (если доступно)\n\n"
            "⚠️ КРИТИЧНО: Отвечай ТОЛЬКО на основе предоставленной информации. "
            "Если конкретная информация не указана (например, нет данных об удобствах), "
            "честно скажи 'эту информацию лучше уточнить через кнопку Забронировать', "
            "но НЕ придумывай факты и НЕ угадывай."
        )
        
        try:
            # Формируем сообщения для API с учетом истории
            messages = [{"role": "system", "content": navia_prompt}]
            
            # Добавляем историю диалога
            messages.extend(chat_history)
            
            logger.info(f"Отправляем запрос к OpenAI API с {len(messages)} сообщениями")
            logger.debug(f"Последнее сообщение пользователя: {user_message[:100]}...")
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=800,
                temperature=0.8
            )
            
            logger.info("Успешно получен ответ от OpenAI API")
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка при обращении к OpenAI для Navia с контекстом: {e}", exc_info=True)
            logger.error(f"Контекст сообщения: {user_message[:200]}...")
            logger.error(f"История чата: {len(chat_history)} сообщений")
            return self._get_fallback_navia_response(user_message)
    
    # Оставляем старый метод для совместимости
    async def get_navia_response(self, user_message: str) -> str:
        """Получить ответ от Navia - тревел-ассистента (без контекста)"""
        return await self.get_navia_response_with_context(user_message, [])

    def _get_fallback_navia_response(self, user_message: str) -> str:
        """Резервный ответ Navia на случай ошибки API"""
        return (
            "🌟 Привет! Я Navia, ваш персональный тревел-ассистент! ✈️\n\n"
            "К сожалению, сейчас у меня небольшие технические трудности, но я всё равно готова помочь! 😊\n\n"
            "💡 Расскажите мне:\n"
            "• Куда хотите поехать?\n"
            "• Когда планируете путешествие?\n"
            "• Какой у вас бюджет?\n"
            "• Что больше всего интересует в поездке?\n\n"
            "🎯 Для подбора конкретных туров нажмите кнопку 'Найти тур' в меню! Там вы сможете указать все параметры и получить актуальные предложения.\n\n"
            "Или воспользуйтесь другими кнопками меню для быстрого доступа к функциям! 🎯"
        )

    async def get_completion(self, prompt: str, temperature: float = 0.5) -> str:
        """
        Получить простое завершение от OpenAI для заданного промпта

        Args:
            prompt: Текст промпта для GPT-4
            temperature: Температура для генерации (0.0-1.0).
                        0.0 = детерминированный, 1.0 = креативный.
                        По умолчанию 0.5 (сбалансированно)

        Returns:
            Ответ от GPT-4
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=700,  # Увеличено с 500 для более детальных ответов
                temperature=temperature
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Ошибка при получении completion от OpenAI: {e}")
            raise e

    async def generate_hotel_description(self, hotel_data: dict) -> str:
        """
        Генерировать краткое описание отеля (4-5 предложений).

        Args:
            hotel_data: {hotel_name, stars, rating, city, region, features, meal_description, price}

        Returns:
            Описание отеля из 4-5 предложений
        """
        hotel_name = hotel_data.get('hotel_name', 'Отель')
        stars = hotel_data.get('stars', 0)
        rating = hotel_data.get('rating', 0)
        city = hotel_data.get('city', '')
        region = hotel_data.get('region', '')
        features = hotel_data.get('features', {})
        meal_type = hotel_data.get('meal_description', '')
        price = hotel_data.get('price', 0)

        # Формируем строку с рейтингом только если он есть
        rating_text = ""
        if rating and rating > 0:
            rating_text = f", рейтинг {rating}/10"

        prompt = f"""
Ты - эксперт по туризму. Напиши краткое привлекательное описание отеля (4-5 предложений).

Данные:
- {hotel_name}, {stars}⭐{rating_text}
- {city}, {region}
- Питание: {meal_type}
- Цена от: {price:,} ₽
"""

        if features:
            prompt += "\nОсобенности:\n"
            if features.get('beach_distance'):
                prompt += f"- До пляжа: {features['beach_distance']}м\n"
            if features.get('line'):
                prompt += f"- {features['line']}-я линия\n"
            if features.get('wi_fi'):
                prompt += f"- Wi-Fi: {features['wi_fi']}\n"

        # Формируем список акцентов в зависимости от наличия рейтинга
        accents = "расположение, цена, комфорт, удобства"
        if rating and rating > 0:
            accents = "расположение, цена, комфорт, рейтинг, удобства"

        prompt += f"""

ВАЖНЫЕ ПРАВИЛА:
1. Используй ТОЛЬКО факты из предоставленных данных - НЕ придумывай информацию
2. Если удобство не указано в списке особенностей - НЕ упоминай его
3. Каждое описание должно быть уникальным по структуре и стилю
4. Варьируй акценты: {accents}
5. Формулировки питания:
   - "без питания" → "питание не включено"
   - "завтрак" → "включён завтрак"
   - "полупансион" → "включён полупансион"
   - "все включено" → "работает по системе всё включено"
6. Избегай штампов и клише - будь креативным

Пиши на русском, 4-5 предложений, без эмодзи, естественно и разнообразно."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты - эксперт по описаниям отелей. Пишешь точно, креативно и разнообразно. Используешь только факты из данных."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.9
            )

            description = response.choices[0].message.content.strip()
            logger.info(f"Сгенерировано описание для {hotel_name}")
            return description

        except Exception as e:
            logger.error(f"Ошибка генерации описания: {e}")

            # Форматируем тип питания для fallback
            meal_formatted = meal_type.lower()
            if "без питания" in meal_formatted or meal_formatted == "ro":
                meal_text = "питание не включено"
            elif "завтрак" in meal_formatted or meal_formatted == "bb":
                meal_text = "включён завтрак"
            elif "полупансион" in meal_formatted or meal_formatted == "hb":
                meal_text = "включён полупансион"
            elif "все включено" in meal_formatted or "all inclusive" in meal_formatted or meal_formatted == "ai":
                meal_text = "работает по системе всё включено"
            elif "полный пансион" in meal_formatted or meal_formatted == "fb":
                meal_text = "включён полный пансион"
            else:
                meal_text = f"тип питания: {meal_type}"

            # Fallback описание - не упоминаем рейтинг если он None или 0
            if rating and rating > 0:
                return (
                    f"{hotel_name} ({stars}⭐) - отличный выбор для отдыха в {city}. "
                    f"Отель имеет рейтинг {rating}/10, {meal_text}. "
                    f"Идеальное место для комфортного отпуска."
                )
            else:
                return (
                    f"{hotel_name} ({stars}⭐) - отличный выбор для отдыха в {city}. "
                    f"В отеле {meal_text}. "
                    f"Идеальное место для комфортного отпуска."
                )

    async def extract_amenities(self, user_text: str) -> list:
        """
        Извлечь упоминания удобств из текста пользователя
        
        Args:
            user_text: Текст с предпочтениями пользователя
        
        Returns:
            Список кодов удобств ['pool', 'spa', 'gym']
        
        Поддерживаемые удобства:
        - pool (бассейн)
        - spa (спа, массаж)
        - gym (тренажерный зал, фитнес)
        - wifi (вай-фай, интернет)
        - parking (парковка)
        - kids_club (детская площадка, детский клуб)
        - animation (анимация, развлечения)
        - beach_line (пляж, первая линия)
        - restaurant (ресторан)
        - bar (бар)
        """
        
        prompt = f"""
Проанализируй запрос пользователя о туре и извлеки упоминания удобств отеля.

Запрос: "{user_text}"

Список доступных удобств:
- pool: бассейн, плавать, pool
- spa: спа, массаж, сауна, баня, spa
- gym: тренажерный зал, фитнес, спортзал, gym
- wifi: вай-фай, интернет, wi-fi, wifi
- parking: парковка, место для машины, parking
- kids_club: детская площадка, детский клуб, анимация для детей
- animation: анимация, развлечения, шоу, программа
- beach_line: пляж, первая линия, у моря, beach
- restaurant: ресторан, питание, restaurant
- bar: бар, напитки, bar

ВАЖНО:
- Извлекай только явные упоминания удобств
- Если пользователь пишет "бассейн", добавь "pool"
- Если пользователь пишет "spa" или "массаж", добавь "spa"
- Не добавляй удобства, если их нет в запросе

Ответь ТОЛЬКО в формате JSON списка (без дополнительного текста):
["pool", "spa"]

Если ничего не найдено, верни пустой список: []
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты эксперт по анализу запросов о турах. Извлекай только явные упоминания удобств. Отвечай ТОЛЬКО JSON списком."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            
            # Парсим JSON
            import json
            amenities = json.loads(result)
            
            # Валидация: оставляем только известные коды
            valid_amenities_codes = [
                'pool', 'spa', 'gym', 'wifi', 'parking', 
                'kids_club', 'animation', 'beach_line', 'restaurant', 'bar'
            ]
            
            filtered_amenities = [
                a for a in amenities 
                if a in valid_amenities_codes
            ]
            
            logger.info(f"Извлеченные удобства из '{user_text[:50]}...': {filtered_amenities}")
            return filtered_amenities
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON ответа GPT: {e}, ответ: {result}")
            return []
        except Exception as e:
            logger.error(f"Ошибка извлечения удобств: {e}")
            return []

    async def analyze_hotel_rating(self, rating_text: str) -> dict:
        """Анализ рейтинга отеля через ChatGPT-4"""
        
        prompt = f"""
        Пользователь ответил на вопрос о желаемом рейтинге отеля: "{rating_text}"
        
        Проанализируй ответ и определи параметр hotelCategory для API запроса.
        
        Возможные значения hotelCategory:
        - 1: отели от 1 звезды и выше (1, 2, 3, 4, 5 звезд)
        - 2: отели от 2 звезд и выше (2, 3, 4, 5 звезд)  
        - 3: отели от 3 звезд и выше (3, 4, 5 звезд)
        - 4: отели от 4 звезд и выше (4, 5 звезд)
        - 5: отели от 5 звезд (только 5 звезд)
        - null: любая категория (если пользователь не указал предпочтения)
        
        Правила обработки:
        - "от 1 звезды", "1+ звезд", "от одной звезды", "от 1 звезд" -> 1
        - "от 2 звезд", "2+ звезд", "от двух звезд" -> 2
        - "от 3 звезд", "3+ звезд", "от трех звезд", "от 3-х звезд" -> 3
        - "от 4 звезд", "4+ звезд", "от четырех звезд", "от 4-х звезд" -> 4
        - "от 5 звезд", "5+ звезд", "от пяти звезд", "от 5-ти звезд" -> 5
        - "1 звезда", "эконом", "бюджетный" -> 1
        - "2 звезды" -> 2
        - "3 звезды", "стандарт", "средний" -> 3
        - "4 звезды", "хороший", "комфорт" -> 4
        - "5 звезд", "люкс", "премиум", "лучший" -> 5
        - "нет предпочтений", "любой", "не важно", "все равно" -> null
        
        ВАЖНО: Если пользователь указывает "от X звезд", это означает поиск отелей от X звезд и выше!
        
        Ответь ТОЛЬКО в формате JSON:
        {{
            "hotelCategory": число_или_null,
            "description": "краткое_описание_для_пользователя"
        }}
        
        Примеры:
        - "от 1 звезды" -> {{"hotelCategory": 1, "description": "отели от 1 звезды и выше"}}
        - "от 3 звезд" -> {{"hotelCategory": 3, "description": "отели от 3 звезд и выше"}}
        - "5 звезд" -> {{"hotelCategory": 5, "description": "отели 5 звезд"}}
        - "4 звезды" -> {{"hotelCategory": 4, "description": "отели от 4 звезд и выше"}}
        - "3 звезды" -> {{"hotelCategory": 3, "description": "отели от 3 звезд и выше"}}
        - "бюджетный" -> {{"hotelCategory": 1, "description": "отели от 1 звезды и выше"}}
        - "не важно" -> {{"hotelCategory": null, "description": "любая категория"}}
        """
        
        try:
            rating_response = await self.get_completion(prompt)
            
            # Парсим JSON ответ
            import json
            try:
                rating_data = json.loads(rating_response)
                hotel_category = rating_data.get('hotelCategory')
                rating_description = rating_data.get('description', 'обработано')
                
                return {
                    'hotelCategory': hotel_category,
                    'description': rating_description
                }
                
            except json.JSONDecodeError:
                # Если не удалось распарсить JSON, возвращаем значения по умолчанию
                return {
                    'hotelCategory': None,
                    'description': 'любая категория'
                }
                
        except Exception as e:
            logger.error(f"Ошибка при обработке рейтинга через OpenAI: {e}")
            # В случае ошибки возвращаем базовые данные
            return {
                'hotelCategory': None,
                'description': 'любая категория'
            }
    
    async def update_tour_params_with_context(
        self, 
        previous_params: dict, 
        user_message: str
    ) -> dict:
        """
        Обновить параметры тура с учетом контекста.
        
        Args:
            previous_params: Предыдущие распознанные параметры
            user_message: Новое сообщение пользователя (что изменить)
            
        Returns:
            dict: Обновленные параметры (все поля, обновленные + неизмененные)
            
        Example:
            previous_params = {'country': 'TR', 'adults': 2, 'max_budget': 80000}
            user_message = "изменить бюджет на 150к"
            result = {'country': 'TR', 'adults': 2, 'max_budget': 150000}
        """
        
        from datetime import datetime, timedelta
        import json
        
        today = datetime.now()
        future_date = today + timedelta(days=30)
        
        prompt = f"""
Ты - помощник по обновлению параметров туристического запроса.

У пользователя уже есть параметры тура:
{json.dumps(previous_params, ensure_ascii=False, indent=2)}

Пользователь хочет изменить:
"{user_message}"

ЗАДАЧА: Проанализируй ЧТО ИМЕННО пользователь хочет изменить и верни ПОЛНЫЙ набор параметров с учетом изменений.

ПРАВИЛА:
1. Если параметр НЕ упоминается в сообщении - оставь его БЕЗ ИЗМЕНЕНИЙ из previous_params
2. Если параметр упоминается - обнови его значение
3. Верни ВСЕ параметры (и обновленные, и неизмененные)

ПРИМЕРЫ:
• "изменить бюджет на 150к" → max_budget: 150000, остальное без изменений
• "добавить бассейн" → amenities: [...предыдущие..., "pool"], остальное без изменений
• "вместо Турции в Египет" → country: "EG", остальное без изменений
• "2 детей 5 и 7 лет" → kids: 2, kids_ages: [5, 7], остальное без изменений
• "убрать детей" → kids: 0, kids_ages: [], остальное без изменений
• "взрослых 3" → adults: 3, остальное без изменений

ФОРМАТ ОТВЕТА - СТРОГО JSON (без комментариев):
{{
    "country": "TR" или null,
    "from_city": "Moscow" или null,
    "start_date": "дата в формате ДД.ММ.ГГГГ",
    "nights": число или "7..9",
    "adults": число,
    "kids": число,
    "kids_ages": [массив возрастов],
    "min_budget": число или null,
    "max_budget": число или null,
    "amenities": [массив кодов удобств]
}}

Удобства: pool-бассейн, heated_pool-подогрев.бассейн, spa-спа, wifi-вайфай, bar-бар, 
kids_club-детский клуб, kids_pool-детский бассейн, aquapark-аквапарк, nanny-няня

ВАЖНО: Сегодня {today.strftime('%d.%m.%Y')}, все даты должны быть в будущем!
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты эксперт по обновлению параметров туристических запросов. Отвечай ТОЛЬКО JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.2
            )
            
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"AI контекстное обновление: {ai_response[:200]}...")
            
            # Убираем markdown блоки если есть
            if ai_response.startswith('```'):
                ai_response = ai_response.split('```')[1]
                if ai_response.startswith('json'):
                    ai_response = ai_response[4:]
            
            result = json.loads(ai_response)
            
            # Валидация даты
            from utils.helpers import get_min_date, get_max_date
            min_date = get_min_date()
            max_date = get_max_date()
            default_date = datetime.now() + timedelta(days=30)
            
            if result.get('start_date'):
                try:
                    date_obj = datetime.strptime(result['start_date'], '%d.%m.%Y')
                    if date_obj < min_date or date_obj > max_date:
                        logger.warning(f"Дата вне допустимого диапазона, используем дату по умолчанию")
                        result['start_date'] = default_date.strftime('%d.%m.%Y')
                except ValueError:
                    logger.warning(f"Неверный формат даты от AI: {result['start_date']}")
                    result['start_date'] = default_date.strftime('%d.%m.%Y')
            
            logger.info(f"Параметры обновлены контекстно: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON при контекстном обновлении: {e}, ответ: {ai_response}")
            # Возвращаем предыдущие параметры без изменений
            return previous_params
        except Exception as e:
            logger.error(f"Ошибка контекстного обновления параметров: {e}", exc_info=True)
            return previous_params

# В функции analyze_tour_params добавить в промпт:
# "- departure_city: город вылета (если указан)"