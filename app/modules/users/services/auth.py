from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants.messages import MessageDescriptions
from app.core.azure_oauth_utils import azure_oauth_utils_manager
from app.core.config import settings
from app.modules.common.utils.logging import logger
from app.modules.users.crud.user import crud_get_user_by_email
from app.modules.users.services.user import create_user
from app.modules.users.utils.auth import create_access_token, create_refresh_token


def azure_login(db: Session, code: str):
    """Handle Azure AD OAuth login"""
    logger.debug("Starting Azure AD OAuth login process")

    logger.debug("Exchanging authorization code for access token")
    token_response = azure_oauth_utils_manager.acquire_token_by_authorization_code(code)
    access_token = token_response.get("access_token")

    if not access_token:
        logger.warning("Authorization code exchange failed: no access token received")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MessageDescriptions.AUTH_FAILED)

    # Retrieve user info from Microsoft Graph
    logger.debug("Retrieving user info from Microsoft Graph")
    user_info = azure_oauth_utils_manager.get_user_info(access_token)
    email = user_info.get("mail") or user_info.get("userPrincipalName")

    if not email:
        logger.warning("User info retrieved but no email found")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MessageDescriptions.AUTH_EMAIL_NOT_FOUND)
    logger.debug(f"User email retrieved: {email}")

    try:
        logger.debug(f"Looking up user by email: {email}")
        user = crud_get_user_by_email(db, email)
        if not user:
            logger.info(f"Creating new user with email: {email}")
            user = create_user(db, email=email, name=user_info.get("displayName"), avatar_url=user_info.get("picture"))
            db.commit()
            logger.info(f"User created successfully: user_id={user.id}, email={email}")
        else:
            logger.debug(f"User found: user_id={user.id}")

    except Exception as e:
        logger.error(f"Failed to create/find user: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MessageDescriptions.AUTH_FAILED)

    # Generate tokens and return response
    try:
        logger.debug(f"Generating access and refresh tokens for user: user_id={user.id}")
        response = {"user": {"id": user.id, "email": user.email, "name": user.name}, "token": {"access_token": create_access_token({"sub": str(user.id)}), "refresh_token": create_refresh_token({"sub": str(user.id)}), "token_type": "bearer", "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}}
        logger.success(f"Azure login successful for user: user_id={user.id}")
        return response
    except Exception as e:
        logger.error(f"Failed to generate tokens: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MessageDescriptions.AUTH_FAILED)
