from datetime import datetime
from typing import Optional

import pytz
from sqlalchemy import Column, DateTime, Integer, MetaData, func
from sqlmodel import Field, SQLModel

metadata = MetaData()


class BaseDatabaseModel(SQLModel):
    id: int = Field(
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), onupdate=func.now()))


def get_id_column():
    """Get integer column type for current database dialect"""
    return Integer


def get_json_column():
    """Get JSON column type for current database dialect"""
    from sqlalchemy import JSON

    return JSON
