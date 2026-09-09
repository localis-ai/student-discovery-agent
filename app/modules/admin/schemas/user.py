from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AdminUserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    position: Optional[str]
    is_deleted: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    position: Optional[str] = None
    password: Optional[str] = None
    is_deleted: Optional[bool] = None


class AdminUserCreate(BaseModel):
    email: str
    password: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    position: Optional[str] = None


class AdminBulkUserCreate(BaseModel):
    users: List["AdminUserCreate"]


class AdminBulkUserUpdate(BaseModel):
    class Item(BaseModel):
        id: int
        updates: AdminUserUpdate

    users: List[Item]


class AdminBulkUserDelete(BaseModel):
    user_ids: List[int]


class AdminUserBulkResult(BaseModel):
    success: bool
    user_id: int
    error: Optional[str] = None


class AdminUserBulkResponse(BaseModel):
    success: bool
    message: str
    data: List[AdminUserBulkResult]
    total_processed: int
    total_success: int
    total_failed: int
