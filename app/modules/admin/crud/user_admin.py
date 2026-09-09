from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.user import User
from app.modules.common.utils.logging import logger


def crud_admin_get_users(db: Session, **kwargs) -> Tuple[List[User], int]:
    logger.info(f"Admin CRUD: get_users called with filters: {kwargs}")
    query = db.query(User)
    if "name" in kwargs and kwargs["name"]:
        query = query.filter(User.name.ilike(f"%{kwargs['name']}%"))
    if "email" in kwargs and kwargs["email"]:
        query = query.filter(User.email.ilike(f"%{kwargs['email']}%"))
    if "position" in kwargs and kwargs["position"]:
        query = query.filter(User.position == kwargs["position"])
    if "created_at_gte" in kwargs and kwargs["created_at_gte"]:
        gte = datetime.fromisoformat(kwargs["created_at_gte"])
        query = query.filter(User.created_at >= gte)
    if "created_at_lte" in kwargs and kwargs["created_at_lte"]:
        lte = datetime.fromisoformat(kwargs["created_at_lte"])
        query = query.filter(User.created_at <= lte)
    if "is_deleted" in kwargs and kwargs["is_deleted"] is not None:
        query = query.filter(User.is_deleted == kwargs["is_deleted"])
    total = query.count()
    order_by = kwargs.get("order_by", "created_at")
    dir = kwargs.get("dir", "desc")
    if dir == "asc":
        query = query.order_by(getattr(User, order_by).asc())
    else:
        query = query.order_by(getattr(User, order_by).desc())
    page = int(kwargs.get("page", 1))
    limit = int(kwargs.get("limit", 20))
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    users = query.all()
    return users, total


def crud_admin_get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def crud_admin_update_user(db: Session, user_id: int, **updates) -> Optional[User]:
    logger.debug(f"Admin CRUD: update_user called for id={user_id} with updates={updates}")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Admin CRUD: update_user user not found id={user_id}")
        return None
    for key, value in updates.items():
        if hasattr(user, key) and key != "email" and key != "id":
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    logger.info(f"Admin CRUD: updated user id={user_id}")
    return user


def crud_admin_soft_delete_user(db: Session, user_id: int) -> bool:
    logger.debug(f"Admin CRUD: soft delete user id={user_id}")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Admin CRUD: soft delete user not found id={user_id}")
        return False
    user.is_deleted = True
    db.commit()
    logger.info(f"Admin CRUD: soft deleted user id={user_id}")
    return True


def crud_admin_restore_user(db: Session, user_id: int) -> bool:
    logger.debug(f"Admin CRUD: restore user id={user_id}")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Admin CRUD: restore user not found id={user_id}")
        return False
    user.is_deleted = False
    db.commit()
    logger.info(f"Admin CRUD: restored user id={user_id}")
    return True
