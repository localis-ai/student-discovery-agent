from datetime import datetime
from typing import Optional

import pytz
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User model"""

    __tablename__ = "users"

    id: int = Field(
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), onupdate=func.now()))
    is_deleted: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))

    email: str = Field(sa_column=Column(String(255), unique=True, nullable=False))
    hashed_password: Optional[str] = Field(default=None, sa_column=Column(String(255)))
    name: Optional[str] = Field(default=None, sa_column=Column(String(255)))
    avatar_url: Optional[str] = Field(default=None, sa_column=Column(String(500)))
    bio: Optional[str] = Field(default=None, sa_column=Column(Text))
    position: Optional[str] = Field(default=None, sa_column=Column(String(255)))
