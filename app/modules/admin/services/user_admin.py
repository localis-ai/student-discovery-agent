from typing import List, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.messages import MessageDescriptions
from app.models.user import User
from app.modules.admin.crud.user_admin import (
    crud_admin_get_user_by_id,
    crud_admin_get_users,
    crud_admin_restore_user,
    crud_admin_soft_delete_user,
    crud_admin_update_user,
)
from app.modules.common.utils.logging import logger
from app.modules.users.services.user import bulk_create_users, bulk_update_users, create_user
from app.modules.users.utils.auth import get_password_hash


def admin_get_users(db: Session, **kwargs) -> Tuple[List[User], int]:
    logger.info(f"Admin service: get_users with filters: {kwargs}")
    result = crud_admin_get_users(db, **kwargs)
    logger.info(f"Admin service: retrieved {len(result[0])} users (total={result[1]})")
    return result


def admin_get_user_by_id(db: Session, user_id: int) -> User:
    logger.info(f"Admin service: get_user_by_id user_id={user_id}")
    user = crud_admin_get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"Admin service: user not found user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MessageDescriptions.USER_NOT_FOUND)
    return user


def admin_update_user(db: Session, user_id: int, **updates) -> User:
    logger.info(f"Admin service: update_user user_id={user_id}, updates={list(updates.keys())}")
    user = crud_admin_get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"Admin service: update_user user not found user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MessageDescriptions.USER_NOT_FOUND)

    if "password" in updates and updates["password"] is not None:
        updates["hashed_password"] = get_password_hash(updates.pop("password"))

    user = crud_admin_update_user(db, user_id, **updates)
    db.refresh(user)
    logger.info(f"Admin service: updated user_id={user_id}")
    return user


def admin_soft_delete_user(db: Session, user_id: int) -> bool:
    logger.info(f"Admin service: soft_delete_user user_id={user_id}")
    user = crud_admin_get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"Admin service: soft_delete_user user not found user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MessageDescriptions.USER_NOT_FOUND)
    success = crud_admin_soft_delete_user(db, user_id)
    if success:
        logger.info(f"Admin service: successfully soft deleted user_id={user_id}")
    return success


def admin_restore_user(db: Session, user_id: int) -> bool:
    logger.info(f"Admin service: restore_user user_id={user_id}")
    user = crud_admin_get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"Admin service: restore_user user not found user_id={user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MessageDescriptions.USER_NOT_FOUND)
    success = crud_admin_restore_user(db, user_id)
    if success:
        logger.info(f"Admin service: successfully restored user_id={user_id}")
    return success


def admin_bulk_delete_users(db: Session, user_ids: List[int]) -> dict:
    logger.info(f"Admin service: bulk_delete_users count={len(user_ids)}")
    results = []
    success_count = 0
    for user_id in user_ids:
        try:
            user = crud_admin_get_user_by_id(db, user_id)
            if not user:
                results.append({"success": False, "user_id": user_id, "error": "User not found"})
                continue
            if crud_admin_soft_delete_user(db, user_id):
                results.append({"success": True, "user_id": user_id})
                success_count += 1
            else:
                results.append({"success": False, "user_id": user_id, "error": "Failed to delete"})
        except Exception as e:
            logger.error(f"Admin service: error deleting user_id={user_id}: {e}")
            results.append({"success": False, "user_id": user_id, "error": str(e)})
    logger.info(f"Admin service: bulk_delete_users completed: {success_count}/{len(user_ids)} succeeded")
    return {
        "success": success_count == len(user_ids),
        "message": f"Deleted {success_count} out of {len(user_ids)} users",
        "data": results,
        "total_processed": len(user_ids),
        "total_success": success_count,
        "total_failed": len(user_ids) - success_count,
    }


def admin_create_user(db: Session, **user_data) -> User:
    logger.info(f"Admin service: create_user email={user_data.get('email')}")
    if "password" in user_data and user_data["password"] is not None:
        user_data["hashed_password"] = get_password_hash(user_data.pop("password"))
    return create_user(db, **user_data)


def admin_bulk_create_users(db: Session, users_data: List[dict]) -> List[dict]:
    logger.info(f"Admin service: bulk_create_users count={len(users_data)}")
    processed = []
    for user_data in users_data:
        if "password" in user_data and user_data["password"] is not None:
            user_data["hashed_password"] = get_password_hash(user_data.pop("password"))
        processed.append(user_data)
    return bulk_create_users(db, processed)


def admin_bulk_update_users(db: Session, updates: List[dict]) -> List[dict]:
    logger.info(f"Admin service: bulk_update_users count={len(updates)}")
    processed = []
    for item in updates:
        update_data = item["updates"]
        if "password" in update_data and update_data["password"] is not None:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        processed.append({"id": item["id"], "updates": update_data})
    return bulk_update_users(db, processed)
