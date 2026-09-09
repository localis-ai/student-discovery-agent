from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.constants.messages import MessageConstants
from app.core.config import settings
from app.db import get_db
from app.models.user import User
from app.modules.common.schemas.common import ApiResponse
from app.modules.common.utils.logging import logger
from app.modules.users.crud.user import crud_get_user_by_email
from app.modules.users.schemas.auth import LoginRequest, RefreshTokenRequest, RegisterRequest
from app.modules.users.schemas.user import UserUpdate
from app.modules.users.services.user import create_user, update_user
from app.modules.users.utils.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
    verify_token,
)

router = APIRouter(tags=["Auth"])


@router.post("/auth/refresh", response_model=ApiResponse[dict])
def refresh_token_endpoint(request: RefreshTokenRequest):
    logger.debug("Token refresh requested")
    refresh_token = request.refresh_token

    payload = verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        logger.warning("Invalid refresh token: invalid payload or type")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MessageConstants.INVALID_CREDENTIALS)

    user_id = payload.get("sub")

    if not user_id:
        logger.warning("Invalid refresh token: missing user_id")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MessageConstants.INVALID_CREDENTIALS)

    access_token = create_access_token({"sub": user_id})
    logger.info(f"Token refreshed successfully for user {user_id}")

    return ApiResponse(
        success=True,
        message=MessageConstants.OPERATION_SUCCESSFUL,
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        },
    )


@router.post("/auth/register", response_model=ApiResponse[dict])
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    logger.debug(f"Register requested for email: {request.email}")
    hashed_password = get_password_hash(request.password)
    user = create_user(
        db,
        email=request.email,
        name=request.name,
        avatar_url=request.avatar_url,
        bio=request.bio,
        position=request.position,
        hashed_password=hashed_password,
    )
    logger.info(f"User registered successfully: {user.email} (ID: {user.id})")
    return ApiResponse(
        success=True,
        message=MessageConstants.OPERATION_SUCCESSFUL,
        data={
            "user": {"id": user.id, "email": user.email, "name": user.name},
            "token": {
                "access_token": create_access_token({"sub": str(user.id)}),
                "refresh_token": create_refresh_token({"sub": str(user.id)}),
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            },
        },
    )


@router.post("/auth/login", response_model=ApiResponse[dict])
def login(request: LoginRequest, db: Session = Depends(get_db)):
    logger.debug(f"Login requested for email: {request.email}")
    user = crud_get_user_by_email(db, request.email)
    if not user or not user.hashed_password or not verify_password(request.password, user.hashed_password):
        logger.warning(f"Login failed for email: {request.email}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MessageConstants.INVALID_CREDENTIALS)
    logger.info(f"Login successful for user: {user.email} (ID: {user.id})")
    return ApiResponse(
        success=True,
        message=MessageConstants.OPERATION_SUCCESSFUL,
        data={
            "user": {"id": user.id, "email": user.email, "name": user.name},
            "token": {
                "access_token": create_access_token({"sub": str(user.id)}),
                "refresh_token": create_refresh_token({"sub": str(user.id)}),
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            },
        },
    )


@router.get("/me", response_model=ApiResponse[dict])
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return ApiResponse(
        success=True,
        message=MessageConstants.USER_RETRIEVED_SUCCESS,
        data={
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "avatar_url": current_user.avatar_url,
            "bio": current_user.bio,
            "position": current_user.position,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at,
        },
    )


@router.put("/me", response_model=ApiResponse[dict])
def update_current_user_info(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = updates.model_dump(exclude_unset=True)
    updated_user = update_user(db, current_user.id, **update_data)
    return ApiResponse(
        success=True,
        message=MessageConstants.USER_UPDATED_SUCCESS,
        data={
            "id": updated_user.id,
            "email": updated_user.email,
            "name": updated_user.name,
            "avatar_url": updated_user.avatar_url,
            "bio": updated_user.bio,
            "position": updated_user.position,
            "created_at": updated_user.created_at,
            "updated_at": updated_user.updated_at,
        },
    )
