from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator


class FileResponse(BaseModel):
    id: int
    filename: Optional[str]
    mime_type: Optional[str]
    size_bytes: Optional[int]
    storage_url: Optional[str]
    file_type: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TagResponse(BaseModel):
    id: int
    name: str
    scope: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProjectResponse(BaseModel):
    project: ProjectResponse
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True


class MeetingResponse(BaseModel):
    id: int
    title: Optional[str]
    description: Optional[str]
    url: Optional[str]
    start_time: Optional[datetime]
    is_personal: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    due_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MeetingNoteResponse(BaseModel):
    id: int
    meeting_id: int
    content: Optional[str]
    last_editor_id: Optional[int]
    last_edited_at: Optional[datetime]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    position: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email_ascii(cls, v: str) -> str:
        """Ensure email contains only ASCII characters"""
        try:
            v.encode("ascii")
        except UnicodeEncodeError:
            raise ValueError("Email must contain only ASCII characters")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            # Remove trailing spaces
            v = v.strip()
            # Check length
            if len(v) > 100:
                raise ValueError("Name must not exceed 100 characters")
            # Check if empty after stripping
            if not v:
                raise ValueError("Name cannot be empty or only whitespace")
        return v

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v):
        if v is not None and v.strip():
            # Basic URL validation
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("Avatar URL must be a valid HTTP/HTTPS URL")
        return v

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v):
        if v is not None:
            # Remove trailing spaces
            v = v.strip()
            # Check reasonable length (e.g., 500 characters max for bio)
            if len(v) > 500:
                raise ValueError("Bio must not exceed 500 characters")
        return v

    @field_validator("position")
    @classmethod
    def validate_position(cls, v):
        if v is not None:
            # Remove trailing spaces
            v = v.strip()
            # Check reasonable length
            if len(v) > 100:
                raise ValueError("Position must not exceed 100 characters")
            # Check if empty after stripping
            if not v:
                raise ValueError("Position cannot be empty or only whitespace")
        return v


class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    position: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            # Remove trailing spaces
            v = v.strip()
            # Check length
            if len(v) > 100:
                raise ValueError("Name must not exceed 100 characters")
            # Check if empty after stripping
            if not v:
                raise ValueError("Name cannot be empty or only whitespace")
        return v

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v):
        if v is not None and v.strip():
            # Basic URL validation
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("Avatar URL must be a valid HTTP/HTTPS URL")
        return v

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v):
        if v is not None:
            # Remove trailing spaces
            v = v.strip()
            # Check reasonable length (e.g., 500 characters max for bio)
            if len(v) > 500:
                raise ValueError("Bio must not exceed 500 characters")
        return v

    @field_validator("position")
    @classmethod
    def validate_position(cls, v):
        if v is not None:
            # Remove trailing spaces
            v = v.strip()
            # Check reasonable length
            if len(v) > 100:
                raise ValueError("Position must not exceed 100 characters")
            # Check if empty after stripping
            if not v:
                raise ValueError("Position cannot be empty or only whitespace")
        return v


class BulkUserCreate(BaseModel):
    users: List[UserCreate]


class BulkUserUpdateItem(BaseModel):
    id: int
    updates: UserUpdate


class BulkUserUpdate(BaseModel):
    users: List[BulkUserUpdateItem]


class BulkUserDelete(BaseModel):
    user_ids: List[int]


class BulkOperationResult(BaseModel):
    success: bool
    id: Optional[int] = None
    error: Optional[str] = None


class BulkUserResponse(BaseModel):
    success: bool
    message: str
    data: List[BulkOperationResult]
    total_processed: int
    total_success: int
    total_failed: int


class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    position: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Relationships
    # uploaded_files: List[FileResponse] = []
    # created_tags: List[TagResponse] = []
    # projects: List[UserProjectResponse] = []
    # created_projects: List[ProjectResponse] = []
    # created_meetings: List[MeetingResponse] = []
    # created_tasks: List[TaskResponse] = []
    # assigned_tasks: List[TaskResponse] = []
    # notifications: List[NotificationResponse] = []
    # edited_notes: List[MeetingNoteResponse] = []

    class Config:
        from_attributes = True
