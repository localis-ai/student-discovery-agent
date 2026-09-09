from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.messages import MessageDescriptions
from app.core.config import settings
from app.models.user import User
from app.modules.common.utils.logging import logger
from app.modules.common.utils.minio import (
    download_file_from_minio,
    upload_bytes_to_minio,
)
from app.modules.users.crud.user import (
    crud_check_email_exists,
    crud_create_user,
    crud_get_user_by_id,
    crud_get_users,
    crud_soft_delete_user,
    crud_update_user,
)


def get_users(db: Session, **kwargs) -> Tuple[List[User], int]:
    logger.info(f"Retrieving users with filters: {kwargs}")
    result = crud_get_users(db, **kwargs)
    logger.info(f"Retrieved {len(result[0])} users (total={result[1]})")
    return result


def check_email_exists(db: Session, email: str) -> bool:
    try:
        logger.info(f"Checking if email exists: {email}")
        result = crud_check_email_exists(db, email)
        logger.info(f"Email check result for {email}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error checking email existence: {email}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MessageDescriptions.INTERNAL_SERVER_ERROR,
        )


def update_user(db: Session, user_id: int, **updates) -> User:
    logger.info(f"Updating user: user_id={user_id}, updates={list(updates.keys())}")
    user = crud_get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"User not found for update: user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MessageDescriptions.USER_NOT_FOUND)
    user = crud_update_user(db, user_id, **updates)
    db.refresh(
        user,
        [
            "projects",
            "created_projects",
            "created_meetings",
            "uploaded_files",
            "created_tags",
            "created_meeting_items",
            "assigned_meeting_items",
            "notifications",
            "edited_notes",
        ],
    )
    logger.info(f"User updated successfully: user_id={user_id}")
    return user


def create_user(db: Session, **user_data) -> User:
    email = user_data.get("email")
    logger.info(f"Creating user with email: {email}")
    if email and crud_check_email_exists(db, email):
        logger.warning(f"Email already exists: {email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MessageDescriptions.RESOURCE_ALREADY_EXISTS,
        )
    user = crud_create_user(db, **user_data)
    logger.info(f"User created successfully: user_id={user.id}, email={email}")
    return user


def delete_user(db: Session, user_id: int) -> bool:
    logger.info(f"Deleting user: user_id={user_id}")
    user = crud_get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"User not found for deletion: user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MessageDescriptions.USER_NOT_FOUND)

    try:
        logger.info(f"Soft-deleting user: user_id={user_id}")
        result = crud_soft_delete_user(db, user_id)
        if result:
            logger.info(f"Soft-deleting meetings for user: user_id={user_id}")
        logger.success(f"User soft-deleted successfully: user_id={user_id}")
        return result
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MessageDescriptions.INTERNAL_SERVER_ERROR,
        )


def bulk_create_users(db: Session, users_data: List[dict]) -> List[dict]:
    logger.info(f"Bulk creating users: count={len(users_data)}")
    results = []
    for idx, user_data in enumerate(users_data, 1):
        try:
            user = create_user(db, **user_data)
            results.append({"success": True, "id": user.id, "error": None})
        except Exception:
            logger.exception(f"Failed to create user in bulk operation ({idx}/{len(users_data)})")
            results.append({"success": False, "id": None, "error": MessageDescriptions.INTERNAL_SERVER_ERROR})
    logger.info(f"Bulk user creation completed: total={len(users_data)}, success={sum(1 for r in results if r['success'])}")
    return results


def bulk_update_users(db: Session, updates: List[dict]) -> List[dict]:
    logger.info(f"Bulk updating users: count={len(updates)}")
    results = []
    for idx, update_item in enumerate(updates, 1):
        user_id = update_item["id"]
        update_data = update_item["updates"]
        try:
            update_user(db, user_id, **update_data)
            results.append({"success": True, "id": user_id, "error": None})
        except Exception:
            logger.exception(f"Failed to update user in bulk operation ({idx}/{len(updates)}) user_id={user_id}")
            results.append({"success": False, "id": user_id, "error": MessageDescriptions.INTERNAL_SERVER_ERROR})
    logger.info(f"Bulk user update completed: total={len(updates)}, success={sum(1 for r in results if r['success'])}")
    return results


