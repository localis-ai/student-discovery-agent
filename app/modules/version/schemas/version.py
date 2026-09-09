from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.common.schemas.common import ApiResponse


# ===== BASE SCHEMAS =====
class VersionBase(BaseModel):
    """Base version schema"""

    version: str = Field(
        ...,
        min_length=5,  # "0.0.0" minimum 5 chars
        max_length=50,
        description="Semantic version (x.x.x format)",
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Version description or release notes",
    )

    @field_validator("version", mode="before")
    @classmethod
    def validate_version_format(cls, v):
        """Validate semantic version format (x.x.x)"""
        import re

        if v is None:
            raise ValueError("Version is required")
        if isinstance(v, str):
            v = v.strip()
            pattern = r"^\d+\.\d+\.\d+$"
            if not re.match(pattern, v):
                raise ValueError("Version must follow semantic versioning (x.x.x format)")
            # Validate individual parts don't exceed normal range
            parts = v.split(".")
            if len(parts) != 3:
                raise ValueError("Version must have exactly 3 parts (major.minor.patch)")
        return v


# ===== REQUEST SCHEMAS =====
class VersionCreate(VersionBase):
    """Schema for creating a new version"""

    pass


# ===== RESPONSE SCHEMAS =====
class VersionResponse(BaseModel):
    """Version response schema"""

    id: int
    version: str
    description: Optional[str]
    is_current: bool
    is_deprecated: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ===== API RESPONSE WRAPPERS =====
class VersionApiResponse(ApiResponse[VersionResponse]):
    """API response wrapper for single version"""

    data: VersionResponse
