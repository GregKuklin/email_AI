from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import aiohttp
import asyncio
from io import BytesIO
from typing import Optional
from datetime import datetime
import os

class PDFGenerator:
    def __init__(self):
        # Настраиваем шрифты с поддержкой кириллицы
        self._setup_fonts()
    
    def _setup_fonts(self):
        """Настройка шрифтов с поддержкой кириллицы"""
        try:
            # Путь к папке со шрифтами
            fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
            
            # Пути к файлам шрифтов DejaVu Sans
            dejavu_regular = os.path.join(fonts_dir, 'DejaVuSans.ttf')
            dejavu_bold = os.path.join(fonts_dir, 'DejaVuSans-Bold.ttf')
            
            # Проверяем наличие шрифтов DejaVu Sans
            if os.path.exists(dejavu_regular) and os.path.exists(dejavu_bold):
                # Регистрируем DejaVu шрифты
                pdfmetrics.registerFont(TTFont('DejaVuSans', dejavu_regular))
                pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', dejavu_bold))
                
                self.font_name = 'DejaVuSans'
                self.font_bold = 'DejaVuSans-Bold'
                print("Шрифты DejaVu Sans успешно зарегистрированы")
                return
            
            # Если DejaVu шрифты не найдены, пробуем системные шрифты Windows
            windows_fonts = {
                'Arial': 'C:/Windows/Fonts/arial.ttf',
                'Arial-Bold': 'C:/Windows/Fonts/arialbd.ttf'
            }
            
            fonts_registered = 0
            for font_name, font_path in windows_fonts.items():
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    fonts_registered += 1
            
            if fonts_registered == 2:
                self.font_name = 'Arial'
                self.font_bold = 'Arial-Bold'
                print("Используем системные шрифты Arial")
                return
            
            # Если ничего не найдено, используем стандартные шрифты
            raise Exception("Подходящие шрифты не найдены")
            
        except Exception as e:
            print(f"Ошибка при настройке шрифтов: {e}")
            # Fallback на стандартные шрифты
            self.font_name = 'Helvetica'
            self.font_bold = 'Helvetica-Bold'
            print("Используем стандартные шрифты Helvetica (без поддержки кириллицы)")
    
    async def generate_detailed_tour_pdf(self, hotel_card, rooms_data: dict, request_id: str):
        """
        Генерация подробного PDF с полной информацией о туре.
        
        Args:
            hotel_card: HotelCard с основной информацией
            rooms_data: Данные о номерах из hotel_rooms API
            request_id: ID поискового запроса
        
        Returns:
            BytesIO buffer с PDF файлом
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        
        # Создаем стили
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=self.font_bold,
            fontSize=18,
            spaceAfter=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a5490')
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontName=self.font_bold,
            fontSize=14,
            spaceAfter=10,
            textColor=colors.HexColor('#2c5f8d')
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            spaceAfter=10
        )
        
        # ============ СТРАНИЦА 1: ОБЩАЯ ИНФОРМАЦИЯ ============
        story.append(Paragraph(f"Предложение по туру", title_style))
        story.append(Paragraph(f"{hotel_card.hotel_name}", subtitle_style))
        story.append(Spacer(1, 15))
        
        # Основная информация об отеле
        hotel_info = [
            ["Параметр", "Значение"],
            ["Отель:", hotel_card.hotel_name],
            ["Категория:", f"{hotel_card.stars} звезд {hotel_card.format_stars()}"],
            ["Рейтинг:", f"{hotel_card.rating}/10"],
            ["Местоположение:", f"{hotel_card.region}, {hotel_card.city}"],
            ["Дата вылета:", hotel_card.start_date],
            ["Ночей:", str(hotel_card.nights)],
            ["Туроператор:", hotel_card.operator_name],
        ]
        
        # Особенности отеля
        if hotel_card.features.beach_distance:
            hotel_info.append(["Расстояние до пляжа:", f"{hotel_card.features.beach_distance}м"])
        if hotel_card.features.line:
            hotel_info.append(["Линия пляжа:", f"{hotel_card.features.line}-я"])
        if hotel_card.features.beach_type:
            hotel_info.append(["Тип пляжа:", hotel_card.features.beach_type])
        if hotel_card.features.wi_fi:
            hotel_info.append(["Wi-Fi:", hotel_card.features.wi_fi])
        
        table = Table(hotel_info, colWidths=[2.5*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#e8f0f7')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
            ('FONTNAME', (0, 1), (0, -1), self.font_bold),
            ('FONTNAME', (1, 1), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))

        # Предупреждение о ценах
        price_warning = Paragraph(
            "<i>Цены актуальны на момент подбора и могут меняться</i>",
            normal_style
        )
        story.append(price_warning)
        story.append(Spacer(1, 20))

        # ============ ДОСТУПНЫЕ НОМЕРА И ПИТАНИЕ ============
        story.append(Paragraph("Доступные номера и варианты питания", subtitle_style))
        story.append(Spacer(1, 10))
        
        if rooms_data and isinstance(rooms_data, list):
            for room in rooms_data[:3]:  # Показываем до 3 типов номеров
                room_info = room.get('room', {})
                meal_types = room.get('meal_types', [])
                
                # Название и описание номера
                room_name = room_info.get('name_ru', 'Стандартный номер')
                story.append(Paragraph(f"<b>{room_name}</b>", normal_style))
                
                # Детали номера
                room_details = []
                if room_info.get('area'):
                    room_details.append(f"Площадь: {room_info['area']}м²")
                if room_info.get('accommodation'):
                    room_details.append(f"Размещение: {room_info['accommodation']}")
                
                if room_details:
                    story.append(Paragraph(" • ".join(room_details), normal_style))
                
                # Описание номера
                if room_info.get('description'):
                    desc = room_info['description'][:300] + "..." if len(room_info.get('description', '')) > 300 else room_info.get('description', '')
                    story.append(Paragraph(desc, normal_style))
                
                # Удобства номера
                facilities = room_info.get('facilities', [])
                if facilities:
                    fac_names = [f['name'] for f in facilities[:8]]  # Показываем 8 удобств
                    fac_text = " • ".join(fac_names)
                    story.append(Paragraph(f"<b>Удобства:</b> {fac_text}", normal_style))
                
                # Таблица с ценами по типам питания
                if meal_types:
                    price_data = [["Тип питания", "Описание", "Цена"]]
                    for meal in meal_types[:4]:  # До 4 вариантов питания
                        meal_id = meal.get('id', '')
                        meal_desc = meal.get('description', '')
                        meal_price = meal.get('min_price', 0)
                        price_formatted = f"{meal_price:,}₽".replace(',', ' ')
                        price_data.append([meal_id, meal_desc, price_formatted])
                    
                    price_table = Table(price_data, colWidths=[1*inch, 2.5*inch, 1.5*inch])
                    price_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5f8d')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                        ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
                        ('FONTNAME', (0, 1), (-1, -1), self.font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                    ]))
                    story.append(price_table)
                
                story.append(Spacer(1, 15))
        else:
            # Если данных о номерах нет, показываем базовую информацию
            basic_info = [
                ["Тип питания", "Цена"],
                [f"{hotel_card.meal_type} - {hotel_card.meal_description}", f"{hotel_card.format_price()}₽"]
            ]
            basic_table = Table(basic_info, colWidths=[3*inch, 2*inch])
            basic_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5f8d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
                ('FONTNAME', (0, 1), (-1, -1), self.font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(basic_table)
            story.append(Spacer(1, 15))
        
        # ============ ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ============
        story.append(Paragraph("Дополнительная информация", subtitle_style))
        
        additional_info = Paragraph(
            f"<b>Доступность:</b> {hotel_card.availability}<br/>"
            f"<b>Мгновенное подтверждение:</b> {'Да' if hotel_card.instant_confirm else 'Нет'}<br/>"
            f"<b>Бонусные баллы:</b> {hotel_card.bonus_count} баллов<br/>",
            normal_style
        )
        story.append(additional_info)
        story.append(Spacer(1, 20))
        
        # ============ ССЫЛКА НА БРОНИРОВАНИЕ ============
        story.append(Paragraph("Бронирование", subtitle_style))
        booking_text = Paragraph(
            f"Для бронирования тура перейдите по ссылке:<br/>"
            f"<link href='{hotel_card.tour_link}'>{hotel_card.tour_link}</link><br/><br/>"
            f"<b>Важно:</b> Цены актуальны на момент создания PDF. "
            f"Для актуальной информации перейдите на сайт Level.Travel.",
            normal_style
        )
        story.append(booking_text)
        story.append(Spacer(1, 20))
        
        # ============ КОНТАКТЫ ============
        contact_info = Paragraph(
            f"<b>Контактная информация:</b><br/>"
            f"Сайт: https://tp.media/r?marker=624775&trs=409439&p=660&u=https%3A%2F%2Flevel.travel&campaign_id=26<br/>"
            f"Этот PDF создан автоматически ботом для подбора туров<br/>"
            f"Request ID: {request_id}",
            normal_style
        )
        story.append(contact_info)
        
        # Генерируем PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    async def generate_tour_pdf(self, tour_data, user_data):
        """Генерация PDF с информацией о туре (старый метод для совместимости)"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Создаем стили
        styles = getSampleStyleSheet()
        
        # Обновляем стили для использования выбранного шрифта
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=self.font_bold,
            fontSize=16,
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            spaceAfter=12
        )
        
        story = []
        
        # Заголовок
        story.append(Paragraph("Предложение по туру", title_style))
        story.append(Spacer(1, 20))
        
        # Форматируем дату
        checkin_date = tour_data.get('checkin_date', 'Не указано')
        if checkin_date and checkin_date != 'Не указано':
            try:
                date_obj = datetime.strptime(checkin_date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d.%m.%Y')
            except:
                formatted_date = checkin_date
        else:
            formatted_date = 'Не указано'
        
        # Форматируем цену
        price = tour_data.get('price', 'Не указано')
        if isinstance(price, (int, float)) and price > 0:
            formatted_price = f"{price:,}".replace(',', ' ') + " руб."
        else:
            formatted_price = "Не указано"
        
        # Информация о туре в виде таблицы
        tour_info = [
            ["Отель:", tour_data.get('hotel_name', 'Не указано')],
            ["Категория:", tour_data.get('hotel_category', 'Не указано')],
            ["Рейтинг:", str(tour_data.get('hotel_rating', 'Не указано'))],
            ["Дата заселения:", formatted_date],
            ["Количество ночей:", str(tour_data.get('nights', 'Не указано'))],
            ["Цена:", formatted_price],
            ["", "Цены актуальны на момент подбора и могут меняться"]
        ]
        
        table = Table(tour_info, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 30))
        
        # Ссылка на бронирование
        if tour_data.get('tour_link'):
            story.append(Paragraph("Ссылка для бронирования:", title_style))
            booking_link = Paragraph(
                f"<link href='{tour_data['tour_link']}'>{tour_data['tour_link']}</link>",
                normal_style
            )
            story.append(booking_link)
            story.append(Spacer(1, 20))
        
        # Контактная информация
        story.append(Paragraph("Контактная информация:", title_style))
        contact_info = Paragraph(
            "Для получения дополнительной информации:<br/>"
            "Сайт: https://www.travelata.ru<br/>"
            "Этот PDF создан автоматически ботом для подбора туров",
            normal_style
        )
        story.append(contact_info)
        story.append(Spacer(1, 20))
        
        # Важная информация
        warning = Paragraph(
            "⚠️ Внимание: стоимость и наличие тура актуальны на момент создания предложения. "
            "Цена может измениться, тур может быть раскуплен. "
            "Для актуальной информации и бронирования переходите по ссылке выше.",
            normal_style
        )
        story.append(warning)
        
        # Генерируем PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    async def download_image(self, url: str) -> Optional[BytesIO]:
        """Скачивание изображения для PDF"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        return BytesIO(image_data)
        except Exception as e:
            print(f"Ошибка загрузки изображения: {e}")
        return None