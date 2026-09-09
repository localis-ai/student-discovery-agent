from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.constants.messages import MessageConstants
from app.db import get_db
from app.modules.admin.schemas.user import (
    AdminBulkUserCreate,
    AdminBulkUserDelete,
    AdminBulkUserUpdate,
    AdminUserBulkResponse,
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
)
from app.modules.admin.services.user_admin import (
    admin_bulk_create_users,
    admin_bulk_delete_users,
    admin_bulk_update_users,
    admin_create_user,
    admin_get_user_by_id,
    admin_get_users,
    admin_restore_user,
    admin_soft_delete_user,
    admin_update_user,
)
from app.modules.admin.utils.auth import get_admin_user
from app.modules.common.schemas.common import ApiResponse, PaginatedResponse, create_pagination_meta

router = APIRouter(prefix="/admin/users", tags=["Admin-Users"])


@router.post("", response_model=ApiResponse[AdminUserResponse])
def create_user(user: AdminUserCreate, db: Session = Depends(get_db), _: dict = Depends(get_admin_user)):
    created_user = admin_create_user(db, **user.model_dump())
    return ApiResponse(success=True, message=MessageConstants.USER_CREATED_SUCCESS, data=created_user)


@router.post("/bulk/create", response_model=AdminUserBulkResponse)
def bulk_create_users(bulk_request: AdminBulkUserCreate, db: Session = Depends(get_db), _: dict = Depends(get_admin_user)):
    users_data = [user.model_dump() for user in bulk_request.users]
    results = admin_bulk_create_users(db, users_data)
    total_processed = len(results)
    total_success = sum(1 for r in results if r["success"])
    total_failed = total_processed - total_success
    return AdminUserBulkResponse(success=total_failed == 0, message=MessageConstants.OPERATION_SUCCESSFUL, data=results, total_processed=total_processed, total_success=total_success, total_failed=total_failed)


@router.put("/bulk/update", response_model=AdminUserBulkResponse)
def bulk_update_users(bulk_request: AdminBulkUserUpdate, db: Session = Depends(get_db), _: dict = Depends(get_admin_user)):
    updates = [{"id": item.id, "updates": item.updates.model_dump(exclude_unset=True)} for item in bulk_request.users]
    results = admin_bulk_update_users(db, updates)
    total_processed = len(results)
    total_success = sum(1 for r in results if r["success"])
    total_failed = total_processed - total_success
    return AdminUserBulkResponse(success=total_failed == 0, message=MessageConstants.OPERATION_SUCCESSFUL, data=results, total_processed=total_processed, total_success=total_success, total_failed=total_failed)


@router.get("", response_model=PaginatedResponse[AdminUserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: dict = Depends(get_admin_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    order_by: str = Query("created_at"),
    dir: str = Query("desc"),
    name: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    position: Optional[str] = Query(None),
    is_deleted: Optional[bool] = Query(None),
):
    kwargs = {
        "page": page,
        "limit": limit,
        "order_by": order_by,
        "dir": dir,
        "name": name,
        "email": email,
        "position": position,
        "is_deleted": is_deleted,
    }
    users, total = admin_get_users(db, **kwargs)
    pagination_meta = create_pagination_meta(page, limit, total)
    return PaginatedResponse(
        success=True,
        message=MessageConstants.USER_RETRIEVED_SUCCESS,
        data=users,
        pagination=pagination_meta,
    )


@router.get("/{user_id}", response_model=ApiResponse[dict])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_admin_user),
):
    user = admin_get_user_by_id(db, user_id)
    return ApiResponse(
        success=True,
        message=MessageConstants.USER_RETRIEVED_SUCCESS,
        data={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "bio": user.bio,
            "position": user.position,
            "is_deleted": user.is_deleted,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        },
    )


@router.put("/{user_id}", response_model=ApiResponse[dict])
def update_user(
    user_id: int,
    request: AdminUserUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(get_admin_user),
):
    updates = request.model_dump(exclude_unset=True)
    user = admin_update_user(db, user_id, **updates)
    return ApiResponse(
        success=True,
        message=MessageConstants.USER_UPDATED_SUCCESS,
        data={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "bio": user.bio,
            "position": user.position,
            "is_deleted": user.is_deleted,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        },
    )


@router.delete("/{user_id}", response_model=ApiResponse[dict])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_admin_user),
):
    admin_soft_delete_user(db, user_id)
    return ApiResponse(
        success=True,
        message=MessageConstants.USER_DELETED_SUCCESS,
        data={"success": True},
    )


@router.post("/{user_id}/restore", response_model=ApiResponse[dict])
def restore_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_admin_user),
):
    admin_restore_user(db, user_id)
    return ApiResponse(
        success=True,
        message=MessageConstants.USER_UPDATED_SUCCESS,
        data={"success": True},
    )


@router.delete("", response_model=AdminUserBulkResponse)
def bulk_delete_users(
    request: AdminBulkUserDelete,
    db: Session = Depends(get_db),
    _: dict = Depends(get_admin_user),
):
    return admin_bulk_delete_users(db, request.user_ids)
