from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.constants.messages import MessageConstants
from app.db import get_db
from app.models.user import User
from app.modules.common.schemas.common import ApiResponse, PaginatedResponse, create_pagination_meta
from app.modules.common.utils.logging import logger
from app.modules.users.crud.user import ALLOWED_USER_ORDER_FIELDS, crud_get_user_by_id
from app.modules.users.schemas.user import UserResponse
from app.modules.users.services.user import get_user_avatar, get_users, upload_user_avatar, validate_avatar_file
from app.modules.users.utils.auth import get_current_user

router = APIRouter(tags=["User"])


@router.get("/users", response_model=PaginatedResponse[UserResponse])
def get_users_endpoint(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    order_by: str = Query("created_at"),
    project_id: Optional[int] = Query(None),
    dir: str = Query("desc"),
    name: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    position: Optional[str] = Query(None),
    created_at_gte: Optional[str] = Query(None),
    created_at_lte: Optional[str] = Query(None),
):
    # Sanitize query params to avoid SQL injection / unexpected crash
    if order_by not in ALLOWED_USER_ORDER_FIELDS:
        logger.warning(f"Invalid order_by value provided: {order_by}, falling back to created_at")
        order_by = "created_at"

    dir = dir.lower()
    if dir not in {"asc", "desc"}:
        logger.warning(f"Invalid dir value provided: {dir}, falling back to desc")
        dir = "desc"

    kwargs = {
        "page": page,
        "limit": limit,
        "order_by": order_by,
        "dir": dir,
        "name": name,
        "email": email,
        "position": position,
        "created_at_gte": created_at_gte,
        "created_at_lte": created_at_lte,
        "project_id": project_id,
    }

    logger.debug(f"Fetching user list: {kwargs}")

    try:
        users, total = get_users(db, **kwargs)
    except ValueError as e:
        logger.warning(f"Invalid query parameter: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    pagination_meta = create_pagination_meta(page, limit, total)

    return PaginatedResponse(
        success=True,
        message=MessageConstants.USER_RETRIEVED_SUCCESS,
        data=users,
        pagination=pagination_meta,
    )


@router.post("/users/avatar/upload", response_model=ApiResponse[dict])
def upload_avatar_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload user avatar with strict validation (PNG/JPEG only, max 1MB)"""
    logger.debug(f"Uploading avatar for user_id={current_user.id}: {file.filename} ({file.content_type})")

    # Read file content
    file_content = file.file.read()

    # Validate file with magic bytes checking
    is_valid, error_msg = validate_avatar_file(file_content, file.content_type)

    if not is_valid:
        logger.warning(f"Avatar validation failed for user_id={current_user.id}: {error_msg}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Upload avatar
    avatar_url = upload_user_avatar(db, current_user.id, file_content, file.content_type)

    if not avatar_url:
        logger.error(f"Failed to upload avatar: user_id={current_user.id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload avatar")

    logger.info(f"Avatar uploaded successfully: user_id={current_user.id}, size={len(file_content)} bytes")
    return ApiResponse(
        success=True,
        message=MessageConstants.USER_AVATAR_UPLOADED_SUCCESS,
        data={"avatar_url": avatar_url},
    )


@router.get("/users/{user_id}/avatar")
def get_avatar_endpoint(user_id: int, db: Session = Depends(get_db)):
    """Get user avatar (public endpoint)"""
    logger.debug(f"Retrieving avatar for user_id={user_id}")

    # Check user exists
    user = crud_get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"User not found: user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get avatar from MinIO
    avatar_bytes = get_user_avatar(user_id)

    if not avatar_bytes:
        logger.debug(f"Avatar not found: user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")

    # Return avatar as image stream
    logger.debug(f"Avatar retrieved: user_id={user_id}, size={len(avatar_bytes)} bytes")
    return StreamingResponse(
        iter([avatar_bytes]),
        media_type=user.avatar_url.split(".")[-1] if user.avatar_url else "image/jpeg",
        headers={"Content-Disposition": f"inline; filename=avatar_{user_id}"},
    )
