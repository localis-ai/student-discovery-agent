from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.user import User
from app.modules.common.utils.logging import logger

ALLOWED_USER_ORDER_FIELDS = {"id", "email", "name", "position", "created_at", "updated_at"}


def crud_get_users(db: Session, **kwargs) -> Tuple[List[User], int]:
    logger.info(f"CRUD: get_users called with filters: {kwargs}")
    query = db.query(User).filter(User.is_deleted == False)
    if "name" in kwargs and kwargs["name"]:
        query = query.filter(User.name.ilike(f"%{kwargs['name']}%"))
    if "email" in kwargs and kwargs["email"]:
        # allow partial/case-insensitive matches when listing users
        query = query.filter(User.email.ilike(f"%{kwargs['email']}%"))
    if "position" in kwargs and kwargs["position"]:
        query = query.filter(User.position == kwargs["position"])
    if "created_at_gte" in kwargs and kwargs["created_at_gte"]:
        try:
            gte = datetime.fromisoformat(kwargs["created_at_gte"])
        except ValueError as e:
            raise ValueError(f"Invalid datetime format for created_at_gte: {kwargs['created_at_gte']}") from e
        query = query.filter(User.created_at >= gte)
    if "created_at_lte" in kwargs and kwargs["created_at_lte"]:
        try:
            lte = datetime.fromisoformat(kwargs["created_at_lte"])
        except ValueError as e:
            raise ValueError(f"Invalid datetime format for created_at_lte: {kwargs['created_at_lte']}") from e
        query = query.filter(User.created_at <= lte)
    total = query.count()
    order_by = kwargs.get("order_by", "created_at")
    if order_by not in ALLOWED_USER_ORDER_FIELDS:
        logger.warning(f"Unsafe order_by value provided: {order_by}, fallback to created_at")
        order_by = "created_at"
    dir = kwargs.get("dir", "desc").lower()
    if dir not in {"asc", "desc"}:
        logger.warning(f"Unsafe dir value provided: {dir}, fallback to desc")
        dir = "desc"
    order_attr = getattr(User, order_by)
    if dir == "asc":
        query = query.order_by(order_attr.asc())
    else:
        query = query.order_by(order_attr.desc())
    page = int(kwargs.get("page", 1))
    limit = int(kwargs.get("limit", 20))
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    users = query.all()
    return users, total


def crud_check_email_exists(db: Session, email: str) -> bool:
    # perform an exact match for root-level existence checks (e.g. during registration)
    return bool(crud_get_user_by_email(db, email))


def crud_update_user(db: Session, user_id: int, **updates) -> User:
    logger.debug(f"CRUD: update_user called for id={user_id} with updates={updates}")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"CRUD: update_user user not found id={user_id}")
        return None
    for key, value in updates.items():
        if hasattr(user, key):
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    logger.info(f"CRUD: updated user id={user_id}")
    return user


def crud_get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id, User.is_deleted == False).first()


def crud_get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email, User.is_deleted == False).first()


def crud_create_user(db: Session, **user_data) -> User:
    logger.debug(f"CRUD: create_user called with data: {user_data}")
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"CRUD: created user id={user.id}")
    return user


def crud_soft_delete_user(db: Session, user_id: int) -> bool:
    """Soft delete user by marking is_deleted=True, preserving all user data."""
    logger.debug(f"CRUD: soft delete user id={user_id}")
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        logger.warning(f"CRUD: soft delete user not found id={user_id}")
        return False

    user.is_deleted = True
    db.commit()
    logger.info(f"CRUD: soft deleted user id={user_id}")
    return True
