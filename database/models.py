import os
import sqlalchemy
from dotenv import load_dotenv
from sqlalchemy import BigInteger, Boolean, String, Float, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from datetime import datetime

load_dotenv(dotenv_path=".env")
engine = create_async_engine(url="sqlite+aiosqlite:///db.sqlite3", echo=True)
async_session = async_sessionmaker(engine)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class Hotel(Base):
    __tablename__ = "hotels"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hotelName: Mapped[str] = mapped_column(String, nullable=True)
    hotelDescription: Mapped[str] = mapped_column(String, nullable=True)


class Favorite(Base):
    """Избранные туры пользователей"""
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    hotel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hotel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    nights: Mapped[int] = mapped_column(BigInteger, nullable=True)
    start_date: Mapped[str] = mapped_column(String(20), nullable=True)
    tour_id: Mapped[str] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str] = mapped_column(String(255), nullable=True)
    tour_data: Mapped[str] = mapped_column(Text, nullable=True)  # JSON с полными данными тура
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


async def async_main():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)  # Удаляем старые таблицы
        await conn.run_sync(Base.metadata.create_all)  # Создаем новые