def bulk_delete_users(db: Session, user_ids: List[int]) -> List[dict]:
    results = []
    for user_id in user_ids:
        try:
            success = delete_user(db, user_id)
            if success:
                results.append({"success": True, "id": user_id, "error": None})
            else:
                results.append({"success": False, "id": user_id, "error": MessageDescriptions.USER_NOT_FOUND})
        except Exception:
            logger.exception(f"Failed to delete user in bulk operation user_id={user_id}")
            results.append({"success": False, "id": user_id, "error": MessageDescriptions.INTERNAL_SERVER_ERROR})
    return results


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return crud_get_user_by_id(db, user_id)


def upload_user_avatar(db: Session, user_id: int, file_bytes: bytes, mime_type: str) -> Optional[str]:
    """Upload user avatar to MinIO and update user profile.

    Args:
        db: Database session
        user_id: User ID
        file_bytes: Avatar file content as bytes
        mime_type: File MIME type

    Returns:
        Avatar URL if successful, None otherwise
    """
    logger.debug(f"Uploading avatar for user_id={user_id}, size={len(file_bytes)} bytes")
    user = crud_get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"User not found for avatar upload: user_id={user_id}")
        return None

    # Upload to MinIO with bucket prefix: user_{user_id}
    object_name = f"user_{user_id}"
    upload_result = upload_bytes_to_minio(
        file_bytes,
        settings.MINIO_PUBLIC_BUCKET_NAME,
        object_name,
        mime_type,
    )

    if upload_result:
        logger.debug(f"Avatar uploaded to MinIO: user_id={user_id}")
        # Generate presigned URL
        app_base_url = getattr(settings, "API_BASE_URL", "https://meeting-agent-api-dev.wc504.io.vn/api/v1")
        avatar_url = f"{app_base_url}/users/{user_id}/avatar"

        if avatar_url:
            logger.debug(f"Presigned URL generated: user_id={user_id}")
            # Update user avatar_url
            user.avatar_url = avatar_url
            db.commit()
            db.refresh(user)
            logger.info(f"User avatar updated: user_id={user_id}")
            return avatar_url

    logger.error(f"Failed to upload avatar: user_id={user_id}")
    return None


def get_user_avatar(user_id: int) -> Optional[bytes]:
    """Retrieve user avatar from MinIO.

    Args:
        user_id: User ID

    Returns:
        Avatar file bytes if exists, None otherwise
    """
    logger.debug(f"Retrieving avatar for user_id={user_id}")
    object_name = f"user_{user_id}"
    avatar_bytes = download_file_from_minio(settings.MINIO_PUBLIC_BUCKET_NAME, object_name)

    if avatar_bytes:
        logger.debug(f"Avatar retrieved: user_id={user_id}")
        return avatar_bytes

    logger.debug(f"Avatar not found: user_id={user_id}")
    return None


def validate_avatar_file(file_bytes: bytes, content_type: Optional[str]) -> tuple:
    """Validate avatar file using magic bytes library (PNG/JPEG only, max 1MB).

    Args:
        file_bytes: File content as bytes
        content_type: MIME type from Content-Type header

    Returns:
        Tuple of (is_valid, error_message)
    """
    max_size = 1 * 1024 * 1024  # 1MB

    # Check file size
    if len(file_bytes) > max_size:
        msg = f"File size exceeds 1MB limit ({len(file_bytes)} bytes)"
        logger.warning(f"Avatar file too large: {len(file_bytes)} bytes (max {max_size})")
        return False, msg

    if len(file_bytes) == 0:
        logger.warning("Avatar file is empty")
        return False, "File is empty"

    # Validate Content-Type header
    if not content_type or not content_type.startswith("image/"):
        logger.warning(f"Invalid Content-Type for avatar: {content_type}")
        return False, f"Invalid Content-Type: {content_type}. Only image files allowed."
    return True, None
