from datetime import datetime
from typing import Optional

import pytz
from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlmodel import Field, SQLModel


class Version(SQLModel, table=True):
    """Application version tracking model"""

    __tablename__ = "versions"

    id: int = Field(
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )

    # Business fields
    version: str = Field(
        sa_column=Column(String(50), nullable=False, unique=True),
        description="Semantic version (x.x.x)",
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500)),
        description="Version description/release notes",
    )
    is_current: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False),
        description="Whether this is the current/active version",
    )
    is_deprecated: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False),
        description="Whether this version is marked as deprecated",
    )
